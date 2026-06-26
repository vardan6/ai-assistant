from types import SimpleNamespace

from app.ai import IntentService
from app.ai.intent_schema import coerce_intent, make_empty_intent, validate_intent
from app.ai.smalltalk import is_smalltalk


class FakeModel:
    """Stands in for a langchain chat model; returns a canned content string."""

    def __init__(self, content: str):
        self._content = content
        self.model = "fake-intent-model"

    def invoke(self, messages):  # noqa: ARG002
        return SimpleNamespace(content=self._content)


def test_smalltalk_detection():
    assert is_smalltalk("Hi!")
    assert is_smalltalk("how are you ?")
    assert not is_smalltalk("which plants are offline?")


def test_smalltalk_fast_path_skips_llm():
    service = IntentService()
    # A model that would raise if invoked proves the fast-path short-circuits.
    class Boom:
        def invoke(self, messages):
            raise AssertionError("LLM should not be called for smalltalk")
    env = service.parse("hello", model=Boom())
    assert env["fast_path"] == "smalltalk"
    assert env["intent"]["confidence"] == 1.0


def test_intent_service_parses_json():
    service = IntentService()
    model = FakeModel('{"types": ["A"], "out_of_scope": false, "confidence": 0.9, "summary": "status"}')
    env = service.parse("which plants are offline?", model=model)
    assert env["parse_errors"] == []
    assert env["intent"]["types"] == ["A"]
    assert env["intent"]["confidence"] == 0.9


def test_intent_service_tolerates_markdown_fences():
    service = IntentService()
    model = FakeModel('```json\n{"types": ["B"], "metric": "daily_yield", "confidence": 0.8}\n```')
    env = service.parse("average daily yield?", model=model)
    assert env["parse_errors"] == []
    assert env["intent"]["types"] == ["B"]
    assert env["intent"]["metric"] == "daily_yield"


def test_schema_validation_rejects_bad_types():
    errors = validate_intent({"types": ["Z"], "confidence": 0.5})
    assert any("types" in e for e in errors)


def test_coerce_fills_missing_fields():
    intent = coerce_intent({"types": ["C"]})
    assert intent["entities"] == make_empty_intent()["entities"]
    assert intent["out_of_scope"] is False
