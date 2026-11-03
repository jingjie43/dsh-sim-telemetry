# -*- coding: utf-8 -*-
"""用「累计转角」找弯（不靠曲率峰值）——大半径长弯（如蒙扎 Curva Grande）也能抓到。

原理：
  - 曲率峰值法会漏掉半径大的长弯（蒙扎 Curva Grande 半径 ~200m，κ≈0.005，正好卡在阈值上）
  - 但「这个弯总共转了多少度」是弯的固有属性：chicane 90°、长弯 60~180°，与快慢无关
  - 做法：用世界坐标算切线角 θ，κ=dθ/ds，把 |κ| 超过小阈值的连续段当成一个弯，
    转角 = ∫|κ|·ds（度）。再按「转角 + apex 速度 + 方向」区分弯型。

用法: python scripts/corners_by_angle.py [frames_xxx.jsonl]
"""
import bisect
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
path = sys.argv[1] if len(sys.argv) > 1 else max(
    glob.glob(os.path.join(DATA, "frames_*.jsonl")), key=os.path.getmtime)

GRID = E.GRID
LOW_THR = 0.0020      # 曲率下限（1/半径 500 米）—— 比 detect_corners 的 0.005 低很多
MIN_ANGLE = 12.0      # 累计转角小于这个度数的不算弯


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


def lap_track(lap, streams, total):
    """把一圈映射到「距离 → (x,z)」网格。"""
    pts = []
    for f in lap["fr"]:
        d = E.dist_at(streams, f["st"])
        mo = nearest_motion(streams, f["st"])
        if d is None or not mo:
            continue
        x, z = mo.get("x"), mo.get("z")
        if x is None or z is None:
            continue
        pts.append((d, x, z))
    pts.sort()
    ds = [p[0] for p in pts]
    n = int(total / GRID) + 1
    xs, zs = [None] * n, [None] * n
    for i in range(n):
        target = i * GRID
        j = bisect.bisect_left(ds, target)
        cand = [k for k in (j - 1, j) if 0 <= k < len(pts)]
        if not cand:
            continue
        k = min(cand, key=lambda k: abs(pts[k][0] - target))
        if abs(pts[k][0] - target) > GRID * 4:
            continue
        xs[i], zs[i] = pts[k][1], pts[k][2]
    return xs, zs


frame, laps_pkts, sess, _ = L.load(path)
lap_objs = L.cut_laps(frame, laps_pkts)
streams = E.load_streams(path)
print("文件:", os.path.basename(path), "· 圈数:", len(lap_objs),
      "· trackId:", sess.get("trackId"))
if not lap_objs:
    sys.exit(1)

# 多圈平均的轨迹（取每圈平均位置，压掉走线差异）
total = E.detect_track_len(laps_pkts, sess)
tracks = [lap_track(l, streams, total) for l in lap_objs]
n = int(total / GRID) + 1
ax, az = [None] * n, [None] * n
for i in range(n):
    xs = [t[0][i] for t in tracks if t[0][i] is not None]
    zs = [t[1][i] for t in tracks if t[1][i] is not None]
    if xs and zs:
        ax[i], az[i] = sum(xs) / len(xs), sum(zs) / len(zs)

# 切线角 + 曲率
theta = [None] * n
for i in range(1, n):
    if ax[i] is None or az[i] is None or ax[i - 1] is None or az[i - 1] is None:
        continue
    dx, dz = ax[i] - ax[i - 1], az[i] - az[i - 1]
    if dx == 0 and dz == 0:
        continue
    theta[i] = math.atan2(dz, dx)

k = [None] * n
for i in range(1, n):
    if theta[i] is None or theta[i - 1] is None:
        continue
    d = theta[i] - theta[i - 1]
    if d > math.pi:
        d -= 2 * math.pi
    elif d < -math.pi:
        d += 2 * math.pi
    k[i] = d / GRID

# 平滑
ks = [None] * n
for i in range(n):
    w = [k[j] for j in range(max(0, i - 3), min(n, i + 4)) if k[j] is not None]
    ks[i] = sum(w) / len(w) if w else None

