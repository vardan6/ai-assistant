"""Built-in slash commands."""
from __future__ import annotations

from .registry import CommandContext, CommandRegistry, CommandResult, CommandSpec, ParsedCommand


def register(registry: CommandRegistry) -> None:
    registry.register(CommandSpec(
        name="tools",
        description="List every registered backend tool with its live description and argument names.",
        handler=_tools_command,
    ))
    registry.register(CommandSpec(
        name="context",
        description="Placeholder for reporting the current chat context and routing state.",
        handler=_placeholder_command,
    ))
    registry.register(CommandSpec(
        name="data",
        description="Placeholder for reporting the source datasets available to the tools.",
        handler=_placeholder_command,
    ))


def _tools_command(context: CommandContext, command: ParsedCommand) -> CommandResult:  # noqa: ARG001
    specs = context.tool_registry.specs()
    sections = [f"## Available tools ({len(specs)})"]
    for spec in specs:
        lines = [f"### `{spec.name}`", "", spec.description, ""]
        parameter_names = sorted((spec.parameters or {}).get("properties", {}).keys())
        if parameter_names:
            lines.append(f"Args: {', '.join(f'`{name}`' for name in parameter_names)}")
        else:
            lines.append("Args: none")
        sections.append("\n".join(lines))
    return CommandResult(
        content="\n\n".join(sections).strip(),
        metadata={
            "kind": "slash_command",
            "command_name": "tools",
            "tool_count": len(specs),
        },
    )


def _placeholder_command(context: CommandContext, command: ParsedCommand) -> CommandResult:  # noqa: ARG001
    return CommandResult(
        content=(
            f"## /{command.name}\n\n"
            "This slash command is registered and available in autocomplete, but its behavior is not implemented yet."
        ),
        metadata={
            "kind": "slash_command",
            "command_name": command.name,
            "placeholder": True,
        },
    )
