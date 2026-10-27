# -*- coding: utf-8 -*-
"""生成三圈成绩单（1920x1080 两张）：
  1. docs/session-20261026-overview.png  三圈总览 + 问题标注
  2. docs/session-20261026-corners.png   逐弯 apex 对比表

数据来自 frames_20261026_143303.jsonl（Silverstone，3 圈，无回退）
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (11, 16, 32)
CARD = (20, 28, 46)
HEAD = (28, 40, 60)
LINE = (40, 52, 78)
ACCENT = (79, 209, 197)
BLUE = (96, 165, 250)
WHITE = (235, 241, 250)
DIM = (140, 152, 172)
GOLD = (250, 204, 120)
RED = (248, 113, 113)
ORANGE = (251, 146, 60)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

LAPS = [
    ("L2", "1:32.311", "★ 最快", 324, 227, 66, 9, 5, "基准圈（第 4/5 弯最快）"),
    ("L1", "1:32.376", "+0.065", 324, 228, 67, 9, 5, "第 3/11 弯慢，第 6 弯跑宽"),
    ("L3", "1:32.800", "+0.489", 324, 226, 64, 9, 8, "第 17 弯出界 + 甩尾"),
]

CORNERS = [
    (1, "R", 282, 282, 281, "", None),
    (2, "L", 282, 283, 281, "", None),
    (3, "L", 266, 250, 262, "L2 apex 最低，但整体最快", None),
    (4, "R", 94, 106, 92, "L2 快 12~14 ★", ACCENT),
    (5, "L", 86, 95, 86, "L2 快 9 ★", ACCENT),
    (6, "L", 183, 179, 180, "L1 入口慢 17、跑宽 5.1m", ORANGE),
    (7, "L", 122, 136, 146, "L3 最快 +10", ACCENT),
    (8, "R", 123, 114, 111, "", None),
    (9, "R", 276, 274, 275, "", None),
    (10, "R", 275, 262, 262, "L1 最快 +13", None),
    (11, "R", 287, 282, 284, "L1 apex 最高，但段内慢 20", ORANGE),
    (12, "L", 247, 252, 249, "", None),
    (13, "R", 188, 177, 176, "", None),
    (14, "L", 202, 191, 188, "L1 跑宽 4.8m", ORANGE),
    (15, "R", 208, 215, 208, "L3 出口跑宽 6.4m", ORANGE),
    (16, "R", 206, 200, 189, "L3 apex 最低 −11", ORANGE),
    (17, "L", 79, 87, 88, "L3 出界 8.5m（三圈都跑宽）", RED),
    (18, "R", 140, 137, 136, "L3 入口慢 76 km/h", RED),
]


def f(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def background(d):
    for i in range(-H, W, 120):
        d.line([(i, 0), (i + H, H)], fill=(17, 23, 38), width=2)
    for y in range(0, 5):
        d.line([(0, 8 + y), (W, 8 + y)], fill=(44, 76, 118))


def cell(d, x, y, w, h, text, size=30, bold=False, color=WHITE,
         align="left", pad=18, bg=None):
    if bg:
        d.rectangle([x, y, x + w, y + h], fill=bg)
    tw = d.textlength(text, font=f(size, bold)) if text is not None else 0
    if align == "center":
        tx = x + (w - tw) / 2
    elif align == "right":
        tx = x + w - tw - pad
    else:
        tx = x + pad
    d.text((tx, y + (h - size * 1.45) / 2), text or "", font=f(size, bold), fill=color)


def make_overview():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d)

    d.text((80, 64), "Silverstone · 三圈成绩单", font=f(60, True), fill=WHITE)
    d.text((82, 146), "2026-10-26 · F1 25 · 3 圈 · 无回退 · 极速 324 km/h", font=f(28), fill=DIM)
    d.text((W - 460, 108), "dsh-sim-telemetry", font=f(30, True), fill=ACCENT)

    cols = [("圈次", 150), ("圈速", 240), ("与最快差", 210), ("极速", 150),
            ("均速", 150), ("全油门", 170), ("滑行", 150), ("问题标注", 570)]
    x0, y0, rh, hh = 80, 250, 92, 64
    # 表头
    x = x0
    d.rounded_rectangle([x0, y0, x0 + sum(c[1] for c in cols), y0 + hh + rh * 3 + 8],
                        radius=16, fill=CARD, outline=LINE, width=2)
    for name, w in cols:
        cell(d, x, y0, w, hh, name, 28, True, DIM, "center" if name != "问题标注" else "left", 18, HEAD)
        x += w
    # 数据行
    for ri, lap in enumerate(LAPS):
        y = y0 + hh + ri * rh
        n, t, gap, vmax, vavg, full, brk, coast, note = lap
        is_best = "★" in gap
        x = x0
        row_bg = (25, 36, 56) if ri % 2 == 0 else None
        if ri % 2 == 0:
            d.rectangle([x0 + 2, y, x0 + sum(c[1] for c in cols) - 2, y + rh], fill=(23, 33, 52))
        cell(d, x, y, 150, rh, n, 34, True, ACCENT if is_best else WHITE, "center", 18)
        x += 150
        cell(d, x, y, 240, rh, t, 38, True, GOLD if is_best else WHITE, "center", 18)
        x += 240
        cell(d, x, y, 210, rh, gap, 30, True, GOLD if is_best else (RED if gap == "+0.489" else WHITE), "center", 18)
        x += 210
        cell(d, x, y, 150, rh, str(vmax), 28, False, WHITE, "center", 8)
        x += 150
        cell(d, x, y, 150, rh, str(vavg), 28, False, WHITE, "center", 8)
        x += 150
        cell(d, x, y, 170, rh, "%d%%" % full, 28, False, WHITE, "center", 8)
        x += 170
        cell(d, x, y, 150, rh, "%d%%" % coast, 28, False, WHITE, "center", 8)
        x += 150
        cell(d, x, y, 570, rh, note, 27, False,
             RED if "出界" in note else (ORANGE if "跑宽" in note or "慢" in note else DIM), "left", 18)
    # 结论
    y = y0 + hh + rh * 3 + 40
    d.text((80, y), "结论", font=f(30, True), fill=ACCENT)
    d.text((80, y + 52), "三圈差 0.489 秒 —— 全部损失都出在第 15~18 弯那一段，前面 14 个弯三圈几乎一样。",
           font=f(36, True), fill=WHITE)
    y += 130
    d.text((80, y), "第 17 弯三圈都跑宽（4.1 / 4.7 / 8.5 米），L3 在那里四轮出白线，甩尾后 5710~5830 米",
           font=f(30), fill=(200, 210, 226))
    d.text((80, y + 46), "速度卡在 138~151（另两圈同段 167→223 一路加速），第 18 弯入口比最快圈慢 76 km/h。",
           font=f(30), fill=(200, 210, 226))
    y += 112
    d.line([(80, y), (W - 80, y)], fill=LINE, width=2)
    d.text((80, y + 22), "数据：frames_20261026_143303.jsonl · 弯位编号见轨迹诊断图", font=f(24), fill=DIM)
    d.text((W - 690, y + 22), "红=出界/事故   橙=走线或速度问题   青=亮点", font=f(24), fill=DIM)

    out = os.path.join(DOCS, "session-20261026-overview.png")
    img.save(out)
    return out


def make_corners():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d)

    d.text((80, 54), "逐弯 apex 速度对比（km/h）", font=f(52, True), fill=WHITE)
    d.text((82, 126), "银石 18 个弯 · 三圈同弯 apex 速度 · 标注 = 相对最快圈 L2 的问题",
           font=f(26), fill=DIM)

    cols = [("第N弯", 170), ("方向", 140), ("L1", 190), ("L2 ★", 190), ("L3", 190), ("标注", 900)]
    x0, y0, rh, hh = 80, 186, 42, 52
    total_w = sum(c[1] for c in cols)
    d.rounded_rectangle([x0, y0, x0 + total_w, y0 + hh + rh * len(CORNERS) + 4],
                        radius=14, fill=CARD, outline=LINE, width=2)
    x = x0
    for name, w in cols:
        cell(d, x, y0, w, hh, name, 26, True, DIM, "center" if name != "标注" else "left", 18, HEAD)
        x += w
    for ri, (no, dr, a, b, c, note, color) in enumerate(CORNERS):
        y = y0 + hh + ri * rh
        if ri % 2 == 0:
            d.rectangle([x0 + 2, y, x0 + total_w - 2, y + rh], fill=(23, 33, 52))
        x = x0
        cell(d, x, y, 170, rh, str(no), 25, True, WHITE if not color else color, "center", 8)
        x += 170
        cell(d, x, y, 140, rh, dr, 24, False, DIM, "center", 8)
        x += 140
        # L1 / L2 / L3：与最快（L2）差 >8 标橙
        for i, val in enumerate((a, b, c)):
            col = WHITE
            if i != 1:
                if val - b <= -15:
                    col = RED
                elif val - b <= -8:
                    col = ORANGE
                elif val - b >= 10:
                    col = ACCENT
            cell(d, x, y, 190, rh, str(val), 26, i == 1, col, "center", 8)
            x += 190
        cell(d, x, y, 900, rh, note, 23, False, color or DIM, "left", 18)

    out = os.path.join(DOCS, "session-20261026-corners.png")
    img.save(out)
    return out


if __name__ == "__main__":
    print("已生成:", make_overview())
    print("已生成:", make_corners())
