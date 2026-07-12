#!/usr/bin/env python3
"""Mechanical completeness check: every clock time printed in the extracted text
must be accounted for by its fixture (as an entry, or inside molad_raw/notes).

Handles the sheets' typographic quirks:
- "9.15am" (period separator) and "8:000am" (typo minutes) count as times;
- bare times without am/pm ("Candle lighting ... 4:45") match a fixture time of
  either possible half-day (04:45 or 16:45).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "phase0" / "extracted"
FIXTURES = ROOT / "phase0" / "fixtures"

TIME_RE = re.compile(r"\b(\d{1,2})[:.](\d{2,3})\s*(am|pm)?\b", re.IGNORECASE)


def tokens_in(text: str):
    """Yield ('HH:MM', ampm_known) for each time-like token; bare tokens yield the
    raw 12h form ('H:MM')."""
    for m in TIME_RE.finditer(text or ""):
        h, mm, ap = int(m.group(1)), m.group(2)[:2], m.group(3)
        if h == 0 or h > 12:
            continue  # not a 12h-clock token (e.g. verse refs); sheets never print 24h
        if ap:
            ap = ap.lower()
            hh = h % 12 + (12 if ap == "pm" else 0)
            yield f"{hh:02d}:{mm}", True
        else:
            yield f"{h}:{mm}", False


def anchored_times(text: str) -> Counter:
    """Times with explicit am/pm, normalized to 24h."""
    return Counter(t for t, known in tokens_in(text) if known)


def fixture_times(fx: dict) -> Counter:
    c = Counter()
    for b in fx.get("blocks", []):
        for e in b.get("entries", []):
            c[e["time"]] += 1
        for extra in [b.get("molad_raw") or ""] + list(b.get("notes", [])):
            for t, known in tokens_in(extra):
                if known:
                    c[t] += 1
                else:
                    # bare time in a note: account for it under its 12h form
                    c["~" + t] += 1
    return c


def main() -> int:
    bad = 0
    for txt in sorted(EXTRACTED.glob("*.txt")):
        fixture = FIXTURES / (txt.stem + ".json")
        if not fixture.exists():
            print(f"MISSING FIXTURE: {txt.stem}")
            bad += 1
            continue
        text = txt.read_text()
        have = fixture_times(json.loads(fixture.read_text()))
        # split fixture side into anchored and bare-note buckets
        bare_notes = Counter({k[1:]: v for k, v in have.items() if k.startswith("~")})
        anchored_have = Counter({k: v for k, v in have.items() if not k.startswith("~")})

        missing = Counter()
        for tok, known in tokens_in(text):
            if known:
                if anchored_have[tok] > 0:
                    anchored_have[tok] -= 1
                else:
                    missing[tok] += 1
            else:
                # bare token: try both half-days in fixture entries, then bare notes
                h, mm = tok.split(":")
                am, pm = f"{int(h)%12:02d}:{mm}", f"{int(h)%12+12:02d}:{mm}"
                if anchored_have[pm] > 0:
                    anchored_have[pm] -= 1
                elif anchored_have[am] > 0:
                    anchored_have[am] -= 1
                elif bare_notes[tok] > 0:
                    bare_notes[tok] -= 1
                else:
                    missing[tok] += 1
        extra = Counter({k: v for k, v in anchored_have.items() if v > 0})
        if missing or extra:
            bad += 1
            print(f"MISMATCH {txt.stem}:")
            if missing:
                print(f"  in source but not fixture: {dict(missing)}")
            if extra:
                print(f"  in fixture but not source: {dict(extra)}")
        else:
            print(f"ok {txt.stem}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
