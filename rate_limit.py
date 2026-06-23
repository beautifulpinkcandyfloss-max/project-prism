"""
Rate limiting to protect against API cost abuse once this app is publicly
deployed. Two layers:

1. PER-CLIENT limit -- tries to identify the actual client (via the
   X-Forwarded-For header, which a reverse proxy like nginx adds -- you
   should be running one in front of this for HTTPS anyway) and caps how
   many LLM-calling actions that client can take per time window.

2. GLOBAL limit -- a hard cap across ALL clients combined, as a backstop
   against worst-case cost blowout (many different IPs, a botnet, or
   per-client identification failing) that per-client limiting alone
   wouldn't catch.

HONEST LIMITATIONS:
- This uses a plain in-memory store, which only works correctly if your
  deployment runs as a SINGLE process (true for a typical small Docker/VM
  deployment). If you ever scale to multiple worker processes behind a
  load balancer, each process would track its own counts independently,
  effectively multiplying your real limit -- you'd need a shared store
  (e.g. Redis) at that point. Flagging this now so it isn't a silent gap
  if you scale later.
- Per-client identification falls back to a per-browser-session ID when
  no proxy header is available (local testing, or no reverse proxy in
  front of the app at all) -- which someone could bypass by opening a
  fresh session. The global cap exists specifically as the backstop for
  that case.
- Restarting the app process resets all counters. Acceptable tradeoff for
  simplicity; a restart wiping rate-limit history isn't a real cost risk.
"""

import time
import uuid

import streamlit as st

_per_client_log = {}   # {client_id: [timestamp, timestamp, ...]}
_global_log = []       # [timestamp, timestamp, ...]


def get_client_id() -> str:
    """Best-effort client identification: real IP if behind a reverse
    proxy passing X-Forwarded-For/X-Real-IP, otherwise a stable
    per-browser-session ID."""
    try:
        headers = st.context.headers
        forwarded = headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = headers.get("X-Real-IP")
        if real_ip:
            return real_ip
    except Exception:
        pass

    if "_rate_limit_client_id" not in st.session_state:
        st.session_state["_rate_limit_client_id"] = str(uuid.uuid4())
    return st.session_state["_rate_limit_client_id"]


def _prune(log: list, window_seconds: float, now: float) -> list:
    return [t for t in log if now - t < window_seconds]


def _format_wait(seconds: float) -> str:
    minutes = max(int(seconds // 60) + 1, 1)
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def check_rate_limit(action_label: str, per_client_max: int, per_client_window: int,
                      global_max: int, global_window: int):
    """Call this immediately before any LLM-calling action. Returns
    (allowed: bool, message: str or None). If allowed, the action is
    automatically recorded against both logs -- don't call this more
    than once per actual action taken."""
    now = time.time()
    client_id = get_client_id()

    global _global_log
    _global_log = _prune(_global_log, global_window, now)
    if len(_global_log) >= global_max:
        wait = _format_wait(global_window - (now - _global_log[0]))
        return False, (f"This app has hit its site-wide usage limit for now -- "
                        f"try again in about {wait}.")

    client_log = _prune(_per_client_log.get(client_id, []), per_client_window, now)
    if len(client_log) >= per_client_max:
        wait = _format_wait(per_client_window - (now - client_log[0]))
        return False, (f"You've reached the limit for {action_label} "
                        f"({per_client_max} per {per_client_window // 60} minutes) -- "
                        f"try again in about {wait}.")

    client_log.append(now)
    _per_client_log[client_id] = client_log
    _global_log.append(now)

    return True, None
