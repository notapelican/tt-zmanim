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

# Injected only for the "portrait" PNG variant. The sheet HTML is an A4 print
# document with small absolute pt fonts; on a 1080px canvas that reads tiny. We
# don't touch the engine's layout — instead we single-column it, loosen the line
# rhythm a little, and then (in _PORTRAIT_FIT_JS below) scale the whole block up
# to fill the canvas. The overrides need !important to beat the pt-absolute
# engine CSS (same trick as column-count). Spacing is in the *design* frame; the
# fit transform scales it along with everything else.
_PORTRAIT_CSS = """
<style id="ttcc-portrait">
  html, body { margin: 0 !important; padding: 0 !important; background: #fff; }
  body.sheet { width: auto !important; }
  .single, .multi { column-count: 1 !important; }
  .single .row { margin: 2.5px 0 !important; }
  .single .barwrap { margin: 9px 0 3px !important; }
  .single .subtitle { margin-bottom: 6px !important; }
  .single .foot { margin-top: 12px !important; }
</style>
"""

# Runs in-page after layout. Wraps the sheet in a fixed 1080x1440 canvas and
# uniformly scales it to fill (contain). Because the sheet's rows are single-line
# (label + dotted leader + value), the block height barely depends on width — so
# we first pick a design width that makes the block's aspect match the 3:4 target
# (height * 1080/1440), then scale to fill and center. This fills the frame with
# readable type instead of leaving a small print doc floating in the corner.
_PORTRAIT_FIT_JS = """
() => {
  const TW = %d, TH = %d, PAD = 44;
  const availW = TW - 2 * PAD, availH = TH - 2 * PAD;
  const stage = document.createElement('div');
  stage.id = 'ttcc-stage';
  stage.style.position = 'absolute';
  stage.style.transformOrigin = 'top left';
  while (document.body.firstChild) stage.appendChild(document.body.firstChild);
  const canvas = document.createElement('div');
  canvas.id = 'ttcc-canvas';
  canvas.style.cssText =
    'position:relative;width:' + TW + 'px;height:' + TH + 'px;overflow:hidden;background:#fff;';
  canvas.appendChild(stage);
  document.body.appendChild(canvas);
  const measure = (w) => { stage.style.width = w + 'px'; return { w: stage.scrollWidth, h: stage.scrollHeight }; };
  let m = measure(760);
  let designW = Math.round(m.h * (TW / TH));
  designW = Math.max(480, Math.min(940, designW));
  m = measure(designW);
  const s = Math.min(availW / m.w, availH / m.h);
  stage.style.transform = 'scale(' + s + ')';
  stage.style.left = ((TW - m.w * s) / 2) + 'px';
  stage.style.top = ((TH - m.h * s) / 2) + 'px';
  return { w: m.w, h: m.h, s: s };
}
""" % (_PORTRAIT_W, _PORTRAIT_H)

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
    """Screenshot the HTML. ``variant="portrait"`` scales the sheet to fill a 3:4
    social canvas (1080x1440, emitted at 2x = 2160x2880); otherwise a full-page
    screenshot at print width."""
    from playwright.sync_api import sync_playwright

    portrait = variant == "portrait"
    if portrait:
        html = _inject_head(html, _PORTRAIT_CSS)

    with sync_playwright() as p:
        browser = _launch(p)
        try:
            if portrait:
                page = browser.new_page(
                    viewport={"width": _PORTRAIT_W, "height": _PORTRAIT_H},
                    device_scale_factor=2,
                )
                page.set_default_timeout(timeout_ms)
                page.set_content(html, wait_until="networkidle")
                # Fit-to-canvas: screenshot() ignores @page, so we scale in-page
                # and clip to an exact 1080x1440 region.
                page.evaluate(_PORTRAIT_FIT_JS)
                return page.screenshot(
                    clip={"x": 0, "y": 0, "width": _PORTRAIT_W, "height": _PORTRAIT_H},
                    type="png",
                )
            page = browser.new_page(
                viewport={"width": 900, "height": 1200},
                device_scale_factor=2,
            )
            page.set_default_timeout(timeout_ms)
            page.set_content(html, wait_until="networkidle")
            return page.screenshot(full_page=True, type="png")
        finally:
            browser.close()
