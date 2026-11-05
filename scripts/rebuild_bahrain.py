# -*- coding: utf-8 -*-
"""巴林（Bahrain International Circuit，trackId 3）15 弯校准：三份数据三取二。

官方弯名：巴林没有传统弯名，F1 官方就是 Turn 1 ~ Turn 15。
布局：右-左-右-左（T1-T4）、右-左-右-左-右（T5-T9）、左-右-左（T10-T12）、
右-左-右（T13-T15）——具体以实跑数据为准。

数据：
  frames_20261105_164654  2 圈（快圈 1:43.414）
  frames_20261105_170036  3 圈（快圈 1:39.352，另两圈慢）
  frames_20261105_171819  3 圈（1:38.941 / 1:44.832 / 1:36.799，全正常）← 最佳

用法: python scripts/rebuild_bahrain.py
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
    "frames_20261105_164654.jsonl",
    "frames_20261105_170036.jsonl",
    "frames_20261105_171819.jsonl",
]

# (弯号, 名称, 方向, 区间起点, 区间终点, 区间内弯数)
CORNERS = [
    (1,  "Turn 1",  "R", 680,  800,  2),   # T1 右 + T2 左（连续）
    (3,  "Turn 3",  "R", 800,  915,  1),
    (4,  "Turn 4",  "L", 940,  1070, 1),
    (5,  "Turn 5",  "L", 1470, 1670, 2),   # T5 + T6
    (7,  "Turn 7",  "R", 1690, 1830, 1),
    (8,  "Turn 8",  "L", 1835, 1980, 1),
    (9,  "Turn 9",  "R", 1985, 2160, 1),
    (10, "Turn 10", "L", 2180, 2400, 1),
    (11, "Turn 11", "R", 2540, 2820, 2),   # T11 + T12
    (13, "Turn 13", "R", 3380, 3700, 1),
    (14, "Turn 14", "L", 3705, 4260, 1),
    (15, "Turn 15", "L", 4860, 5100, 1),
]


def load_series(path):
    frames, laps_pkts, sess, _ = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(path)
    total = E.detect_track_len(laps_pkts, sess)
    series = [E.resample(E.lap_series(l, streams), total=total) for l in lap_objs]
    if not series:
        return None, None, sess, total
    curv = E.average_curvature(series) if len(series) > 1 else E.curvature(E._yaw_series(series[0]))
    v = E.average_field(series, "v")
    return curv, v, sess, total


def find_peaks(curv, a, b, n, grid=GRID):
    ia, ib = max(0, int(a / grid)), min(len(curv) - 1, int(b / grid))
    cand = []
    for i in range(ia + 1, ib):
        k = curv[i]
        if k is None:
            continue
        left = abs(curv[i - 1]) if curv[i - 1] is not None else 0
        right = abs(curv[i + 1]) if i + 1 < len(curv) and curv[i + 1] is not None else 0
        if abs(k) >= left and abs(k) >= right:
            cand.append((i * grid, abs(k)))
    cand.sort(key=lambda x: -x[1])
    picked = []
    for d, k in cand:
        if all(abs(d - p[0]) > 45 for p in picked):
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
        curv, v, sess, total = load_series(p)
        if curv is None:
            print("跳过（没完整圈）:", ds)
            continue
        series_by_file[ds] = (curv, v)
        print("载入:", ds, " 赛道长度 %.0f 米, trackId %s" % (total, sess.get("trackId")))

    print()
    print("巴林 15 弯 · 三份数据交叉定位")
    print(" 弯号  名称      方向  " + "  ".join("数据%d" % (i + 1) for i in range(len(series_by_file)))
          + "   三取二  半径  apex速度")
    out = []
    for no, name, dr, a, b, n in CORNERS:
        per_ds = {}
        for ds, (curv, v) in series_by_file.items():
            per_ds[ds] = find_peaks(curv, a, b, n)
        cells = []
        apex_list = []
        for i, ds in enumerate(DATASETS):
            peaks = per_ds.get(ds)
            if peaks:
                cells.append(" ".join("%.0f" % p[0] for p in peaks))
                for p in peaks:
                    apex_list.append(p[0])
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
            if best and len(best) >= 2:
                chosen = sum(best) / len(best)
            else:
                chosen = dd[0]
        r = None
        av = None
        for ds, (curv, v) in series_by_file.items():
            peaks = per_ds.get(ds) or []
            if peaks:
                d, k = peaks[0]
                i = int(d / GRID)
                if k > 1e-9:
                    r = round(1 / k)
                if v and i < len(v) and v[i]:
                    av = v[i]
                break
        print("  %2d   %-8s %s   %-20s %s  %3.0f m  %s" % (
            no, name, dr, " | ".join(cells), "✓" if chosen else "?",
            r or 0, av or "-"))
        if n > 1:
            picked = []
            for ds in series_by_file:
                for p in per_ds.get(ds) or []:
                    picked.append(p[0])
            picked.sort()
            groups = []
            for x in picked:
                if groups and abs(x - groups[-1][-1]) <= 40:
                    groups[-1].append(x)
                else:
                    groups.append([x])
            groups = [g for g in groups if len(g) >= 2]
            if len(groups) < n:
                first = next(iter(series_by_file.values()))[0]
                pks = find_peaks(first, a, b, n)
                groups = [[p[0]] for p in pks]
            for j, g in enumerate(groups[:n]):
                out.append({"no": no + j, "name": "Turn %d" % (no + j), "dir": dr,
                            "entry_m": a, "exit_m": b,
                            "apex_m": round(sum(g) / len(g)), "radius_m": r})
        else:
            out.append({"no": no, "name": name, "dir": dr, "entry_m": a, "exit_m": b,
                        "apex_m": round(chosen) if chosen else None, "radius_m": r})

    print()
    print("=" * 96)
    print("粘进 tracks.py 的 detected_corners：")
    for c in out:
        print('            {"no": %2d, "name": "%s", "entry_m": %4d, "apex_m": %s, "exit_m": %4d, "dir": "%s", "radius_m": %s},'
              % (c["no"], c["name"], c["entry_m"],
                 ("%.0f" % c["apex_m"]) if c["apex_m"] else "None",
                 c["exit_m"], c["dir"],
                 ("%.0f" % c["radius_m"]) if c["radius_m"] else "None"))


if __name__ == "__main__":
    main()
