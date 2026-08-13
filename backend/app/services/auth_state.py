"""In-memory holder for the current logged-in user's Supabase session.

This is a local desktop app running as a single process for a single user,
so a module-level variable is enough - no database, no multi-tenancy. It
intentionally does not survive a server restart: the frontend keeps its own
copy of the Supabase session in localStorage and re-posts it here on load.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    access_token: str
    email: str


_session: Session | None = None


def set_session(access_token: str, email: str) -> None:
    global _session
    _session = Session(access_token=access_token, email=email)


def get_session() -> Session | None:
    return _session


def clear_session() -> None:
    global _session
    _session = None
