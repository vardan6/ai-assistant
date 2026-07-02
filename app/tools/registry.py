"""Tool registry — uniform registration pattern for data tools.

Each tool is a plain callable that takes a `ToolContext` plus JSON args and
returns a **structured dict** (never prose, never raw CSV rows). Tools are
decoupled from langchain: the registry converts specs to OpenAI-format function
schemas at bind time and dispatches calls by name. This keeps every tool
unit-testable in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import inspect
from typing import Any, Callable

from ..data import DataSource

# A tool handler: (context, **json_args) -> structured result dict.
ToolHandler = Callable[..., dict[str, Any]]


@dataclass(slots=True)
class ToolContext:
    """Everything a tool needs to do its work, injected at call time."""

    data: DataSource
    reference_now: Callable[[], datetime] | None = None

    def effective_now(self) -> datetime:
        if self.reference_now is not None:
            return self.reference_now()
        return self.data.dataset_today()


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
        arg_error = _validate_tool_args(spec, args)
        if arg_error is not None:
            return arg_error
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


def _validate_tool_args(spec: ToolSpec, args: dict[str, Any] | None) -> dict[str, Any] | None:
    if args is None:
        return None
    if not isinstance(args, dict):
        return _invalid_tool_args_error(
            spec.name,
            message=f"Tool '{spec.name}' expects arguments as a JSON object.",
        )

    signature = inspect.signature(spec.handler)
    accepted_kwargs: set[str] = set()
    accepts_var_kwargs = False
    for index, param in enumerate(signature.parameters.values()):
        if index == 0:
            continue
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            accepts_var_kwargs = True
            continue
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            accepted_kwargs.add(param.name)

    unknown_args = sorted(name for name in args if name not in accepted_kwargs)
    if unknown_args and not accepts_var_kwargs:
        label = "argument" if len(unknown_args) == 1 else "arguments"
        return _invalid_tool_args_error(
            spec.name,
            message=f"Unknown {label} for tool '{spec.name}': {', '.join(unknown_args)}.",
            unknown_args=unknown_args,
        )

    try:
        signature.bind(None, **args)
    except TypeError as exc:
        return _invalid_tool_args_error(spec.name, message=str(exc))
    return None


def _invalid_tool_args_error(
    tool_name: str,
    *,
    message: str,
    unknown_args: list[str] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": "invalid_arguments",
        "tool": tool_name,
        "message": message,
    }
    if unknown_args:
        error["unknown_args"] = unknown_args
    return {"ok": False, "error": error}
