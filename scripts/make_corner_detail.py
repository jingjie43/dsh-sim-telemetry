# -*- coding: utf-8 -*-
"""逐弯细节对比图：每个弯一个小面板，三圈的速度 / 油门 / 刹车叠在一起。

用法:
  python scripts/make_corner_detail.py <track_key> <frames_xxx.jsonl> [输出路径]
例:
  python scripts/make_corner_detail.py spa C:\\Users\\Lenovo\\.dsh\\sim-telemetry\\frames_20261103_143320.jsonl

输出默认: 桌面/<track>-corners-detail.png + docs/<track>-corners-detail.png
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
DESK = os.path.join(os.path.expanduser("~"), "Desktop")

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
COLORS = [(96, 165, 250), (250, 160, 100), (120, 220, 160)]  # L1 L2 L3


def load_laps(path):
    frames, laps_pkts, sess, _ = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = E.load_streams(path)
    laps = []
    for lap in lap_objs:
        pts = E.lap_series(lap, streams)
        laps.append({"n": lap["n"], "ms": lap["lap_ms"], "pts": pts})
    return laps, sess


def draw_panel(img, d, x, y, w, h, no, name, dir_, vmin, vmax, laps, entry, exit_, best_ms):
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=PANEL, outline=LINE, width=1)
    # 标题：弯号 + 名称
    d.text((x + 10, y + 6), "T%d" % no, font=f(17, True), fill=ACCENT)
    d.text((x + 46, y + 6), name[:14], font=f(15, True), fill=WHITE)
    d.text((x + w - 24, y + 7), dir_, font=f(14, True), fill=DIM)

    pad_l, pad_r, pad_t, pad_b = 34, 8, 30, 26
    px0, py0 = x + pad_l, y + pad_t
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    # 纵轴速度范围（该弯内所有圈的 min/max，留边）
    vals = []
    for lap in laps:
        for p in lap["pts"]:
            if entry - 30 <= p["d"] <= exit_ + 30 and p.get("v") is not None:
                vals.append(p["v"])
    if not vals:
        d.text((x + w // 2 - 20, y + h // 2), "无数据", font=f(14), fill=DIM)
        return
    lo = max(0, min(vals) - 15)
    hi = max(vals) + 15
    if hi - lo < 20:
        hi = lo + 20

    # 网格线
    for gv in range(0, 4):
        gy = py0 + ph * gv / 3
        d.line([(px0, gy), (px0 + pw, gy)], fill=(32, 42, 64), width=1)
        d.text((x + 4, gy - 8), "%.0f" % (hi - (hi - lo) * gv / 3), font=f(11), fill=DIM)

    def tx(dd):
        return px0 + (dd - (entry - 30)) / max(1, (exit_ + 30) - (entry - 30)) * pw

    def ty(vv):
        return py0 + ph - (vv - lo) / (hi - lo) * ph

    # 每个弯的 apex 位置（各圈）
    apexes = []
    for li, lap in enumerate(laps):
        seg = [p for p in lap["pts"] if entry - 30 <= p["d"] <= exit_ + 30 and p.get("v") is not None]
        if not seg:
            continue
        pts_px = [(tx(p["d"]), ty(p["v"])) for p in seg]
        for i in range(1, len(pts_px)):
            d.line([pts_px[i - 1], pts_px[i]], fill=COLORS[li % 3], width=2)
        apex = min(seg, key=lambda p: p["v"])
        apexes.append((li, apex))
        d.ellipse([tx(apex["d"]) - 3, ty(apex["v"]) - 3, tx(apex["d"]) + 3, ty(apex["v"]) + 3],
                  fill=COLORS[li % 3])
        # 刹车点：第一个 brake > 0.5 的点
        brk = [p for p in seg if (p.get("brk") or 0) > 0.5]
        if brk:
            d.line([(tx(brk[0]["d"]), py0 + ph - 4), (tx(brk[0]["d"]), py0 + ph)],
                   fill=(220, 90, 90), width=2)

    # 底部：各圈 apex 速度
    texts = []
    for li, apex in apexes:
        texts.append("L%d %d" % (laps[li]["n"], apex["v"]))
    d.text((x + 10, y + h - 18), "  ".join(texts), font=f(13), fill=WHITE)
    # 极差
    av = [a["v"] for _, a in apexes]
    if len(av) >= 2:
        spread = max(av) - min(av)
        col = (230, 120, 90) if spread >= 12 else DIM
        d.text((x + w - 52, y + h - 18), "Δ%d" % spread, font=f(13, True), fill=col)


def main():
    if len(sys.argv) < 3:
        print("用法: python scripts/make_corner_detail.py <track_key> <frames_xxx.jsonl> [输出]")
        return 1
    key = sys.argv[1]
    path = sys.argv[2]
    track = T.TRACKS.get(key)
    if not track:
        print("没有这条赛道:", key)
        return 1
    laps, sess = load_laps(path)
    if not laps:
        print("切不出完整圈")
        return 1
    best_ms = min(l["ms"] for l in laps if l["ms"])
    print("赛道: %s  圈数: %d  最快: %.3f" % (track["name"], len(laps), best_ms / 1000))

    corners = track["detected_corners"]
    n = len(corners)
    cols = 4 if n > 12 else 3
    rows = (n + cols - 1) // cols
    W, H = 1760, 220 + rows * 250
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # 背景斜线
    for i in range(-H, W, 130):
        d.line([(i, 0), (i + H, H)], fill=(19, 25, 42), width=2)

    d.text((60, 40), "%s · 逐弯细节对比（%d 圈）" % (track["name"], len(laps)), font=f(40, True), fill=WHITE)
    d.text((64, 98), "速度曲线三圈叠加；圆点=apex，底部红线=刹车点；Δ=各圈 apex 极差（km/h）",
           font=f(19), fill=DIM)
    # 图例
    for li in range(len(laps)):
        lx = W - 360 + li * 110
        d.line([(lx, 52), (lx + 26, 52)], fill=COLORS[li % 3], width=3)
        d.text((lx + 32, 42), "L%d %s" % (laps[li]["n"], E.fmt_ms(laps[li]["ms"]) if hasattr(E, "fmt_ms") else ""),
               font=f(16), fill=WHITE)

    pw, ph = 410, 220
    for i, c in enumerate(corners):
        cx = 60 + (i % cols) * (pw + 18)
        cy = 150 + (i // cols) * (ph + 22)
        draw_panel(img, d, cx, cy, pw, ph, c["no"], c.get("name") or "", c["dir"],
                   None, None, laps, c["entry_m"], c["exit_m"], best_ms)

    outs = []
    for base in (DESK, DOCS):
        if os.path.isdir(base):
            p = os.path.join(base, "%s-corners-detail.png" % key)
            img.save(p)
            outs.append(p)
    for p in outs:
        print("已保存:", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
