#!/usr/bin/env python3
"""Fit candidate zmanim definitions against the fixture corpus.

For every zman family we grid-search (definition x day-selection x rounding x elevation)
and report the combination that reproduces the most printed values exactly, with
residual stats and outliers. Times are compared at minute resolution.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from solar import CIVIL_ZENITH, elevation_adjustment, sun_event_local, solar_noon_local

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "phase0" / "fixtures"
TZ = ZoneInfo("Australia/Sydney")
LAT, LON = -33.889, 151.260  # 1 Penkivil St, Bondi

ELEVATIONS = [0.0, 15.0, 30.0, 50.0, 75.0]


# ---------- helpers ----------

def parse_iso(s):
    return date.fromisoformat(s) if s else None


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def dt_to_float_minutes(dt: datetime) -> float:
    return dt.hour * 60 + dt.minute + dt.second / 60 + dt.microsecond / 6e7


def round_minutes(x: float, mode: str) -> int:
    if mode == "floor":
        return math.floor(x)
    if mode == "ceil":
        return math.ceil(x)
    return math.floor(x + 0.5)


def sunset(d, zenith):
    return sun_event_local(d, LAT, LON, TZ, zenith, rising=False)


def sunrise(d, zenith):
    return sun_event_local(d, LAT, LON, TZ, zenith, rising=True)


# ---------- observation collection ----------

def label_norm(e):
    return (e.get("label") or "").lower()


def section_norm(e):
    return (e.get("section") or "").lower()


def collect(fixture_paths):
    """Return dict family -> list of observations {date(s), printed_minutes, src, qualifier}."""
    obs = defaultdict(list)
    for p in fixture_paths:
        fx = json.loads(p.read_text())
        for b in fx.get("blocks", []):
            if b.get("type") == "week":
                fri, shab = parse_iso(b.get("friday")), parse_iso(b.get("shabbos"))
                start = parse_iso(b.get("civil_start"))
                weekdays = [start + timedelta(days=i) for i in range(5)] if start else None
                for e in b.get("entries", []):
                    lab, sec = label_norm(e), section_norm(e)
                    t = to_minutes(e["time"])
                    src = f"{p.stem}:{b.get('parsha')}"
                    rec = {"printed": t, "src": src, "raw": e.get("raw", "")}
                    erev = "erev shabbos" in sec
                    if "shkia" in lab and erev and fri:
                        obs["shkia_fri"].append({**rec, "date": fri})
                    elif "shkia" in lab and weekdays and not erev:
                        obs["shkia_wk"].append({**rec, "dates": weekdays})
                    elif ("tzeis hacho" in lab or "tzeis hako" in lab) and erev and fri:
                        obs["tzeis_fri"].append({**rec, "date": fri})
                    elif lab.startswith("tzeis") and weekdays and not erev:
                        obs["tzeis_wk"].append({**rec, "dates": weekdays})
                    elif "plag" in lab and fri:
                        obs["plag_fri"].append({**rec, "date": fri})
                    elif "candle" in lab and erev and fri:
                        obs["candle_fri"].append({**rec, "date": fri})
                    elif ("netz" in lab or "sunrise" in lab) and weekdays:
                        obs["netz_wk"].append({**rec, "dates": weekdays})
                    elif "sheyakir" in lab and weekdays:
                        obs["mishyakir_wk"].append({**rec, "dates": weekdays})
                    elif "shema" in lab and weekdays and "shabbos" not in sec:
                        obs["shema_wk"].append({**rec, "dates": weekdays})
                    elif "shema" in lab and shab and "shabbos" in sec:
                        obs["shema_shab"].append({**rec, "date": shab})
                    elif "motzaei" in lab and shab:
                        obs["motzaei"].append({**rec, "date": shab})
                    elif e.get("kind") == "fast" and e.get("date"):
                        key = "fast_start" if "start" in lab else "fast_end"
                        obs[key].append({**rec, "date": parse_iso(e["date"]), "section": e.get("section")})
            elif b.get("type") == "day":
                d = parse_iso(b.get("date"))
                if not d:
                    continue
                for e in b.get("entries", []):
                    lab = label_norm(e)
                    t = to_minutes(e["time"])
                    src = f"{p.stem}:{b.get('title_raw')}"
                    rec = {"printed": t, "src": src, "date": d, "raw": e.get("raw", "")}
                    if e.get("kind") == "fast":
                        obs["fast_start" if "start" in lab or "commence" in lab else "fast_end"].append(rec)
                    elif "candle" in lab:
                        q = (e.get("qualifier") or "")
                        obs["candle_notbefore" if "not before" in q else "candle_day"].append(rec)
                    elif "alos" in lab or "dawn" in lab:
                        obs["alos"].append(rec)
                    elif "shkia" in lab:
                        obs["shkia_day"].append(rec)
                    elif "motzaei" in lab and "maariv" in lab:
                        obs["motzaei_day"].append(rec)
                    elif "chatzot" in lab or "chatzos" in lab:
                        obs["chatzot"].append(rec)
                    elif "shema" in lab:
                        obs["shema_day"].append(rec)
    return obs


# ---------- fitting primitives ----------

def eval_single(observations, compute, roundings=("floor", "nearest", "ceil")):
    """observations have a single 'date'. compute(date) -> float minutes.
    Returns best (rounding, exact_count, results) by exact matches."""
    best = None
    for r in roundings:
        hits, results = 0, []
        for o in observations:
            try:
                calc = compute(o["date"])
            except ValueError:
                results.append((o, None, None))
                continue
            got = round_minutes(calc, r)
            err = got - o["printed"]
            hits += err == 0
            results.append((o, got, err))
        if best is None or hits > best[1]:
            best = (r, hits, results)
    return best


def eval_range(observations, compute, roundings=("floor", "nearest", "ceil")):
    """observations have 'dates' (Sun..Thu/Fri). Try each fixed weekday index and
    min/max over the range as the day-selection rule."""
    day_rules = [("Sun", 0), ("Mon", 1), ("Tue", 2), ("Wed", 3), ("Thu", 4), ("min", "min"), ("max", "max")]
    best = None
    for rule_name, rule in day_rules:
        for r in roundings:
            hits, results = 0, []
            for o in observations:
                try:
                    vals = [compute(d) for d in o["dates"]]
                except ValueError:
                    results.append((o, None, None))
                    continue
                calc = min(vals) if rule == "min" else max(vals) if rule == "max" else vals[rule]
                got = round_minutes(calc, r)
                err = got - o["printed"]
                hits += err == 0
                results.append((o, got, err))
            if best is None or hits > best[2]:
                best = (rule_name, r, hits, results)
    return best


def summarize(name, n, hits, rule, results, max_show=6):
    lines = [f"### {name}: {hits}/{n} exact  [{rule}]"]
    misses = [(o, got, err) for o, got, err in results if err not in (0, None)]
    for o, got, err in misses[:max_show]:
        lines.append(f"  miss {o['src']}: printed {o['printed']//60:02d}:{o['printed']%60:02d} calc {got//60:02d}:{got%60:02d} ({err:+d}m)")
    if len(misses) > max_show:
        lines.append(f"  ... {len(misses)-max_show} more misses")
    return "\n".join(lines)


# ---------- main ----------

def main():
    fixture_paths = sorted(FIXTURES.glob("*.json"))
    obs = collect(fixture_paths)
    print(f"fixtures: {len(fixture_paths)}")
    for k, v in sorted(obs.items()):
        print(f"  {k}: {len(v)} observations")
    print()

    report = []

    # --- Friday shkia: sunset at civil zenith, sea level vs elevation-adjusted
    for elev in ELEVATIONS:
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        best = eval_single(obs["shkia_fri"], lambda d, z=z: dt_to_float_minutes(sunset(d, z)))
        report.append((f"shkia_fri elev={elev}m", best[1], len(obs["shkia_fri"]),
                       summarize(f"Friday shkia (elev {elev}m)", len(obs["shkia_fri"]), best[1], best[0], best[2])))

    # --- weekday shkia (range)
    for elev in [0.0, 30.0]:
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        best = eval_range(obs["shkia_wk"], lambda d, z=z: dt_to_float_minutes(sunset(d, z)))
        report.append((f"shkia_wk elev={elev}m", best[2], len(obs["shkia_wk"]),
                       summarize(f"Weekday shkia (elev {elev}m)", len(obs["shkia_wk"]), best[2], f"day={best[0]},{best[1]}", best[3])))

    # --- netz (range)
    for elev in ELEVATIONS:
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        best = eval_range(obs["netz_wk"], lambda d, z=z: dt_to_float_minutes(sunrise(d, z)))
        report.append((f"netz elev={elev}m", best[2], len(obs["netz_wk"]),
                       summarize(f"Netz (elev {elev}m)", len(obs["netz_wk"]), best[2], f"day={best[0]},{best[1]}", best[3])))

    # --- candle lighting = shkia - offset
    for elev in [0.0, 30.0]:
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        for off in (15, 18, 20, 22):
            best = eval_single(obs["candle_fri"],
                               lambda d, z=z, off=off: dt_to_float_minutes(sunset(d, z)) - off)
            report.append((f"candle off={off} elev={elev}", best[1], len(obs["candle_fri"]),
                           summarize(f"Candle lighting (shkia-{off}m, elev {elev}m)", len(obs["candle_fri"]), best[1], best[0], best[2])))

    # --- Friday tzeis / weekday tzeis / motzaei: degree scan
    def scan_degrees(family, single, lo=55, hi=105):
        out = []
        for tenth in range(lo, hi + 1):  # degrees*10
            deg = tenth / 10.0
            z = 90.0 + deg
            if single:
                best = eval_single(obs[family], lambda d, z=z: dt_to_float_minutes(sunset(d, z)))
                out.append((deg, best[1], best[0], best[2]))
            else:
                best = eval_range(obs[family], lambda d, z=z: dt_to_float_minutes(sunset(d, z)))
                out.append((deg, best[2], f"day={best[0]},{best[1]}", best[3]))
        out.sort(key=lambda x: -x[1])
        return out

    for fam, single in (("tzeis_fri", True), ("tzeis_wk", False), ("motzaei", True)):
        if not obs[fam]:
            continue
        top = scan_degrees(fam, single)[:3]
        for deg, hits, rule, results in top:
            report.append((f"{fam} {deg}deg", hits, len(obs[fam]),
                           summarize(f"{fam} @ {deg} deg", len(obs[fam]), hits, rule, results)))
        # fixed-minute alternatives
        for mins in range(20, 46):
            if single:
                best = eval_single(obs[fam], lambda d, m=mins: dt_to_float_minutes(sunset(d, CIVIL_ZENITH)) + m)
                hits, rule, results = best[1], best[0], best[2]
            else:
                best = eval_range(obs[fam], lambda d, m=mins: dt_to_float_minutes(sunset(d, CIVIL_ZENITH)) + m)
                hits, rule, results = best[2], f"day={best[0]},{best[1]}", best[3]
            if hits >= 0.8 * len(obs[fam]):
                report.append((f"{fam} +{mins}min", hits, len(obs[fam]),
                               summarize(f"{fam} = shkia+{mins}min", len(obs[fam]), hits, rule, results)))

    # --- misheyakir degree scan (sunrise side)
    if obs["mishyakir_wk"]:
        out = []
        for tenth in range(95, 130):
            deg = tenth / 10.0
            z = 90.0 + deg
            best = eval_range(obs["mishyakir_wk"], lambda d, z=z: dt_to_float_minutes(sunrise(d, z)))
            out.append((deg, best[2], f"day={best[0]},{best[1]}", best[3]))
        out.sort(key=lambda x: -x[1])
        for deg, hits, rule, results in out[:3]:
            report.append((f"misheyakir {deg}deg", hits, len(obs["mishyakir_wk"]),
                           summarize(f"Misheyakir @ {deg} deg", len(obs["mishyakir_wk"]), hits, rule, results)))

    # --- alos from fast starts + explicit alos lines
    alos_obs = obs["fast_start"] + obs["alos"]
    if alos_obs:
        out = []
        for tenth in range(140, 210):
            deg = tenth / 10.0
            z = 90.0 + deg
            best = eval_single(alos_obs, lambda d, z=z: dt_to_float_minutes(sunrise(d, z)))
            out.append((f"{deg}deg", best[1], best[0], best[2]))
        for mins in (72, 90, 96, 120):
            best = eval_single(alos_obs, lambda d, m=mins: dt_to_float_minutes(sunrise(d, CIVIL_ZENITH)) - m)
            out.append((f"-{mins}min", best[1], best[0], best[2]))
        out.sort(key=lambda x: -x[1])
        for name, hits, rule, results in out[:4]:
            report.append((f"alos {name}", hits, len(alos_obs),
                           summarize(f"Alos {name}", len(alos_obs), hits, rule, results)))

    # --- fast end: same scan as tzeis
    if obs["fast_end"]:
        out = []
        for tenth in range(55, 105):
            deg = tenth / 10.0
            best = eval_single(obs["fast_end"], lambda d, z=90 + deg: dt_to_float_minutes(sunset(d, z)))
            out.append((f"{deg}deg", best[1], best[0], best[2]))
        out.sort(key=lambda x: -x[1])
        for name, hits, rule, results in out[:3]:
            report.append((f"fast_end {name}", hits, len(obs["fast_end"]),
                           summarize(f"Fast end {name}", len(obs["fast_end"]), hits, rule, results)))

    # --- sof zman shema: day-formula grid
    day_starts = {
        "netz": lambda d: dt_to_float_minutes(sunrise(d, CIVIL_ZENITH)),
        "alos16.1": lambda d: dt_to_float_minutes(sunrise(d, 90 + 16.1)),
        "alos16.9": lambda d: dt_to_float_minutes(sunrise(d, 90 + 16.9)),
        "alos18": lambda d: dt_to_float_minutes(sunrise(d, 90 + 18.0)),
        "alos19.8": lambda d: dt_to_float_minutes(sunrise(d, 90 + 19.8)),
        "alos-72": lambda d: dt_to_float_minutes(sunrise(d, CIVIL_ZENITH)) - 72,
        "alos-96": lambda d: dt_to_float_minutes(sunrise(d, CIVIL_ZENITH)) - 96,
        "alos-120": lambda d: dt_to_float_minutes(sunrise(d, CIVIL_ZENITH)) - 120,
    }
    day_ends = {
        "shkia": lambda d: dt_to_float_minutes(sunset(d, CIVIL_ZENITH)),
        "tzeis5.88": lambda d: dt_to_float_minutes(sunset(d, 90 + 5.88)),
        "tzeis6.45": lambda d: dt_to_float_minutes(sunset(d, 90 + 6.45)),
        "tzeis7.12": lambda d: dt_to_float_minutes(sunset(d, 90 + 7.12)),
        "tzeis8.5": lambda d: dt_to_float_minutes(sunset(d, 90 + 8.5)),
        "tzeis+72": lambda d: dt_to_float_minutes(sunset(d, CIVIL_ZENITH)) + 72,
    }
    shema_all = []
    for sn, sf in day_starts.items():
        for en, ef in day_ends.items():
            def shema(d, sf=sf, ef=ef):
                a, b = sf(d), ef(d)
                return a + 3.0 * (b - a) / 12.0
            best_w = eval_range(obs["shema_wk"], shema) if obs["shema_wk"] else None
            best_s = eval_single(obs["shema_shab"] + obs["shema_day"], shema) if (obs["shema_shab"] or obs["shema_day"]) else None
            hw = best_w[2] if best_w else 0
            hs = best_s[1] if best_s else 0
            shema_all.append((f"{sn}->{en}", hw, hs, best_w, best_s))
    shema_all.sort(key=lambda x: -(x[1] + x[2]))
    for name, hw, hs, best_w, best_s in shema_all[:5]:
        nw = len(obs["shema_wk"])
        ns = len(obs["shema_shab"] + obs["shema_day"])
        line = f"### shema {name}: weekday {hw}/{nw}"
        if best_w:
            line += f" [day={best_w[0]},{best_w[1]}]"
        line += f", shabbos/day {hs}/{ns}"
        if best_s:
            line += f" [{best_s[0]}]"
        report.append((f"shema {name}", hw + hs, nw + ns, line))

    # --- plag: same grid, formula start + 10.75 sha'os
    plag_all = []
    for sn, sf in day_starts.items():
        for en, ef in day_ends.items():
            def plag(d, sf=sf, ef=ef):
                a, b = sf(d), ef(d)
                return a + 10.75 * (b - a) / 12.0
            if not obs["plag_fri"]:
                continue
            best = eval_single(obs["plag_fri"], plag)
            plag_all.append((f"{sn}->{en}", best[1], best[0], best[2]))
    plag_all.sort(key=lambda x: -x[1])
    for name, hits, rule, results in plag_all[:5]:
        report.append((f"plag {name}", hits, len(obs["plag_fri"]),
                       summarize(f"Plag {name}", len(obs["plag_fri"]), hits, rule, results)))

    # --- chatzot (halachic midnight): solar noon +/- 12h
    if obs["chatzot"]:
        def midnight(d):
            # chatzot halayla following evening of date d = solar noon + 12h (next civil day, minutes > 1440 wrap)
            noon = solar_noon_local(d, LAT, LON, TZ)
            return dt_to_float_minutes(noon) + 720 - 1440  # expressed as minutes past midnight next day
        best = eval_single(obs["chatzot"], midnight)
        report.append(("chatzot", best[1], len(obs["chatzot"]),
                       summarize("Chatzot halayla (solar noon+12h)", len(obs["chatzot"]), best[1], best[0], best[2])))

    print("\n" + "=" * 70 + "\nFIT REPORT (sorted by family, best variants)\n" + "=" * 70)
    for _, hits, n, text in report:
        print(text)
        print()


if __name__ == "__main__":
    main()
