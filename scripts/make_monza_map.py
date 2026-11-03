# -*- coding: utf-8 -*-
"""生成蒙扎赛道图（弯号 + 官方弯名图例）和弯位表，保存到桌面 + 项目 docs。

布局：左边赛道轨迹 + 编号圈；右边图例（编号 ↔ 官方弯名），互不遮挡。

用法: python scripts/make_monza_map.py
输出: 桌面/monza-track-map.png、桌面/monza-corner-table.png（docs 下各留一份）
"""
import bisect
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402
import tracks as T    # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

DATA = os.path.expanduser(r"~\.dsh\sim-telemetry")
PATH = os.path.join(DATA, "frames_20261028_123025.jsonl")
if not os.path.exists(PATH):
    import glob
    PATH = max(glob.glob(os.path.join(DATA, "frames_*.jsonl")), key=os.path.getmtime)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
DESK = os.path.join(os.path.expanduser("~"), "Desktop")
GRID = E.GRID

BG = (11, 16, 32)
CARD = (20, 28, 46)
LINE = (40, 52, 78)
ACCENT = (79, 209, 197)
BLUE = (96, 165, 250)
WHITE = (235, 241, 250)
DIM = (140, 152, 172)
GOLD = (250, 204, 120)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT


def f(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


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


def load_avg_track():
    frames, laps_pkts, sess, _ = L.load(PATH)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(PATH)
    total = E.DEFAULT_LEN
    n = int(total / GRID) + 1
    accx, accz, cnt = [0.0] * n, [0.0] * n, [0] * n
    for lap in lap_objs:
        for fr in lap["fr"]:
            dd = E.dist_at(streams, fr["st"])
            mo = nearest_motion(streams, fr["st"])
            if dd is None or not mo:
                continue
            x, z = mo.get("x"), mo.get("z")
            if x is None or z is None:
                continue
            i = int(dd / GRID)
            if 0 <= i < n:
                accx[i] += x
                accz[i] += z
                cnt[i] += 1
    ax = [accx[i] / cnt[i] if cnt[i] else None for i in range(n)]
    az = [accz[i] / cnt[i] if cnt[i] else None for i in range(n)]
    series = [E.resample(E.lap_series(l, streams), total=total) for l in lap_objs]
    v = E.average_field(series, "v", GRID)
    return ax, az, v, len(lap_objs)


def background(d, W, H):
    for i in range(-H, W, 140):
        d.line([(i, 0), (i + H, H)], fill=(17, 23, 38), width=2)
    for y in range(0, 5):
        d.line([(0, 8 + y), (W, 8 + y)], fill=(44, 76, 118))


def make_map():
    ax, az, v, nlaps = load_avg_track()
    monza = T.get_by_track_id(11)
    corners = monza["detected_corners"]

    W, H = 2200, 1700
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d, W, H)

    d.text((80, 48), "Monza · 赛道图（官方弯名）", font=f(52, True), fill=WHITE)
    d.text((84, 122), "11 个弯 · 实跑轨迹 3 圈平均 · trackId 11 · 5798 米 · 2026-10-28",
           font=f(22), fill=DIM)
    d.text((W - 340, 80), "dsh-sim-telemetry", font=f(24, True), fill=ACCENT)

    pts = [(ax[i], az[i]) for i in range(len(ax)) if ax[i] is not None]
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    minz, maxz = min(p[1] for p in pts), max(p[1] for p in pts)

    # 左侧赛道区
    arena = (80, 1580, 250, H - 170)
    scale = min((arena[1] - arena[0] - 120) / max(1e-6, maxx - minx),
                (arena[3] - arena[2]) / max(1e-6, maxz - minz))
    ox = arena[0] + 60 + ((arena[1] - arena[0] - 120) - (maxx - minx) * scale) / 2
    oy = arena[2] + ((arena[3] - arena[2]) - (maxz - minz) * scale) / 2

    def to_screen(x, z):
        return (ox + (x - minx) * scale, oy + (maxz - z) * scale)

    path = [to_screen(ax[i], az[i]) for i in range(len(ax)) if ax[i] is not None]
    for i in range(1, len(path)):
        d.line([path[i - 1], path[i]], fill=(205, 214, 228), width=6)
    sx, sy = path[0]
    d.ellipse([sx - 8, sy - 8, sx + 8, sy + 8], fill=BLUE)
    d.text((sx + 14, sy - 12), "起点", font=f(22, True), fill=BLUE)

    cx0 = sum(p[0] for p in pts) / len(pts)
    cz0 = sum(p[1] for p in pts) / len(pts)
    center = to_screen(cx0, cz0)

    def corner_point(c):
        i = min(len(ax) - 1, int((c["apex_m"] or 0) / GRID))
        if ax[i] is None:
            return None
        return to_screen(ax[i], az[i])

    def outward(p):
        dx, dy = p[0] - center[0], p[1] - center[1]
        n = math.hypot(dx, dy) or 1
        return dx / n, dy / n

    # 编号圈（只标数字，弯名看右边图例）
    used = []
    for c in corners:
        p = corner_point(c)
        if not p:
            continue
        dx, dy = outward(p)
        off = 46
        lx, ly = p[0] + dx * off, p[1] + dy * off
        for _ in range(12):
            if all(math.hypot(lx - q[0], ly - q[1]) > 56 for q in used):
                break
            off += 30
            lx, ly = p[0] + dx * off, p[1] + dy * off
        # 别跑出赛道区
        lx = min(max(lx, arena[0] + 30), arena[1] - 30)
        ly = min(max(ly, arena[2] + 20), arena[3] - 20)
        used.append((lx, ly))
        d.line([p, (lx, ly)], fill=(70, 85, 115), width=2)
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=ACCENT)
        d.ellipse([lx - 22, ly - 22, lx + 22, ly + 22], fill=(16, 27, 44),
                  outline=ACCENT, width=3)
        no = str(c["no"])
        tw = d.textlength(no, font=f(27, True))
        d.text((lx - tw / 2, ly - 19), no, font=f(27, True), fill=ACCENT)

    # 右侧图例
    lx0 = 1660
    lw = W - lx0 - 80
    d.rounded_rectangle([lx0, 250, lx0 + lw, H - 170], radius=18, fill=CARD,
                        outline=LINE, width=2)
    d.text((lx0 + 32, 274), "官方弯名", font=f(32, True), fill=GOLD)
    d.line([(lx0 + 32, 330), (lx0 + lw - 32, 330)], fill=LINE, width=2)

    # 按弯名分组（保持编号顺序）
    groups = []
    for c in corners:
        name = c.get("name") or ""
        if groups and groups[-1]["name"] == name:
            groups[-1]["cs"].append(c)
        else:
            groups.append({"name": name, "cs": [c]})

    y = 356
    rowh = 132
    for g in groups:
        nos = [c["no"] for c in g["cs"]]
        dirs = " ".join(c["dir"] for c in g["cs"])
        no_txt = " · ".join(str(n) for n in nos)
        d.text((lx0 + 32, y), no_txt, font=f(34, True), fill=ACCENT)
        d.text((lx0 + lw - 130, y + 4), dirs, font=f(26, True), fill=DIM)
        nm = g["name"]
        d.text((lx0 + 32, y + 52), nm, font=f(26, True), fill=WHITE)
        # 距离
        rng = "%d–%d m" % (g["cs"][0]["entry_m"], g["cs"][-1]["exit_m"])
        d.text((lx0 + 32, y + 90), rng, font=f(21), fill=DIM)
        y += rowh

    d.line([(80, H - 130), (W - 80, H - 130)], fill=LINE, width=2)
    d.text((80, H - 108), "弯号对应 tracks.py 的 monza.detected_corners；弯名来源：F1 官方《How every corner at Monza got its name》",
           font=f(21), fill=DIM)
    d.text((80, H - 72), "同一行有多个编号的是成组弯（Prima Variante ×2 / Seconda Variante ×2 / Ascari ×3）",
           font=f(21), fill=DIM)
    return img


