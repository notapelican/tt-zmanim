"""Schedule-rules engine for TTCC sheets (warplan module 3).

The shul's minyan-time policies as editable data. Every davening line is one of:
  - zman-anchored : offset from a halachic time, with explicit rounding and the
                    halachic bound the line must respect (editor warns, never
                    blocks, when a manual edit crosses it);
  - fixed clock   : e.g. "Shacharis Mon-Fri 6:15 & 7:30";
  - manual override: typed on a given Timesheet; always wins over the rule.

Rules are grouped into ScheduleProfiles with activation conditions (date range,
DST state, or a zman condition such as "Friday plag >= 17:50"), so the *set* of
minyanim can differ by season, not just the times.

Rule constants below were recovered from the 27-sheet fixture corpus by
phase0/scripts/fit_rules.py and are regression-tested by engine/validate_rules.py;
the triage of what fits exactly vs. what the shul overrides per sheet is in
phase3/PHASE3-FINDINGS.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from .zmanim import ZmanimEngine

# Section keys (renderer maps these to the printed headings; see RENDERER-CONTRACT.md)
WEEKDAY = "weekday_davening"
EREV_SHABBOS = "erev_shabbos_davening"
EREV_SHABBOS_EARLY = "erev_shabbos_early_minyan"
SHABBOS_DAY = "shabbos_day"


def _fmt(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def _parse_hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _grid_round(dt: datetime, grid: int, mode: str) -> datetime:
    """Round a minute-precision datetime onto a `grid`-minute grid."""
    if grid <= 1:
        return dt
    total = dt.hour * 60 + dt.minute
    if mode == "floor":
        snapped = total // grid * grid
    elif mode == "ceil":
        snapped = -(-total // grid) * grid
    else:  # nearest
        snapped = int(round(total / grid)) * grid
    return dt.replace(hour=0, minute=0) + timedelta(minutes=snapped)


@dataclass(frozen=True)
class WeekContext:
    """Everything a rule may need about the week being generated.
    `weekdays` are the Sun-Thurs dates a ranged weekday line covers (yom tov
    days already excluded by the caller); `friday`/`shabbos` may be None for a
    partial week."""
    sunday: date
    friday: date | None
    shabbos: date | None
    weekdays: tuple[date, ...]
    mevorchim: bool = False
    engine: ZmanimEngine = field(default_factory=ZmanimEngine, compare=False)

    def zman(self, anchor: str, d: date, rounding: str | None = None) -> datetime:
        fn = getattr(self.engine, anchor)
        return fn(d, rounding=rounding) if rounding else fn(d)


# --- timing specs ---------------------------------------------------------

@dataclass(frozen=True)
class ZmanAnchored:
    """time = round_grid( zman(anchor, day) + offset_min )."""
    anchor: str                    # method name on ZmanimEngine: shkia, tzeis,
                                   # tzeis_shabbos, plag_hamincha, candle_lighting...
    day: str                       # 'friday' | 'shabbos' | 'earliest' | 'latest'
                                   # (earliest/latest of ctx.weekdays)
    offset_min: int = 0
    rounding: str = "floor"        # rounding applied to the anchor zman itself
    grid: int = 1                  # snap final time onto an n-minute grid
    grid_rounding: str = "nearest"

    def resolve(self, ctx: WeekContext) -> tuple[datetime, date] | None:
        if self.day == "friday":
            if ctx.friday is None:
                return None
            days = [ctx.friday]
        elif self.day == "shabbos":
            if ctx.shabbos is None:
                return None
            days = [ctx.shabbos]
        else:
            days = list(ctx.weekdays)
            if not days:
                return None
        # earliest/latest by TIME OF DAY across the covered days: a ranged
        # line prints one clock time valid for the whole range (the safe
        # extreme), not the chronologically first/last moment.
        pick = min if self.day == "earliest" else max
        dt, line_date = pick(
            ((ctx.zman(self.anchor, d, self.rounding), d) for d in days),
            key=lambda pair: pair[0].time())
        dt += timedelta(minutes=self.offset_min)
        return _grid_round(dt, self.grid, self.grid_rounding), line_date


@dataclass(frozen=True)
class FixedTime:
    time: str                      # "HH:MM"

    def resolve(self, ctx: WeekContext) -> tuple[datetime, date] | None:
        d = ctx.sunday
        t = _parse_hm(self.time)
        return datetime(d.year, d.month, d.day, t.hour, t.minute), d


@dataclass(frozen=True)
class Bound:
    """Halachic bound carried on a line so a later editor can warn (not block)
    when a manual edit crosses it. `direction` says which side is permitted:
    'not_before' means edited time must be >= the bound zman; 'not_after' <=."""
    anchor: str
    direction: str                 # 'not_before' | 'not_after'
    day: str = "same"              # 'same' = the date the line resolved to

    def resolve(self, ctx: WeekContext, line_date: date) -> dict:
        rounding = "ceil" if self.direction == "not_before" else "floor"
        dt = ctx.zman(self.anchor, line_date, rounding)
        return {"zman": self.anchor, "direction": self.direction,
                "date": line_date.isoformat(), "time": _fmt(dt)}


# --- rules and profiles ---------------------------------------------------

@dataclass(frozen=True)
class ScheduleRule:
    """One davening line. `when` optionally gates the line on week state
    ('mevorchim' / 'not_mevorchim'). `day_spec` is the printed day qualifier
    for ranged weekday lines ('Sun.' / 'Mon.-Fri.' / 'Sun.-Thurs.'); the
    assembler adjusts it when yom tov truncates the week."""
    id: str
    section: str
    label: str
    timing: ZmanAnchored | FixedTime
    day_spec: str | None = None
    qualifier: str | None = None   # 'not before' | 'not after approx' | ...
    bound: Bound | None = None
    when: str | None = None
    kind: str = "minyan"

    def applies(self, ctx: WeekContext) -> bool:
        if self.when == "mevorchim":
            return ctx.mevorchim
        if self.when == "not_mevorchim":
            return not ctx.mevorchim
        return True

    def resolve(self, ctx: WeekContext) -> dict | None:
        if not self.applies(ctx):
            return None
        resolved = self.timing.resolve(ctx)
        if resolved is None:
            return None
        dt, line_date = resolved
        line = {
            "rule_id": self.id,
            "section": self.section,
            "label": self.label,
            "kind": self.kind,
            "day_spec": self.day_spec,
            "date": line_date.isoformat() if isinstance(self.timing, ZmanAnchored)
                    and self.timing.day in ("friday", "shabbos") else None,
            "time": _fmt(dt),
            "qualifier": self.qualifier,
            "source": "rule",
        }
        if self.bound:
            line["bound"] = self.bound.resolve(ctx, line_date)
        return line


@dataclass(frozen=True)
class Condition:
    """Profile activation condition.
    type: 'always' | 'date_range' | 'dst' | 'zman' | 'all_of' | 'any_of'
      date_range: recurring month-day window, inclusive ('12-14'..'01-27'
                  wraps the year end)
      dst:        daylight saving in effect on the week's Friday (or Sunday
                  when there is no Friday)
      zman:       compare a Friday zman to a clock time, e.g. plag >= 17:50
    """
    type: str
    start_md: str | None = None
    end_md: str | None = None
    zman: str | None = None
    op: str | None = None
    time: str | None = None
    children: tuple["Condition", ...] = ()

    def active(self, ctx: WeekContext) -> bool:
        if self.type == "always":
            return True
        if self.type == "all_of":
            return all(c.active(ctx) for c in self.children)
        if self.type == "any_of":
            return any(c.active(ctx) for c in self.children)
        probe = ctx.friday or ctx.sunday
        if self.type == "date_range":
            md = f"{probe.month:02d}-{probe.day:02d}"
            if self.start_md <= self.end_md:
                return self.start_md <= md <= self.end_md
            return md >= self.start_md or md <= self.end_md
        if self.type == "dst":
            probe_dt = datetime(probe.year, probe.month, probe.day, 12,
                                tzinfo=ctx.engine.loc.tz)
            return probe_dt.dst() != timedelta(0)
        if self.type == "zman":
            if ctx.friday is None:
                return False
            z = ctx.zman(self.zman, ctx.friday)
            zt, ref = _fmt(z), self.time
            return {"<=": zt <= ref, ">=": zt >= ref,
                    "<": zt < ref, ">": zt > ref}[self.op]
        raise ValueError(f"unknown condition type {self.type}")


@dataclass(frozen=True)
class ScheduleProfile:
    """A named set of minyanim active under a condition. Profiles are
    additive: every active profile contributes its rules."""
    id: str
    name: str
    condition: Condition
    rules: tuple[ScheduleRule, ...]

    def active(self, ctx: WeekContext) -> bool:
        return self.condition.active(ctx)


@dataclass(frozen=True)
class NoteTemplate:
    """Reusable sheet note. trigger: 'always' | 'dst' | 'standard_time' |
    'dst_change_week' — evaluated by the assembler, which may also substitute
    {placeholders} from week context."""
    id: str
    trigger: str
    text: str


@dataclass
class Timesheet:
    """A generated sheet: the date range, the generated blocks (plain data,
    see RENDERER-CONTRACT.md) and the per-line manual overrides that were
    applied. Overrides always win over rules and are keyed by the line's
    rule_id (or a fresh id for added lines):
        {"<rule_id>": {"time": "19:15"}}         edit a time
        {"<rule_id>": {"suppress": true}}        drop the line/section
        {"add:<id>": {full line dict}}           insert a manual line
    Keys may be block-scoped as "week:<sunday ISO>|<rule_id>" or
    "day:<date ISO>|<rule_id>" so an edit applies to one block of a
    multi-week/yom-tov sheet (see assemble.scope_overrides). Bare keys
    apply to every block (legacy sheets).
    """
    start: date
    end: date
    format: str = "weekly"
    blocks: list[dict] = field(default_factory=list)
    overrides: dict[str, dict] = field(default_factory=dict)
    export_history: list[dict] = field(default_factory=list)


def apply_overrides(lines: list[dict], overrides: dict[str, dict]) -> list[dict]:
    """Manual overrides always win over rules. Suppressed lines are removed,
    edited lines keep their bound (so an editor can still warn), added lines
    are appended with source='manual'."""
    out = []
    for line in lines:
        ov = overrides.get(line.get("rule_id", ""))
        if ov:
            if ov.get("suppress"):
                continue
            line = {**line, **{k: v for k, v in ov.items() if k != "suppress"},
                    "source": "override"}
        out.append(line)
    for key, ov in overrides.items():
        if key.startswith("add:"):
            out.append({"rule_id": key, "source": "manual", "kind": "minyan", **ov})
    return out


# --- the recovered TTCC rule set (fit: phase0/scripts/fit_rules.py) --------

_BASE_RULES = (
    # Weekday Shacharis: fixed sets. Sunday also applies on NSW public
    # holidays (the assembler swaps the day_spec).
    ScheduleRule("shacharis_sun_1", WEEKDAY, "Shacharis", FixedTime("08:00"), day_spec="Sun."),
    ScheduleRule("shacharis_sun_2", WEEKDAY, "Shacharis", FixedTime("09:15"), day_spec="Sun."),
    ScheduleRule("shacharis_wk_1", WEEKDAY, "Shacharis", FixedTime("06:15"), day_spec="Mon.–Fri."),
    ScheduleRule("shacharis_wk_2", WEEKDAY, "Shacharis", FixedTime("07:30"), day_spec="Mon.–Fri."),
    # Weekday Mincha: 10 min before the earliest shkia of the covered days
    # (so it is >=10 min before shkia on every covered day).
    ScheduleRule("weekday_mincha", WEEKDAY, "Mincha",
                 ZmanAnchored("shkia", "earliest", -10, rounding="nearest"),
                 day_spec="Sun.–Thurs.",
                 bound=Bound("shkia", "not_after")),
    # Weekday Maariv: at the latest weekday tzeis of the covered days.
    ScheduleRule("weekday_maariv", WEEKDAY, "Maariv",
                 ZmanAnchored("tzeis", "latest", 0, rounding="ceil"),
                 day_spec="Sun.–Thurs.",
                 bound=Bound("tzeis", "not_before")),

    # Erev Shabbos: Mincha 8 min after candle lighting; Kabbolas Shabbos 10
    # min before Friday tzeis, so the Maariv that follows lands at tzeis.
    ScheduleRule("es_mincha", EREV_SHABBOS, "Mincha",
                 ZmanAnchored("candle_lighting", "friday", +8, rounding="nearest"),
                 bound=Bound("shkia", "not_after")),
    ScheduleRule("es_kabbolas_shabbos", EREV_SHABBOS, "Kabbolas Shabbos followed by Maariv",
                 ZmanAnchored("tzeis", "friday", -10, rounding="ceil"),
                 bound=Bound("candle_lighting", "not_before")),

    # Shabbos morning: Mevorchim -> Tehillim 8:15 + Shacharis 10:10;
    # otherwise Chassidus 9:15 + Shacharis 10:00.
    ScheduleRule("shab_tehillim", SHABBOS_DAY, "Tehillim", FixedTime("08:15"),
                 when="mevorchim"),
    ScheduleRule("shab_shacharis_mev", SHABBOS_DAY,
                 "Shacharis (Kiddush / farbrengen after Musaf)", FixedTime("10:10"),
                 when="mevorchim"),
    ScheduleRule("shab_chassidus", SHABBOS_DAY, "Chassidus", FixedTime("09:15"),
                 when="not_mevorchim"),
    ScheduleRule("shab_shacharis", SHABBOS_DAY, "Shacharis (followed by Musaf)",
                 FixedTime("10:00"), when="not_mevorchim"),
    # Shabbos Mincha: shkia - 18 snapped to the nearest 5-minute mark. The
    # assembler appends ", Pirkei Avos N" / ", Seder Nigunim" decorations.
    ScheduleRule("shab_mincha", SHABBOS_DAY, "Mincha",
                 ZmanAnchored("shkia", "shabbos", -18, rounding="nearest",
                              grid=5, grid_rounding="nearest"),
                 bound=Bound("shkia", "not_after")),
    # Motzaei Shabbos Maariv: at tzeis 8.5 deg as displayed by chabad.org (nearest).
    ScheduleRule("motzaei_maariv", SHABBOS_DAY, "Motzaei Shabbos, Maariv",
                 ZmanAnchored("tzeis_shabbos", "shabbos", 0, rounding="nearest"),
                 bound=Bound("tzeis_shabbos", "not_before")),
)

# Early Erev Shabbos minyan + Shabbos-afternoon halacha shiur: run while
# Friday plag is late enough (>= 17:50 across the corpus; all such weeks are
# DST). The shul sometimes defers the season start a week after Tishrei —
# that is a per-sheet suppression, not a rule (see PHASE3-FINDINGS).
_EARLY_ES_RULES = (
    ScheduleRule("early_es_mincha", EREV_SHABBOS_EARLY,
                 "Mincha (must be completely finished before Plag Hamincha)",
                 ZmanAnchored("plag_hamincha", "friday", -20, rounding="ceil"),
                 bound=Bound("plag_hamincha", "not_after")),
    ScheduleRule("early_es_candles_from", EREV_SHABBOS_EARLY, "Candle lighting",
                 ZmanAnchored("plag_hamincha", "friday", 0, rounding="ceil"),
                 qualifier="not before", kind="zman",
                 bound=Bound("plag_hamincha", "not_before")),
    ScheduleRule("early_es_candles_to", EREV_SHABBOS_EARLY, "Candle lighting",
                 ZmanAnchored("plag_hamincha", "friday", +10, rounding="ceil"),
                 qualifier="not after approx", kind="zman"),
    ScheduleRule("early_es_ks", EREV_SHABBOS_EARLY,
                 "Kabbolas Shabbos (followed by Maariv)",
                 ZmanAnchored("plag_hamincha", "friday", 0, rounding="ceil"),
                 bound=Bound("plag_hamincha", "not_before")),
    ScheduleRule("early_es_kiddush_before", EREV_SHABBOS_EARLY, "Start Kiddush & meal",
                 ZmanAnchored("tzeis", "friday", -30, rounding="ceil"),
                 qualifier="before", kind="zman"),
    ScheduleRule("early_es_kiddush_after", EREV_SHABBOS_EARLY, "Start Kiddush & meal",
                 ZmanAnchored("tzeis", "friday", 0, rounding="ceil"),
                 qualifier="or after", kind="zman"),
    ScheduleRule("early_es_shema", EREV_SHABBOS_EARLY,
                 "Kerias Shema (said from Tzeis Hachochavim)",
                 ZmanAnchored("tzeis", "friday", 0, rounding="ceil"),
                 qualifier="from", kind="zman"),
    ScheduleRule("early_es_kezayis", EREV_SHABBOS_EARLY,
                 "Eat another kezayis bread after Tzeis Hachochavim",
                 ZmanAnchored("tzeis", "friday", 0, rounding="ceil"),
                 qualifier="after", kind="zman"),
)

# Shabbos-afternoon halacha shiur, 30 min before Shabbos Mincha (-48 snapped
# to the same 5-minute grid == Shabbos Mincha - 30). Runs through the DST
# season — a longer window than the early-ES-minyan plag condition (the
# corpus prints it on late-March Shabbosos after the early minyan has
# stopped for the year).
_HALACHA_SHIUR_RULES = (
    ScheduleRule("shab_halacha_shiur", SHABBOS_DAY,
                 "Halacha shiur, from the Shulchan Aruch Harav",
                 ZmanAnchored("shkia", "shabbos", -48, rounding="nearest",
                              grid=5, grid_rounding="nearest")),
)

# Summer-holiday extras (school holidays, roughly mid-Dec..late Jan; the
# range is operator-adjusted each year and lines are frequently overridden).
_SUMMER_HOLIDAY_RULES = (
    ScheduleRule("holiday_early_mincha", WEEKDAY, "Mincha", FixedTime("14:00"),
                 day_spec="Sun.–Thurs."),
    ScheduleRule("holiday_late_maariv", WEEKDAY, "Maariv", FixedTime("21:00"),
                 day_spec="Sun.–Thurs."),
)

DEFAULT_PROFILES = (
    ScheduleProfile("base", "Year-round schedule", Condition("always"), _BASE_RULES),
    ScheduleProfile("early_erev_shabbos", "Early Erev Shabbos minyan season",
                    Condition("zman", zman="plag_hamincha", op=">=", time="17:50"),
                    _EARLY_ES_RULES),
    ScheduleProfile("halacha_shiur_season", "Shabbos halacha shiur (DST season)",
                    Condition("dst"), _HALACHA_SHIUR_RULES),
    ScheduleProfile("summer_holidays", "Summer school-holiday extras",
                    Condition("date_range", start_md="12-14", end_md="01-27"),
                    _SUMMER_HOLIDAY_RULES),
)

DEFAULT_NOTES = (
    NoteTemplate("kiddush_window_dst", "dst",
                 "It is customary to not make Kiddush on Friday nights between "
                 "6:55pm and 7:55pm Daylight Saving Time (per the Mogen Avrohom; "
                 "Alter Rebbe's Shulchan Aruch O.C. 271)."),
    NoteTemplate("kiddush_window_est", "standard_time",
                 "It is customary to not make Kiddush on Friday nights between "
                 "5:55pm and 6:55pm (per the Mogen Avrohom; Alter Rebbe's "
                 "Shulchan Aruch O.C. 271)."),
    NoteTemplate("dst_change", "dst_change_week",
                 "Note: clocks change on {dst_date} — Daylight Saving "
                 "{dst_direction}. All times printed are clock times for "
                 "the day they refer to."),
)


def active_profiles(ctx: WeekContext,
                    profiles: tuple[ScheduleProfile, ...] = DEFAULT_PROFILES
                    ) -> list[ScheduleProfile]:
    return [p for p in profiles if p.active(ctx)]


def davening_lines(ctx: WeekContext,
                   profiles: tuple[ScheduleProfile, ...] = DEFAULT_PROFILES,
                   overrides: dict[str, dict] | None = None) -> list[dict]:
    """Resolve every active profile's rules for the week and apply manual
    overrides (which always win). Returns plain line dicts; ordering within a
    section follows rule declaration order, profiles in declaration order."""
    lines = []
    for p in active_profiles(ctx, profiles):
        for rule in p.rules:
            line = rule.resolve(ctx)
            if line is not None:
                line["profile_id"] = p.id
                lines.append(line)
    return apply_overrides(lines, overrides or {})
