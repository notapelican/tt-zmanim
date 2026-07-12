#!/usr/bin/env python3
"""Deterministic parser: extracted sheet text -> fixture JSON (SCHEMA.md).

Handles the two regular layouts:
  weekly  - "The week of Parshas X:" blocks with known section headings
  yomtov  - day blocks headed "Title: <hebrew date> (Weekday D Mon.)"

Usage: parse_sheets.py <extracted-txt-stem> [more stems...]
Writes phase0/fixtures/<stem>.json. Validate with check_fixtures.py afterwards.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "phase0" / "extracted"
FIXTURES = ROOT / "phase0" / "fixtures"

MONTHS = {m[:3].lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}
MONTHS["sept"] = 9

TIME_RE = re.compile(r"(?<![\d:.])(\d{1,2})[:.](\d{2,3})\s*(?:(am|pm)\b|(?![\d:.]))", re.IGNORECASE)

SECTION_HEADINGS = [
    "davening times during the week",
    "erev shabbos key times",
    "erev shabbos candle lighting and davening",
    "erev shabbos early minyan",
    "shabbos day and motzaei shabbos",
    "times for the week ahead",
]
NOTE_PREFIXES = (
    "note", "it is customary", "daylight saving", "public holiday", "covid",
    "refreshments", "“when av enters", "a kosheren", "a freilichen", "after maariv",
    "all night learning", "for chol", "additional readings", "machatzis",
    "the erev shabbos", "this is based on", "remember to make",
)
ZMAN_WORDS = ("shkia", "tzeis", "netz", "sunrise", "plag", "sheyakir", "shema",
              "candle", "alos", "dawn", "chatzo", "mincha gedola", "molad",
              "sha'a", "sha’a", "kiddush levana")


def hy_to_civil_year(hy: int, month: int) -> int:
    return hy - 3761 if month >= 9 else hy - 3760


def parse_time(h, m, ap):
    hh, mm = int(h), int(m[:2])
    ap = ap.lower()
    hh = hh % 12 + (12 if ap == "pm" else 0)
    return f"{hh:02d}:{mm:02d}"


def qualifier_for(line_lower, pos):
    ctx = line_lower[max(0, pos - 30):pos]
    for q in ("not before", "finish by", "not after approx", "approx", "from", "before", "after", "by"):
        if q in ctx:
            return q if q != "by" or "finish by" in ctx else ("finish by" if "finish by" in ctx else "by")
    return None


def kind_for(label_lower, line_lower):
    if ("fast" in line_lower or "tzom" in line_lower) and re.search(r"start|end|begin|commence", line_lower):
        return "fast"
    if "chometz" in line_lower or "bedika" in line_lower:
        return "deadline"
    if any(w in label_lower for w in ZMAN_WORDS):
        return "zman"
    return "minyan"


WD = {"sun": 6, "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "shabbos": 5}
# weekday->offset from the week's Sunday
WD_OFF = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "shabbos": 6, "sat": 6}


def entries_from_line(line, section, default_date, week_start=None):
    """One entry per am/pm time token on the line."""
    out = []
    stripped = re.sub(r"^[•●\-\*\s]+", "", line).strip()
    low = stripped.lower()
    matches = list(TIME_RE.finditer(stripped))
    # bare tokens (no am/pm) inherit meridiem from the nearest anchored token to
    # the right on the same line ("Sun. 8:00 & 9:15am"), else from the left
    meridiems = [m.group(3) for m in matches]
    for j, ap in enumerate(meridiems):
        if ap is None:
            nxt = next((meridiems[k] for k in range(j + 1, len(meridiems)) if meridiems[k]), None)
            prv = next((meridiems[k] for k in range(j - 1, -1, -1) if meridiems[k]), None)
            meridiems[j] = nxt or prv
    matches = [m for j, m in enumerate(matches) if meridiems[j]]
    meridiems = [ap for ap in meridiems if ap]
    if not matches:
        return out
    label = stripped[: matches[0].start()].strip(" .…:;,-–")
    label = re.sub(r"\.{2,}", "", label).strip() or "(unlabeled)"
    dspec = None
    md = re.search(r"\b(Sun|Mon|Tues?|Wed|Thurs?|Fri|Shabbos)[a-z]*\.?\s*[–&\-—]?\s*(Sun|Mon|Tues?|Wed|Thurs?|Fri|Shabbos)?[a-z]*\.?", stripped)
    if md and md.group(0).strip():
        dspec = md.group(0).strip()
    kind = kind_for(label.lower(), low)
    edate = default_date
    if kind == "fast" and week_start:
        wd = re.search(r"\b(sun|mon|tue|wed|thu|fri)[a-z]*\.?", low)
        if wd:
            edate = (week_start + timedelta(days=WD_OFF[wd.group(1)])).isoformat()
    for m, ap in zip(matches, meridiems):
        out.append({
            "section": section,
            "label": ("Fast start" if kind == "fast" and re.search(r"start|begin|commence", low[: m.start()])
                      else "Fast end" if kind == "fast" else label),
            "kind": kind,
            "day_spec_raw": dspec,
            "date": edate,
            "time": parse_time(m.group(1), m.group(2), ap),
            "qualifier": qualifier_for(low, m.start()),
            "raw": stripped[:160],
        })
    return out


def is_note(line_lower):
    return any(line_lower.startswith(p) for p in NOTE_PREFIXES)


# ---------------- weekly ----------------

WEEK_TITLE = re.compile(r"^The week of (?:Parshas |Pesach.*?& Parshas )?(.+?):?\s*$", re.MULTILINE)
CIVIL_RANGE = re.compile(
    r"\((\d{1,2})\s*(?:([A-Za-z]+)\.?)?\s*[–—-]\s*(\d{1,2})\s+([A-Za-z]+)\.?\s*[’‘']?(\d{2})\)")


def parse_weekly(stem: str, text: str, hy: int) -> dict:
    lines = text.splitlines()
    # locate week-title line indices
    idxs = [i for i, ln in enumerate(lines) if ln.strip().lower().startswith("the week of")]
    blocks = []
    global_notes_tail = []
    for bi, start_i in enumerate(idxs):
        end_i = idxs[bi + 1] if bi + 1 < len(idxs) else len(lines)
        chunk = lines[start_i:end_i]
        title = chunk[0].strip()
        parsha = re.sub(r"^The week of (Parshas )?", "", title).rstrip(":").strip()
        # civil range may sit on title line or next line(s)
        head = " ".join(chunk[:3])
        m = CIVIL_RANGE.search(head)
        if not m:
            raise ValueError(f"{stem}: no civil range in '{head[:100]}'")
        d2, mon2 = int(m.group(3)), MONTHS[m.group(4)[:4].lower()[:3] if m.group(4)[:4].lower() != "sept" else "sept"]
        year = hy_to_civil_year(hy, mon2)
        end = date(year, mon2, d2)
        start = end - timedelta(days=6)
        hebrew_raw = re.sub(r"\s+", " ", " ".join(chunk[1:3])).strip()[:80]
        b = {"type": "week", "title_raw": title, "parsha": parsha, "shabbos_labels": [],
             "hebrew_dates_raw": hebrew_raw,
             "civil_start": start.isoformat(), "civil_end": end.isoformat(),
             "friday": (end - timedelta(days=1)).isoformat(), "shabbos": end.isoformat(),
             "entries": [], "molad_raw": None, "notes": [], "suspected_errata": []}
        section = None
        i = 1
        while i < len(chunk):
            ln = chunk[i].strip()
            low = ln.lower()
            i += 1
            if not ln:
                continue
            if low.startswith("shabbos kodesh"):
                labels = [s.strip() for s in ln.split(":", 1)[1].split(",")] if ":" in ln else []
                b["shabbos_labels"] = [l for l in labels[1:] if l] if len(labels) > 1 else []
                section = "Shabbos kodesh"
                continue
            matched_heading = next((h for h in SECTION_HEADINGS if h in low), None)
            if matched_heading and not TIME_RE.search(ln):
                section = ln.rstrip(":")
                continue
            if low.startswith("molad"):
                mol = ln
                if i < len(chunk) and ("chodesh" in chunk[i].lower() or "time" in chunk[i].lower()):
                    mol += " " + chunk[i].strip()
                    i += 1
                b["molad_raw"] = mol
                continue
            if is_note(low):
                note = ln
                while i < len(chunk) and chunk[i].strip() and not TIME_RE.search(chunk[i]) \
                        and not is_note(chunk[i].strip().lower()) \
                        and not any(h in chunk[i].lower() for h in SECTION_HEADINGS) \
                        and not chunk[i].strip().lower().startswith(("shabbos kodesh", "molad", "the week of")):
                    note += " " + chunk[i].strip()
                    i += 1
                b["notes"].append(note[:300])
                continue
            if TIME_RE.search(ln):
                sec_low = (section or "").lower()
                ddate = None
                if "erev shabbos" in sec_low:
                    ddate = b["friday"]
                elif "shabbos day" in sec_low:
                    ddate = b["shabbos"]
                b["entries"].extend(entries_from_line(ln, section, ddate, week_start=start))
            # untimed non-note lines are ignored (layout filler)
        blocks.append(b)
    return {"source_pdf": stem + ".pdf", "readable_name": stem, "hebrew_year": hy,
            "format": "weekly", "blocks": blocks}


# ---------------- yomtov ----------------

DAY_HEAD = re.compile(
    r"^(.{2,70}?):\s*([0-9]{1,2}[–\-]?[0-9]{0,2}\s+\w+.*?)\(\s*"
    r"(?:(Sun|Mon|Tues?|Wed|Thurs?|Fri|Shabbos)[a-z]*\.?\s+)?(\d{1,2})\s+([A-Za-z]+)\.?\s*\)\s*.{0,25}$")
DAY_HEAD_RANGE = re.compile(r"\(\s*\w*\.?\s*\d{1,2}\s*[–—-]")


def parse_yomtov(stem: str, text: str, hy: int) -> dict:
    lines = text.splitlines()
    blocks = []
    cur = None
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        m = DAY_HEAD.match(s)
        if m and not TIME_RE.search(s):
            is_range = bool(DAY_HEAD_RANGE.search(s)) or "-" in m.group(2)[:6] or "–" in m.group(2)[:6]
            d = None
            if not is_range:
                mon = MONTHS.get(m.group(5)[:4].lower()[:3] if m.group(5)[:4].lower() != "sept" else "sept")
                if mon:
                    d = date(hy_to_civil_year(hy, mon), mon, int(m.group(4))).isoformat()
            cur = {"type": "day", "title_raw": m.group(1).strip(), "weekday_raw": m.group(3),
                   "hebrew_date_raw": m.group(2).strip(), "date": d, "labels": [m.group(1).strip()],
                   "omer_day": None, "entries": [], "notes": [], "suspected_errata": []}
            blocks.append(cur)
            continue
        if cur is None:
            cur = {"type": "day", "title_raw": "(preamble)", "weekday_raw": None,
                   "hebrew_date_raw": None, "date": None, "labels": [], "omer_day": None,
                   "entries": [], "notes": [], "suspected_errata": []}
            blocks.append(cur)
        if TIME_RE.search(s):
            if low.startswith("molad"):
                cur["notes"].append(s[:300])
            elif low.startswith(("it is customary",)):
                cur["notes"].append(s[:300])
            else:
                cur["entries"].extend(entries_from_line(s, cur["title_raw"], cur["date"]))
        elif is_note(low):
            cur["notes"].append(s[:300])
    return {"source_pdf": stem + ".pdf", "readable_name": stem, "hebrew_year": hy,
            "format": "yomtov", "blocks": blocks}


def main():
    for stem in sys.argv[1:]:
        text = (EXTRACTED / (stem + ".txt")).read_text()
        mhy = re.search(r"57\d\d", stem)
        hy = int(mhy.group(0)) if mhy else 5786
        if "the week of" in text.lower():
            fx = parse_weekly(stem, text, hy)
        else:
            fx = parse_yomtov(stem, text, hy)
        out = FIXTURES / (stem + ".json")
        out.write_text(json.dumps(fx, indent=1, ensure_ascii=False))
        n = sum(len(b["entries"]) for b in fx["blocks"])
        print(f"{stem}: {len(fx['blocks'])} blocks, {n} entries")


if __name__ == "__main__":
    main()