def make_table():
    ax, az, v, nlaps = load_avg_track()
    monza = T.get_by_track_id(11)
    corners = monza["detected_corners"]

    W, H = 1700, 1060
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d, W, H)
    d.text((80, 46), "Monza 弯位表", font=f(52, True), fill=WHITE)
    d.text((84, 116), "实跑校准 · 官方弯名 · 3 圈平均（2026-10-28）", font=f(24), fill=DIM)

    cols = [("弯号", 120), ("官方弯名", 330), ("入口", 130), ("apex", 130),
            ("出口", 130), ("方向", 110), ("转角", 120), ("半径", 140), ("apex速度", 160)]
    x0, y0, rh, hh = 80, 190, 66, 56
    total_w = sum(c[1] for c in cols)
    d.rounded_rectangle([x0, y0, x0 + total_w, y0 + hh + rh * len(corners) + 4],
                        radius=14, fill=CARD, outline=LINE, width=2)
    x = x0
    for name_, w in cols:
        d.rectangle([x, y0, x + w, y0 + hh], fill=(28, 40, 60))
        tw = d.textlength(name_, font=f(24, True))
        d.text((x + (w - tw) / 2, y0 + 14), name_, font=f(24, True), fill=DIM)
        x += w
    for ri, c in enumerate(corners):
        y = y0 + hh + ri * rh
        if ri % 2 == 0:
            d.rectangle([x0 + 2, y, x0 + total_w - 2, y + rh], fill=(23, 33, 52))
        i = min(len(v) - 1, int((c["apex_m"] or 0) / GRID))
        apex_v = v[i] if v else None
        vals = [str(c["no"]), c.get("name") or "", "%.0f" % c["entry_m"],
                "%.0f" % c["apex_m"], "%.0f" % c["exit_m"], c["dir"],
                ("%.0f°" % c["angle_deg"]) if c.get("angle_deg") else "-",
                ("%.0f m" % c["radius_m"]) if c.get("radius_m") else "-",
                ("%d km/h" % apex_v) if apex_v else "-"]
        x = x0
        for ci, ((name_, w), val) in enumerate(zip(cols, vals)):
            bold = ci in (0, 1)
            color = ACCENT if ci == 0 else (GOLD if ci == 1 else WHITE)
            tw = d.textlength(val, font=f(24, bold))
            d.text((x + (w - tw) / 2, y + 16), val, font=f(24, bold), fill=color)
            x += w

    d.text((80, H - 76), "数据：frames_20261028_123025.jsonl · 3 圈 · 排除了暖胎圈",
           font=f(22), fill=DIM)
    return img


def save(img, name):
    outs = []
    for base in (DESK, DOCS):
        if not os.path.isdir(base):
            continue
        p = os.path.join(base, name)
        img.save(p)
        outs.append(p)
    return outs


if __name__ == "__main__":
    for p in save(make_map(), "monza-track-map.png"):
        print("已保存:", p)
    for p in save(make_table(), "monza-corner-table.png"):
        print("已保存:", p)
