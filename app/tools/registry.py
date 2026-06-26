"""Tool registry — uniform registration pattern for data tools.

Each tool is a plain callable that takes a `ToolContext` plus JSON args and
returns a **structured dict** (never prose, never raw CSV rows). Tools are
decoupled from langchain: the registry converts specs to OpenAI-format function
schemas at bind time and dispatches calls by name. This keeps every tool
unit-testable in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..data import DataSource

# A tool handler: (context, **json_args) -> structured result dict.
ToolHandler = Callable[..., dict[str, Any]]


@dataclass(slots=True)
class ToolContext:
    """Everything a tool needs to do its work, injected at call time."""

    data: DataSource


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the args object
    handler: ToolHandler

    def openai_schema(self) -> dict[str, Any]:
        """Function schema accepted by `ChatModel.bind_tools`."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(slots=True)
class ToolRegistry:
    _specs: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._specs[spec.name] = spec

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
    ) -> Callable[[ToolHandler], ToolHandler]:
        """Decorator form of `register`."""

        def decorator(handler: ToolHandler) -> ToolHandler:
            self.register(
                ToolSpec(
                    name=name,
                    description=description,
                    parameters=parameters or _empty_object_schema(),
                    handler=handler,
                )
            )
            return handler

        return decorator

    def names(self) -> list[str]:
        return list(self._specs)

    def specs(self, names: list[str] | None = None) -> list[ToolSpec]:
        if names is None:
            return list(self._specs.values())
        return [self._specs[n] for n in names if n in self._specs]

    def bind_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        return [spec.openai_schema() for spec in self.specs(names)]

    def invoke(self, name: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Execute a tool by name. Always returns a dict with an `ok` flag."""
        spec = self._specs.get(name)
        if spec is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            result = spec.handler(context, **(args or {}))
        except Exception as exc:  # tools must never crash the loop
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if not isinstance(result, dict):
            return {"ok": False, "error": "Tool returned a non-dict result"}
        result.setdefault("ok", True)
        return result


def _empty_object_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "additionalProperties": False}
