#!/usr/bin/env python3
"""Mechanical completeness check: every clock time printed in the extracted text
must be accounted for by its fixture (as an entry, or inside molad_raw/notes).
Compares multisets of normalized HH:MM tokens and reports discrepancies.
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

TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2,3})\s*(am|pm)\b", re.IGNORECASE)


def norm(h: str, m: str, ap: str) -> str:
    hh, mm = int(h), int(m[:2])  # tolerate typos like 8:000am
    ap = ap.lower()
    if ap == "pm" and hh != 12:
        hh += 12
    if ap == "am" and hh == 12:
        hh = 0
    return f"{hh:02d}:{mm:02d}"


def times_in(text: str) -> Counter:
    return Counter(norm(*m.groups()) for m in TIME_RE.finditer(text or ""))


def fixture_times(fx: dict) -> Counter:
    c = Counter()
    for b in fx.get("blocks", []):
        for e in b.get("entries", []):
            c[e["time"]] += 1
        c += times_in(b.get("molad_raw") or "")
        for n in b.get("notes", []):
            c += times_in(n)
        for s in b.get("suspected_errata", []):
            pass  # errata strings describe, not account
    return c


def main() -> int:
    bad = 0
    for txt in sorted(EXTRACTED.glob("*.txt")):
        fixture = FIXTURES / (txt.stem + ".json")
        if not fixture.exists():
            print(f"MISSING FIXTURE: {txt.stem}")
            bad += 1
            continue
        source = times_in(txt.read_text())
        fx = json.loads(fixture.read_text())
        have = fixture_times(fx)
        missing = source - have
        extra = have - source
        if missing or extra:
            bad += 1
            print(f"MISMATCH {txt.stem}:")
            if missing:
                print(f"  in source but not fixture: {dict(missing)}")
            if extra:
                print(f"  in fixture but not source: {dict(extra)}")
        else:
            print(f"ok {txt.stem} ({sum(source.values())} times)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
