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

# --- social canvases --------------------------------------------------------
#
# Both image variants put one printed page on a fixed canvas, centred, with a
# margin of white all round. That margin is the crop insurance: nothing is drawn
# inside ``pad``, so a centre-ward crop — or a circular avatar crop — only ever
# eats white. Only the first page is drawn; two pages on one canvas would each
# land near half size. The plugin counts the pages and says so next to the
# button, and the PDF carries all of them.
#
# What differs is the shape of the page put on the canvas:
#
# * ``page: None`` keeps the sheet on its A4 box and scales the whole page to
#   fit. A4 is 1:1.41 and the 3:4 canvas is 1:1.33, so the letterbox bars cost
#   almost nothing — the sheet arrives as printed, at nearly the largest size
#   the frame allows.
# * ``page: "canvas"`` re-boxes the page to the canvas's own shape, so the
#   sheet's fit-to-page pass (page_layout.FIT_JS) lays the block out inside a
#   square exactly as it would on paper. Letterboxing A4 into a square instead
#   spends a third of the frame on white and leaves the type ~40% smaller.
#   Multi-block ranges arrange themselves the way the layout spec already says
#   (two full-height columns, or a 2x2 grid), so a fortnight or a month still
#   lands readably on one square.
#
# ``css`` is a per-canvas typographic adjustment. A week's rows are wide and
# short, so a single-week block is a landscape slab; in a tall frame it needs a
# looser rhythm to reach the foot. The values are in the *design* frame, so the
# fit pass scales them with the type. Multi-block pages already fill a tall
# frame and are left alone.
_A4_PX = (210 * 96 / 25.4, 297 * 96 / 25.4)  # the .page box, in CSS px

_CANVASES = {
    # 1:1 WhatsApp canvas — the shape WhatsApp shows whole, in the chat bubble,
    # in Status and as a thumbnail. Emitted at 2x = 2160x2160.
    "square": {"w": 1080, "h": 1080, "pad": 32, "page": "canvas", "css": ""},
    # 3:4 for feeds and phone screens. Emitted at 2x = 2160x2880.
    "portrait": {"w": 1080, "h": 1440, "pad": 40, "page": None, "css": """
  .single .row { margin:2.5px 0 !important; }
  .single .barwrap { margin:9px 0 3px !important; }
  .single .subtitle { margin-bottom:6px !important; }
  .single .foot { margin-top:12px !important; }
  /* Two blocks stack instead of standing side by side: half of a tall frame's
     width starves the rows, and the fit pass then has to hold the whole page
     back to keep them readable. One over the other, each gets the full width
     and the pair fills the frame. The divider turns with them. */
  .page-cells.two { grid-template-columns:1fr !important; }
  .page-cells.two > .cell { padding:0 0 2mm !important; }
  .page-cells.two > .cell:nth-child(2n) { border-left:0 !important;
      border-top:1px solid #000 !important; padding:2mm 0 0 !important; }
"""},
}


def _canvas_css(name: str) -> str:
    """Centre one page of the sheet on the named canvas.

    The page is absolutely centred and scaled as a whole, so the centring is
    exact and needs no measure-and-scale pass in the browser.
    """
    c = _CANVASES[name]
    availw, availh = c["w"] - 2 * c["pad"], c["h"] - 2 * c["pad"]
    if c["page"] == "canvas":
        pw, ph, scale = availw, availh, 1.0
    else:
        pw, ph = _A4_PX
        scale = min(availw / pw, availh / ph)
    box = f"width:{pw:g}px !important; height:{ph:g}px !important;"
    return f"""
<style id="ttcc-canvas-{name}">
  /* Let the sheet's fit pass grow the block past the print ceiling: on a share
     image, filling the frame is the point. It stops of its own accord when a
     row can no longer fit its label — see page_layout.FIT_JS. */
  :root {{ --ttcc-fit-max: 4; }}
  html {{ margin:0 !important; padding:0 !important; background:#fff !important; }}
  body, body.sheet {{ position:relative !important; margin:0 !important;
                      width:{c["w"]}px !important; height:{c["h"]}px !important;
                      overflow:hidden !important; background:#fff !important; }}
  .page {{ position:absolute !important; left:50% !important; top:50% !important;
           {box} margin:0 !important; box-shadow:none !important;
           transform:translate(-50%, -50%) scale({scale:.6g}) !important;
           page-break-after:auto !important; break-after:auto !important; }}
  .page ~ .page {{ display:none !important; }}
{c["css"]}</style>
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

    ``variant="square"`` lays the sheet out on a 1:1 WhatsApp canvas
    (1080x1080, emitted at 2x = 2160x2160); ``variant="portrait"`` on a 3:4
    social canvas (1080x1440 -> 2160x2880); otherwise a full-page screenshot at
    print width. See ``_canvas_css`` for how the image variants are laid out.
    """
    from playwright.sync_api import sync_playwright

    canvas = _CANVASES.get(variant)
    if canvas:
        html = _inject_head(html, _canvas_css(variant))

    with sync_playwright() as p:
        browser = _launch(p)
        try:
            if canvas:
                page = browser.new_page(
                    viewport={"width": canvas["w"], "height": canvas["h"]},
                    device_scale_factor=2,
                )
                page.set_default_timeout(timeout_ms)
                _apply_referer(page, referer)
                page.set_content(html, wait_until="networkidle")
                # The sheet's own fit pass sizes the content inside the re-boxed
                # page; nothing else to do once it reports it has settled.
                _wait_for_fit(page, html, timeout_ms)
                return page.screenshot(
                    clip={"x": 0, "y": 0, "width": canvas["w"], "height": canvas["h"]},
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
