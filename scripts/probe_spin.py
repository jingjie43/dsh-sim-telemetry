# -*- coding: utf-8 -*-
"""找甩尾/spin 的另一种指纹：方向盘从大角度快速反打 + 车速同时掉。"""
import glob
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402
import tracks as T    # noqa: E402

GRID = E.GRID
TOTAL = E.DEFAULT_LEN
DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
path = sys.argv[1] if len(sys.argv) > 1 else max(
    glob.glob(os.path.join(DATA, "frames_*.jsonl")), key=os.path.getmtime)

frames, laps_pkts, sess, _ = L.load(path)
lap_objs = L.cut_laps(frames, laps_pkts)
streams = E.load_streams(path)
track = T.get_by_track_id(sess.get("trackId", -1))
series = [E.resample(E.lap_series(l, streams), total=TOTAL) for l in lap_objs]


def label(d):
    c, _ph = T.corner_at(track, d) if track else (None, None)
    return f"第{c['no']}弯" if c else ""


print("① 方向盘反打（0.5 秒内 steer 变化 > 0.8）")
for li, lap in enumerate(lap_objs):
    rs = series[li]
    hits = []
    for i in range(10, len(rs["steer"]) - 10):
        a, b = rs["steer"][i - 10], rs["steer"][i + 10]
        if a is None or b is None:
            continue
        if abs(b - a) > 0.8:
            hits.append((i * GRID, a, b))
    merged = []
    for d, a, b in hits:
        if merged and d - merged[-1][0] < 60:
            continue
        merged.append((d, a, b))
    if not merged:
        print(f"  L{lap['n']}  无")
    for d, a, b in merged:
        print(f"  L{lap['n']}  {d:5.0f} m  steer {a:+.2f} → {b:+.2f}  {label(d)}")

print()
print("② 出界记录：L3 5710-5830 米期间的 gx 符号（+右/-左）与油门")
for li, lap in enumerate(lap_objs):
    if lap["n"] != 3:
        continue
    rs = series[li]
    row = []
    for d in range(5700, 5841, 10):
        i = int(d / GRID)
        g = rs["gx"][i]
        row.append(f"{d}:{'R' if g and g > 0 else 'L' if g and g < 0 else '0'}{abs(g or 0):.1f}/t{rs['thr'][i]}")
    print("  " + "  ".join(row))

print()
print("③ 三圈 第 17-18 弯（5680-5890）速度并排")
for li, lap in enumerate(lap_objs):
    rs = series[li]
    row = []
    for d in range(5680, 5891, 30):
        i = min(int(d / GRID), len(rs["v"]) - 1)
        row.append(f"{d}:{rs['v'][i]}")
    print(f"  L{lap['n']}  " + "  ".join(row))
