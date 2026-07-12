#!/usr/bin/env python3
"""Fit the shul's minyan-time rules (warplan module 3) against the fixture corpus.

Phase 0/1 recovered the *zmanim* definitions; this script recovers the *schedule
rules* — the offsets and fixed times TTCC uses for davening lines — by scoring
candidate rules against every 'minyan' entry in the weekly blocks of all 27
fixtures. The winning rules are encoded in engine/rules.py (DEFAULT_RULES) and
regression-tested by engine/validate_rules.py; the full triage of what fits and
what is a per-sheet manual override lives in phase3/PHASE3-FINDINGS.md.

Recovered rules (exact-hit rates printed by this script):

  weekday Mincha        = earliest shkia of the covered days − 10 min (floor)
  weekday Maariv        = latest weekday tzeis (6°) of the covered days (ceil)
  Erev Shabbos Mincha   = candle lighting + 8 min
  Kabbolas Shabbos      = Friday tzeis (6°, ceil) − 10 min  (so Maariv lands at tzeis)
  early ES Mincha       = plag hamincha − 20 min
  early ES candles      = "not before" plag, "not after approx" plag + 10
  early ES Kabbolas Sh. = plag hamincha
  early ES kiddush      = "before" tzeis − 30 "or after" tzeis; Shema "from" tzeis
  Shabbos Mincha        = shkia − 18 min rounded to nearest 5-minute mark
  Halacha shiur         = Shabbos Mincha − 30 min (runs in the same season as
                          the early ES minyan)
  Motzaei Sh. Maariv    = tzeis 8.4° (already validated by engine/validate.py)

  Fixed times: Shacharis Mon–Fri 6:15 & 7:30; Sun 8:00 & 9:15 (9:15 was 9:00
  until 5783); holiday-period third minyan 9:15; Shabbos: Tehillim 8:15 +
  Shacharis 10:10 on Mevorchim, Chassidus 9:15 + Shacharis 10:00 otherwise;
  summer-holiday extras Mincha 2:00pm / Maariv 9:00pm.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.zmanim import ZmanimEngine  # noqa: E402

E = ZmanimEngine()

DAY_ABBR = {"sun": 6, "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thur": 3,
            "thurs": 3, "fri": 4, "sat": 5, "shabbos": 5}


def parse_dayspec(spec: str | None, week_start: date, week_end: date) -> list[date] | None:
    """Dates in [week_start, week_end] covered by a printed day qualifier like
    'Sun.-Thurs.', 'Thurs. & Fri.', 'Mon., Wed.-Fri.'."""
    if not spec:
        return None
    s = spec.lower().replace("–", "-").replace(".", "")
    toks = re.findall(r"[a-z]+", s)

    def wd(t):
        for k, v in DAY_ABBR.items():
            if t.startswith(k):
                return v
        return None

    week = [week_start + timedelta(days=i)
            for i in range((week_end - week_start).days + 1)]
    if re.match(r"\s*\w+\s*-\s*\w+", s) and len(toks) >= 2 \
            and wd(toks[0]) is not None and wd(toks[1]) is not None:
        a, b = wd(toks[0]), wd(toks[1])
        out, started = [], False
        for d in week:
            if d.weekday() == a:
                started = True
            if started:
                out.append(d)
            if started and d.weekday() == b:
                break
        return out
    out = [d for t in toks if (w := wd(t)) is not None
           for d in week if d.weekday() == w]
    return out or None


def hhmm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def mins(dt) -> int:
    return dt.hour * 60 + dt.minute


def fmt(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def load_rows():
    rows = []
    for p in sorted((ROOT / "phase0" / "fixtures").glob("*.json")):
        fx = json.load(open(p))
        for b in fx["blocks"]:
            if b["type"] != "week":
                continue
            for e in b["entries"]:
                rows.append(dict(
                    src=fx["readable_name"], sec=e["section"] or "",
                    label=e["label"], spec=e["day_spec_raw"], t=hhmm(e["time"]),
                    kind=e["kind"], raw=e["raw"],
                    ws=date.fromisoformat(b["civil_start"]),
                    we=date.fromisoformat(b["civil_end"]),
                    fri=date.fromisoformat(b["friday"]) if b.get("friday") else None,
                    shab=date.fromisoformat(b["shabbos"]) if b.get("shabbos") else None,
                    labels=b.get("shabbos_labels") or []))
    return rows


def nearest5(m: int) -> int:
    return int(round(m / 5)) * 5


class Family:
    def __init__(self, name):
        self.name = name
        self.hits, self.known_alt, self.misses = 0, Counter(), []

    def score(self, row, calc, alts=()):
        if row["t"] == calc:
            self.hits += 1
        else:
            for alt_name, alt_val in alts:
                if row["t"] == alt_val:
                    self.known_alt[alt_name] += 1
                    return
            self.misses.append((row, calc))

    def report(self):
        n = self.hits + sum(self.known_alt.values()) + len(self.misses)
        print(f"{self.name:22s} {self.hits:3d}/{n:3d} rule-exact"
              + "".join(f"  [{k}: {v}]" for k, v in self.known_alt.items()))
        for row, calc in self.misses:
            print(f"    miss {row['src'][:26]:26s} printed {fmt(row['t'])}"
                  f" rule {fmt(calc)} ({row['t'] - calc:+d}m)  {row['raw'][:64]}")


def is_weekday_section(sec: str) -> bool:
    s = sec.lower()
    return ("davening" in s and "shabbos" not in s) or s.startswith("davening times")


def main():
    rows = load_rows()
    fams = {k: Family(k) for k in [
        "weekday_mincha", "weekday_maariv", "es_mincha", "kabbolas_shabbos",
        "early_es_mincha", "early_es_candles", "early_es_ks", "early_es_kiddush",
        "early_es_shema", "shabbos_mincha", "halacha_shiur",
        "shacharis_fixed", "shabbos_morning"]}
    # The fixed Shacharis menu across all profiles. Sun 9:00 became 9:15 after
    # 5783; 9:45 is the January-5786 reduced schedule. Combined lines like
    # "Sun 8:00 & 9:15; Mon-Fri 6:15 & 7:30" are transcribed with one glued
    # day_spec, so the fit scores menu membership; the Sun-vs-weekday *sets*
    # are schedule-profile configuration (see engine/rules.py).
    SHACHARIS_MENU = {8 * 60, 9 * 60 + 15, 9 * 60, 6 * 60 + 15, 7 * 60 + 30, 9 * 60 + 45}

    for r in rows:
        sec, lab = r["sec"].lower(), r["label"].lower()
        early = "early" in sec and "erev" in sec
        erev_shabbos = "erev shabbos" in sec and not early
        shabbos_day = "shabbos day" in sec

        if r["kind"] == "minyan" and is_weekday_section(sec):
            days = parse_dayspec(r["spec"] or r["label"], r["ws"], r["we"])
            if not days:
                days = [r["ws"] + timedelta(days=i) for i in range(5)]
            days = [d for d in days if d.weekday() != 5 and d != r["fri"]]
            if lab.startswith("mincha") and days:
                calc = min(mins(E.shkia(d, "floor")) for d in days) - 10
                fams["weekday_mincha"].score(r, calc, alts=[("fixed 2:00pm", 840)])
            elif lab.startswith("maariv") and days:
                calc = max(mins(E.tzeis(d, "ceil")) for d in days)
                fams["weekday_maariv"].score(r, calc, alts=[("fixed 9:00pm", 1260)])
            elif lab.startswith("shacharis") or "shacharis" in sec:
                if r["t"] in SHACHARIS_MENU:
                    fams["shacharis_fixed"].hits += 1
                else:
                    fams["shacharis_fixed"].misses.append((r, 375))

        elif r["kind"] == "minyan" and erev_shabbos and r["fri"]:
            cl = mins(E.candle_lighting(r["fri"]))
            if lab.startswith("mincha"):
                fams["es_mincha"].score(r, cl + 8)
            elif "kabbolas" in lab:
                fams["kabbolas_shabbos"].score(r, mins(E.tzeis(r["fri"], "ceil")) - 10)

        elif early and r["fri"]:
            plag = mins(E.plag_hamincha(r["fri"], "ceil"))
            tz = mins(E.tzeis(r["fri"], "ceil"))
            if lab.startswith("mincha"):
                fams["early_es_mincha"].score(r, plag - 20)
            elif "candle" in lab and "chanukah" not in lab:
                fams["early_es_candles"].score(r, plag, alts=[("plag+10 (not-after)", plag + 10)])
            elif "kabbolas" in lab:
                fams["early_es_ks"].score(r, plag)
            elif "kiddush" in lab:
                fams["early_es_kiddush"].score(r, tz - 30, alts=[("tzeis (or-after)", tz)])
            elif "shema" in lab or "kezayis" in lab:
                fams["early_es_shema"].score(r, tz)

        elif r["kind"] == "minyan" and shabbos_day and r["shab"]:
            shk = mins(E.shkia(r["shab"], "floor"))
            if lab.startswith("mincha"):
                fams["shabbos_mincha"].score(r, nearest5(shk - 18), alts=[("fixed 12:25 (RH)", 745)])
            elif "halacha" in lab:
                fams["halacha_shiur"].score(r, nearest5(shk - 18) - 30)
            elif lab.startswith(("tehillim", "chassidus", "shacharis")):
                mev = any("mevorchim" in (x or "").lower() for x in r["labels"])
                ok = {"tehillim": (495,), "chassidus": (555,),
                      "shacharis": (610,) if mev else (600,)}
                key = next(k for k in ok if lab.startswith(k))
                if r["t"] in ok[key]:
                    fams["shabbos_morning"].hits += 1
                else:
                    fams["shabbos_morning"].misses.append((r, ok[key][0]))

    total_hits = total_n = 0
    for f in fams.values():
        f.report()
        total_hits += f.hits + sum(f.known_alt.values())
        total_n += f.hits + sum(f.known_alt.values()) + len(f.misses)
    print(f"\nTOTAL: {total_hits}/{total_n} ({100 * total_hits / total_n:.1f}%) "
          f"explained by recovered rules; every miss triaged in phase3/PHASE3-FINDINGS.md")


if __name__ == "__main__":
    main()
