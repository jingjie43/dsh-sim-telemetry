# -*- coding: utf-8 -*-
"""Spa-Francorchamps（trackId 10）19 弯校准：三份数据三取二。

背景：2026-11-03 发现 engineer.DEFAULT_LEN=5890（银石长度）被所有赛道共用，
Spa 7007 米的数据后段（Blanchimont/Bus Stop）被整段丢弃。已改成按数据里的
trackLen 检测（E.detect_track_len），本脚本直接受益。

官方 19 弯（F1 官网《How every corner at the Circuit de Spa-Francorchamps got its name》2026-07-15）：
  T1 La Source / T2-4 Le Raidillon de l'Eau Rouge / T5-6 Les Combes / T7 Malmedy /
  T8 Bruxelles / T9 Jacky Ickx Curve / T10-11 Pouhon / T12-13 Fagnes /
  T14 Campus / T15 Curve Paul Frere / T16-17 Blanchimont / T18-19 Bus Stop

做法：先定每组弯的区间（来自三份数据转角法稳定段），区间内找 n 个曲率峰当 apex，
三份数据三取二（差 ≤40 米）。

用法: python scripts/rebuild_spa.py
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
    "frames_20261103_142238.jsonl",
    "frames_20261103_143320.jsonl",
    "frames_20261103_144227.jsonl",
]

# (弯号, 官方名, 方向, 区间起点, 区间终点, 区间内弯数)
CORNERS = [
    (1,  "La Source",        "R", 330,   480,  1),
    (2,  "Eau Rouge",        "L", 1120,  1190, 1),
    (3,  "Eau Rouge",        "R", 1192,  1260, 1),
    (4,  "Raidillon",        "L", 1280,  1380, 1),
    (5,  "Les Combes",       "L", 2370,  2478, 1),
    (6,  "Les Combes",       "R", 2482,  2600, 1),
    (7,  "Malmedy",          "R", 2605,  2765, 1),
    (8,  "Bruxelles",        "R", 2955,  3205, 1),
    (9,  "Jacky Ickx Curve", "L", 3215,  3400, 1),
    (10, "Pouhon",           "L", 3755,  3990, 1),
    (11, "Pouhon",           "L", 3995,  4230, 1),
    (12, "Fagnes",           "R", 4425,  4612, 2),
    (13, "Fagnes",           "R", 4425,  4612, 0),  # 占位，12 拆 2 个
    (14, "Campus",           "L", 4875,  5150, 1),
    (15, "Curve Paul Frere", "R", 5155,  5400, 1),
    (16, "Blanchimont",      "L", 5790,  6055, 1),
    (17, "Blanchimont",      "L", 6060,  6300, 1),
    (18, "Bus Stop",         "R", 6700,  6798, 1),
    (19, "Bus Stop",         "L", 6802,  6895, 1),
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
    """在 [a,b] 里找 n 个 |κ| 局部峰（峰之间最小间隔 60 米），按距离排序。"""
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
        if all(abs(d - p[0]) > 60 for p in picked):
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
        print("载入:", ds, " 圈数 OK, 赛道长度 %.0f 米, trackId %s" % (total, sess.get("trackId")))

    print()
    print("Spa 19 弯 · 三份数据交叉定位")
    print(" 弯号  官方弯名          方向  " + "  ".join("数据%d" % (i + 1) for i in range(len(series_by_file)))
          + "   三取二  半径  apex速度")
    out = []
    detail = {}
    for no, name, dr, a, b, n in CORNERS:
        if n == 0:
            continue
        # 每份数据各找 n 个峰
        per_ds = {}
        for ds, (curv, v) in series_by_file.items():
            peaks = find_peaks(curv, a, b, n)
            per_ds[ds] = peaks
        cells = []
        apex_list = []
        for i in range(len(DATASETS)):
            ds = DATASETS[i]
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
        print("  %2d   %-16s %s   %-18s %s  %s  %s" % (
            no, name, dr, " | ".join(cells), "✓" if chosen else "?",
            ("%3.0f m" % r) if r else "-", ("%d" % av) if av else "-"))
        if n > 1:
            # 一个区间里有 n 个弯：把三取二后的峰值拆成 n 个条目
            picked = []
            for ds, (curv, v) in series_by_file.items():
                for p in (per_ds.get(ds) or []):
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
                # 兜底：用第一份数据的 n 个峰
                first = next(iter(series_by_file.values()), (None, None))
                pks = find_peaks(first[0], a, b, n) if first[0] else []
                groups = [[p[0]] for p in pks]
            for j, g in enumerate(groups[:n]):
                out.append({"no": no + j, "name": name, "dir": dr,
                            "entry_m": a, "exit_m": b,
                            "apex_m": round(sum(g) / len(g), 0), "radius_m": r})
        else:
            out.append({"no": no, "name": name, "dir": dr, "entry_m": a, "exit_m": b,
                        "apex_m": round(chosen, 0) if chosen else None, "radius_m": r})
        detail[no] = per_ds

    # Fagnes 特殊：12 区间 2 个峰，编号 12/13
    print()
    print("=" * 100)
    print("粘进 tracks.py 的 detected_corners：")
    print()
    for c in out:
        print('            {"no": %2d, "name": "%s", "entry_m": %4d, "apex_m": %s, "exit_m": %4d, "dir": "%s", "radius_m": %s},'
              % (c["no"], c["name"], c["entry_m"],
                 ("%.0f" % c["apex_m"]) if c["apex_m"] else "None",
                 c["exit_m"], c["dir"],
                 ("%.0f" % c["radius_m"]) if c["radius_m"] else "None"))


if __name__ == "__main__":
    main()
