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

# 1:1 WhatsApp canvas (emitted at 2x = 2160x2160). Square is the shape WhatsApp
# shows whole — chat bubble, status and thumbnail alike — and the sheet sits
# inside a padded safe area (~8% per side) so a centre-ward crop, or a circular
# avatar crop, only eats white and never a time.
_SQUARE = 1080
_SQUARE_SAFE = 968                               # the sheet panel inside the canvas
_SQUARE_PAD = (_SQUARE - _SQUARE_SAFE) // 2      # canvas padding around it
_SQUARE_INNER = 28                               # the panel's own inner margin (px)

# The page box itself is re-shaped into that square rather than an A4 page being
# scaled into it: A4 is 0.71 wide-to-tall, so letterboxing it inside a square
# wastes ~30% of the canvas on white and shrinks the type to match. Resizing the
# box instead lets the sheet's own fit-to-page pass (page_layout.FIT_JS, which
# runs before the screenshot) reflow and fill the square with the largest type
# that fits — no transform of ours involved.
#
# Only the first page is rendered. A multi-page sheet (a yom-tov range with day
# blocks) cannot be squeezed into one square: its 2x2 cell grid needs A4-ish
# width, and forcing several pages into panels either overlaps the dotted-leader
# rows or shrinks past the fit floor and clips them. The plugin counts the pages
# in the preview and says so next to the button; the PDF carries all of them.
_SQUARE_CSS = f"""
<style id="ttcc-square">
  html {{ margin:0 !important; padding:0 !important; background:#fff !important; }}
  body, body.sheet {{ box-sizing:border-box !important; margin:0 !important;
    width:{_SQUARE}px !important; height:{_SQUARE}px !important;
    padding:{_SQUARE_PAD}px !important; background:#fff !important;
    display:flex !important; align-items:center !important;
    justify-content:center !important; }}
  .page {{ box-sizing:border-box !important; width:{_SQUARE_SAFE}px !important;
    height:{_SQUARE_SAFE}px !important; margin:0 !important;
    page-break-after:auto !important; break-after:auto !important; }}
  .page ~ .page {{ display:none !important; }}
  .page-margin {{ left:{_SQUARE_INNER}px !important; top:{_SQUARE_INNER}px !important;
    right:{_SQUARE_INNER}px !important; bottom:{_SQUARE_INNER}px !important; }}
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


_FITTED = "document.documentElement.getAttribute('data-ttcc-fitted') === '1'"


def _wait_for_fit(page, html: str, timeout_ms: int) -> None:
    """Block until the sheet's embedded fit-to-page script has scaled every
    page (it sets data-ttcc-fitted on <html>). No-op for HTML without it."""
    if 'id="ttcc-fit"' not in html:
        return
    try:
        page.wait_for_function(_FITTED, timeout=timeout_ms)
    except Exception:
        pass  # print whatever we have rather than failing the export


def _apply_referer(page, referer: str | None) -> None:
    """Send a Referer on sub-resource fetches so domain-locked web fonts (Adobe
    Fonts / Typekit projects restricted to the site's domain) serve during a
    headless render. Harmless for open fonts (Google) and the rest of the page."""
    if referer:
        try:
            page.set_extra_http_headers({"Referer": referer})
        except Exception:
            pass


def html_to_pdf(html: str, *, timeout_ms: int = 20000, referer: str | None = None) -> bytes:
    """Print the HTML to PDF, honoring the sheet's own ``@page`` size/margins
    and printing background colors (the blue/purple section bars)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch(p)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            _apply_referer(page, referer)
            page.set_content(html, wait_until="networkidle")
            _wait_for_fit(page, html, timeout_ms)
            return page.pdf(print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def html_to_png(
    html: str, *, variant: str = "print", timeout_ms: int = 20000, referer: str | None = None
) -> bytes:
    """Screenshot the HTML.

    ``variant="portrait"`` scales the sheet to fill a 3:4 social canvas
    (1080x1440, emitted at 2x = 2160x2880); ``variant="square"`` fills a padded
    1:1 WhatsApp canvas (1080x1080 -> 2160x2160); otherwise a full-page
    screenshot at print width.
    """
    from playwright.sync_api import sync_playwright

    portrait = variant == "portrait"
    square = variant == "square"
    if portrait:
        html = _inject_head(html, _PORTRAIT_CSS)
    elif square:
        html = _inject_head(html, _SQUARE_CSS)

    with sync_playwright() as p:
        browser = _launch(p)
        try:
            if square:
                page = browser.new_page(
                    viewport={"width": _SQUARE, "height": _SQUARE},
                    device_scale_factor=2,
                )
                page.set_default_timeout(timeout_ms)
                _apply_referer(page, referer)
                page.set_content(html, wait_until="networkidle")
                # The square panels are sized in CSS, so the sheet's own fit pass
                # fills them; nothing left to scale here.
                _wait_for_fit(page, html, timeout_ms)
                return page.screenshot(
                    clip={"x": 0, "y": 0, "width": _SQUARE, "height": _SQUARE},
                    type="png",
                )
            if portrait:
                page = browser.new_page(
                    viewport={"width": _PORTRAIT_W, "height": _PORTRAIT_H},
                    device_scale_factor=2,
                )
                page.set_default_timeout(timeout_ms)
                _apply_referer(page, referer)
                page.set_content(html, wait_until="networkidle")
                _wait_for_fit(page, html, timeout_ms)
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
            _apply_referer(page, referer)
            page.set_content(html, wait_until="networkidle")
            _wait_for_fit(page, html, timeout_ms)
            return page.screenshot(full_page=True, type="png")
        finally:
            browser.close()
