"""Vision transcription provider and orchestration tests."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError, RateLimitError

from app.database import Database, sqlite_url
from app.models import Document
from app.pdf import RenderedPage
from app.transcription import (
    FakeTranscriber,
    InvalidTranscriptionResponse,
    OpenAITranscriber,
    TranscriptionError,
    TransientTranscriptionError,
    plan_transcription,
    transcribe_pages,
    transcribe_pages_to_database,
)


def make_page(tmp_path: Path, number: int, contents: bytes = b"png-data") -> RenderedPage:
    image = tmp_path / f"page_{number:04d}.png"
    image.write_bytes(contents)
    return RenderedPage(number, image, 100, 200)


class FakeResponses:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def fake_client(*outcomes: Any) -> SimpleNamespace:
    return SimpleNamespace(responses=FakeResponses(list(outcomes)))


def response(markdown: str = "# Notes", request_id: str = "resp_123") -> SimpleNamespace:
    return SimpleNamespace(
        output_text=markdown,
        id=request_id,
        usage=SimpleNamespace(input_tokens=120, output_tokens=30),
    )


def request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


def test_openai_transcriber_uses_base64_original_detail(tmp_path: Path) -> None:
    client = fake_client(response("# Linear Systems\n\n@todo review eigenvalues"))
    ticks = iter([10.0, 10.25])
    transcriber = OpenAITranscriber(
        "test-key", "gpt-test", client=client, clock=lambda: next(ticks)
    )

    result = transcriber.transcribe(make_page(tmp_path, 1, b"image-bytes"))

    assert result.markdown.endswith("@todo review eigenvalues")
    assert result.request_id == "resp_123"
    assert result.duration_seconds == 0.25
    assert result.input_tokens == 120
    call = client.responses.calls[0]
    image = call["input"][0]["content"][1]
    assert image["detail"] == "original"
    assert image["image_url"].startswith("data:image/png;base64,")
    assert "image-bytes" not in image["image_url"]


def test_transient_error_retries_with_bounded_backoff(tmp_path: Path) -> None:
    timeout = APITimeoutError(request=request())
    client = fake_client(timeout, timeout, response())
    sleeps: list[float] = []
    transcriber = OpenAITranscriber(
        "test-key", "gpt-test", client=client, sleep=sleeps.append, clock=lambda: 0.0
    )

    transcriber.transcribe(make_page(tmp_path, 1))

    assert len(client.responses.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_rate_limit_exhaustion_is_transient_error(tmp_path: Path) -> None:
    error = RateLimitError("limited", response=httpx.Response(429, request=request()), body=None)
    transcriber = OpenAITranscriber(
        "test-key",
        "gpt-test",
        max_attempts=2,
        client=fake_client(error, error),
        sleep=lambda _: None,
    )

    with pytest.raises(TransientTranscriptionError, match="after 2 attempts"):
        transcriber.transcribe(make_page(tmp_path, 1))


def test_authentication_error_is_not_retried_or_leaked(tmp_path: Path) -> None:
    error = AuthenticationError(
        "bad secret detail", response=httpx.Response(401, request=request()), body=None
    )
    client = fake_client(error)
    transcriber = OpenAITranscriber("test-key", "gpt-test", client=client)

    with pytest.raises(TranscriptionError, match="AuthenticationError") as raised:
        transcriber.transcribe(make_page(tmp_path, 1))

    assert "bad secret detail" not in str(raised.value)
    assert len(client.responses.calls) == 1


def test_empty_response_and_missing_image_fail(tmp_path: Path) -> None:
    transcriber = OpenAITranscriber("test-key", "gpt-test", client=fake_client(response(" ")))

    with pytest.raises(InvalidTranscriptionResponse, match="empty Markdown"):
        transcriber.transcribe(make_page(tmp_path, 1))
    with pytest.raises(FileNotFoundError):
        transcriber.transcribe(RenderedPage(2, tmp_path / "missing.png", 1, 1))


def test_fake_provider_and_resume_skip_completed_pages(tmp_path: Path) -> None:
    pages = [make_page(tmp_path, number) for number in (1, 2, 3)]
    provider = FakeTranscriber({2: "second", 3: "third"})
    persisted: list[int] = []

    results = transcribe_pages(
        pages,
        provider,
        existing={1: "stored first"},
        on_completed=lambda result: persisted.append(result.page_number),
    )

    assert [result.markdown for result in results] == ["stored first", "second", "third"]
    assert provider.calls == [2, 3]
    assert persisted == [2, 3]
    assert results[0].provider == "stored"


def test_partial_failure_can_resume_without_repeating_success(tmp_path: Path) -> None:
    pages = [make_page(tmp_path, number) for number in (1, 2)]
    provider = FakeTranscriber({1: "first"})
    persisted: dict[int, str] = {}

    with pytest.raises(TranscriptionError, match="page 2"):
        transcribe_pages(
            pages,
            provider,
            on_completed=lambda result: persisted.update({result.page_number: result.markdown}),
        )

    resumed = FakeTranscriber({2: "second"})
    results = transcribe_pages(pages, resumed, existing=persisted)
    assert [result.markdown for result in results] == ["first", "second"]
    assert resumed.calls == [2]


def test_database_adapter_checkpoints_and_resumes(tmp_path: Path) -> None:
    database = Database(sqlite_url(tmp_path / "transcription.db"))
    database.initialize()
    document = database.add_document(
        Document(
            source_message_id="message",
            filename="notes.pdf",
            sender="writer@example.com",
            received_at=datetime(2026, 8, 26, tzinfo=UTC),
            raw_pdf_path="notes.pdf",
        )
    )
    database.save_page_transcription(document.id, 1, "stored first")
    pages = [make_page(tmp_path, number) for number in (1, 2)]
    provider = FakeTranscriber({2: "new second"})

    results = transcribe_pages_to_database(database, document.id, pages, provider)

    assert [result.markdown for result in results] == ["stored first", "new second"]
    assert provider.calls == [2]
    assert database.page_markdown(document.id) == {1: "stored first", 2: "new second"}
    database.close()


def test_wrong_page_and_invalid_order_are_rejected(tmp_path: Path) -> None:
    page = make_page(tmp_path, 1)

    class WrongPage(FakeTranscriber):
        def transcribe(self, page: RenderedPage) -> Any:
            result = super().transcribe(page)
            return SimpleNamespace(**{**result.__dict__, "page_number": 2})

    with pytest.raises(InvalidTranscriptionResponse, match="wrong page"):
        transcribe_pages([page], WrongPage({1: "text"}))
    with pytest.raises(ValueError, match="unique, positive, and ordered"):
        transcribe_pages([make_page(tmp_path, 2), page], FakeTranscriber({}))


def test_dry_run_plan_reports_payload_without_content(tmp_path: Path) -> None:
    pages = [make_page(tmp_path, 1, b"abc"), make_page(tmp_path, 2, b"12345")]

    plan = plan_transcription(pages, "gpt-test")

    assert plan.model == "gpt-test"
    assert plan.detail == "original"
    assert plan.page_count == 2
    assert plan.image_bytes == 8
    assert plan.estimated_base64_bytes == 12


@pytest.mark.parametrize(("key", "model"), [("", "gpt-test"), ("key", "")])
def test_provider_requires_key_and_model(key: str, model: str) -> None:
    with pytest.raises(ValueError):
        OpenAITranscriber(key, model)


def test_provider_requires_positive_attempt_count() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        OpenAITranscriber("key", "model", max_attempts=0)
