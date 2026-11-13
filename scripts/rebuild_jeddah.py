# -*- coding: utf-8 -*-
"""沙特吉达（Jeddah Corniche，trackId 29）27 弯三取二校准。

数据：
  frames_20261113_152919  4 圈（1:38.434 最快）
  frames_20261113_153826  3 圈（1:35.907 最快）
  frames_20261113_154356  3 圈（1:36.911 最快）

官方弯名：吉达只有 Turn 1-27 编号（无传统弯名）。
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
    "frames_20261113_152919.jsonl",
    "frames_20261113_153826.jsonl",
    "frames_20261113_154356.jsonl",
]

# (弯号, 名称, 方向, 区间起, 区间止)
CORNERS = [
    (1, "Turn 1", "R", 440, 580),
    (2, "Turn 2", "L", 560, 700),
    (3, "Turn 3", "R", 650, 800),
    (4, "Turn 4", "L", 960, 1080),
    (5, "Turn 5", "R", 1080, 1270),
    (6, "Turn 6", "L", 1250, 1470),
    (7, "Turn 7", "R", 1450, 1720),
    (8, "Turn 8", "L", 1700, 1840),
    (9, "Turn 9", "R", 2300, 2500),
    (10, "Turn 10", "L", 2500, 2690),
    (11, "Turn 11", "R", 2680, 2970),
    (12, "Turn 12", "L", 2960, 3060),
    (13, "Turn 13", "R", 3060, 3190),
    (14, "Turn 14", "L", 3180, 3470),
    (15, "Turn 15", "R", 3580, 3700),
    (16, "Turn 16", "L", 3700, 3890),
    (17, "Turn 17", "R", 3940, 4090),
    (18, "Turn 18", "L", 4260, 4400),
    (19, "Turn 19", "R", 4390, 4650),
    (20, "Turn 20", "L", 4720, 4960),
    (21, "Turn 21", "R", 4960, 5210),
    (22, "Turn 22", "L", 5210, 5400),
    (23, "Turn 23", "R", 5400, 5510),
    (24, "Turn 24", "L", 5490, 5620),
    (25, "Turn 25", "R", 5600, 5700),
    (26, "Turn 26", "L", 5690, 5800),
    (27, "Turn 27", "R", 5790, 5960),
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
    print("吉达 27 弯 · 三份数据交叉定位")
    print(" 弯号  名称     方向 " + "  ".join("数据%d" % (i + 1) for i in range(len(series_by_file))))
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
                near = [y for y in dd if abs(y - x) <= 35]
                if best is None or len(near) > len(best):
                    best = near
            chosen = sum(best) / len(best) if best and len(best) >= 2 else dd[0]
        print("  %2d   %-8s %s   %-20s %s" % (no, name, dr, " | ".join(cells), "✓" if chosen else "?"))
        out.append({"no": no, "name": name, "dir": dr, "entry_m": a, "exit_m": b,
                    "apex_m": round(chosen) if chosen else None, "checked": bool(chosen)})
    print()
    print("=" * 96)
    print("粘进 tracks.py 的 detected_corners：")
    for c in out:
        print('            {"no": %2d, "name": "%-8s", "entry_m": %4d, "apex_m": %s, "exit_m": %4d, "dir": "%s"},'
              % (c["no"], c["name"], c["entry_m"],
                 ("%.0f" % c["apex_m"]) if c["apex_m"] else "None",
                 c["exit_m"], c["dir"]))
    ok = sum(1 for c in out if c["checked"])
    print()
    print("✓ 确认 %d / %d 弯" % (ok, len(out)))


if __name__ == "__main__":
    main()
