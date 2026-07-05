"""Post-target state machine — illegal transitions raise, everywhere."""

TARGET_TRANSITIONS: dict[str, set[str]] = {
    "draft":           {"scheduled", "queued", "canceled"},
    "scheduled":       {"queued", "canceled", "requires_action"},
    "queued":          {"publishing", "canceled", "requires_action"},
    "publishing":      {"published", "failed", "requires_action"},
    "failed":          {"queued"},              # retry
    "requires_action": {"queued", "canceled"},  # after reconnect/fix
    "published":       set(),
    "canceled":        set(),
}


class IllegalTransition(Exception):
    pass


def assert_transition(current: str, new: str) -> None:
    allowed = TARGET_TRANSITIONS.get(current)
    if allowed is None:
        raise IllegalTransition(f"unknown state {current!r}")
    if new not in allowed:
        raise IllegalTransition(f"{current} -> {new} is not allowed")


def transition(target, new_state: str) -> None:
    assert_transition(target.status, new_state)
    target.status = new_state
