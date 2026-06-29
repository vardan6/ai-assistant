from __future__ import annotations

from app import cli


def _payload(answer: str = "One plant is offline.") -> dict:
    return {
        "answer": answer,
        "intent": {
            "types": ["A"],
            "metric": "status",
            "time_range": "today",
            "out_of_scope": False,
            "confidence": 0.95,
        },
        "intent_meta": {"fast_path": "", "parse_errors": []},
        "gating_mode": "gated",
        "bound_tools": ["plants"],
        "tool_calls": [
            {
                "name": "plants",
                "args": {"status": "offline"},
                "result": {"ok": True},
                "latency_ms": 9,
            }
        ],
        "telemetry": {
            "total_usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
            "elapsed_ms": 1000,
            "intent_model": "intent-model",
            "synthesis_model": "synth-model",
        },
    }


def test_cli_one_shot_creates_session_and_prints_answer(monkeypatch, capsys):
    calls: list[tuple[str, str, dict | None]] = []

    def fake_http_json(method: str, url: str, payload=None):
        calls.append((method, url, payload))
        if url.endswith("/health"):
            return {"ok": True, "dataset_today": "2026-06-22T23:50:00"}
        if url.endswith("/api/sessions"):
            return {"id": "sess-new", "title": "CLI one-shot: offline plants"}
        raise AssertionError(f"Unexpected request: {method} {url}")

    def fake_stream_chat(base_url: str, payload: dict):
        assert base_url == "http://127.0.0.1:9006"
        assert payload == {
            "question": "Which plants are offline?",
            "gating_mode": "gated",
            "session_id": "sess-new",
        }
        return _payload()

    monkeypatch.setattr(cli, "_http_json", fake_http_json)
    monkeypatch.setattr(cli, "_stream_chat", fake_stream_chat)

    rc = cli.main([
        "--server", "http://127.0.0.1:9006",
        "--title", "CLI one-shot: offline plants",
        "--prompt", "Which plants are offline?",
    ])

    out = capsys.readouterr()
    assert rc == 0
    assert out.out == "One plant is offline.\n"
    assert "session: sess-new" in out.err
    assert "usage: in=5 out=3 total=8 time=1000ms" in out.err
    assert calls == [
        ("GET", "http://127.0.0.1:9006/health", None),
        ("POST", "http://127.0.0.1:9006/api/sessions", {"title": "CLI one-shot: offline plants"}),
    ]


def test_cli_one_shot_reuses_session_when_session_id_is_supplied(monkeypatch, capsys):
    calls: list[tuple[str, str, dict | None]] = []

    def fake_http_json(method: str, url: str, payload=None):
        calls.append((method, url, payload))
        if url.endswith("/health"):
            return {"ok": True, "dataset_today": "2026-06-22T23:50:00"}
        if url.endswith("/api/sessions/sess-existing"):
            return {"id": "sess-existing", "title": "Existing chat", "messages": []}
        raise AssertionError(f"Unexpected request: {method} {url}")

    def fake_stream_chat(base_url: str, payload: dict):
        assert payload["session_id"] == "sess-existing"
        assert payload["gating_mode"] == "bind_all"
        return _payload("Bound answer.")

    monkeypatch.setattr(cli, "_http_json", fake_http_json)
    monkeypatch.setattr(cli, "_stream_chat", fake_stream_chat)

    rc = cli.main(
        [
            "--server",
            "http://127.0.0.1:9006",
            "--session-id",
            "sess-existing",
            "--gating-mode",
            "bind_all",
            "Continue the chat",
        ]
    )

    out = capsys.readouterr()
    assert rc == 0
    assert out.out == "Bound answer.\n"
    assert "session: sess-existing" not in out.err
    assert calls == [
        ("GET", "http://127.0.0.1:9006/health", None),
        ("GET", "http://127.0.0.1:9006/api/sessions/sess-existing", None),
    ]


def test_cli_rejects_duplicate_prompt_forms(capsys):
    rc = cli.main(["--prompt", "Hello", "Hi"])

    out = capsys.readouterr()
    assert rc == 2
    assert "Specify the prompt as a positional argument or --prompt, not both." in out.err
