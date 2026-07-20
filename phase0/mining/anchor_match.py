"""Stage 2: for every mined item with a civil date + time, compute candidate
zmanim anchors (offset in minutes to each zman that day) so rule inference can
cluster by anchor instead of by wall-clock time. Reads findings/batch*.json,
writes findings/anchored.json."""
from __future__ import annotations
import json, re, sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/home/user/tt-zmanim")
from engine.zmanim import ZmanimEngine

MINE = Path(__file__).parent
eng = ZmanimEngine()

TIME_RE = re.compile(r"(\d{1,2})[:.](\d{2})\s*(am|pm)", re.I)


def parse_times(s):
    out = []
    for h, m, ap in TIME_RE.findall(s or ""):
        h, m = int(h), int(m)
        if ap.lower() == "pm" and h != 12:
            h += 12
        if ap.lower() == "am" and h == 12:
            h = 0
        out.append((h, m))
    return out


def zman_table(d: date):
    t = {}
    # eng.chatzos is halachic MIDNIGHT (noon + 12h); derive noon / mincha gedola.
    for name, fn in [
        ("alos", lambda: eng.alos(d, "nearest")),
        ("misheyakir", lambda: eng.misheyakir(d, "nearest")),
        ("netz", lambda: eng.netz(d, "nearest")),
        ("sof_shema", lambda: eng.sof_zman_shema(d, "nearest")),
        ("sof_tfila", lambda: eng.sof_zman_tfila(d, "nearest")),
        ("solar_noon", lambda: eng.chatzos(d, "nearest") - timedelta(hours=12)),
        ("mincha_gedola", lambda: eng.chatzos(d, "nearest") - timedelta(hours=11, minutes=30)),
        ("plag", lambda: eng.plag_hamincha(d, "nearest")),
        ("candles", lambda: eng.candle_lighting(d)),
        ("shkia", lambda: eng.shkia(d, "nearest")),
        ("tzeis", lambda: eng.tzeis(d, "nearest")),
        ("tzeis_shabbos", lambda: eng.tzeis_shabbos(d, "nearest")),
        ("chatzos_layla", lambda: eng.chatzos(d, "nearest")),
    ]:
        try:
            v = fn()
        except Exception:
            v = None
        if v is not None:
            t[name] = v
    return t


def main():
    items = []
    for f in sorted((MINE / "findings").glob("batch*.json")):
        data = json.loads(f.read_text())
        items.extend(data.get("items", []))
    out = []
    for it in items:
        rec = dict(it)
        d = it.get("civil_date")
        times = parse_times(it.get("time") or "")
        if d and times:
            try:
                dd = date.fromisoformat(d)
            except ValueError:
                out.append(rec); continue
            zt = zman_table(dd)
            anchors = []
            for (h, m) in times:
                cands = []
                for name, z in zt.items():
                    lt = z.astimezone(z.tzinfo)
                    off = (h * 60 + m) - (lt.hour * 60 + lt.minute)
                    if abs(off) <= 90:
                        cands.append({"zman": name, "zman_time": lt.strftime("%H:%M"),
                                      "offset_min": off})
                cands.sort(key=lambda c: abs(c["offset_min"]))
                anchors.append({"printed": f"{h:02d}:{m:02d}", "candidates": cands[:4]})
            rec["anchors"] = anchors
        out.append(rec)
    (MINE / "findings" / "anchored.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"anchored {len(out)} items -> findings/anchored.json")


if __name__ == "__main__":
    main()
