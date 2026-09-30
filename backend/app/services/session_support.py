"""Shared exact-match session selectors and their provider identifiers."""

from types import MappingProxyType

_SUPPORTED_SESSIONS = MappingProxyType(
    {(2025, "italian-grand-prix", "race"): (2025, "Italian Grand Prix", "Race")}
)


def resolve_supported_session(
    year: int, event: str, session: str
) -> tuple[int, str, str] | None:
    return _SUPPORTED_SESSIONS.get((year, event, session))
