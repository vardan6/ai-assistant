"""Slash-command registry for chat-only commands like `/tools`."""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any, Callable

from ..tools import ToolRegistry


CommandHandler = Callable[["CommandContext", "ParsedCommand"], "CommandResult"]


@dataclass(slots=True)
class CommandContext:
    tool_registry: ToolRegistry


@dataclass(slots=True)
class ParsedCommand:
    raw: str
    name: str
    args: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CommandResult:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommandSpec:
    name: str
    description: str
    handler: CommandHandler

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
        }


@dataclass(slots=True)
class CommandRegistry:
    _specs: dict[str, CommandSpec] = field(default_factory=dict)

    def register(self, spec: CommandSpec) -> None:
        key = spec.name.strip().lower()
        if not key:
            raise ValueError("Command name cannot be empty")
        if key in self._specs:
            raise ValueError(f"Command already registered: {spec.name}")
        self._specs[key] = CommandSpec(
            name=key,
            description=spec.description,
            handler=spec.handler,
        )

    def specs(self) -> list[CommandSpec]:
        return [self._specs[name] for name in sorted(self._specs)]

    def execute(self, raw: str, context: CommandContext) -> tuple[CommandSpec, CommandResult]:
        parsed = parse_command(raw)
        if parsed is None:
            raise ValueError("Command input must start with '/'.")
        spec = self._specs.get(parsed.name)
        if spec is None:
            raise KeyError(parsed.name)
        return spec, spec.handler(context, parsed)


def parse_command(raw: str) -> ParsedCommand | None:
    text = str(raw or "").strip()
    if not text.startswith("/"):
        return None
    tokens = shlex.split(text[1:])
    if not tokens:
        return None
    return ParsedCommand(
        raw=text,
        name=tokens[0].strip().lower(),
        args=tokens[1:],
    )
