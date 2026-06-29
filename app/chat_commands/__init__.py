"""Slash-command entrypoint."""
from __future__ import annotations

from . import builtin
from .registry import CommandContext, CommandRegistry, CommandResult, CommandSpec, ParsedCommand, parse_command

__all__ = [
    "CommandContext",
    "CommandRegistry",
    "CommandResult",
    "CommandSpec",
    "ParsedCommand",
    "build_command_registry",
    "parse_command",
]


def build_command_registry() -> CommandRegistry:
    registry = CommandRegistry()
    builtin.register(registry)
    return registry