# 速度（每圈平均）
v = E.average_field([E.resample(E.lap_series(l, streams), total=total) for l in lap_objs], "v")

# 方向用 yaw 曲率的符号（车自己的参考系）—— 世界坐标的转向符号会随赛道朝向翻转
series_all = [E.resample(E.lap_series(l, streams), total=total) for l in lap_objs]
kyaw = E.average_curvature(series_all)
# 方向盘（最直接：车在往哪边打）。steer>0 按 F1 约定是左打
steer = E.average_field(series_all, "steer")
yaw_dir = [None] * n
for i in range(n):
    if kyaw and i < len(kyaw) and kyaw[i] is not None:
        yaw_dir[i] = 1 if kyaw[i] > 0 else -1

print()
print("== 按「累计转角」找弯（曲率下限 %.4f、转角下限 %.0f°）==" % (LOW_THR, MIN_ANGLE))
print("  距离范围      方向  转角(°)   apex速度  最小半径")
segs = []
cur = None
for i in range(n):
    kv = ks[i]
    if kv is None:
        continue
    if abs(kv) >= LOW_THR:
        if cur is None:
            cur = {"from": i, "to": i, "turn": 0.0, "ysign": 0.0, "ycount": 0}
        cur["to"] = i
        cur["turn"] += abs(kv) * GRID
        if yaw_dir[i] is not None:
            cur["ysign"] += yaw_dir[i]
            cur["ycount"] += 1
    else:
        if cur:
            segs.append(cur)
            cur = None
if cur:
    segs.append(cur)

out = []
for s in segs:
    ang = math.degrees(s["turn"])
    if ang < MIN_ANGLE:
        continue
    a, b = s["from"] * GRID, s["to"] * GRID
    vs = [(v[i], i * GRID) for i in range(s["from"], s["to"] + 1) if v[i]]
    apex_v, apex_d = (min(vs) if vs else (None, None))
    radii = [1 / abs(ks[i]) for i in range(s["from"], s["to"] + 1)
             if ks[i] is not None and abs(ks[i]) > 1e-6]
    rmin = min(radii) if radii else None
    # 方向优先级：方向盘符号（最直接）> yaw 曲率符号 > 世界坐标（最后兜底）
    st_vals = [steer[i] for i in range(s["from"], s["to"] + 1)
               if i < len(steer) and steer[i] is not None]
    st_avg = (sum(st_vals) / len(st_vals)) if st_vals else None
    if st_avg is not None and abs(st_avg) > 0.02:
        direction = "L" if st_avg > 0 else "R"
        src = "steer"
    elif s["ycount"]:
        direction = "L" if s["ysign"] > 0 else "R"
        src = "yaw"
    else:
        direction = "R"
        src = "?"
    out.append({"from": a, "to": b, "dir": direction, "angle": ang,
                "apex_m": apex_d, "apex_v": apex_v, "rmin": rmin, "src": src})

# 合并相邻同方向、间距小的段（长弯被切成几截的情况）
merged = []
for c in out:
    if merged:
        last = merged[-1]
        gap = c["from"] - last["to"]
        if c["dir"] == last["dir"] and gap < 120:
            last["to"] = c["to"]
            last["angle"] += c["angle"]
            last["apex_v"] = min(x for x in (last["apex_v"], c["apex_v"]) if x is not None) \
                if (last["apex_v"] or c["apex_v"]) else None
            last["rmin"] = min(x for x in (last["rmin"], c["rmin"]) if x is not None) \
                if (last["rmin"] or c["rmin"]) else None
            continue
    merged.append(dict(c))

print("  共 %d 个候选弯（合并后 %d 个）" % (len(out), len(merged)))
print("  序号  距离范围        方向  转角(°)   apex速度  最小半径  方向来源")
for i, c in enumerate(merged, 1):
    print("  %2d  %6.0f-%-6.0f  %s   %6.1f    %6s     %5s    %s"
          % (i, c["from"], c["to"], c["dir"], c["angle"],
             ("%.0f" % c["apex_v"]) if c["apex_v"] else "-",
             ("%.0f" % c["rmin"]) if c["rmin"] else "-",
             c.get("src", "")))
