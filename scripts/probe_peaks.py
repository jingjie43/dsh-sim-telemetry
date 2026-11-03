# -*- coding: utf-8 -*-
"""看曲率峰的全部候选（不加官方弯数约束），用来人工核对赛道弯位。

用法: python scripts/probe_peaks.py [frames_xxx.jsonl]
"""
import glob
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

frames, laps_pkts, sess, _ = L.load(path)
lap_objs = L.cut_laps(frames, laps_pkts)
streams = E.load_streams(path)
series = [E.resample(E.lap_series(l, streams)) for l in lap_objs]
cur = E.average_curvature(series)
v = E.average_field(series, "v")
print("文件:", os.path.basename(path), "· trackId:", sess.get("trackId"),
      "· 圈数:", len(lap_objs))

print()
print("== 自然峰（无官方弯数约束，阈值 0.005、合并 60 米）==")
nat = E.detect_corners({"v": v}, expected=None, curv=cur)
print("峰数:", len(nat))
print(" 序号  apex_m  方向  半径    apex速度  entry-exit")
for i, c in enumerate(nat, 1):
    print("  %2d   %6.0f    %s    %5s     %4s     %.0f-%.0f"
          % (i, c["apex_d"], c["dir"], c.get("radius_m") or "-",
             c.get("apex_v") or "-", c["start"], c["end"]))

print()
print("== 强制 11 个（官方弯数约束）==")
forced = E.detect_corners({"v": v}, expected=11, curv=cur)
for i, c in enumerate(forced, 1):
    print("  %2d   %6.0f    %s    %5s     %4s     %.0f-%.0f"
          % (i, c["apex_d"], c["dir"], c.get("radius_m") or "-",
             c.get("apex_v") or "-", c["start"], c["end"]))

print()
print("== 曲率强度 top 20（按 |κ| 排序，看哪些峰被官方弯数挤掉了）==")
n = len(cur)
rows = []
for i in range(15, n - 15):
    if cur[i] is None:
        continue
    rows.append((abs(cur[i]), i * E.GRID, cur[i]))
rows.sort(reverse=True)
seen = []
for mag, d, k in rows:
    if any(abs(d - s) < 40 for s in seen):
        continue
    seen.append(d)
    if len(seen) > 20:
        break
    print("  %6.0f m  |κ|=%.4f  %s  半径 %s"
          % (d, mag, "L" if k > 0 else "R",
             ("%.0f" % (1 / mag)) if mag > 1e-6 else "-"))
