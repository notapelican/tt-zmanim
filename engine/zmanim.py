"""Zmanim engine for TTCC (Bondi/Sydney), per the Alter Rebbe (Baal HaTanya)'s shitta.

Constants below are taken verbatim from KosherJava's ComplexZmanimCalendar (the
reference implementation chabad.org's zmanim are built on) and confirmed against
27 historical TTCC sheets in phase0/ (see phase0/PHASE0-FINDINGS.md):

  netz amiti / shkia amitis  : sun's centre 1.583 deg below geometric horizon
  alos (dawn)                : sunrise offset by 16.9 deg  (getAlosBaalHatanya)
  tzeis (weekday/fast end)   : sunset offset by 6.0 deg    (getTzaisBaalHatanya)
  tzeis Geonim 8.5 deg       : motzaei Shabbos/YT, "not before" 2nd-night candles
  misheyakir                 : sunrise offset by 10.2 deg  (getMisheyakir10Point2Degrees)
  candle lighting            : sea-level shkia minus 18 minutes
  sof zman shema / plag      : 3 / 10.75 shaos zmanios of the netz-amiti->shkia-amitis day

Location defaults to chabad.org's Sydney coordinate as identified in Phase 0
(NOT the shul's literal Bondi address - the historical sheets were computed
for a generic "Sydney" point). TODO(phase1): confirm exact coordinate/elevation
against chabad.org directly once reachable; current value is fit-derived.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .solar import CIVIL_ZENITH, elevation_adjustment, sun_event_local, solar_noon_local

SYDNEY_LAT = -33.88
SYDNEY_LON = 151.22
SYDNEY_ELEVATION_M = 10.0  # fit-derived; confirm against chabad.org (see module docstring)
SYDNEY_TZ = ZoneInfo("Australia/Sydney")

ZENITH_AMITI = 90.0 + 1.583
ZENITH_ALOS_BAAL_HATANYA = 90.0 + 16.9
ZENITH_TZEIS_BAAL_HATANYA = 90.0 + 6.0
ZENITH_TZEIS_GEONIM_8_5 = 90.0 + 8.4  # 78/79 fit vs. 8.5 (see phase0/PHASE0-FINDINGS.md); name kept for KosherJava cross-reference
ZENITH_MISHEYAKIR_10_2 = 90.0 + 10.2

CANDLE_LIGHTING_OFFSET_MIN = 18


def _round(x: float, mode: str) -> datetime:
    """Round a fractional-minute datetime down to the minute (mode='floor'/'ceil'/'nearest').
    x is a datetime with sub-minute precision; truncate/round its seconds."""
    if mode == "floor":
        return x.replace(second=0, microsecond=0)
    if mode == "ceil":
        base = x.replace(second=0, microsecond=0)
        return base if x == base else base + timedelta(minutes=1)
    # nearest
    base = x.replace(second=0, microsecond=0)
    return base + timedelta(minutes=1) if x.second >= 30 else base


@dataclass(frozen=True)
class Location:
    lat: float = SYDNEY_LAT
    lon: float = SYDNEY_LON
    elevation_m: float = SYDNEY_ELEVATION_M
    tz: ZoneInfo = SYDNEY_TZ


class ZmanimEngine:
    """All methods return a rounded local datetime. `d` is the civil date the
    zman's day begins on (i.e. for tzeis/candle lighting on a Friday, pass that
    Friday's date)."""

    def __init__(self, location: Location = Location()):
        self.loc = location

    def _sunrise_zenith(self, d: date, zenith: float) -> datetime:
        return sun_event_local(d, self.loc.lat, self.loc.lon, self.loc.tz, zenith, rising=True)

    def _sunset_zenith(self, d: date, zenith: float) -> datetime:
        return sun_event_local(d, self.loc.lat, self.loc.lon, self.loc.tz, zenith, rising=False)

    def _civil_zenith(self) -> float:
        return CIVIL_ZENITH + elevation_adjustment(self.loc.elevation_m)

    # --- sea-level-adjusted standard sunrise/sunset (weekly "Netz"/"Shkia" lines) ---
    def netz(self, d: date, rounding: str = "nearest") -> datetime:
        return _round(self._sunrise_zenith(d, self._civil_zenith()), rounding)

    def shkia(self, d: date, rounding: str = "nearest") -> datetime:
        return _round(self._sunset_zenith(d, self._civil_zenith()), rounding)

    # --- Baal HaTanya netz amiti / shkia amitis (1.583 deg, no elevation) ---
    def netz_amiti(self, d: date) -> datetime:
        return self._sunrise_zenith(d, ZENITH_AMITI)

    def shkia_amitis(self, d: date) -> datetime:
        return self._sunset_zenith(d, ZENITH_AMITI)

    # --- degree-based zmanim ---
    def alos(self, d: date, rounding: str = "nearest") -> datetime:
        return _round(self._sunrise_zenith(d, ZENITH_ALOS_BAAL_HATANYA), rounding)

    def misheyakir(self, d: date, rounding: str = "nearest") -> datetime:
        return _round(self._sunrise_zenith(d, ZENITH_MISHEYAKIR_10_2), rounding)

    def tzeis(self, d: date, rounding: str = "ceil") -> datetime:
        """Weekday tzeis / minor-fast end. Default rounds UP (never end a fast early)."""
        return _round(self._sunset_zenith(d, ZENITH_TZEIS_BAAL_HATANYA), rounding)

    def tzeis_shabbos(self, d: date, rounding: str = "ceil") -> datetime:
        """Motzaei Shabbos/Yom Tov Maariv, and 'not before' 2nd-night candle lighting.
        Default rounds UP (never end Shabbos/YT early)."""
        return _round(self._sunset_zenith(d, ZENITH_TZEIS_GEONIM_8_5), rounding)

    def candle_lighting(self, d: date, offset_min: int = CANDLE_LIGHTING_OFFSET_MIN,
                        rounding: str = "floor") -> datetime:
        """Erev Shabbos / erev-YT candle lighting. Default rounds DOWN (never light late).
        Subtracts the offset from the unrounded shkia so we round exactly once."""
        raw_shkia = self._sunset_zenith(d, self._civil_zenith())
        return _round(raw_shkia - timedelta(minutes=offset_min), rounding)

    # --- shaos zmaniyos of the Baal HaTanya day (netz amiti -> shkia amitis) ---
    def _shaah_zmanis_baal_hatanya(self, d: date) -> timedelta:
        return (self.shkia_amitis(d) - self.netz_amiti(d)) / 12

    def sof_zman_shema(self, d: date, rounding: str = "floor") -> datetime:
        return _round(self.netz_amiti(d) + 3 * self._shaah_zmanis_baal_hatanya(d), rounding)

    def sof_zman_tfila(self, d: date, rounding: str = "floor") -> datetime:
        return _round(self.netz_amiti(d) + 4 * self._shaah_zmanis_baal_hatanya(d), rounding)

    def plag_hamincha(self, d: date, rounding: str = "ceil") -> datetime:
        return _round(self.netz_amiti(d) + 10.75 * self._shaah_zmanis_baal_hatanya(d), rounding)

    def chatzos(self, d: date, rounding: str = "nearest") -> datetime:
        """Halachic midnight (start of the night following civil date d)."""
        noon = solar_noon_local(d, self.loc.lat, self.loc.lon, self.loc.tz)
        return _round(noon + timedelta(hours=12), rounding)
