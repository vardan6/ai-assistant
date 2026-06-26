"""Thin HTTP CLI for the :9006 FastAPI server."""
from __future__ import annotations

import json
import sys
from typing import Any
from urllib import error, request

from .config import load_config


def _print_trace(payload: dict[str, Any]) -> None:
    intent = payload["intent"]
    meta = payload["intent_meta"]
    fast = f" (fast-path: {meta['fast_path']})" if meta.get("fast_path") else ""
    print(f"  intent: types={intent['types']} metric={intent['metric']} "
          f"time_range={intent['time_range']} out_of_scope={intent['out_of_scope']} "
          f"confidence={intent['confidence']}{fast}")
    print(f"  gating: {payload['gating_mode']} tools={payload['bound_tools'] or '[]'}")
    if meta.get("parse_errors"):
        print(f"  intent parse errors: {meta['parse_errors']}")
    for call in payload["tool_calls"]:
        ok = call["result"].get("ok", True)
        print(f"  tool: {call['name']}({call['args']}) -> ok={ok} [{call['latency_ms']}ms]")


def _print_footer(payload: dict[str, Any]) -> None:
    telemetry = payload["telemetry"]
    total = telemetry["total_usage"]
    print(
        "  usage: "
        f"in={total['input_tokens']} out={total['output_tokens']} total={total['total_tokens']} "
        f"time={telemetry['elapsed_ms']}ms intent={telemetry['intent_model'] or '-'} "
        f"synth={telemetry['synthesis_model'] or '-'}"
    )


def _base_url() -> str:
    config = load_config()
    return f"http://{config.server_host}:{config.server_port}"


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, headers=headers, method=method)
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def _stream_chat(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = request.Request(
        f"{base_url}/api/chat/stream",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    final_payload: dict[str, Any] | None = None
    with request.urlopen(req) as resp:
        for raw_line in resp:
            line = raw_line.decode().strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") == "trace":
                trace = event["event"]
                if trace["kind"] == "tool_started":
                    print(f"  trace: {trace['message']}")
                elif trace["kind"] == "tool_finished":
                    print(f"  trace: {trace['message']} [{trace['latency_ms']}ms]")
            elif event.get("type") == "final":
                final_payload = event["response"]
            elif event.get("type") == "error":
                raise RuntimeError(event.get("error", "Unknown stream error"))
    if final_payload is None:
        raise RuntimeError("Server stream closed without a final response.")
    return final_payload


def main() -> int:
    try:
        base_url = _base_url()
        health = _http_json("GET", f"{base_url}/health")
        session = _http_json("POST", f"{base_url}/api/sessions", {"title": "CLI chat"})
    except Exception as exc:
        print(f"Failed to connect to server: {exc}", file=sys.stderr)
        return 1
    print(f"Ready. Dataset 'today' = {health['dataset_today']}")
    print("Ask a question (Ctrl-D or 'exit' to quit). Prefix with '/bind_all ' or '/gated ' for one request.\n")

    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break
        gating_mode = "gated"
        if question.startswith("/bind_all "):
            gating_mode = "bind_all"
            question = question[len("/bind_all "):].strip()
        elif question.startswith("/gated "):
            question = question[len("/gated "):].strip()
        if not question:
            continue
        try:
            payload = _stream_chat(
                base_url,
                {
                    "question": question,
                    "gating_mode": gating_mode,
                    "session_id": session["id"],
                },
            )
        except error.HTTPError as exc:
            detail = exc.read().decode() or str(exc)
            print(f"  error: {detail}\n", file=sys.stderr)
            continue
        except Exception as exc:
            print(f"  error: {exc}\n", file=sys.stderr)
            continue
        _print_trace(payload)
        _print_footer(payload)
        print(f"\nassistant> {payload['answer']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
