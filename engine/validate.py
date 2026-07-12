#!/usr/bin/env python3
"""Golden regression: run the confirmed ZmanimEngine against all 27 fixtures.

Reuses phase0/scripts/fit_zmanim.py's observation harvesting (same families,
same day-selection logic) but scores the ENGINE's fixed definitions instead of
grid-searching, since Phase 0 already confirmed which definition each family uses.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phase0" / "scripts"))
sys.path.insert(0, str(ROOT))

import fit_zmanim as F  # noqa: E402
from engine.zmanim import ZmanimEngine  # noqa: E402

engine = ZmanimEngine()


def m(dt):
    return dt.hour * 60 + dt.minute + dt.second / 60


FAMILY_FUNCS = {
    "shkia_fri": ("single", lambda o: m(engine.shkia(o["date"], "floor"))),
    "shkia_wk": ("range_min", lambda d: m(engine.shkia(d, "floor"))),
    "candle_fri": ("single", lambda o: m(engine.candle_lighting(o["date"]))),
    "netz_wk": ("range_max", lambda d: m(engine.netz(d, "ceil"))),
    "tzeis_fri": ("single", lambda o: m(engine.tzeis(o["date"]))),
    "tzeis_wk": ("range_max", lambda d: m(engine.tzeis(d, "ceil"))),
    "motzaei": ("single", lambda o: m(engine.tzeis_shabbos(o["date"]))),
    "motzaei_day": ("single", lambda o: m(engine.tzeis_shabbos(o["date"]))),
    "fast_end": ("single", lambda o: m(engine.tzeis(o["date"], "ceil"))),
    "candle_notbefore": ("single", lambda o: m(engine.tzeis_shabbos(o["date"]))),
    "mishyakir_wk": ("range_max", lambda d: m(engine.misheyakir(d, "ceil"))),
    "shema_wk": ("range_min", lambda d: m(engine.sof_zman_shema(d, "floor"))),
    "shema_shab": ("single", lambda o: m(engine.sof_zman_shema(o["date"], "floor"))),
    "shema_day": ("single", lambda o: m(engine.sof_zman_shema(o["date"], "floor"))),
    "plag_fri": ("single", lambda o: m(engine.plag_hamincha(o["date"]))),
    "candle_day": ("single", lambda o: m(engine.candle_lighting(o["date"]))),
    "shkia_day": ("single", lambda o: m(engine.shkia(o["date"], "floor"))),
    "chatzot": ("single", lambda o: m(engine.chatzos(o["date"]))),
}
# alos excluded: fixtures mix fast-start (alos) with explicit "alos"/"dawn" lines
# that need per-item date resolution already done during collect().
FAMILY_FUNCS["alos"] = ("single", lambda o: m(engine.alos(o["date"], "nearest")))
FAMILY_FUNCS["fast_start"] = ("single", lambda o: m(engine.alos(o["date"], "nearest")))


def score(fam, kind, fn, observations):
    hits, misses = 0, []
    for o in observations:
        try:
            if kind == "single":
                calc = round(fn(o))
            elif kind == "range_min":
                calc = round(min(fn(d) for d in o["dates"]))
            else:  # range_max
                calc = round(max(fn(d) for d in o["dates"]))
        except ValueError:
            continue
        if calc == o["printed"]:
            hits += 1
        else:
            misses.append((o, calc))
    return hits, len(observations), misses


def main():
    fixture_paths = sorted((ROOT / "phase0" / "fixtures").glob("*.json"))
    obs = F.collect(fixture_paths)
    total_hits = total_n = 0
    for fam, (kind, fn) in FAMILY_FUNCS.items():
        hits, n, misses = score(fam, kind, fn, obs.get(fam, []))
        total_hits += hits
        total_n += n
        flag = "" if hits == n else "  <-- residual"
        print(f"{fam:20s} {hits:3d}/{n:3d}{flag}")
        for o, calc in misses[:5]:
            print(f"    miss {o['src']}: printed {o['printed']//60:02d}:{o['printed']%60:02d}"
                  f" engine {calc//60:02d}:{calc%60:02d} ({calc - o['printed']:+d}m)  {o.get('raw', '')[:70]}")
    print(f"\nTOTAL: {total_hits}/{total_n} ({100*total_hits/total_n:.1f}%)")


if __name__ == "__main__":
    main()
