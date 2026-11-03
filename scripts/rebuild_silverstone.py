# -*- coding: utf-8 -*-
"""重建银石（Silverstone）18 弯校准：区间 + 曲率峰定位 apex + 三份数据三取二。

为什么不用旧的 detect_corners：它靠「取曲率最强的 18 个峰」凑官方弯数，
数据稍有不同就多选/少选一个峰，导致后面的弯整体错位（2026-10-28 实测：
两份银石数据的第 6 弯差 740 米、第 8 弯差 870 米）。

新做法：
  1. 用转角法（corners_by_angle）在三份数据上找稳定的「弯段」，确定每个官方弯的区间
  2. 区间内用平均曲率找 apex（三份数据分别算 → 三取二，差 ≤40 米算一致）
  3. 方向按官方布局（数据的方向判断在高速大半径弯上不可靠）

用法: python scripts/rebuild_silverstone.py
"""
import glob
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402

DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
GRID = E.GRID
TOTAL = E.DEFAULT_LEN

DATASETS = [
    "frames_20261026_122836.jsonl",
    "frames_20261026_131106.jsonl",
    "frames_20261026_143303.jsonl",
]

# 官方 18 弯（F1 官方《How every Silverstone corner got its name》2026-07-01）
# 区间来自三份数据转角法稳定的弯段；The Loop/Aintree 与 Club 1/2 是相邻连续弯，按段内拆分
CORNERS = [
    (1, "Abbey",       "R", 345, 550),
    (2, "Farm",        "L", 580, 760),
    (3, "Village",     "R", 835, 990),
    (4, "The Loop",    "L", 1000, 1250),
    (5, "Aintree",     "L", 1250, 1350),
    (6, "Brooklands",  "R", 1885, 2090),
    (7, "Luffield",    "R", 2105, 2345),
    (8, "Woodcote",    "R", 2470, 2700),
    (9, "Copse",       "R", 3015, 3240),
    (10, "Maggotts",   "R", 3550, 3635),
    (11, "Maggotts",   "R", 3685, 3810),
    (12, "Becketts",   "L", 3830, 3960),
    (13, "Becketts",   "L", 3970, 4150),
    (14, "Chapel",     "R", 4170, 4285),
    (15, "Stowe",      "R", 4950, 5220),
    (16, "Vale",       "R", 5480, 5575),
    (17, "Club",       "R", 5585, 5730),
    (18, "Club",       "R", 5730, 5880),
]


def load_series(path):
    frames, laps_pkts, sess, _ = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(path)
    series = [E.resample(E.lap_series(l, streams), total=TOTAL) for l in lap_objs]
    if not series:
        return None, None, sess
    curv = E.average_curvature(series) if len(series) > 1 else E.curvature(E._yaw_series(series[0]))
    v = E.average_field(series, "v")
    return curv, v, sess


def find_apex(curv, v, a, b):
    """区间 [a,b] 内 |κ| 最大的点 = apex；返 (apex_m, apex_v, radius)。"""
    ia = max(0, int(a / GRID))
    ib = min(len(curv) - 1, int(b / GRID))
    best = None
    for i in range(ia, ib + 1):
        k = curv[i] if i < len(curv) else None
        if k is None:
            continue
        if best is None or abs(k) > abs(best[1]):
            best = (i, k)
    if best is None:
        return None, None, None
    i, k = best
    d = i * GRID
    vv = v[i] if v and i < len(v) else None
    r = round(1 / abs(k)) if abs(k) > 1e-9 else None
    return d, vv, r


def main():
    rows = {}
    for ds in DATASETS:
        p = os.path.join(DATA, ds)
        if not os.path.exists(p):
            print("跳过（不存在）:", ds)
            continue
        curv, v, sess = load_series(p)
        if curv is None:
            print("跳过（没完整圈）:", ds)
            continue
        for no, name, dr, a, b in CORNERS:
            apex, av, r = find_apex(curv, v, a, b)
            rows.setdefault(no, {})[ds] = (apex, av, r)

    print("银石 18 弯 · 三份数据交叉定位（区间内曲率峰）")
    print()
    print(" 弯号  官方弯名      方向   " + "  ".join("数据%d" % (i + 1) for i in range(len(rows.get(1, {}))))
          + "   三取二  半径  apex速度")
    out = []
    for no, name, dr, a, b in CORNERS:
        vals = rows.get(no, {})
        apexes = [(ds, t[0]) for ds, t in vals.items() if t[0] is not None]
        # 三取二：找被至少两份数据支持的 apexe（差 ≤40 米）
        chosen = None
        if apexes:
            dd = sorted(x[1] for x in apexes)
            best = None
            for i in range(len(dd)):
                near = [x for x in dd if abs(x - dd[i]) <= 40]
                if best is None or len(near) > len(best):
                    best = near
            if best and len(best) >= 2:
                chosen = sum(best) / len(best)
            else:
                chosen = dd[0]
        r = None
        av = None
        for ds, t in vals.items():
            if t[2] and r is None:
                r = t[2]
            if t[1] and av is None:
                av = t[1]
        cells = []
        for i in range(len(DATASETS) if rows else 0):
            ds = DATASETS[i] if i < len(DATASETS) else None
            t = vals.get(ds) if ds else None
            cells.append("%6.0f" % t[0] if t and t[0] is not None else "     -")
        ok = "✓" if chosen else "?"
        print("  %2d   %-12s  %s   %s   %s   %s   %s"
              % (no, name, dr, "  ".join(cells), ok,
                 ("%.0f m" % r) if r else "-", ("%d" % av) if av else "-"))
        out.append({"no": no, "name": name, "dir": dr, "entry_m": a, "exit_m": b,
                    "apex_m": round(chosen, 0) if chosen else None,
                    "radius_m": r, "apex_v": av})

    print()
    print("=" * 90)
    print("粘进 tracks.py 的 detected_corners（区间 entry/exit 用上面定义的，apex 用三取二结果）：")
    print()
    for c in out:
        print('            {"no": %2d, "name": "%-10s", "entry_m": %4d, "apex_m": %s, "exit_m": %4d, "dir": "%s", "radius_m": %s},'
              % (c["no"], c["name"], c["entry_m"],
                 ("%.0f" % c["apex_m"]) if c["apex_m"] else "None",
                 c["exit_m"], c["dir"],
                 ("%.0f" % c["radius_m"]) if c["radius_m"] else "None"))


if __name__ == "__main__":
    main()
