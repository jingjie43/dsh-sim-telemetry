# -*- coding: utf-8 -*-
"""核对 lapDistance 与「实际走过的距离」是否一致。

为什么要做这一步：蒙扎数据在 980~2145 米之间一个曲率峰都没有（应该有过 Curva Grande、
Roggia 这些弯），怀疑 lapDistance 在那一段跳变或与实际弧长脱节。
方法：用 Motion 的世界坐标 (x,z) 累加实际弧长，跟 LapData 的 lapDistance 对比。

用法: python scripts/check_distance.py [frames_xxx.jsonl]
"""
import bisect
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402

DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
path = sys.argv[1] if len(sys.argv) > 1 else max(
    glob.glob(os.path.join(DATA, "frames_*.jsonl")), key=os.path.getmtime)


def nearest_motion(streams, st):
    m = streams.get("motion") or {}
    keys = streams.setdefault("_mkeys", sorted(m.keys()))
    i = bisect.bisect_left(keys, round(st, 2))
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(keys):
            k = keys[j]
            if best is None or abs(k - st) < abs(best - st):
                best = k
    return m.get(best) if best is not None else None


frame, laps_pkts, sess, _ = L.load(path)
lap_objs = L.cut_laps(frame, laps_pkts)
streams = E.load_streams(path)
print("文件:", os.path.basename(path), "· 圈数:", len(lap_objs))
if not lap_objs:
    sys.exit(1)

for lap in lap_objs[:1]:
    print()
    print("== L%d（%s） lapDistance vs 实际弧长 ==" % (lap["n"], L.fmt(lap["lap_ms"])))
    rows = []
    prev = None
    arc = 0.0
    for f in lap["fr"]:
        st = f["st"]
        d = E.dist_at(streams, st)
        mo = nearest_motion(streams, st)
        if d is None or not mo:
            continue
        x, z = mo.get("x"), mo.get("z")
        if x is None or z is None:
            continue
        if prev is not None:
            arc += math.hypot(x - prev[0], z - prev[1])
        prev = (x, z)
        rows.append((st, d, arc))

    print("  采样点 %d" % len(rows))
    print("  lapDist   实际弧长   差(弧长-距离)   st")
    step = max(1, len(rows) // 24)
    for i in range(0, len(rows), step):
        st, d, arc = rows[i]
        print("  %7.0f   %8.1f   %+10.1f     %.2f" % (d, arc, arc - d, st))

    # 逐段检查：lapDistance 是否单调、有无跳跃
    jumps = []
    last_d = None
    for st, d, arc in rows:
        if last_d is not None:
            dd = d - last_d
            if abs(dd) > 60:          # 相邻帧距离跳 60 米以上（20Hz 下最多几米）
                jumps.append((st, last_d, d, dd))
        last_d = d
    print()
    if jumps:
        print("  ⚠️ lapDistance 跳变 %d 处：" % len(jumps))
        for st, a, b, dd in jumps[:10]:
            print("    st %.2f: %.1f → %.1f（跳 %+.1f 米）" % (st, a, b, dd))
    else:
        print("  ✅ lapDistance 连续，无跳变")

    # 总量对比
    if rows:
        print()
        print("  终点 lapDistance = %.1f 米，实际累计弧长 = %.1f 米（差 %+.1f 米）"
              % (rows[-1][1], rows[-1][2], rows[-1][2] - rows[-1][1]))
