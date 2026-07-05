import pytest

from app.services.state_machine import IllegalTransition, assert_transition


def test_legal_paths():
    assert_transition("draft", "queued")
    assert_transition("queued", "publishing")
    assert_transition("publishing", "published")
    assert_transition("publishing", "failed")
    assert_transition("failed", "queued")
    assert_transition("scheduled", "queued")
    assert_transition("publishing", "requires_action")
    assert_transition("requires_action", "queued")


@pytest.mark.parametrize("cur,new", [
    ("published", "queued"),       # published is terminal
    ("draft", "published"),        # cannot skip pipeline
    ("canceled", "queued"),        # canceled is terminal
    ("queued", "published"),       # must pass through publishing
])
def test_illegal_paths(cur, new):
    with pytest.raises(IllegalTransition):
        assert_transition(cur, new)
