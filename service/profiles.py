"""JSON <-> schedule-profile dataclass adapter.

The WordPress plugin stores schedule profiles / rules / notes as JSON and passes
edited ones back into ``engine.assemble.generate(profiles=..., notes=...)``. The
engine wants the frozen dataclasses in ``engine.rules``. This module converts
between the two, explicitly (not via ``asdict``) so that:

  - the ``timing`` union is discriminated by an explicit ``type`` field;
  - ``Condition`` recursion (``children``) is preserved;
  - containers round-trip back to **tuples**, matching the engine's frozen
    dataclasses, so ``profiles == from_json(to_json(profiles))`` holds exactly.

This is the highest-drift-risk code in the plugin; ``service/tests`` asserts the
identity above on ``DEFAULT_PROFILES``/``DEFAULT_NOTES`` and re-runs the schedule
regression through adapter-round-tripped profiles.
"""
from __future__ import annotations

from engine.rules import (
    Bound,
    Condition,
    FixedTime,
    NoteTemplate,
    ScheduleProfile,
    ScheduleRule,
    ZmanAnchored,
)

# --- timing (ZmanAnchored | FixedTime) --------------------------------------

def _timing_to_json(t: ZmanAnchored | FixedTime) -> dict:
    if isinstance(t, ZmanAnchored):
        return {
            "type": "zman_anchored",
            "anchor": t.anchor,
            "day": t.day,
            "offset_min": t.offset_min,
            "rounding": t.rounding,
            "grid": t.grid,
            "grid_rounding": t.grid_rounding,
        }
    if isinstance(t, FixedTime):
        return {"type": "fixed", "time": t.time}
    raise TypeError(f"unknown timing type: {type(t).__name__}")


def _timing_from_json(d: dict) -> ZmanAnchored | FixedTime:
    ty = d.get("type")
    if ty == "zman_anchored":
        return ZmanAnchored(
            anchor=d["anchor"],
            day=d["day"],
            offset_min=d.get("offset_min", 0),
            rounding=d.get("rounding", "floor"),
            grid=d.get("grid", 1),
            grid_rounding=d.get("grid_rounding", "nearest"),
        )
    if ty == "fixed":
        return FixedTime(time=d["time"])
    raise ValueError(f"unknown timing type: {ty!r}")


# --- Bound ------------------------------------------------------------------

def _bound_to_json(b: Bound | None) -> dict | None:
    if b is None:
        return None
    return {"anchor": b.anchor, "direction": b.direction, "day": b.day}


def _bound_from_json(d: dict | None) -> Bound | None:
    if d is None:
        return None
    return Bound(anchor=d["anchor"], direction=d["direction"], day=d.get("day", "same"))


# --- ScheduleRule -----------------------------------------------------------

def _rule_to_json(r: ScheduleRule) -> dict:
    return {
        "id": r.id,
        "section": r.section,
        "label": r.label,
        "timing": _timing_to_json(r.timing),
        "day_spec": r.day_spec,
        "qualifier": r.qualifier,
        "bound": _bound_to_json(r.bound),
        "when": r.when,
        "kind": r.kind,
    }


def _rule_from_json(d: dict) -> ScheduleRule:
    return ScheduleRule(
        id=d["id"],
        section=d["section"],
        label=d["label"],
        timing=_timing_from_json(d["timing"]),
        day_spec=d.get("day_spec"),
        qualifier=d.get("qualifier"),
        bound=_bound_from_json(d.get("bound")),
        when=d.get("when"),
        kind=d.get("kind", "minyan"),
    )


# --- Condition (recursive) --------------------------------------------------

def _condition_to_json(c: Condition) -> dict:
    return {
        "type": c.type,
        "start_md": c.start_md,
        "end_md": c.end_md,
        "zman": c.zman,
        "op": c.op,
        "time": c.time,
        "children": [_condition_to_json(ch) for ch in c.children],
    }


def _condition_from_json(d: dict) -> Condition:
    return Condition(
        type=d["type"],
        start_md=d.get("start_md"),
        end_md=d.get("end_md"),
        zman=d.get("zman"),
        op=d.get("op"),
        time=d.get("time"),
        children=tuple(_condition_from_json(ch) for ch in d.get("children", ())),
    )


# --- ScheduleProfile --------------------------------------------------------

def _profile_to_json(p: ScheduleProfile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "condition": _condition_to_json(p.condition),
        "rules": [_rule_to_json(r) for r in p.rules],
    }


def _profile_from_json(d: dict) -> ScheduleProfile:
    return ScheduleProfile(
        id=d["id"],
        name=d["name"],
        condition=_condition_from_json(d["condition"]),
        rules=tuple(_rule_from_json(r) for r in d["rules"]),
    )


# --- NoteTemplate -----------------------------------------------------------

def _note_to_json(n: NoteTemplate) -> dict:
    return {"id": n.id, "trigger": n.trigger, "text": n.text}


def _note_from_json(d: dict) -> NoteTemplate:
    return NoteTemplate(id=d["id"], trigger=d["trigger"], text=d["text"])


# --- public: collections ----------------------------------------------------

def profiles_to_json(profiles) -> list[dict]:
    return [_profile_to_json(p) for p in profiles]


def profiles_from_json(data: list[dict]) -> tuple[ScheduleProfile, ...]:
    return tuple(_profile_from_json(d) for d in data)


def notes_to_json(notes) -> list[dict]:
    return [_note_to_json(n) for n in notes]


def notes_from_json(data: list[dict]) -> tuple[NoteTemplate, ...]:
    return tuple(_note_from_json(d) for d in data)
