"""NOAA solar position calculator (Meeus-based), matching the algorithm used by
KosherJava/PhpZmanim's NOAACalculator. Computes sunrise/sunset for an arbitrary
solar zenith angle, returned as timezone-aware local datetimes with second precision.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

GEOMETRIC_ZENITH = 90.0
# 16' solar radius + 34' refraction, per NOAA "official" sunrise/sunset
CIVIL_ZENITH = 90.0 + 50.0 / 60.0
EARTH_RADIUS_M = 6356900.0


def elevation_adjustment(elevation_m: float) -> float:
    """Extra zenith degrees from observer elevation (KosherJava formula)."""
    if elevation_m <= 0:
        return 0.0
    return math.degrees(math.acos(EARTH_RADIUS_M / (EARTH_RADIUS_M + elevation_m)))


def _julian_day(d: date) -> float:
    y, m = d.year, d.month
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d.day + b - 1524.5


def _solar_geometry(t: float):
    """Return (declination_deg, eq_of_time_minutes) for julian centuries t."""
    l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mrad = math.radians(m)
    c = (
        math.sin(mrad) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * mrad) * (0.019993 - 0.000101 * t)
        + math.sin(3 * mrad) * 0.000289
    )
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    epsr = math.radians(eps)
    decl = math.degrees(math.asin(math.sin(epsr) * math.sin(math.radians(lam))))
    y = math.tan(epsr / 2.0) ** 2
    l0r = math.radians(l0)
    eot = 4.0 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mrad)
        + 4 * e * y * math.sin(mrad) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mrad)
    )
    return decl, eot


def _hour_angle(lat: float, decl: float, zenith: float) -> float:
    latr, declr = math.radians(lat), math.radians(decl)
    cos_ha = (
        math.cos(math.radians(zenith)) / (math.cos(latr) * math.cos(declr))
        - math.tan(latr) * math.tan(declr)
    )
    if cos_ha < -1.0 or cos_ha > 1.0:
        raise ValueError("sun never reaches this zenith on this date/latitude")
    return math.degrees(math.acos(cos_ha))


def sun_event_utc_minutes(d: date, lat: float, lon: float, zenith: float, rising: bool) -> float:
    """Minutes after 00:00 UTC of the rise/set event, iterated for accuracy."""
    jd = _julian_day(d)
    # first pass: geometry at local solar noon
    t = (jd - 2451545.0) / 36525.0
    minutes = 720.0 - 4.0 * lon  # rough noon UTC
    for _ in range(3):
        t_event = (jd + minutes / 1440.0 - 2451545.0) / 36525.0
        decl, eot = _solar_geometry(t_event)
        ha = _hour_angle(lat, decl, zenith)
        noon = 720.0 - 4.0 * lon - eot
        minutes = noon - 4.0 * ha if rising else noon + 4.0 * ha
    return minutes


def sun_event_local(
    d: date, lat: float, lon: float, tz: ZoneInfo, zenith: float, rising: bool
) -> datetime:
    minutes = sun_event_utc_minutes(d, lat, lon, zenith, rising)
    utc_dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return utc_dt.astimezone(tz)


def solar_noon_local(d: date, lat: float, lon: float, tz: ZoneInfo) -> datetime:
    jd = _julian_day(d)
    minutes = 720.0 - 4.0 * lon
    for _ in range(2):
        t = (jd + minutes / 1440.0 - 2451545.0) / 36525.0
        _, eot = _solar_geometry(t)
        minutes = 720.0 - 4.0 * lon - eot
    utc_dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return utc_dt.astimezone(tz)
