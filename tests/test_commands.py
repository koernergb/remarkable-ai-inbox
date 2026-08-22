"""Deterministic command detection tests."""

import pytest

from app.commands import CommandType, detect_commands


def test_ask_prefers_preceding_question_paragraph() -> None:
    markdown = """# Stability

Positive eigenvalues grow exponentially.

Why does that make the equilibrium unstable?

@ask"""

    commands = detect_commands(markdown, page_number=2)

    assert len(commands) == 1
    assert commands[0].command is CommandType.ASK
    assert commands[0].context == "Why does that make the equilibrium unstable?"
    assert commands[0].page_number == 2
    assert commands[0].line_number == 7


def test_ask_falls_back_to_bounded_section() -> None:
    commands = detect_commands("# Notes\nEigenvalues control growth.\n@ask")

    assert commands[0].context == "Eigenvalues control growth."


def test_inline_todo_uses_text_after_marker() -> None:
    commands = detect_commands("Earlier notes\n@todo: redo exercise 4")

    assert commands[0].command is CommandType.TODO
    assert commands[0].context == "redo exercise 4"


def test_standalone_todo_uses_preceding_block() -> None:
    commands = detect_commands("- Review complex eigenvalues\n@todo")

    assert commands[0].context == "- Review complex eigenvalues"


def test_context_stops_at_previous_command() -> None:
    markdown = """First concept
@challenge
Second concept
Why is it true?
@ask"""

    commands = detect_commands(markdown)

    assert [command.command for command in commands] == [CommandType.CHALLENGE, CommandType.ASK]
    assert commands[1].context == "Second concept\nWhy is it true?"


def test_empty_summary_falls_back_to_page() -> None:
    commands = detect_commands("@summarize\n\nA later concept")

    assert commands[0].context == "A later concept"


@pytest.mark.parametrize(
    "markdown",
    [
        "contact person@ask.com",
        "this is @asking for trouble",
        "```\n@ask\n```",
        "~~~python\n@todo delete everything\n~~~",
    ],
)
def test_false_positives_are_ignored(markdown: str) -> None:
    assert detect_commands(markdown) == []


def test_markers_are_case_insensitive_but_raw_text_is_preserved() -> None:
    commands = detect_commands("Test this material\n@Challenge")

    assert commands[0].command is CommandType.CHALLENGE
    assert commands[0].raw_marker == "@Challenge"


def test_multiple_commands_on_one_line_preserve_source_order() -> None:
    commands = detect_commands("Question?\n@ask @summarize")

    assert [item.command for item in commands] == [CommandType.ASK, CommandType.SUMMARIZE]
    assert [item.column for item in commands] == [1, 6]
