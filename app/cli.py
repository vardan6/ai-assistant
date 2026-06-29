"""Thin HTTP CLI for the :9006 FastAPI server."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib import error, request

from .config import load_config


def _print_trace(payload: dict[str, Any], *, stream: Any | None = None) -> None:
    stream = stream or sys.stderr
    intent = payload["intent"]
    meta = payload["intent_meta"]
    fast = f" (fast-path: {meta['fast_path']})" if meta.get("fast_path") else ""
    print(
        f"  intent: types={intent['types']} metric={intent['metric']} "
        f"time_range={intent['time_range']} out_of_scope={intent['out_of_scope']} "
        f"confidence={intent['confidence']}{fast}",
        file=stream,
    )
    print(f"  gating: {payload['gating_mode']} tools={payload['bound_tools'] or '[]'}", file=stream)
    if meta.get("parse_errors"):
        print(f"  intent parse errors: {meta['parse_errors']}", file=stream)
    for call in payload["tool_calls"]:
        ok = call["result"].get("ok", True)
        print(f"  tool: {call['name']}({call['args']}) -> ok={ok} [{call['latency_ms']}ms]", file=stream)


def _print_footer(payload: dict[str, Any], *, stream: Any | None = None) -> None:
    stream = stream or sys.stderr
    telemetry = payload["telemetry"]
    total = telemetry["total_usage"]
    print(
        "  usage: "
        f"in={total['input_tokens']} out={total['output_tokens']} total={total['total_tokens']} "
        f"time={telemetry['elapsed_ms']}ms intent={telemetry['intent_model'] or '-'} "
        f"synth={telemetry['synthesis_model'] or '-'}",
        file=stream,
    )


def _base_url(server: str | None = None) -> str:
    if server:
        return server.rstrip("/")
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


def _create_session(base_url: str, *, title: str) -> dict[str, Any]:
    return _http_json("POST", f"{base_url}/api/sessions", {"title": title})


def _verify_session(base_url: str, session_id: str) -> dict[str, Any]:
    return _http_json("GET", f"{base_url}/api/sessions/{session_id}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Interactive and one-shot terminal client for the Solar AI Assistant server.",
    )
    parser.add_argument("prompt_pos", nargs="?", metavar="PROMPT", help="prompt text")
    parser.add_argument("--prompt", metavar="TEXT", help="prompt text for one-shot mode")
    parser.add_argument(
        "--session-id",
        metavar="ID",
        default="",
        help="reuse an existing chat session instead of creating a new one",
    )
    parser.add_argument(
        "--title",
        metavar="TEXT",
        default="CLI chat",
        help="title for a newly created session (default: CLI chat)",
    )
    parser.add_argument(
        "--gating-mode",
        choices=["gated", "bind_all"],
        default="gated",
        help="tool binding mode for the request (default: gated)",
    )
    parser.add_argument(
        "--server",
        metavar="URL",
        default="",
        help="override the server base URL instead of config host/port",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        default=False,
        help="suppress trace and usage footer output in one-shot mode",
    )
    return parser


def _run_one_shot(args: argparse.Namespace) -> int:
    if args.prompt and args.prompt_pos:
        print("Specify the prompt as a positional argument or --prompt, not both.", file=sys.stderr)
        return 2

    prompt = (args.prompt or args.prompt_pos or "").strip()
    if not prompt:
        print("A prompt is required in one-shot mode.", file=sys.stderr)
        return 2

    base_url = _base_url(args.server)
    try:
        _http_json("GET", f"{base_url}/health")
        if args.session_id:
            session = _verify_session(base_url, args.session_id)
        else:
            session = _create_session(base_url, title=args.title)
            print(f"session: {session['id']}", file=sys.stderr)
        payload = _stream_chat(
            base_url,
            {
                "question": prompt,
                "gating_mode": args.gating_mode,
                "session_id": session["id"],
            },
        )
    except error.HTTPError as exc:
        detail = exc.read().decode() or str(exc)
        print(f"Request failed: {detail}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to connect to server: {exc}", file=sys.stderr)
        return 1

    print(payload["answer"])
    if not args.no_stats:
        _print_trace(payload)
        _print_footer(payload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.prompt or args.prompt_pos:
        return _run_one_shot(args)

    try:
        base_url = _base_url(args.server)
        health = _http_json("GET", f"{base_url}/health")
        if args.session_id:
            session = _verify_session(base_url, args.session_id)
        else:
            session = _create_session(base_url, title=args.title)
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
        gating_mode = args.gating_mode
        if question.startswith("/bind_all "):
            gating_mode = "bind_all"
            question = question[len("/bind_all "):].strip()
        elif question.startswith("/gated "):
            gating_mode = "gated"
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
        _print_trace(payload, stream=sys.stdout)
        _print_footer(payload, stream=sys.stdout)
        print(f"\nassistant> {payload['answer']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
