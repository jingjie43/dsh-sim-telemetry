# -*- coding: utf-8 -*-
"""伊莫拉（Imola，trackId 27）19 弯三取二校准。

数据：
  frames_20261113_162600  L1 1:25.627 快
  frames_20261113_163404  L3 1:25.300 快
  frames_20261113_164430  3 圈全正常（1:22.457 最快）

官方弯名：Tamburello×2 / Villeneuve / Tosa / Piratella×2 / Acque Minerali×2 /
          Variante Alta×2 / Rivazza×2 / Turn 13-19
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
    "frames_20261113_162600.jsonl",
    "frames_20261113_163404.jsonl",
    "frames_20261113_164430.jsonl",
]

# (弯号, 名称, 方向, 区间起, 区间止)
CORNERS = [
    (1, "Tamburello",      "R", 780, 890),
    (2, "Tamburello",      "L", 880, 970),
    (3, "Villeneuve",      "R", 960, 1065),
    (4, "Tosa",            "L", 1070, 1215),
    (5, "Piratella",       "R", 1480, 1600),
    (6, "Piratella",       "L", 1600, 1755),
    (7, "Acque Minerali",  "R", 1835, 2045),
    (8, "Acque Minerali",  "L", 2275, 2395),
    (9, "Variante Alta",   "R", 2475, 2815),
    (10, "Variante Alta",  "L", 2885, 3275),
    (11, "Rivazza",        "L", 3500, 3600),
    (12, "Rivazza",        "R", 3595, 3705),
    (13, "Turn 13",        "L", 4090, 4245),
    (14, "Turn 14",        "R", 4295, 4445),
    (15, "Turn 15",        "R", 4440, 4585),
    (16, "Turn 16",        "L", 4575, 4630),
    (17, "Turn 17",        "R", 4760, 4845),
    (18, "Turn 18",        "L", 4835, 4880),
    (19, "Turn 19",        "R", 4870, 4912),
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


def find_peaks(curv, a, b, n=1):
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
        if all(abs(d - p[0]) > 30 for p in picked):
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
    print("伊莫拉 19 弯 · 三份数据交叉定位")
    print(" 弯号  名称              方向 " + "  ".join("数据%d" % (i + 1) for i in range(len(series_by_file))))
    out = []
    for no, name, dr, a, b in CORNERS:
        per_ds = {}
        for ds, (curv, v) in series_by_file.items():
            per_ds[ds] = find_peaks(curv, a, b, 1)
        cells, apex_list = [], []
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
                near = [y for y in dd if abs(y - x) <= 30]
                if best is None or len(near) > len(best):
                    best = near
            chosen = sum(best) / len(best) if best and len(best) >= 2 else dd[0]
        print("  %2d   %-16s %s   %-20s %s" % (no, name, dr, " | ".join(cells), "✓" if chosen else "?"))
        out.append({"no": no, "name": name, "dir": dr, "entry_m": a, "exit_m": b,
                    "apex_m": round(chosen) if chosen else None, "checked": bool(chosen)})
    print()
    print("=" * 100)
    print("粘进 tracks.py 的 detected_corners：")
    for c in out:
        print('            {"no": %2d, "name": "%-16s", "entry_m": %4d, "apex_m": %s, "exit_m": %4d, "dir": "%s"},'
              % (c["no"], c["name"], c["entry_m"],
                 ("%.0f" % c["apex_m"]) if c["apex_m"] else "None",
                 c["exit_m"], c["dir"]))
    ok = sum(1 for c in out if c["checked"])
    print()
    print("✓ 确认 %d / %d 弯" % (ok, len(out)))


if __name__ == "__main__":
    main()
