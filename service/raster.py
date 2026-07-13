"""HTML -> PDF / PNG rasterization via headless Chromium (Playwright).

This is the rasterization step the engine repo does not implement: the engine
only produces HTML. The service owns Chromium so the WordPress host (SiteGround,
no shell/Chromium) never has to.

Sync Playwright is used deliberately: the FastAPI export endpoints are declared
``def`` (not ``async def``), so FastAPI runs them in a worker thread with no
running event loop, where the sync API is valid.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# 3:4 portrait social canvas (WhatsApp/social share). width:height = 0.75.
_PORTRAIT_W = 1080
_PORTRAIT_H = 1440

# Injected only for the "portrait" PNG variant: constrain the single-week sheet
# into the social canvas. Layout/content is untouched — this only frames it.
_PORTRAIT_CSS = f"""
<style id="ttcc-portrait">
  @page {{ size: {_PORTRAIT_W}px {_PORTRAIT_H}px; margin: 0; }}
  html, body {{ width: {_PORTRAIT_W}px; margin: 0; padding: 0; }}
  body {{ padding: 48px 56px; box-sizing: border-box; }}
  .single, .multi {{ column-count: 1 !important; }}
</style>
"""

_LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]


@lru_cache(maxsize=1)
def _chromium_executable() -> str | None:
    """Resolve a Chromium executable that actually exists on disk.

    Order: TTCC_CHROMIUM_PATH env override -> the ``chromium`` symlink under
    PLAYWRIGHT_BROWSERS_PATH (present in this environment / the Docker image) ->
    Playwright's own default path. Returns None if none exist, so the caller can
    fall back to Playwright's default resolution. This avoids ``playwright
    install`` when a browser is already provisioned but at a different build
    number than the pip package expects.
    """
    override = os.environ.get("TTCC_CHROMIUM_PATH")
    if override and Path(override).exists():
        return override

    browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if browsers:
        link = Path(browsers) / "chromium"
        if link.exists():
            return str(link)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            default = p.chromium.executable_path
        if default and Path(default).exists():
            return default
    except Exception:
        pass
    return None


@lru_cache(maxsize=1)
def chromium_available() -> bool:
    """True if a Chromium executable is present on disk. Cheap: does not launch
    a browser. Never raises."""
    try:
        return _chromium_executable() is not None
    except Exception:
        return False


def _launch(p):
    exe = _chromium_executable()
    kwargs = {"headless": True, "args": _LAUNCH_ARGS}
    if exe:
        kwargs["executable_path"] = exe
    return p.chromium.launch(**kwargs)


def _inject_head(html: str, snippet: str) -> str:
    lower = html.lower()
    idx = lower.find("</head>")
    if idx == -1:
        return snippet + html
    return html[:idx] + snippet + html[idx:]


def html_to_pdf(html: str, *, timeout_ms: int = 20000) -> bytes:
    """Print the HTML to PDF, honoring the sheet's own ``@page`` size/margins
    and printing background colors (the blue/purple section bars)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch(p)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            page.set_content(html, wait_until="networkidle")
            return page.pdf(print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def html_to_png(
    html: str, *, variant: str = "print", timeout_ms: int = 20000
) -> bytes:
    """Screenshot the HTML. ``variant="portrait"`` frames the single-week sheet
    into a 3:4 social canvas; otherwise a full-page screenshot at print width."""
    from playwright.sync_api import sync_playwright

    portrait = variant == "portrait"
    if portrait:
        html = _inject_head(html, _PORTRAIT_CSS)

    with sync_playwright() as p:
        browser = _launch(p)
        try:
            page = browser.new_page(
                viewport={"width": _PORTRAIT_W if portrait else 900, "height": 1200},
                device_scale_factor=2,
            )
            page.set_default_timeout(timeout_ms)
            page.set_content(html, wait_until="networkidle")
            return page.screenshot(full_page=True, type="png")
        finally:
            browser.close()
