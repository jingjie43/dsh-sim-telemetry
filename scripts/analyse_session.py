# -*- coding: utf-8 -*-
"""深度异常分析：在遥测里定位「出界 / spin / 明显掉速」的具体位置。

除 engineer 的默认 spin 判据外，这里再加两种特征：
  1. 走线偏离：三圈世界坐标按距离对齐 → 取平均当参考线 → 找偏离 > 阈值的连续段
     （银石赛道半宽约 6~7 米，偏离超过 6 米基本就是四轮出白线）
  2. 姿态异常：yaw 变化率异常 + 速度掉 → 甩尾 / 打滑

用法:
  python scripts/analyse_session.py [frames_xxx.jsonl]
  环境变量 DEV_TH=3.5 可调偏离阈值（默认 5.0 米）
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
import tracks as T    # noqa: E402

GRID = E.GRID
TOTAL = E.DEFAULT_LEN
DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
DEV_TH = float(os.environ.get("DEV_TH", "5.0"))   # 走线偏离阈值（米）


def nearest_motion(streams, st):
    m = streams.get("motion") or {}
    if not m:
        return None
    keys = streams.setdefault("_mkeys", sorted(m.keys()))
    i = bisect.bisect_left(keys, round(st, 2))
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(keys):
            k = keys[j]
            if best is None or abs(k - st) < abs(best - st):
                best = k
    return m.get(best) if best is not None else None


def lap_world(lap, streams):
    """一圈里每个速度帧对应的 (dist, x, z)。"""
    out = []
    for f in lap["fr"]:
        d = E.dist_at(streams, f["st"])
        mo = nearest_motion(streams, f["st"])
        if d is None or not mo:
            continue
        x, z = mo.get("x"), mo.get("z")
        if x is None or z is None:
            continue
        out.append((d, x, z))
    out.sort()
    return out


def to_grid_world(pts, grid=GRID, total=TOTAL):
    n = int(total / grid) + 1
    xs, zs = [None] * n, [None] * n
    if not pts:
        return xs, zs
    ds = [p[0] for p in pts]
    for i in range(n):
        target = i * grid
        j = bisect.bisect_left(ds, target)
        cand = [k for k in (j - 1, j) if 0 <= k < len(pts)]
        if not cand:
            continue
        p = min(cand, key=lambda k: abs(pts[k][0] - target))
        if abs(pts[p][0] - target) > grid * 4:
            continue
        xs[i], zs[i] = pts[p][1], pts[p][2]
    return xs, zs


def corner_label(track, d):
    if not track:
        return ""
    c, phase = T.corner_at(track, d)
    if not c:
        return ""
    return "第%d弯" % c["no"] + (("(%s)" % phase) if phase else "")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else max(
        glob.glob(os.path.join(DATA, "frames_*.jsonl")), key=os.path.getmtime)
    print("分析文件:", os.path.basename(path))

    frames, laps_pkts, sess, flashbacks = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(path)
    track = T.get_by_track_id(sess.get("trackId", -1))
    print("赛道:", (track or {}).get("name", "?"), "· 圈数:", len(lap_objs),
          "· 回退:", len(flashbacks))

    series = [E.resample(E.lap_series(l, streams), total=TOTAL) for l in lap_objs]
    worlds = [to_grid_world(lap_world(l, streams)) for l in lap_objs]

    # 参考线 = 三圈平均
    refx = [None] * (int(TOTAL / GRID) + 1)
    refz = [None] * (int(TOTAL / GRID) + 1)
    for i in range(len(refx)):
        xs = [w[0][i] for w in worlds if i < len(w[0]) and w[0][i] is not None]
        zs = [w[1][i] for w in worlds if i < len(w[1]) and w[1][i] is not None]
        if xs and zs:
            refx[i] = sum(xs) / len(xs)
            refz[i] = sum(zs) / len(zs)

    def deviation(i, lap_i):
        x, z = worlds[lap_i][0][i], worlds[lap_i][1][i]
        if x is None or refx[i] is None:
            return None
        return math.hypot(x - refx[i], z - refz[i])

    print()
    print("=" * 66)
    print("① 走线偏离（参考线 = 三圈平均，阈值 %.1f 米）" % DEV_TH)
    for li, lap in enumerate(lap_objs):
        segs, cur = [], None
        for i in range(len(refx)):
            dev = deviation(i, li)
            if dev is None:
                continue
            if dev > DEV_TH:
                if cur is None:
                    cur = {"from": i * GRID, "to": i * GRID, "max": dev}
                cur["to"] = i * GRID
                cur["max"] = max(cur["max"], dev)
            else:
                if cur:
                    segs.append(cur)
                    cur = None
        if cur:
            segs.append(cur)
        segs = [s for s in segs if s["to"] - s["from"] >= 10]
        if not segs:
            print("  L%d  %s  走线稳定（偏离 < %.1f 米）"
                  % (lap["n"], L.fmt(lap["lap_ms"]), DEV_TH))
            continue
        for s in segs:
            label = corner_label(track, (s["from"] + s["to"]) / 2)
            print("  L%d  %s  %.0f-%.0f 米 最大偏离 %.1f 米 %s"
                  % (lap["n"], L.fmt(lap["lap_ms"]), s["from"], s["to"], s["max"], label))

    print()
    print("② 姿态异常（yaw 变化率 > 0.045 rad/m）")
    for li, lap in enumerate(lap_objs):
        rs = series[li]
        yaw = rs.get("yaw") or []
        found = []
        for i in range(2, len(yaw) - 2):
            a, b = yaw[i - 2], yaw[i + 2]
            if a is None or b is None:
                continue
            d = b - a
            if d > math.pi:
                d -= 2 * math.pi
            elif d < -math.pi:
                d += 2 * math.pi
            rate = abs(d) / (4 * GRID)
            if rate > 0.045:
                v0 = rs["v"][max(0, i - 6)]
                v1 = rs["v"][min(len(rs["v"]) - 1, i + 6)]
                drop = (v0 - v1) if (v0 and v1) else 0
                found.append((i * GRID, rate, round(drop, 0)))
        merged = []
        for d, rate, drop in found:
            if merged and d - merged[-1][1] < 40:
                merged[-1][1] = d
                merged[-1][2] = max(merged[-1][2], rate)
                merged[-1][3] = max(merged[-1][3], drop)
            else:
                merged.append([d, d, rate, drop])
        if not merged:
            print("  L%d  车头姿态正常" % lap["n"])
        for m in merged:
            label = corner_label(track, (m[0] + m[1]) / 2)
            print("  L%d  %.0f-%.0f 米  yaw 速率 %.3f rad/m  速度掉 %.0f km/h  %s"
                  % (lap["n"], m[0], m[1], m[2], m[3], label))

    print()
    best_i = min(range(len(lap_objs)), key=lambda i: lap_objs[i]["lap_ms"])
    print("③ 相对最快圈 L%d 的逐段速度差（>6 km/h 才列）" % lap_objs[best_i]["n"])
    for li, lap in enumerate(lap_objs):
        if li == best_i:
            continue
        rs, rb = series[li], series[best_i]
        diffs = []
        for i in range(min(len(rs["v"]), len(rb["v"]))):
            a, b = rs["v"][i], rb["v"][i]
            if a is None or b is None:
                continue
            if b - a > 6:
                diffs.append((i * GRID, b - a))
        if not diffs:
            print("  L%d  没有明显慢的段落" % lap["n"])
            continue
        groups = []
        for d, dv in diffs:
            if groups and d - groups[-1][1] <= 20:
                groups[-1][1] = d
                groups[-1][2] = max(groups[-1][2], dv)
            else:
                groups.append([d, d, dv])
        groups = sorted(groups, key=lambda g: g[2], reverse=True)[:5]
        for g in groups:
            label = corner_label(track, (g[0] + g[1]) / 2)
            print("  L%d  %.0f-%.0f 米  比最快圈慢 %.0f km/h  %s"
                  % (lap["n"], g[0], g[1], g[2], label))


if __name__ == "__main__":
    main()
