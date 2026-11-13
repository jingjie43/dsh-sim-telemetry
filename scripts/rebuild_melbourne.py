# -*- coding: utf-8 -*-
"""澳大利亚（Albert Park，trackId 0）14 弯三取二校准。

数据：
  frames_20261113_133103  4 圈（L1 1:30.560 快）
  frames_20261113_134234  3 圈（L3 1:30.372 快）
  frames_20261113_134927  3 圈（1:25.387 最快，全快圈）← 最佳

官方弯名：Albert Park 2022 改版后 14 弯，官方只有 Turn 1-14 编号。
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
    "frames_20261113_133103.jsonl",
    "frames_20261113_134234.jsonl",
    "frames_20261113_134927.jsonl",
]

# (弯号, 名称, 方向, 区间起, 区间止, 区间内弯数)
CORNERS = [
    (1,  "Turn 1",  "R", 250, 440, 1),
    (2,  "Turn 2",  "L", 440, 600, 1),
    (3,  "Turn 3",  "R", 1000, 1180, 1),
    (4,  "Turn 4",  "L", 1180, 1340, 1),
    (5,  "Turn 5",  "R", 1370, 1560, 1),
    (6,  "Turn 6",  "L", 1800, 1960, 1),
    (7,  "Turn 7",  "R", 1955, 2050, 1),
    (8,  "Turn 8",  "L", 2380, 2520, 1),
    (9,  "Turn 9",  "R", 2800, 3070, 1),
    (10, "Turn 10", "L", 3250, 3390, 1),
    (11, "Turn 11", "R", 3385, 3530, 1),
    (12, "Turn 12", "L", 3700, 3840, 1),
    (13, "Turn 13", "R", 4070, 4230, 1),
    (14, "Turn 14", "L", 4330, 4550, 1),
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
    print("澳大利亚（Albert Park）14 弯 · 三份数据交叉定位")
    print(" 弯号  名称     方向 " + "  ".join("数据%d" % (i + 1) for i in range(len(series_by_file))))
    out = []
    for no, name, dr, a, b, n in CORNERS:
        per_ds = {}
        for ds, (curv, v) in series_by_file.items():
            per_ds[ds] = find_peaks(curv, a, b, n)
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
                near = [y for y in dd if abs(y - x) <= 40]
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
