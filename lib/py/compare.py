# -*- coding: utf-8 -*-
"""多份采集对比图：速度曲线叠加 / 逐弯改进表并排。

用法：
  python compare.py speed  <out.png> <frames1> <frames2> ...
  python compare.py advice <out.png> <frames1> <frames2> ...
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402
import tracks as T    # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT


def f(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


BG = (14, 19, 34)
PANEL = (21, 29, 48)
LINE = (44, 56, 84)
WHITE = (232, 238, 248)
DIM = (140, 152, 172)
ACCENT = (79, 209, 197)
GOLD = (250, 204, 120)
COLORS = [(96, 165, 250), (250, 160, 100), (120, 220, 160),
          (220, 140, 230), (240, 210, 110), (160, 200, 90)]


def fmt_ms(ms):
    if not ms:
        return "-"
    s = ms / 1000.0
    return "%d:%06.3f" % (int(s // 60), s % 60)


def load_best(path):
    frames, laps_pkts, sess, _ = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(path)
    best = None
    for lap in lap_objs:
        pts = E.lap_series(lap, streams)
        if not pts:
            continue
        if best is None or lap["lap_ms"] < best["ms"]:
            best = {"ms": lap["lap_ms"], "n": lap["n"], "pts": pts,
                    "trackId": sess.get("trackId")}
    return best, sess


def track_name_of(tid):
    t = T.get_by_track_id(tid)
    return t["name"] if t else "track%s" % tid


def draw_speed(out, files):
    data = []
    for p in files:
        best, sess = load_best(p)
        if best:
            data.append((p, best, sess))
    if not data:
        print("没有可对比的数据")
        return 1
    total = E.detect_track_len([], data[0][2]) if data else E.DEFAULT_LEN
    W, H = 1700, 900
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for i in range(-H, W, 130):
        d.line([(i, 0), (i + H, H)], fill=(19, 25, 42), width=2)
    name = track_name_of(data[0][1]["trackId"])
    d.text((60, 40), "%s · 速度曲线对比（%d 份采集）" % (name, len(data)), font=f(38, True), fill=WHITE)

    pad_l, pad_r, pad_t, pad_b = 90, 60, 130, 90
    px0, py0 = pad_l, pad_t
    pw, ph = W - pad_l - pad_r, H - pad_t - pad_b
    d.line([(px0, py0 + ph), (px0 + pw, py0 + ph)], fill=LINE, width=2)
    d.line([(px0, py0), (px0, py0 + ph)], fill=LINE, width=2)
    for gv in range(0, 361, 60):
        gy = py0 + ph - gv / 360 * ph
        d.line([(px0, gy), (px0 + pw, gy)], fill=(30, 38, 58), width=1)
        d.text((40, gy - 8), str(gv), font=f(15), fill=DIM)
    for gd in range(0, 7001, 1000):
        gx = px0 + gd / 7000 * pw
        d.line([(px0 + gx - px0, py0), (px0 + gx - px0, py0 + ph)], fill=(30, 38, 58), width=1)
        d.text((gx - 12, py0 + ph + 8), str(gd), font=f(14), fill=DIM)

    def tx(dd):
        return px0 + dd / 7000 * pw

    def ty(vv):
        return py0 + ph - max(0, min(360, vv)) / 360 * ph

    for i, (p, best, sess) in enumerate(data):
        col = COLORS[i % len(COLORS)]
        pts = [(tx(q["d"]), ty(q["v"])) for q in best["pts"] if q.get("v") is not None]
        for j in range(1, len(pts)):
            d.line([pts[j - 1], pts[j]], fill=col, width=2)
        # 图例
        ly = 90 + i * 22
        d.line([(W - 420, ly), (W - 390, ly)], fill=col, width=3)
        d.text((W - 380, ly - 8), "%s  %s  L%d" % (fmt_ms(best["ms"]), os.path.basename(p)[7:-6], best["n"]),
               font=f(15), fill=WHITE)

    d.text((60, H - 55), "横轴：赛道距离（米）  纵轴：速度（km/h）；每份采集取最快圈", font=f(17), fill=DIM)
    img.save(out)
    print("已保存:", out)
    return 0


def draw_advice(out, files):
    rows = []
    for p in files:
        r = E.analyse(p)
        rows.append((p, r))
    if not rows:
        print("没有可对比的数据")
        return 1
    W = 1900
    rh, hh = 40, 56
    H = 120 + hh + rh * 22 + 70
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for i in range(-H, W, 130):
        d.line([(i, 0), (i + H, H)], fill=(19, 25, 42), width=2)
    name = track_name_of(rows[0][1]["session"].get("trackId"))
    d.text((60, 32), "%s · 逐弯改进表对比（%d 份采集）" % (name, len(rows)), font=f(34, True), fill=WHITE)

    cols = [("弯", 70), ("名称", 260)]
    for _, r in rows:
        cols.append(("L%d" % r.get("best_index", 0), 0))  # 占位
    # 每份采集一列
    widths = [70, 260] + [160] * len(rows)
    x0, y0 = 60, 110
    total_w = sum(widths)
    d.rounded_rectangle([x0, y0, x0 + total_w, y0 + hh + rh * 19 + 4], radius=12, fill=PANEL, outline=LINE, width=2)
    x = x0
    headers = ["弯", "名称"] + [os.path.basename(p)[7:20] for p, _ in rows]
    for i, h in enumerate(headers):
        d.rectangle([x, y0, x + widths[i], y0 + hh], fill=(28, 40, 60))
        d.text((x + 8, y0 + 16), h, font=f(17, True), fill=DIM)
        x += widths[i]

    names = {i + 1: (c.get("name") or "") for i, c in enumerate(rows[0][1].get("corners") or [])}
    corner_rows = rows[0][1].get("corner_rows") or []
    for ri, cr in enumerate(corner_rows):
        yy = y0 + hh + ri * rh
        if ri % 2 == 0:
            d.rectangle([x0 + 2, yy, x0 + total_w - 2, yy + rh], fill=(24, 34, 54))
        x = x0
        vals = [str(cr["no"]), names.get(cr["no"], "")]
        for p, r in rows:
            v = None
            for rc in (r.get("corner_rows") or []):
                if rc["no"] == cr["no"]:
                    ap = [l["apex"] for l in (rc.get("laps") or []) if l.get("apex")]
                    if ap:
                        v = max(ap)
            vals.append(str(v) if v else "-")
        for i, val in enumerate(vals):
            color = ACCENT if i == 0 else (WHITE if i == 1 else GOLD)
            d.text((x + 8, yy + 9), val[:18], font=f(17, i < 2), fill=color)
            x += widths[i]

    d.text((60, H - 45), "每份采集显示该弯的最优 apex 速度（km/h）", font=f(16), fill=DIM)
    img.save(out)
    print("已保存:", out)
    return 0


def main():
    if len(sys.argv) < 4:
        print("用法: python compare.py speed|advice <out.png> <frames1> <frames2> ...")
        return 1
    action = sys.argv[1]
    out = sys.argv[2]
    files = sys.argv[3:]
    if action == "speed":
        return draw_speed(out, files)
    if action == "advice":
        return draw_advice(out, files)
    print("未知 action:", action)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
