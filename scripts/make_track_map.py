# -*- coding: utf-8 -*-
"""通用赛道图 + 弯位表生成（任意已校准赛道）。

用法:
  python scripts/make_track_map.py silverstone
  python scripts/make_track_map.py monza
  python scripts/make_track_map.py silverstone <frames_xxx.jsonl>

输出到桌面 + 项目 docs：
  <track>-track-map.png     赛道图（左轨迹+弯号，右官方弯名图例）
  <track>-corner-table.png  弯位表（入口/apex/出口/方向/转角/半径/apex速度）
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

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
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


def pick_data(track_id):
    """优先用命令行指定；否则在所有 frames 里找「有 Motion 且 trackId 匹配」的最新一份。"""
    if len(sys.argv) > 2:
        return sys.argv[2]
    cand = []
    for p in glob.glob(os.path.join(DATA, "frames_*.jsonl")):
        try:
            if os.path.getsize(p) < 20000:
                continue
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    if '"id": 1' in line or '"id":1' in line:
                        r = __import__("json").loads(line)
                        if r.get("trackId") == track_id:
                            cand.append((os.path.getmtime(p), p))
                        break
        except Exception:
            continue
    return max(cand)[1] if cand else None


def load_avg_track(path, total=None):
    frames, laps_pkts, sess, _ = L.load(path)
    if not total:
        total = E.detect_track_len(laps_pkts, sess)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(path)
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


def make_map(track, ax, az, v, nlaps, src):
    corners = track["detected_corners"]
    name = track["name"]
    W, H = 2200, 1700
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d, W, H)
    d.text((80, 48), "%s · 赛道图（官方弯名）" % name, font=f(52, True), fill=WHITE)
    d.text((84, 122), "%d 个弯 · 实跑轨迹 %d 圈平均 · trackId %s · %s 米 · 校准 %s"
           % (len(corners), nlaps, track["track_id"], track["length_m"],
              track.get("calibrated_from", "")[:34]),
           font=f(21), fill=DIM)
    d.text((W - 340, 80), "dsh-sim-telemetry", font=f(24, True), fill=ACCENT)

    pts = [(ax[i], az[i]) for i in range(len(ax)) if ax[i] is not None]
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    minz, maxz = min(p[1] for p in pts), max(p[1] for p in pts)
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

    groups = []
    for c in corners:
        nm = c.get("name") or ""
        if groups and groups[-1]["name"] == nm:
            groups[-1]["cs"].append(c)
        else:
            groups.append({"name": nm, "cs": [c]})

    y = 356
    rowh = 72 if len(groups) > 10 else 96
    for g in groups:
        nos = [c["no"] for c in g["cs"]]
        dirs = " ".join(c["dir"] for c in g["cs"])
        no_txt = " · ".join(str(n) for n in nos)
        d.text((lx0 + 30, y), no_txt, font=f(24, True), fill=ACCENT)
        d.text((lx0 + 150, y + 2), g["name"], font=f(24, True), fill=WHITE)
        d.text((lx0 + lw - 90, y + 2), dirs, font=f(20), fill=DIM)
        y += rowh

    d.line([(80, H - 130), (W - 80, H - 130)], fill=LINE, width=2)
    d.text((80, H - 108), "弯号对应 tracks.py 的 %s.detected_corners" % track.get("_key", ""),
           font=f(21), fill=DIM)
    d.text((80, H - 72), "数据：%s · %d 圈" % (os.path.basename(src), nlaps),
           font=f(21), fill=DIM)
    return img


def make_table(track, ax, az, v, nlaps, src):
    corners = track["detected_corners"]
    rows = len(corners)
    W = 1700
    rh, hh, y0 = 58, 52, 186
    H = y0 + hh + rh * rows + 120
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d, W, H)
    d.text((80, 42), "%s 弯位表" % track["name"], font=f(48, True), fill=WHITE)
    d.text((84, 108), "实跑校准 · 官方弯名 · %d 圈平均 · 状态 %s"
           % (nlaps, track["status"]), font=f(22), fill=DIM)

    cols = [("弯号", 110), ("官方弯名", 300), ("入口", 120), ("apex", 120),
            ("出口", 120), ("方向", 100), ("转角", 110), ("半径", 130), ("apex速度", 150)]
    x0 = 80
    total_w = sum(c[1] for c in cols)
    d.rounded_rectangle([x0, y0, x0 + total_w, y0 + hh + rh * rows + 4],
                        radius=14, fill=CARD, outline=LINE, width=2)
    x = x0
    for nm, w in cols:
        d.rectangle([x, y0, x + w, y0 + hh], fill=(28, 40, 60))
        tw = d.textlength(nm, font=f(22, True))
        d.text((x + (w - tw) / 2, y0 + 13), nm, font=f(22, True), fill=DIM)
        x += w
    for ri, c in enumerate(corners):
        y = y0 + hh + ri * rh
        if ri % 2 == 0:
            d.rectangle([x0 + 2, y, x0 + total_w - 2, y + rh], fill=(23, 33, 52))
        i = min(len(v) - 1, int((c["apex_m"] or 0) / GRID))
        av = v[i] if v else None
        vals = [str(c["no"]), c.get("name") or "", "%.0f" % c["entry_m"],
                "%.0f" % c["apex_m"], "%.0f" % c["exit_m"], c["dir"],
                ("%.0f°" % c["angle_deg"]) if c.get("angle_deg") else "-",
                ("%.0f m" % c["radius_m"]) if c.get("radius_m") else "-",
                ("%d km/h" % av) if av else "-"]
        x = x0
        for ci, ((nm, w), val) in enumerate(zip(cols, vals)):
            bold = ci in (0, 1)
            color = ACCENT if ci == 0 else (GOLD if ci == 1 else WHITE)
            tw = d.textlength(val, font=f(22, bold))
            d.text((x + (w - tw) / 2, y + 14), val, font=f(22, bold), fill=color)
            x += w
    d.text((80, H - 62), "数据：%s · %d 圈" % (os.path.basename(src), nlaps),
           font=f(20), fill=DIM)
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


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "monza"
    track = T.TRACKS.get(key)
    if not track:
        print("没有这条赛道:", key, "（可选:", ", ".join(T.TRACKS), "）")
        return 1
    track["_key"] = key
    src = pick_data(track["track_id"])
    if not src:
        print("没找到这条赛道的采集数据")
        return 1
    print("赛道:", track["name"], "· 数据:", os.path.basename(src))
    ax, az, v, nlaps = load_avg_track(src)
    for p in save(make_map(track, ax, az, v, nlaps, src), "%s-track-map.png" % key):
        print("已保存:", p)
    for p in save(make_table(track, ax, az, v, nlaps, src), "%s-corner-table.png" % key):
        print("已保存:", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
