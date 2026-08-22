"""Deterministic handwritten command detection and context extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class CommandType(StrEnum):
    ASK = "@ask"
    CHALLENGE = "@challenge"
    TODO = "@todo"
    SUMMARIZE = "@summarize"


@dataclass(frozen=True)
class DetectedCommand:
    """A supported marker and the deterministic text assigned to it."""

    command: CommandType
    raw_marker: str
    page_number: int
    context: str
    line_number: int
    column: int


_COMMAND_RE = re.compile(r"(?<![\w@])@(ask|challenge|todo|summarize)(?![\w.])", re.IGNORECASE)
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _content_without_commands(lines: list[str]) -> str:
    cleaned = [_COMMAND_RE.sub("", line).rstrip() for line in lines]
    return "\n".join(cleaned).strip()


def _bounded_context(lines: list[str], command_line: int) -> str:
    start = 0
    for index in range(command_line - 1, -1, -1):
        if _COMMAND_RE.search(lines[index]):
            start = index + 1
            break
        if _HEADING_RE.match(lines[index]):
            start = index + 1
            break
    return _content_without_commands(lines[start:command_line])


def _question_context(context: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", context) if part.strip()]
    for paragraph in reversed(paragraphs):
        if "?" in paragraph:
            return paragraph
    return context


def detect_commands(markdown: str, page_number: int = 1) -> list[DetectedCommand]:
    """Detect supported markers in source order and assign bounded context."""
    lines = markdown.splitlines()
    active_fence: str | None = None
    detections: list[DetectedCommand] = []
    page_context = _content_without_commands(lines)

    for line_index, line in enumerate(lines):
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if active_fence is None:
                active_fence = marker
            elif marker == active_fence:
                active_fence = None
            continue
        if active_fence is not None:
            continue

        for match in _COMMAND_RE.finditer(line):
            command = CommandType(f"@{match.group(1).lower()}")
            inline = line[match.end() :].strip(" \t:-")
            context = _bounded_context(lines, line_index)
            if command is CommandType.TODO and inline:
                context = inline
            elif command is CommandType.ASK:
                context = _question_context(context)
            elif command in {CommandType.CHALLENGE, CommandType.SUMMARIZE} and not context:
                context = page_context
            detections.append(
                DetectedCommand(
                    command=command,
                    raw_marker=match.group(0),
                    page_number=page_number,
                    context=context,
                    line_number=line_index + 1,
                    column=match.start() + 1,
                )
            )
    return detections
