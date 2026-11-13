# -*- coding: utf-8 -*-
"""摩纳哥（Circuit de Monaco，trackId 5）19 弯三取二校准。

数据：
  frames_20261105_174656  4 圈（1:28.3 最快）
  frames_20261107_162059  4 圈（1:17.489 最快）
  frames_20261107_162850  3 圈（1:17.477 最快）

官方弯名（F1《How every Monaco corner got its name》）：
  T1 Sainte Devote / T2 Beau Rivage / T3 Massenet / T4 Casino Square /
  T5 Mirabeau Superior / T6 Hairpin / T7 Mirabeau Inferior / T8 Portier /
  T9 The Tunnel / T10-11 Nouvelle Chicane / T12 Tabac / T13-16 Swimming Pool /
  T17 Turn 17 / T18 La Rascasse / T19 Antony Noghes
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402

DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
GRID = E.GRID

DATASETS = [
    "frames_20261105_174656.jsonl",
    "frames_20261107_162059.jsonl",
    "frames_20261107_162850.jsonl",
]

# (弯号, 名称, 方向, 区间起, 区间止, 区间内弯数)
CORNERS = [
    (1,  "Sainte Devote",        "R", 140, 300, 1),
    (2,  "Beau Rivage",          "L", 300, 500, 1),
    (3,  "Massenet",             "L", 520, 660, 1),
    (4,  "Casino Square",        "R", 660, 870, 1),
    (5,  "Mirabeau Superior",    "R", 870, 1085, 1),
    (6,  "Hairpin",              "L", 1085, 1250, 1),
    (7,  "Mirabeau Inferior",    "R", 1250, 1330, 1),
    (8,  "Portier",              "R", 1330, 1520, 1),
    (9,  "The Tunnel",           "R", 1550, 1830, 1),
    (10, "Nouvelle Chicane",     "R", 2040, 2160, 1),
    (11, "Nouvelle Chicane",     "L", 2160, 2230, 1),
    (12, "Tabac",                "R", 2330, 2580, 1),
    (13, "Swimming Pool",        "R", 2580, 2660, 1),
    (14, "Swimming Pool",        "L", 2660, 2740, 1),
    (15, "Swimming Pool",        "R", 2740, 2820, 1),
    (16, "Swimming Pool",        "L", 2820, 2900, 1),
    (17, "Turn 17",              "R", 2900, 2950, 1),
    (18, "La Rascasse",          "L", 2950, 3070, 1),
    (19, "Antony Noghes",        "R", 3070, 3200, 1),
]


def load_series(path):
    frames, laps_pkts, sess, _ = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(path)
    total = E.detect_track_len(laps_pkts, sess)
    series = [E.resample(E.lap_series(l, streams), total=total) for l in lap_objs]
    if not series:
        return None, None
    curv = E.average_curvature(series) if len(series) > 1 else E.curvature(E._yaw_series(series[0]))
    v = E.average_field(series, "v")
    return curv, v


def find_peaks(curv, a, b, n):
    ia, ib = max(0, int(a / GRID)), min(len(curv) - 1, int(b / GRID))
    cand = []
    for i in range(ia + 1, ib):
        k = curv[i]
        if k is None:
            continue
        left = abs(curv[i - 1]) if curv[i - 1] is not None else 0
        right = abs(curv[i + 1]) if i + 1 < len(curv) and curv[i + 1] is not None else 0
        if abs(k) >= left and abs(k) >= right:
            cand.append((i * GRID, abs(k)))
    cand.sort(key=lambda x: -x[1])
    picked = []
    for d, k in cand:
        if all(abs(d - p[0]) > 40 for p in picked):
            picked.append((d, k))
        if len(picked) >= n:
            break
    picked.sort()
    return picked


def main():
    series_by_file = {}
    for ds in DATASETS:
        p = os.path.join(DATA, ds)
        if not os.path.exists(p):
            print("跳过（不存在）:", ds)
            continue
        curv, v = load_series(p)
        if curv is None:
            print("跳过（没完整圈）:", ds)
            continue
        series_by_file[ds] = (curv, v)
        print("载入:", ds)

    print()
    print("摩纳哥 19 弯 · 三份数据交叉定位")
    hdr = " 弯号  名称             方向 " + "  ".join("数据%d" % (i + 1) for i in range(len(series_by_file)))
    print(hdr)
    out = []
    for no, name, dr, a, b, n in CORNERS:
        per_ds = {}
        for ds, (curv, v) in series_by_file.items():
            per_ds[ds] = find_peaks(curv, a, b, n)
        cells = []
        apex_list = []
        for ds in DATASETS:
            peaks = per_ds.get(ds)
            if peaks:
                cells.append(" ".join("%.0f" % p[0] for p in peaks))
                apex_list.extend(p[0] for p in peaks)
            else:
                cells.append("-")
        chosen = None
        if apex_list:
            dd = sorted(apex_list)
            best = None
            for x in dd:
                near = [y for y in dd if abs(y - x) <= 40]
                if best is None or len(near) > len(best):
                    best = near
            chosen = sum(best) / len(best) if best and len(best) >= 2 else dd[0]
        print("  %2d   %-16s %s   %-22s %s" % (no, name, dr, " | ".join(cells), "✓" if chosen else "?"))
        out.append({"no": no, "name": name, "dir": dr, "entry_m": a, "exit_m": b,
                    "apex_m": round(chosen) if chosen else None, "checked": bool(chosen)})

    print()
    print("=" * 100)
    print("粘进 tracks.py 的 detected_corners：")
    for c in out:
        print('            {"no": %2d, "name": "%-18s", "entry_m": %4d, "apex_m": %s, "exit_m": %4d, "dir": "%s"},'
              % (c["no"], c["name"], c["entry_m"],
                 ("%.0f" % c["apex_m"]) if c["apex_m"] else "None",
                 c["exit_m"], c["dir"]))
    ok = sum(1 for c in out if c["checked"])
    print()
    print("✓ 确认 %d / %d 弯" % (ok, len(out)))


if __name__ == "__main__":
    main()
