# -*- coding: utf-8 -*-
"""逐圈细节探针：最低速度点 / 最大横向 G / yaw 变化最快处 / 指定区间的逐米时间线。"""
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

frames, laps_pkts, sess, flashbacks = L.load(path)
lap_objs = L.cut_laps(frames, laps_pkts)
streams = E.load_streams(path)
track = T.get_by_track_id(sess.get("trackId", -1))
series = [E.resample(E.lap_series(l, streams), total=TOTAL) for l in lap_objs]


def label(d):
    if not track:
        return ""
    c, ph = T.corner_at(track, d)
    return f"第{c['no']}弯" if c else ""


def yaw_rate(rs, i):
    yaw = rs.get("yaw") or []
    a, b = yaw[max(0, i - 2)], yaw[min(len(yaw) - 1, i + 2)]
    if a is None or b is None:
        return None
    d = b - a
    if d > math.pi:
        d -= 2 * math.pi
    elif d < -math.pi:
        d += 2 * math.pi
    return d / (4 * GRID)


for li, lap in enumerate(lap_objs):
    rs = series[li]
    print("=" * 70)
    print(f"L{lap['n']}  {L.fmt(lap['lap_ms'])}   满油门 {lap.get('full')}%")
    # 最低速度点
    lows = sorted(((rs["v"][i], i * GRID) for i in range(len(rs["v"])) if rs["v"][i]),
                  key=lambda x: x[0])[:3]
    for v, d in lows:
        i = int(d / GRID)
        print(f"  最低速 {v:3} km/h @ {d:5.0f} m  {label(d):6}  "
              f"油门{rs['thr'][i]}% 刹车{rs['brk'][i]}% 方向{rs['steer'][i]} gx={rs['gx'][i]}")
    # 横向 G 峰值
    gxp = sorted(((abs(rs["gx"][i]), i * GRID) for i in range(len(rs["gx"]))
                  if rs["gx"][i] is not None), key=lambda x: x[0], reverse=True)[:3]
    print("  横向G峰:", "  ".join(f"{g:.2f}@{d:.0f}m({label(d)})" for g, d in gxp))
    # yaw 变化最快
    rates = [(abs(yaw_rate(rs, i)), i * GRID) for i in range(len(rs["v"]))
             if yaw_rate(rs, i) is not None]
    rates.sort(reverse=True)
    print("  yaw速率峰:", "  ".join(f"{r:.3f}@{d:.0f}m({label(d)})" for r, d in rates[:3]))

# L3 终点前逐米时间线
print()
print("=" * 70)
print("L3 在 5500-5890 米（第 15-18 弯，出界段）逐 10 米：")
for li, lap in enumerate(lap_objs):
    if lap["n"] != 3:
        continue
    rs = series[li]
    print("   dist  v   油门 刹车 方向   gx     yaw速率")
    for d in range(5500, 5891, 10):
        i = min(int(d / GRID), len(rs["v"]) - 1)
        g = rs["gx"][i]
        r = yaw_rate(rs, i)
        print(f"  {d:5d} {str(rs['v'][i] or '-'):>4} {str(rs['thr'][i]):>4} "
              f"{str(rs['brk'][i]):>4} {str(rs['steer'][i]):>6} "
              f"{('%.2f' % g) if g is not None else '-':>6} "
              f"{('%.3f' % r) if r is not None else '-':>7}")

print()
print("三圈在 5650-5890 米的速度对比：")
for li, lap in enumerate(lap_objs):
    rs = series[li]
    row = []
    for d in range(5650, 5891, 20):
        i = min(int(d / GRID), len(rs["v"]) - 1)
        row.append(f"{d}:{rs['v'][i]}")
    print(f"  L{lap['n']}  " + "  ".join(row))
