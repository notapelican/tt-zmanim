#!/usr/bin/env python3
"""Phase 2 golden regression: luach layer vs all 27 fixtures.

Checks every calendar-derived element the sheets print:
  - week blocks: parsha, hebrew date range, shabbos labels, molad line,
    Rosh Chodesh announcement days
  - day blocks: hebrew date, holiday labels, omer day
  - entries: fast dates, Pirkei Avos chapters

Exits nonzero if exact hits drop below BASELINE_HITS.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import luach  # noqa: E402
from engine.hebcal import to_hebrew  # noqa: E402

WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Shabbos"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-")
    return re.sub(r"[^a-z0-9]", "", s.lower())


# Fixture spelling -> canonical sedra spelling (normalized comparison keys)
SEDRA_ALIASES = {
    "mikketz": "mikeitz", "kitissa": "kisisa", "kisissa": "kisisa",
    "shlachlcha": "shlach", "lechlcha": "lechlecha", "vaera": "vaeira",
    "pikudei": "pekudei",
}

LABEL_ALIASES = {
    "hagadol": "hagadol", "shushanpurimkatan": "shushanpurimkatan",
    "roshchodesh": "roshchodesh",
}

# Day-block label spellings seen in sheets -> canonical holiday labels
DAY_ALIASES = {
    "hoshanorabbo": "hoshanarabbah", "hoshanarabba": "hoshanarabbah",
    "sheminiazeres": "sheminiatzeres", "shminiazeres": "sheminiatzeres",
    "erevroshhashana": "erevroshhashana", "roshhashanaday1": "roshhashanaday1",
    "succosday1": "succosday1", "sheviishelpesach": "sheviishelpesach",
    "acharonshelpesach": "acharonshelpesach", "shabboscholhamoedsuccos": "cholhamoedsuccos",
    "shabboscholhamoed": "cholhamoedpesach", "cholhamoed": "cholhamoed",
    "tzomgedaliah": "tzomgedaliah", "tzomgedalia": "tzomgedaliah",
    "taanisesther": "taanisesther", "fastofesther": "taanisesther",
}


def canon_sedra(name: str) -> str:
    return "".join(SEDRA_ALIASES.get(norm(p), norm(p))
                   for p in re.split(r"[––]", name))


class Scorer:
    def __init__(self):
        self.cats = {}

    def add(self, cat: str, ok: bool, detail: str = ""):
        hits, n, misses = self.cats.setdefault(cat, [0, 0, []])
        c = self.cats[cat]
        c[1] += 1
        if ok:
            c[0] += 1
        else:
            c[2].append(detail)

    def report(self) -> tuple[int, int]:
        th = tn = 0
        for cat, (hits, n, misses) in self.cats.items():
            th += hits
            tn += n
            flag = "" if hits == n else "  <-- residual"
            print(f"{cat:22s} {hits:3d}/{n:3d}{flag}")
            for m in misses[:6]:
                print(f"    miss {m}")
        return th, tn


def parse_molad(raw: str) -> dict | None:
    m = re.search(
        r"Molad for ([A-Za-z ]+?):\s*([A-Za-z. ]+?)\s*(\d{1,2})[:.](\d{2})\s*(am|pm)"
        r"\s*and\s*(\d+)\s*(?:chalakim|chelek|chalokim)", raw, re.I)
    if not m:
        return None
    day_raw = norm(m.group(2))
    day_map = {"sun": 0, "sunday": 0, "mon": 1, "monday": 1, "tue": 2, "tues": 2,
               "tuesday": 2, "wed": 3, "wednesday": 3, "thu": 4, "thur": 4,
               "thurs": 4, "thursday": 4, "fri": 5, "friday": 5, "shabbos": 6,
               "shabbosafternoon": 6, "shabbosevening": 6}
    return {"month": m.group(1).strip(), "weekday": day_map.get(day_raw),
            "hour": int(m.group(3)), "minute": int(m.group(4)),
            "ampm": m.group(5).lower(), "chalakim": int(m.group(6))}


MONTH_ALIASES = {"nissan": "nisan", "menachemav": "av", "cheshvan": "marcheshvan",
                 "tevet": "teves", "adari": "adari", "adarii": "adarii"}


def parse_hebrew_range(raw: str):
    """'27 Iyar – 4 Sivan 5781' -> ((27,'Iyar'),(4,'Sivan',5781)); None if odd."""
    m = re.match(
        r"\s*(\d{1,2})(?:\s+([A-Za-z ]+?))?\s*[––-]\s*(\d{1,2})\s+([A-Za-z IV]+?)"
        r"\s+(\d{4})", raw)
    if not m:
        return None
    return (int(m.group(1)), (m.group(2) or "").strip(), int(m.group(3)),
            m.group(4).strip(), int(m.group(5)))


def check_week(b: dict, sc: Scorer, src: str):
    shabbos = date.fromisoformat(b["shabbos"])
    tag = f"{src}:{b.get('parsha', '?')}"

    # parsha (week_parsha: festival-Shabbos weeks are titled by the deferred sedra)
    got = luach.week_parsha(shabbos)
    fixture_parsha = (b.get("parsha") or "").split(",")[0].strip()  # "Tzav, Erev Pesach"
    ok = got is not None and canon_sedra(got) == canon_sedra(fixture_parsha)
    sc.add("parsha", ok, f"{tag}: got {got}")

    # hebrew date range
    rng = parse_hebrew_range(b.get("hebrew_dates_raw") or "")
    if rng:
        d1, m1, d2, m2, yr = rng
        start, end = date.fromisoformat(b["civil_start"]), date.fromisoformat(b["civil_end"])
        h1, h2 = to_hebrew(start), to_hebrew(end)
        m1 = m1 or h2.month_name  # single-month ranges omit the first month
        ok = (h1.day == d1 and h2.day == d2 and h2.year == yr
              and norm(h2.month_name) == MONTH_ALIASES.get(norm(m2), norm(m2))
              and norm(h1.month_name) == MONTH_ALIASES.get(norm(m1), norm(m1)))
        sc.add("hebrew_range", ok,
               f"{tag}: printed '{b['hebrew_dates_raw'][:40]}' computed {h1} - {h2}")

    # labels
    computed = {LABEL_ALIASES.get(norm(l), norm(l)) for l in luach.shabbos_labels(shabbos)}
    for l in b.get("shabbos_labels", []):
        n = LABEL_ALIASES.get(norm(l), norm(l))
        if n in ("theshabbosbeforeyudshevat",):  # free-text, notes library not luach
            continue
        sc.add("shabbos_labels", n in computed, f"{tag}: '{l}' not in {sorted(computed)}")

    # molad + RC days
    if b.get("molad_raw"):
        p = parse_molad(b["molad_raw"])
        if p:
            ann = luach.rosh_chodesh_announcement(shabbos)
            if ann is None and norm(p["month"]) == "tishrei":
                # Elul sheets print Tishrei's molad although the Shabbos
                # before RH is not Mevorchim - compute it directly.
                hy = to_hebrew(shabbos).year + 1
                ann = {"month": "Tishrei", "molad": luach.molad_announcement(hy, 1)}
            if ann is None:
                sc.add("molad", False, f"{tag}: not Mevorchim per luach")
            else:
                a = ann["molad"]
                mn = MONTH_ALIASES.get(norm(p["month"]), norm(p["month"]))
                ok = (norm(ann["month"]) == mn
                      and a["weekday"] == p["weekday"] and a["hour"] == p["hour"]
                      and a["minute"] == p["minute"] and a["ampm"] == p["ampm"]
                      and a["chalakim"] == p["chalakim"])
                sc.add("molad", ok,
                       f"{tag}: printed {p} computed {ann['month']} "
                       f"{WD[a['weekday']]} {a['hour']}:{a['minute']:02d}{a['ampm']} "
                       f"+{a['chalakim']}")


def check_day(b: dict, sc: Scorer, src: str):
    if not b.get("date"):
        return
    d = date.fromisoformat(b["date"])
    tag = f"{src}:{b.get('title_raw', '')[:30]}"

    # hebrew date ("13 Adar", "2 Tishrei, Erev Shabbos", "5-6 Sivan")
    raw = (b.get("hebrew_date_raw") or "").split(",")[0].strip()
    m = re.match(r"(\d{1,2})(?:[––-]\d{1,2})?\s+([A-Za-z ]+)", raw)
    if m:
        h = to_hebrew(d)
        want_m = MONTH_ALIASES.get(norm(m.group(2)), norm(m.group(2)))
        ok = h.day == int(m.group(1)) and norm(h.month_name) == want_m
        sc.add("day_hebrew_date", ok, f"{tag}: printed '{raw}' computed {h}")

    # labels: every fixture label should appear among computed day/shabbos labels
    computed = {DAY_ALIASES.get(norm(x), norm(x)) for x in luach.day_labels(d)}
    if d.weekday() == 5:
        computed |= {DAY_ALIASES.get(norm(x), norm(x)) for x in luach.shabbos_labels(d)}
        r = luach.shabbos_reading(d)
        if r:
            computed.add(norm(r))
    if d.weekday() == 4:
        computed.add("erevshabbos")
    computed.add(norm(WD[(d.weekday() + 1) % 7]))
    for l in b.get("labels", []):
        parts = [p.strip() for p in re.split(r"[,/]| and ", l) if p.strip()]
        for p in parts:
            n = DAY_ALIASES.get(norm(p), norm(p))
            n = re.sub(r"nidche", "", n)
            n = re.sub(r"^\d(st|nd|rd|th)(night|day)", "", n)  # '1st night Shavuos'
            n = re.sub(r"^shabboskodesh", "", n) or "shabbos"
            hit = (n in computed or f"{n}day1" in computed
                   or any(n in c or c in n for c in computed if len(c) > 3 and len(n) > 3))
            sc.add("day_labels", hit, f"{tag}: '{p}' vs {sorted(computed)[:8]}")

    # omer
    if b.get("omer_day") is not None:
        got = luach.omer_day(d)
        sc.add("omer", got == b["omer_day"], f"{tag}: printed {b['omer_day']} got {got}")


def check_entries(fix: dict, sc: Scorer, src: str):
    for b in fix["blocks"]:
        for e in b.get("entries", []):
            raw = e.get("raw") or ""
            # Pirkei Avos chapters on Shabbos
            m = re.search(r"Pirkei? Avos (\d)(?:\s*&\s*(\d))?", raw)
            if m:
                d = b.get("shabbos") or b.get("date")
                if d:
                    d = date.fromisoformat(d)
                    if d.weekday() == 5:
                        want = tuple(int(g) for g in m.groups() if g)
                        got = luach.pirkei_avos(d)
                        sc.add("pirkei_avos", got == want,
                               f"{src} {d}: printed {want} got {got}")
            # Fast day identification
            if e.get("kind") == "fast" and e.get("date"):
                d = date.fromisoformat(e["date"])
                hy = to_hebrew(d).year
                fast_dates = set()
                for year in (hy, hy + 1):
                    fast_dates |= {f["date"] for f in luach.fasts(year)}
                # Fast lines are printed in the block of (or up to a week
                # before) the fast itself - e.g. Erev-YK lines inside the
                # preceding Shabbos block.
                ok = any(0 <= (f - d).days <= 7 for f in fast_dates)
                sc.add("fast_dates", ok, f"{src} {d}: {raw[:50]}")


BASELINE_HITS = 352  # 352/352: full corpus, exact


def main():
    sc = Scorer()
    for path in sorted((ROOT / "phase0" / "fixtures").glob("*.json")):
        fix = json.loads(path.read_text())
        src = fix["readable_name"]
        for b in fix["blocks"]:
            if b["type"] == "week":
                check_week(b, sc, src)
            elif b["type"] == "day":
                check_day(b, sc, src)
        check_entries(fix, sc, src)
    hits, n = sc.report()
    print(f"\nTOTAL: {hits}/{n} ({100 * hits / n:.1f}%)")
    if hits < BASELINE_HITS:
        print(f"FAIL: below baseline of {BASELINE_HITS}")
        return 1
    if hits > BASELINE_HITS:
        print(f"NOTE: improved over baseline {BASELINE_HITS}; bump BASELINE_HITS to {hits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
