from app.ai.intent_schema import make_empty_intent
from app.ai.turn_router import infer_turn_kind

_RAJASTHAN_HISTORY = [
    {"role": "user", "content": "average daily yield of Rajasthan Solar Park last week?"},
    {"role": "assistant", "content": "Rajasthan Solar Park averaged 123354.2 over 7 days."},
]


def test_bare_pronoun_is_follow_up_when_recent_entity_exists():
    """MT-D2: 'what is its id?' after a plant turn must route as a follow-up."""
    kind = infer_turn_kind(
        "what is its id?",
        intent=make_empty_intent(),
        prompt_history=_RAJASTHAN_HISTORY,
    )
    assert kind == "follow_up"


def test_bare_pronoun_without_history_is_not_follow_up():
    """A cold pronoun with no referent should stay a plain data_question (asks to clarify)."""
    kind = infer_turn_kind(
        "what is its id?",
        intent=make_empty_intent(),
        prompt_history=None,
    )
    assert kind == "data_question"


def test_affirmative_reply_is_follow_up_only_with_history():
    assert infer_turn_kind(
        "yes please",
        intent=make_empty_intent(),
        prompt_history=_RAJASTHAN_HISTORY,
    ) == "follow_up"

    assert infer_turn_kind(
        "yes please",
        intent=make_empty_intent(),
        prompt_history=None,
    ) == "data_question"


def test_recheck_closest_available_window_is_follow_up_with_history():
    assert infer_turn_kind(
        'night (e.g., 19:00-06:00), re-check using the closest available window',
        intent=make_empty_intent(),
        prompt_history=_RAJASTHAN_HISTORY,
    ) == "follow_up"
