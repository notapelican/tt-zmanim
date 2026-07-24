"""TTCC sheet service — FastAPI app.

Wraps ``engine.assemble.generate`` and ``engine.render_html.render_html``. The
service is a pass-through: it parses inputs, applies auth and a range cap, then
returns exactly what the engine produced. It never recomputes or re-rounds a
time.

Run (from the repo root):
    TTCC_SERVICE_TOKEN=... uvicorn service.app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import hmac
import sys
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Ensure the repo root is importable so ``engine`` resolves when the app is
# launched from anywhere (e.g. ``uvicorn service.app:app``).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from engine.assemble import generate  # noqa: E402
from engine.render_html import render_html  # noqa: E402

from .config import load_settings  # noqa: E402
from .version import engine_version  # noqa: E402

SETTINGS = load_settings()

app = FastAPI(
    title="TTCC sheet service",
    version="0.1.0",
    summary="Thin HTTP wrapper over the TTCC zmanim engine/renderer.",
)

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if not SETTINGS.auth_enabled:
        return
    token = creds.credentials if creds else ""
    if not hmac.compare_digest(token, SETTINGS.token or ""):
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")


# --- request models ---------------------------------------------------------

class GenerateRequest(BaseModel):
    start: str | None = None
    end: str | None = None
    profiles: list[dict] | None = None
    notes: list[dict] | None = None
    overrides: dict[str, dict] | None = None


class RenderHtmlRequest(GenerateRequest):
    variant: str = "print"           # "print" | "portrait" (portrait styling is
                                     # applied by the rasterizer for PNG export)
    doc: dict | None = None          # pre-generated generate() dict; render it
                                     # directly (reprint a stored snapshot) with
                                     # no recompute
    template: str = "classic"        # "classic" (engine renderer) | "modern"
    logo_url: str | None = None      # modern only: masthead logo (URL/data URI)
    theme: dict | None = None        # modern only: fonts/size/colors (sanitized)
    fit: bool = True                 # False disables fit-to-page scaling (the
                                     # Settings "natural size" export override)
    referer: str | None = None       # Referer for the headless render, so a
                                     # domain-locked web-font kit (Adobe Fonts)
                                     # serves during PDF/PNG export


# --- helpers ----------------------------------------------------------------

def _parse_range(start: str | None, end: str | None) -> tuple[date, date]:
    if not start or not end:
        raise HTTPException(status_code=422, detail="start and end are required")
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=422, detail="start/end must be ISO dates (YYYY-MM-DD)"
        )
    if e < s:
        raise HTTPException(status_code=422, detail="end must be on or after start")
    if (e - s).days > SETTINGS.max_range_days:
        raise HTTPException(
            status_code=422,
            detail=f"range too large (> {SETTINGS.max_range_days} days)",
        )
    return s, e


def _deserialize_profiles(data: list[dict] | None):
    if data is None:
        return None
    from .profiles import profiles_from_json  # lazy: adapter module

    return profiles_from_json(data)


def _deserialize_notes(data: list[dict] | None):
    if data is None:
        return None
    from .profiles import notes_from_json  # lazy: adapter module

    return notes_from_json(data)


def _engine_kwargs(req: GenerateRequest) -> dict:
    kwargs: dict = {}
    profiles = _deserialize_profiles(req.profiles)
    if profiles is not None:
        kwargs["profiles"] = profiles
    notes = _deserialize_notes(req.notes)
    if notes is not None:
        kwargs["notes"] = notes
    if req.overrides is not None:
        kwargs["overrides"] = req.overrides
    return kwargs


def _generate_doc(req: GenerateRequest) -> dict:
    s, e = _parse_range(req.start, req.end)
    return generate(s, e, **_engine_kwargs(req))


def _resolve_doc(req: RenderHtmlRequest) -> dict:
    if req.doc is not None:
        return req.doc
    return _generate_doc(req)


def _render_html_str(req: RenderHtmlRequest, doc: dict) -> str:
    """Render the resolved doc to HTML with the requested template. The modern
    template is a service-side renderer; classic is the engine renderer. Both
    consume the identical doc — no time is recomputed."""
    if req.template == "modern":
        from .render_modern import render_modern

        html = render_modern(
            doc, variant=req.variant, logo_url=req.logo_url, theme=req.theme
        )
    else:
        from .render_modern import _webfont_links, classic_theme_css

        html = render_html(doc)
        # Classic typography theme (header/subheader/content fonts, sizes,
        # alignment) is injected here so the engine renderer stays pure.
        extra = _webfont_links(req.theme) + classic_theme_css(req.theme)
        if extra:
            html = html.replace("</head>", extra + "</head>", 1)
        # Content-sizing mode ('fixed' = base size drives text, fit shrinks only).
        if isinstance(req.theme, dict) and req.theme.get("fit_mode") == "fixed":
            html = html.replace("<html>", '<html data-ttcc-fit="fixed">', 1)
    if not req.fit:
        # Neutralize the embedded fit script's inline transform so content
        # renders at its natural size (may overflow the page box).
        html = html.replace(
            "</head>",
            "<style>.page-content{transform:none!important;width:100%!important}</style></head>",
            1,
        )
    return html


# --- endpoints --------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    from .raster import chromium_available

    return {
        "status": "ok",
        "engine_version": engine_version(),
        "chromium": chromium_available(),
    }


@app.post("/generate", dependencies=[Depends(require_auth)])
def post_generate(req: GenerateRequest) -> dict:
    doc = _generate_doc(req)
    return {**doc, "engine_version": engine_version()}


@app.post("/highlights", dependencies=[Depends(require_auth)])
def post_highlights(req: GenerateRequest) -> dict:
    """Shabbos & Yom Tov highlights (candle lighting / ends / fasts) per week
    in range — the data behind the public banner widget and the Shabbos
    signage screen. Same pass-through contract as /generate: the engine
    computes everything (see engine/highlights.py)."""
    from engine.highlights import highlights

    s, e = _parse_range(req.start, req.end)
    doc = highlights(s, e, **_engine_kwargs(req))
    return {**doc, "engine_version": engine_version()}


@app.post("/render/html", dependencies=[Depends(require_auth)])
def post_render_html(req: RenderHtmlRequest) -> dict:
    doc = _resolve_doc(req)
    return {"html": _render_html_str(req, doc), "engine_version": engine_version()}


@app.post("/render/whatsapp", dependencies=[Depends(require_auth)])
def post_render_whatsapp(req: RenderHtmlRequest) -> dict:
    from .render_whatsapp import render_whatsapp

    doc = _resolve_doc(req)
    return {"text": render_whatsapp(doc), "engine_version": engine_version()}


@app.post("/render/pdf", dependencies=[Depends(require_auth)])
def post_render_pdf(req: RenderHtmlRequest) -> Response:
    from .raster import html_to_pdf

    html = _render_html_str(req, _resolve_doc(req))
    pdf = html_to_pdf(html, timeout_ms=SETTINGS.render_timeout_ms, referer=req.referer)
    return Response(content=pdf, media_type="application/pdf")


@app.post("/render/png", dependencies=[Depends(require_auth)])
def post_render_png(req: RenderHtmlRequest) -> Response:
    from .raster import html_to_png

    html = _render_html_str(req, _resolve_doc(req))
    png = html_to_png(
        html, variant=req.variant, timeout_ms=SETTINGS.render_timeout_ms, referer=req.referer
    )
    return Response(content=png, media_type="image/png")


@app.post("/render/docx", dependencies=[Depends(require_auth)])
def post_render_docx(req: RenderHtmlRequest) -> Response:
    from .docx_export import render_docx_bytes

    data = render_docx_bytes(_resolve_doc(req))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/profiles/default", dependencies=[Depends(require_auth)])
def get_default_profiles() -> dict:
    from .profiles import notes_to_json, profiles_to_json
    from engine.rules import DEFAULT_NOTES, DEFAULT_PROFILES

    return {
        "profiles": profiles_to_json(DEFAULT_PROFILES),
        "notes": notes_to_json(DEFAULT_NOTES),
        "engine_version": engine_version(),
    }
