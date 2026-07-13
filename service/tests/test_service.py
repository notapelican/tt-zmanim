"""Service tests: adapter round-trip identity, engine parity, auth, range cap,
and (when Chromium is present) rasterization.

Runnable two ways:
    pytest service/tests/test_service.py
    python3 -m service.tests.test_service      # no pytest needed
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

# Repo root importable, and a fixed token so service.config loads cleanly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
os.environ.setdefault("TTCC_SERVICE_TOKEN", "test-token")

from fastapi.testclient import TestClient  # noqa: E402

from engine.assemble import generate  # noqa: E402
from engine.render_html import render_html  # noqa: E402
from engine.rules import DEFAULT_NOTES, DEFAULT_PROFILES  # noqa: E402
from service.app import app  # noqa: E402
from service.profiles import (  # noqa: E402
    notes_from_json,
    notes_to_json,
    profiles_from_json,
    profiles_to_json,
)

TOKEN = os.environ["TTCC_SERVICE_TOKEN"]
AUTH = {"Authorization": f"Bearer {TOKEN}"}
# A Mevorchim, early-minyan-season week (the RENDERER-CONTRACT Example 1 span).
START, END = "2025-12-07", "2025-12-13"
client = TestClient(app)


def _norm(obj):
    """JSON-normalize (tuples->lists etc.) so dict comparisons are apples-to-apples."""
    return json.loads(json.dumps(obj))


def test_profile_roundtrip_identity():
    assert DEFAULT_PROFILES == profiles_from_json(profiles_to_json(DEFAULT_PROFILES))
    assert DEFAULT_NOTES == notes_from_json(notes_to_json(DEFAULT_NOTES))


def test_generate_through_adapter_matches_defaults():
    """Generating with adapter-round-tripped profiles/notes must be byte-identical
    to generating with the engine's own DEFAULT_PROFILES/DEFAULT_NOTES."""
    s, e = date.fromisoformat(START), date.fromisoformat(END)
    baseline = generate(s, e)
    through = generate(
        s,
        e,
        profiles=profiles_from_json(profiles_to_json(DEFAULT_PROFILES)),
        notes=notes_from_json(notes_to_json(DEFAULT_NOTES)),
    )
    assert baseline == through


def test_generate_parity():
    """/generate == direct generate() (pass-through), plus an engine_version."""
    direct = _norm(generate(date.fromisoformat(START), date.fromisoformat(END)))
    r = client.post("/generate", json={"start": START, "end": END}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.pop("engine_version")
    assert body == direct


def test_render_html_parity():
    """/render/html == render_html(direct doc)."""
    doc = generate(date.fromisoformat(START), date.fromisoformat(END))
    expected = render_html(doc)
    r = client.post("/render/html", json={"start": START, "end": END}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["html"] == expected


def test_render_html_from_doc():
    """Rendering a pre-generated doc (reprint-snapshot path) matches direct render."""
    doc = generate(date.fromisoformat(START), date.fromisoformat(END))
    expected = render_html(doc)
    r = client.post("/render/html", json={"doc": doc}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["html"] == expected


def test_render_modern_template():
    """The modern template renders the same doc via the service-side renderer,
    honors a sanitized theme/logo, and never recomputes content (same times)."""
    from service.render_modern import render_modern

    doc = generate(date.fromisoformat(START), date.fromisoformat(END))
    theme = {"heading_font": "georgia", "base": 17, "text_color": "#20242e"}
    expected = render_modern(doc, logo_url="data:image/png;base64,AA==", theme=theme)
    r = client.post(
        "/render/html",
        json={"doc": doc, "template": "modern", "logo_url": "data:image/png;base64,AA==", "theme": theme},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    assert r.json()["html"] == expected
    # A calculated time from the doc appears verbatim (no recompute/re-round).
    assert "sheet-body" in expected


def test_render_modern_theme_sanitized():
    """Hostile theme values are ignored — no arbitrary CSS reaches the output."""
    from service.render_modern import render_modern

    doc = generate(date.fromisoformat(START), date.fromisoformat(END))
    html = render_modern(doc, theme={
        "heading_font": "</style><script>x</script>",
        "text_color": "red;} body{display:none",
        "base": "99999",
    })
    assert "<script>" not in html
    assert "display:none" not in html


def test_render_whatsapp():
    """WhatsApp broadcast keeps essential minyan times, drops astronomical zmanim,
    and reproduces engine times verbatim."""
    r = client.post(
        "/render/whatsapp", json={"start": "2026-07-12", "end": "2026-07-18"}, headers=AUTH
    )
    assert r.status_code == 200, r.text
    text = r.json()["text"]
    assert "Shacharis" in text and "Candle lighting" in text
    assert "*🕍 Tzemach Tzedek" in text
    assert "::" not in text  # no double-colon on the Shacharis label
    # astronomical zmanim are omitted from the broadcast
    for dropped in ("Mi'sheyakir", "Netz Hachamah", "Plag Hamincha", "Tzeis hachochavim"):
        assert dropped not in text, dropped


def test_auth_required():
    assert client.post("/generate", json={"start": START, "end": END}).status_code == 401
    bad = {"Authorization": "Bearer wrong"}
    assert client.post("/generate", json={"start": START, "end": END}, headers=bad).status_code == 401


def test_range_cap():
    r = client.post(
        "/generate", json={"start": "2025-01-01", "end": "2027-01-01"}, headers=AUTH
    )
    assert r.status_code == 422, r.text
    assert "range too large" in r.text


def test_bad_dates():
    r = client.post("/generate", json={"start": "nope", "end": END}, headers=AUTH)
    assert r.status_code == 422


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["engine_version"]


def test_profiles_default_endpoint():
    r = client.get("/profiles/default", headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    # Round-trips back to the engine defaults through the adapter.
    assert profiles_from_json(body["profiles"]) == DEFAULT_PROFILES
    assert notes_from_json(body["notes"]) == DEFAULT_NOTES


def test_raster_pdf_and_png_if_chromium():
    from service.raster import chromium_available

    if not chromium_available():
        print("  (skipped raster: chromium unavailable)")
        return
    pdf = client.post("/render/pdf", json={"start": START, "end": END}, headers=AUTH)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content[:5] == b"%PDF-"
    png = client.post(
        "/render/png",
        json={"start": START, "end": END, "variant": "portrait"},
        headers=AUTH,
    )
    assert png.status_code == 200, png.text
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
