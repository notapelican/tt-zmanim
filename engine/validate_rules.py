#!/usr/bin/env python3
"""Golden regression for the schedule-rules engine (Phase 3).

For every weekly block in the 27 fixtures this script rebuilds the week's
context, resolves the ACTUAL rules engine (engine/rules.py DEFAULT_PROFILES),
and scores each printed minyan/schedule line against the engine's line for the
same rule. It also scores seasonal-profile switching: the early-Erev-Shabbos
minyan section must appear on exactly the weeks the profile condition says.

Exits nonzero if exact hits drop below BASELINE_HITS. Every residual is
triaged in phase3/PHASE3-FINDINGS.md (rule nudged to a 5-minute mark, holiday
override, fast-day Mincha, etc.) — they are printed here for inspection.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.assemble import build_week_context  # noqa: E402
from engine.rules import (DEFAULT_PROFILES, EREV_SHABBOS, EREV_SHABBOS_EARLY,  # noqa: E402
                          SHABBOS_DAY, WEEKDAY, active_profiles, davening_lines)
from engine.zmanim import ZmanimEngine  # noqa: E402

ENGINE = ZmanimEngine()

# Fixed-time menus (profile config, not zman-anchored): scored as membership.
SHACHARIS_MENU = {"06:15", "07:30", "08:00", "09:15",
                  "09:00",   # Sunday 2nd minyan until 5783
                  "09:45"}   # January-5786 reduced schedule
SHABBOS_MORNING = {"tehillim": {"08:15"}, "chassidus": {"09:15"}}


def classify(entry: dict, mevorchim: bool) -> tuple[str, object] | None:
    """Map a fixture minyan entry to (family, expectation). expectation is a
    rule_id (compare against the engine's resolved line) or a set of fixed
    times (menu membership)."""
    sec, lab = (entry["section"] or "").lower(), entry["label"].lower()
    early = "early" in sec and "erev" in sec
    if early:
        if lab.startswith("mincha"):
            return "early_es_mincha", "early_es_mincha"
        if "kabbolas" in lab:
            return "early_es_ks", "early_es_ks"
        if "kiddush" in lab:
            return "early_es_kiddush", ("early_es_kiddush_before", "early_es_kiddush_after")
        if "shema" in lab or "kezayis" in lab:
            return "early_es_shema", "early_es_shema"
        return None  # Chanukah candle lines etc.
    if "erev shabbos" in sec:
        if lab.startswith("mincha"):
            return "es_mincha", "es_mincha"
        if "kabbolas" in lab:
            return "kabbolas_shabbos", "es_kabbolas_shabbos"
        return None
    if "shabbos day" in sec:
        if lab.startswith("mincha"):
            return "shabbos_mincha", "shab_mincha"
        if "halacha" in lab:
            return "halacha_shiur", "shab_halacha_shiur"
        if lab.startswith("tehillim"):
            return "shabbos_morning", SHABBOS_MORNING["tehillim"]
        if lab.startswith("chassidus"):
            return "shabbos_morning", SHABBOS_MORNING["chassidus"]
        if lab.startswith("shacharis"):
            return "shabbos_morning", {"10:10"} if mevorchim else {"10:00"}
        if "maariv" in lab or "motzaei" in lab:
            return "motzaei_maariv", "motzaei_maariv"
        return None
    if "davening" in sec:  # weekday section
        if lab.startswith("mincha"):
            return "weekday_mincha", ("weekday_mincha", "holiday_early_mincha")
        if lab.startswith("maariv"):
            return "weekday_maariv", ("weekday_maariv", "holiday_late_maariv")
        if lab.startswith("shacharis") or "shacharis" in sec:
            return "shacharis_fixed", SHACHARIS_MENU
        return None
    return None


def main():
    fams: dict[str, list] = {}
    profile_hits, profile_misses = 0, []

    for p in sorted((ROOT / "phase0" / "fixtures").glob("*.json")):
        fx = json.load(open(p))
        for b in fx["blocks"]:
            if b["type"] != "week" or not b.get("shabbos"):
                continue
            shabbos = date.fromisoformat(b["shabbos"])
            sunday = shabbos - timedelta(days=6)
            ctx = build_week_context(sunday, ENGINE)
            lines = {l["rule_id"]: l for l in davening_lines(ctx)}
            # early candles resolve to two lines with distinct ids
            early_expected = any(pr.id == "early_erev_shabbos"
                                 for pr in active_profiles(ctx))
            early_printed = any("early" in (e["section"] or "").lower()
                                and "erev" in (e["section"] or "").lower()
                                for e in b["entries"])
            if early_printed == early_expected:
                profile_hits += 1
            else:
                profile_misses.append(
                    f"{fx['readable_name']} {b.get('parsha')}: sheet "
                    f"{'has' if early_printed else 'lacks'} early minyan, "
                    f"engine says {'active' if early_expected else 'inactive'}")

            for e in b["entries"]:
                if e["kind"] != "minyan":
                    continue
                c = classify(e, ctx.mevorchim)
                if c is None:
                    continue
                fam, expect = c
                if isinstance(expect, set):
                    ok = e["time"] in expect
                    calc = "/".join(sorted(expect))
                else:
                    ids = (expect,) if isinstance(expect, str) else expect
                    calcs = [lines[i]["time"] for i in ids if i in lines]
                    ok = e["time"] in calcs
                    calc = "/".join(calcs) if calcs else "(rule inactive)"
                fams.setdefault(fam, []).append(
                    (ok, f"{fx['readable_name'][:26]:26s} printed {e['time']}"
                         f" engine {calc}  {e['raw'][:56]}"))

    total_hits = total_n = 0
    for fam, results in fams.items():
        hits = sum(1 for ok, _ in results if ok)
        total_hits += hits
        total_n += len(results)
        flag = "" if hits == len(results) else "  <-- residual"
        print(f"{fam:20s} {hits:3d}/{len(results):3d}{flag}")
        for ok, msg in results:
            if not ok:
                print(f"    miss {msg}")
    print(f"\nprofile switching     {profile_hits:3d}/{profile_hits + len(profile_misses):3d}")
    for m in profile_misses:
        print(f"    miss {m}")

    total_hits += profile_hits
    total_n += profile_hits + len(profile_misses)
    print(f"\nTOTAL: {total_hits}/{total_n} ({100 * total_hits / total_n:.1f}%)")
    if total_hits < BASELINE_HITS:
        print(f"FAIL: below baseline of {BASELINE_HITS} exact hits")
        return 1
    if total_hits > BASELINE_HITS:
        print(f"NOTE: improved over baseline {BASELINE_HITS}; bump BASELINE_HITS to {total_hits}")
    return 0


# Regression floor: exact hits achieved by the recovered rule set; every
# residual is triaged in phase3/PHASE3-FINDINGS.md. Raise when improved.
BASELINE_HITS = 778


if __name__ == "__main__":
    sys.exit(main())
