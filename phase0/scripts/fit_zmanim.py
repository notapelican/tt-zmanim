#!/usr/bin/env python3
"""Fit candidate zmanim definitions against the fixture corpus.

For every zman family we grid-search (definition x day-selection x rounding x elevation)
and report the combinations that reproduce the most printed values exactly.
Includes the Baal HaTanya (Alter Rebbe) "netz amiti / shkia amitis" hypothesis:
sun's centre at 1.583 deg below the geometric horizon (zenith 91.583, no refraction).
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from solar import CIVIL_ZENITH, elevation_adjustment, sun_event_local, solar_noon_local

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "phase0" / "fixtures"
TZ = ZoneInfo("Australia/Sydney")
LAT, LON = -33.889, 151.260  # 1 Penkivil St, Bondi

AMITI = 91.583  # Baal HaTanya: centre of sun 1.583 deg below geometric horizon
ELEVATIONS = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0]


def parse_iso(s):
    return date.fromisoformat(s) if s else None


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def fmt(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def round_minutes(x: float, mode: str) -> int:
    if mode == "floor":
        return math.floor(x)
    if mode == "ceil":
        return math.ceil(x)
    return math.floor(x + 0.5)


@lru_cache(maxsize=200000)
def sun_min(d: date, zenith: float, rising: bool) -> float:
    """Minutes-past-local-midnight of the event (float, seconds precision)."""
    dt = sun_event_local(d, LAT, LON, TZ, zenith, rising)
    return dt.hour * 60 + dt.minute + dt.second / 60 + dt.microsecond / 6e7


def sunset_m(d, zenith=CIVIL_ZENITH):
    return sun_min(d, zenith, False)


def sunrise_m(d, zenith=CIVIL_ZENITH):
    return sun_min(d, zenith, True)


# ---------- observation collection ----------

def collect(fixture_paths):
    obs = defaultdict(list)
    for p in fixture_paths:
        fx = json.loads(p.read_text())
        for b in fx.get("blocks", []):
            if b.get("type") == "week":
                fri, shab = parse_iso(b.get("friday")), parse_iso(b.get("shabbos"))
                start = parse_iso(b.get("civil_start"))
                for e in b.get("entries", []):
                    lab = (e.get("label") or "").lower()
                    sec = (e.get("section") or "").lower()
                    t = to_minutes(e["time"])
                    src = f"{p.stem}:{b.get('parsha')}"
                    rec = {"printed": t, "src": src, "raw": e.get("raw", "")}
                    erev = "erev shabbos" in sec
                    dspec = (e.get("day_spec_raw") or "").lower()
                    ndays = 6 if "fri" in dspec else 5
                    weekdays = [start + timedelta(days=i) for i in range(ndays)] if start else None
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
                    elif "shema" in lab and t >= 720 and fri:
                        # "Kerias Shema (said from Tzeis Hachochavim) from 7:34pm" in the
                        # early-minyan section: a Friday-night tzeis observation
                        obs["tzeis_fri"].append({**rec, "date": fri})
                    elif "shema" in lab and weekdays and "shabbos" not in sec:
                        obs["shema_wk"].append({**rec, "dates": weekdays})
                    elif "shema" in lab and shab and "shabbos" in sec:
                        obs["shema_shab"].append({**rec, "date": shab})
                    elif "motzaei" in lab and shab:
                        obs["motzaei"].append({**rec, "date": shab})
                    elif e.get("kind") == "fast" and e.get("date"):
                        key = "fast_start" if "start" in lab else "fast_end"
                        obs[key].append({**rec, "date": parse_iso(e["date"])})
            elif b.get("type") == "day":
                d = parse_iso(b.get("date"))
                if not d:
                    continue
                for e in b.get("entries", []):
                    lab = (e.get("label") or "").lower()
                    t = to_minutes(e["time"])
                    src = f"{p.stem}:{(b.get('title_raw') or '')[:30]}"
                    rec = {"printed": t, "src": src, "date": d, "raw": e.get("raw", "")}
                    if e.get("kind") == "fast":
                        obs["fast_start" if ("start" in lab or "commence" in lab) else "fast_end"].append(rec)
                    elif "candle" in lab:
                        q = (e.get("qualifier") or "")
                        obs["candle_notbefore" if "not before" in q else "candle_day"].append(rec)
                    elif "alos" in lab or "dawn" in lab:
                        obs["alos"].append(rec)
                    elif "shkia" in lab:
                        obs["shkia_day"].append(rec)
                    elif "motzaei" in lab and ("maariv" in lab or "yom tov" in lab):
                        obs["motzaei_day"].append(rec)
                    elif "chatzot" in lab or "chatzos" in lab:
                        obs["chatzot"].append(rec)
                    elif "shema" in lab:
                        obs["shema_day"].append(rec)
    return obs


# ---------- evaluation ----------

ROUNDINGS = ("floor", "nearest", "ceil")
DAY_RULES = [("Sun", 0), ("Mon", 1), ("Tue", 2), ("Wed", 3), ("Thu", 4), ("Fri", 5),
             ("min", "min"), ("max", "max")]


def eval_single(observations, compute):
    best = None
    for r in ROUNDINGS:
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


def eval_range(observations, compute):
    best = None
    for rule_name, rule in DAY_RULES:
        for r in ROUNDINGS:
            hits, results = 0, []
            for o in observations:
                try:
                    dates = o["dates"]
                    if rule == "min":
                        calc = min(compute(d) for d in dates)
                    elif rule == "max":
                        calc = max(compute(d) for d in dates)
                    else:
                        if rule >= len(dates):
                            continue
                        calc = compute(dates[rule])
                except ValueError:
                    results.append((o, None, None))
                    continue
                got = round_minutes(calc, r)
                err = got - o["printed"]
                hits += err == 0
                results.append((o, got, err))
            if best is None or hits > best[2]:
                best = (f"day={rule_name}", r, hits, results)
    return best


def summarize(name, n, hits, rule, results, max_show=8):
    lines = [f"### {name}: {hits}/{n} exact  [{rule}]"]
    misses = [(o, got, err) for o, got, err in results if err not in (0, None)]
    for o, got, err in misses[:max_show]:
        lines.append(f"  miss {o['src']}: printed {fmt(o['printed'])} calc {fmt(got)} ({err:+d}m)")
    if len(misses) > max_show:
        lines.append(f"  ... {len(misses) - max_show} more misses")
    return "\n".join(lines)


# ---------- day-definition grids for shaos-zmanios zmanim ----------

def make_starts():
    starts = {"netz": lambda d: sunrise_m(d), "netz_amiti": lambda d: sunrise_m(d, AMITI)}
    for tenth in range(100, 221, 5):  # 10.0 .. 22.0 deg step 0.5
        deg = tenth / 10.0
        starts[f"alos{deg}"] = lambda d, z=90 + deg: sunrise_m(d, z)
    for mins in (72, 90, 96, 120):
        starts[f"netz-{mins}"] = lambda d, m=mins: sunrise_m(d) - m
        starts[f"amiti-{mins}"] = lambda d, m=mins: sunrise_m(d, AMITI) - m
    return starts


def make_ends():
    ends = {"shkia": lambda d: sunset_m(d), "shkia_amitis": lambda d: sunset_m(d, AMITI)}
    for tenth in range(10, 101, 5):  # 1.0 .. 10.0 deg step 0.5
        deg = tenth / 10.0
        ends[f"tzeis{deg}"] = lambda d, z=90 + deg: sunset_m(d, z)
    for mins in (24, 30, 36, 42, 72, 90, 96, 120):
        ends[f"shkia+{mins}"] = lambda d, m=mins: sunset_m(d) + m
        ends[f"amitis+{mins}"] = lambda d, m=mins: sunset_m(d, AMITI) + m
    return ends


def scan_shaos(obs_range, obs_single, fraction, tag, report, top_n=6):
    """fraction: 3/12 for sof zman shema, 10.75/12 for plag."""
    starts, ends = make_starts(), make_ends()
    scored = []
    for sn, sf in starts.items():
        for en, ef in ends.items():
            def zman(d, sf=sf, ef=ef):
                a, b = sf(d), ef(d)
                return a + fraction * (b - a)
            hw = hs = 0
            bw = bs = None
            if obs_range:
                bw = eval_range(obs_range, zman)
                hw = bw[2]
            if obs_single:
                bs = eval_single(obs_single, zman)
                hs = bs[1]
            scored.append((hw + hs, hw, hs, sn, en, bw, bs))
    scored.sort(key=lambda x: -x[0])
    for total, hw, hs, sn, en, bw, bs in scored[:top_n]:
        nw, ns = len(obs_range), len(obs_single)
        line = f"### {tag} {sn} -> {en}:"
        if bw:
            line += f" weekday {hw}/{nw} [{bw[0]},{bw[1]}]"
        if bs:
            line += f" single {hs}/{ns} [{bs[0]}]"
        report.append(line)
        if bs and hs < ns:
            misses = [(o, got, err) for o, got, err in bs[2] if err not in (0, None)]
            for o, got, err in misses[:4]:
                report.append(f"    miss(single) {o['src']}: printed {fmt(o['printed'])} calc {fmt(got)} ({err:+d}m)")
        if bw and hw < nw:
            misses = [(o, got, err) for o, got, err in bw[3] if err not in (0, None)]
            for o, got, err in misses[:4]:
                report.append(f"    miss(wk) {o['src']}: printed {fmt(o['printed'])} calc {fmt(got)} ({err:+d}m)")


# ---------- main ----------

def main():
    fixture_paths = sorted(FIXTURES.glob("*.json"))
    obs = collect(fixture_paths)
    print(f"fixtures: {len(fixture_paths)}")
    for k, v in sorted(obs.items()):
        print(f"  {k}: {len(v)}")
    print()
    report = []

    # Friday shkia & candle lighting: elevation grid
    for elev in ELEVATIONS:
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        b = eval_single(obs["shkia_fri"], lambda d, z=z: sunset_m(d, z))
        report.append(summarize(f"Friday shkia elev={elev}m", len(obs["shkia_fri"]), b[1], b[0], b[2]))
        for off in (18,):
            bc = eval_single(obs["candle_fri"], lambda d, z=z, off=off: sunset_m(d, z) - off)
            report.append(summarize(f"Candle=shkia-{off} elev={elev}m", len(obs["candle_fri"]), bc[1], bc[0], bc[2]))
    # amiti-based shkia, just in case
    b = eval_single(obs["shkia_fri"], lambda d: sunset_m(d, AMITI))
    report.append(summarize("Friday shkia = shkia_amitis(1.583)", len(obs["shkia_fri"]), b[1], b[0], b[2]))

    # weekday shkia
    for elev in (0.0, 15.0, 20.0):
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        b = eval_range(obs["shkia_wk"], lambda d, z=z: sunset_m(d, z))
        report.append(summarize(f"Weekday shkia elev={elev}m", len(obs["shkia_wk"]), b[2], f"{b[0]},{b[1]}", b[3]))

    # netz
    for elev in (0.0, 5.0, 10.0):
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        b = eval_range(obs["netz_wk"], lambda d, z=z: sunrise_m(d, z))
        report.append(summarize(f"Netz elev={elev}m", len(obs["netz_wk"]), b[2], f"{b[0]},{b[1]}", b[3]))
    b = eval_range(obs["netz_wk"], lambda d: sunrise_m(d, AMITI))
    report.append(summarize("Netz = netz_amiti(1.583)", len(obs["netz_wk"]), b[2], f"{b[0]},{b[1]}", b[3]))

    # tzeis families: degree scan (0.05 steps around the promising zone)
    def scan_deg(family, single, lo, hi, step, base_desc):
        out = []
        deg = lo
        while deg <= hi + 1e-9:
            z = 90.0 + deg
            if single:
                b = eval_single(obs[family], lambda d, z=z: sunset_m(d, z))
                out.append((deg, b[1], b[0], b[2]))
            else:
                b = eval_range(obs[family], lambda d, z=z: sunset_m(d, z))
                out.append((deg, b[2], f"{b[0]},{b[1]}", b[3]))
            deg = round(deg + step, 4)
        out.sort(key=lambda x: -x[1])
        for deg, hits, rule, results in out[:4]:
            report.append(summarize(f"{base_desc} @ {deg} deg", len(obs[family]), hits, rule, results))

    scan_deg("tzeis_fri", True, 5.5, 7.0, 0.05, "Friday tzeis")
    scan_deg("tzeis_wk", False, 5.5, 7.0, 0.05, "Weekday tzeis")
    scan_deg("motzaei", True, 8.0, 9.2, 0.05, "Motzaei Shabbos maariv")
    if obs["motzaei_day"]:
        scan_deg("motzaei_day", True, 8.0, 9.2, 0.05, "Motzaei YT maariv")
    if obs["fast_end"]:
        scan_deg("fast_end", True, 5.5, 7.0, 0.05, "Fast end")
    if obs["candle_notbefore"]:
        scan_deg("candle_notbefore", True, 8.0, 9.2, 0.05, "Candle 'not before' (2nd night)")

    # erev-YT candle lighting and day-block shkia (single dates)
    for elev in (0.0, 15.0):
        z = CIVIL_ZENITH + elevation_adjustment(elev)
        if obs["candle_day"]:
            b = eval_single(obs["candle_day"], lambda d, z=z: sunset_m(d, z) - 18)
            report.append(summarize(f"Erev-YT candle=shkia-18 elev={elev}m", len(obs["candle_day"]), b[1], b[0], b[2]))
        if obs["shkia_day"]:
            b = eval_single(obs["shkia_day"], lambda d, z=z: sunset_m(d, z))
            report.append(summarize(f"Day-block shkia elev={elev}m", len(obs["shkia_day"]), b[1], b[0], b[2]))

    # misheyakir
    out = []
    deg = 9.5
    while deg <= 11.5:
        z = 90.0 + deg
        b = eval_range(obs["mishyakir_wk"], lambda d, z=z: sunrise_m(d, z))
        out.append((deg, b[2], f"{b[0]},{b[1]}", b[3]))
        deg = round(deg + 0.05, 4)
    out.sort(key=lambda x: -x[1])
    for deg, hits, rule, results in out[:4]:
        report.append(summarize(f"Misheyakir @ {deg} deg", len(obs["mishyakir_wk"]), hits, rule, results))

    # alos: fast starts + explicit alos lines
    alos_obs = obs["fast_start"] + obs["alos"]
    if alos_obs:
        out = []
        deg = 15.0
        while deg <= 20.0:
            b = eval_single(alos_obs, lambda d, z=90 + deg: sunrise_m(d, z))
            out.append((f"{deg}deg", b[1], b[0], b[2]))
            deg = round(deg + 0.05, 4)
        for mins in (72, 90, 96, 120):
            b = eval_single(alos_obs, lambda d, m=mins: sunrise_m(d) - m)
            out.append((f"netz-{mins}", b[1], b[0], b[2]))
        out.sort(key=lambda x: -x[1])
        for name, hits, rule, results in out[:4]:
            report.append(summarize(f"Alos {name}", len(alos_obs), hits, rule, results))

    # sof zman shema (3/12 of day) and plag (10.75/12 of day)
    scan_shaos(obs["shema_wk"], obs["shema_shab"] + obs["shema_day"], 3.0 / 12.0, "SHEMA", report, top_n=8)
    scan_shaos([], obs["plag_fri"], 10.75 / 12.0, "PLAG", report, top_n=8)

    # chatzot halayla
    if obs["chatzot"]:
        def midnight(d):
            noon = solar_noon_local(d, LAT, LON, TZ)
            return noon.hour * 60 + noon.minute + noon.second / 60 + 720 - 1440
        b = eval_single(obs["chatzot"], midnight)
        report.append(summarize("Chatzot halayla (solar noon+12h)", len(obs["chatzot"]), b[1], b[0], b[2]))

    print("\n".join(report))


if __name__ == "__main__":
    main()
