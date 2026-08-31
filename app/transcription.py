"""Vision transcription providers and resume-safe page orchestration."""

from __future__ import annotations

import base64
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from app.pdf import RenderedPage

if TYPE_CHECKING:
    from app.database import Database

TRANSCRIPTION_PROMPT = """Transcribe this handwritten notebook page into Markdown.

Requirements:
- Preserve headings, paragraphs, lists, checkboxes, and visible reading order.
- Preserve equations as LaTeX where reasonably confident.
- Describe meaningful diagrams briefly in italic Markdown; do not fabricate labels.
- Preserve any text beginning with @ exactly as written.
- Write `[?]` for illegible or uncertain content instead of guessing.
- Return only the page Markdown. Do not add a code fence, preface, summary, or commentary.
"""


class TranscriptionError(RuntimeError):
    """Base error for page transcription failures."""


class TransientTranscriptionError(TranscriptionError):
    """A provider failure that exhausted bounded retries."""


class InvalidTranscriptionResponse(TranscriptionError):
    """The provider returned no usable Markdown."""


@dataclass(frozen=True)
class TranscriptionResult:
    """A page transcription and non-content operational metadata."""

    page_number: int
    markdown: str
    provider: str
    model: str
    request_id: str | None
    duration_seconds: float
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class TranscriptionPlan:
    """Dry-run metadata that reveals no image or note content."""

    model: str
    detail: str
    page_count: int
    image_bytes: int
    estimated_base64_bytes: int


class Transcriber(Protocol):
    """Replaceable page-level transcription provider."""

    @property
    def model(self) -> str: ...

    def transcribe(self, page: RenderedPage) -> TranscriptionResult: ...


def plan_transcription(pages: Sequence[RenderedPage], model: str) -> TranscriptionPlan:
    """Describe a future request set without reading image contents into a payload."""
    total = sum(page.image_path.stat().st_size for page in pages)
    return TranscriptionPlan(
        model=model,
        detail="original",
        page_count=len(pages),
        image_bytes=total,
        estimated_base64_bytes=sum(
            4 * math.ceil(page.image_path.stat().st_size / 3) for page in pages
        ),
    )


def _usage_value(response: Any, field: str) -> int | None:
    usage = getattr(response, "usage", None)
    value = getattr(usage, field, None) if usage is not None else None
    return value if isinstance(value, int) else None


def _is_transient(error: Exception) -> bool:
    if isinstance(
        error,
        (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError),
    ):
        return True
    return isinstance(error, APIStatusError) and error.status_code >= 500


class OpenAITranscriber:
    """Responses API image transcriber using base64 data URLs."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        max_attempts: int = 3,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")
        if not model:
            raise ValueError("OpenAI model is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._model = model
        self.max_attempts = max_attempts
        self.client = client or OpenAI(api_key=api_key, max_retries=0)
        self.sleep = sleep
        self.clock = clock

    @property
    def model(self) -> str:
        return self._model

    def transcribe(self, page: RenderedPage) -> TranscriptionResult:
        """Transcribe one PNG page, retrying transient provider failures only."""
        if not page.image_path.is_file():
            raise FileNotFoundError(page.image_path)
        encoded = base64.b64encode(page.image_path.read_bytes()).decode("ascii")
        image_url = f"data:image/png;base64,{encoded}"
        started = self.clock()
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": TRANSCRIPTION_PROMPT},
                                {
                                    "type": "input_image",
                                    "image_url": image_url,
                                    "detail": "original",
                                },
                            ],
                        }
                    ],
                )
                markdown = str(getattr(response, "output_text", "")).strip()
                if not markdown:
                    raise InvalidTranscriptionResponse("Provider returned empty Markdown")
                return TranscriptionResult(
                    page_number=page.page_number,
                    markdown=markdown,
                    provider="openai",
                    model=self.model,
                    request_id=getattr(response, "id", None),
                    duration_seconds=self.clock() - started,
                    input_tokens=_usage_value(response, "input_tokens"),
                    output_tokens=_usage_value(response, "output_tokens"),
                )
            except InvalidTranscriptionResponse:
                raise
            except Exception as error:
                if not _is_transient(error):
                    raise TranscriptionError(
                        f"OpenAI transcription failed: {type(error).__name__}"
                    ) from error
                last_error = error
                if attempt < self.max_attempts:
                    self.sleep(float(2 ** (attempt - 1)))

        assert last_error is not None
        raise TransientTranscriptionError(
            f"OpenAI transcription failed after {self.max_attempts} attempts: "
            f"{type(last_error).__name__}"
        ) from last_error


class FakeTranscriber:
    """Deterministic provider for tests and local pipeline development."""

    def __init__(self, pages: Mapping[int, str], model: str = "fake-vision") -> None:
        self.pages = dict(pages)
        self._model = model
        self.calls: list[int] = []

    @property
    def model(self) -> str:
        return self._model

    def transcribe(self, page: RenderedPage) -> TranscriptionResult:
        self.calls.append(page.page_number)
        if page.page_number not in self.pages:
            raise TranscriptionError(f"No fake transcription for page {page.page_number}")
        return TranscriptionResult(
            page_number=page.page_number,
            markdown=self.pages[page.page_number],
            provider="fake",
            model=self.model,
            request_id=f"fake-{page.page_number}",
            duration_seconds=0.0,
        )


def transcribe_pages(
    pages: Sequence[RenderedPage],
    transcriber: Transcriber,
    *,
    existing: Mapping[int, str] | None = None,
    on_completed: Callable[[TranscriptionResult], None] | None = None,
) -> list[TranscriptionResult]:
    """Transcribe missing pages in order and persist each result through a callback."""
    page_numbers = [page.page_number for page in pages]
    if page_numbers != sorted(set(page_numbers)) or (page_numbers and page_numbers[0] < 1):
        raise ValueError("Rendered pages must be unique, positive, and ordered")
    completed = dict(existing or {})
    results: list[TranscriptionResult] = []
    for page in pages:
        if page.page_number in completed:
            results.append(
                TranscriptionResult(
                    page_number=page.page_number,
                    markdown=completed[page.page_number],
                    provider="stored",
                    model=transcriber.model,
                    request_id=None,
                    duration_seconds=0.0,
                )
            )
            continue
        result = transcriber.transcribe(page)
        if result.page_number != page.page_number:
            raise InvalidTranscriptionResponse("Provider returned the wrong page number")
        if on_completed is not None:
            on_completed(result)
        results.append(result)
    return results


def transcribe_pages_to_database(
    database: Database,
    document_id: str,
    pages: Sequence[RenderedPage],
    transcriber: Transcriber,
) -> list[TranscriptionResult]:
    """Resume from SQLite and checkpoint every newly completed page."""

    def checkpoint(result: TranscriptionResult) -> None:
        database.save_page_transcription(document_id, result.page_number, result.markdown)

    return transcribe_pages(
        pages,
        transcriber,
        existing=database.page_markdown(document_id),
        on_completed=checkpoint,
    )
