"""Service configuration, read from the environment.

Env vars:
  TTCC_SERVICE_TOKEN     shared secret the WordPress plugin sends as a bearer
                         token. Required unless TTCC_ALLOW_NO_AUTH=1.
  TTCC_ALLOW_NO_AUTH     set to "1" to disable auth for LOCAL DEV ONLY. The app
                         logs a loud warning and refuses to bind a non-loopback
                         host in this mode is the caller's responsibility.
  TTCC_MAX_RANGE_DAYS    cap on (end - start) span, to bound compute/DoS.
                         Default 120 (covers a multi-week sheet or a yom-tov
                         season; a normal sheet is <= a few weeks).
  TTCC_RENDER_TIMEOUT_MS Chromium rasterization timeout in ms. Default 20000.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    token: str | None
    allow_no_auth: bool
    max_range_days: int
    render_timeout_ms: int

    @property
    def auth_enabled(self) -> bool:
        return not self.allow_no_auth


def load_settings() -> Settings:
    token = os.environ.get("TTCC_SERVICE_TOKEN") or None
    allow_no_auth = os.environ.get("TTCC_ALLOW_NO_AUTH") == "1"
    if token is None and not allow_no_auth:
        raise RuntimeError(
            "TTCC_SERVICE_TOKEN is not set. Set it to a shared secret, or set "
            "TTCC_ALLOW_NO_AUTH=1 for local development only."
        )
    return Settings(
        token=token,
        allow_no_auth=allow_no_auth,
        max_range_days=int(os.environ.get("TTCC_MAX_RANGE_DAYS", "120")),
        render_timeout_ms=int(os.environ.get("TTCC_RENDER_TIMEOUT_MS", "20000")),
    )
