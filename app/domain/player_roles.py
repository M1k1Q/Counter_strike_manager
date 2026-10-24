"""Playing roles are independent of the IGL appointment flag."""


def base_role(role: str | None) -> str | None:
    value = " ".join(word for word in (role or "").split() if word.lower() != "igl")
    return value or None


def playing_role(player) -> str:
    # Legacy saves used selected_role="IGL"; retain their natural playing role.
    return (base_role(player.selected_role) or base_role(player.role) or "").lower()
