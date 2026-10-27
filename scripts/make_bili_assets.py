# -*- coding: utf-8 -*-
"""生成 B站 0.2.3 发布物料：封面图 + 视频示意图（1920x1080）。

产出：
  docs/cover-0.2.3.png            B站 封面（16:9）
  docs/video-assets/01-data-fields.png   数据字段对比（视频第二段①）
  docs/video-assets/02-corner-method.png 弯道识别方法对比（视频第二段②）

用法：python scripts/make_bili_assets.py
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1920, 1080
BG = (11, 16, 32)
BG2 = (20, 28, 46)
LINE = (40, 52, 78)
ACCENT = (79, 209, 197)      # 青
BLUE = (96, 165, 250)        # 蓝
WHITE = (235, 241, 250)
DIM = (140, 152, 172)
GOLD = (250, 204, 120)
RED = (248, 113, 113)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
# 轨迹诊断图候选（取最新的那份；找不到就退回纯排版封面）
TRACK_CANDIDATES = [
    os.path.expanduser(r"~\.dsh\sim-telemetry\plots\track_20261026_131106.png"),
    os.path.expanduser(r"~\.dsh\sim-telemetry\plots\track_20261026_132052.png"),
]


def f(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def bg(img, d):
    """深色背景 + 斜线装饰 + 顶部光条。"""
    for i in range(-H, W, 120):
        d.line([(i, 0), (i + H, H)], fill=(17, 23, 38), width=2)
    for y in range(0, 5):
        d.line([(0, 8 + y), (W, 8 + y)], fill=(44, 76, 118))


def fit_cover(path, box_w, box_h, crop_top=0):
    """等比缩放放进 box，返回 (图, w, h)。crop_top 用来裁掉源图自带的标题区。"""
    im = Image.open(path).convert("RGB")
    im = ImageOps.exif_transpose(im)
    if crop_top:
        im = im.crop((0, crop_top, im.width, im.height))
    r = min(box_w / im.width, box_h / im.height)
    return im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)


def draw_check(d, x, y, size=26, color=ACCENT, width=6):
    """画一个勾（不用字体里的 ✓，避免字形缺失变豆腐块）。"""
    d.line([(x, y + size * 0.55), (x + size * 0.38, y + size)], fill=color, width=width)
    d.line([(x + size * 0.38, y + size), (x + size, y)], fill=color, width=width)


def rounded_paste(canvas, im, xy, radius=24):
    """把 im 贴到 canvas 的 xy，带圆角。"""
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    canvas.paste(im, xy, mask)


# ---------------------------------------------------------------- 封面
def make_cover():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(img, d)

    # 左区：标题
    d.text((100, 96), "dsh-sim-telemetry  ·  F1 25 遥测插件", font=f(28), fill=DIM)

    d.text((96, 160), "0.2.3", font=f(168, True), fill=ACCENT)
    d.text((520, 168), "更新", font=f(150, True), fill=WHITE)

    d.text((100, 386), "它会告诉你第几弯出问题了", font=f(76, True), fill=WHITE)

    d.line([(100, 512), (980, 512)], fill=LINE, width=3)

    points = [
        "曲率找弯 · 银石 18 个弯，一个不差",
        "自动检测 spin，正常刹车不误报",
        "轨迹诊断图 · 弯位直接标编号",
    ]
    y = 556
    for p in points:
        draw_check(d, 100, y + 8, 30, ACCENT, 6)
        d.text((156, y), p, font=f(38), fill=(205, 216, 232))
        y += 72

    # 左下角：角标 + 仓库
    d.text((100, 900), "比赛工程师  ·  第二期", font=f(34, True), fill=GOLD)
    d.text((100, 962), "github.com/jingjie43/dsh-sim-telemetry", font=f(26), fill=DIM)

    # 右区：轨迹诊断图白卡
    track = next((p for p in TRACK_CANDIDATES if os.path.exists(p)), None)
    cx, cy, cw, ch = 1010, 130, 830, 820
    d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=30, fill=(247, 249, 252))
    if track:
        im = fit_cover(track, cw - 56, ch - 110, crop_top=92)
        rounded_paste(img, im, (cx + (cw - im.width) // 2, cy + 74 + (ch - 74 - im.height) // 2), 12)
        d.text((cx + 40, cy + 24), "Silverstone · 弯位诊断图", font=f(28, True), fill=(30, 40, 60))
    else:
        d.text((cx + 60, cy + 380), "（轨迹图缺失）", font=f(40), fill=(120, 130, 150))

    out = os.path.join(DOCS, "cover-0.2.3.png")
    img.save(out)
    return out


# ---------------------------------------------------------------- 字段对比
def make_fields():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(img, d)

    d.text((96, 84), "数据更全了", font=f(92, True), fill=WHITE)
    d.text((100, 208), "0.2.3 新增 4 类遥测字段 —— 以前只知道快慢，现在知道车在干什么", font=f(36), fill=DIM)

    # 旧版卡
    lx, ly, lw, lh = 96, 320, 620, 560
    d.rounded_rectangle([lx, ly, lx + lw, ly + lh], radius=22, fill=BG2, outline=LINE, width=2)
    d.text((lx + 44, ly + 36), "0.2.2", font=f(30, True), fill=DIM)
    d.text((lx + 44, ly + 84), "当时只有这些", font=f(34), fill=DIM)
    old = ["速度", "油门", "刹车", "档位"]
    y = ly + 180
    for it in old:
        d.text((lx + 44, y), "·  " + it, font=f(52), fill=(160, 172, 190))
        y += 90

    # 箭头
    ax = 730
    d.line([(ax, 600), (ax + 70, 600)], fill=(70, 85, 115), width=6)
    d.polygon([(ax + 70, 600), (ax + 48, 586), (ax + 48, 614)], fill=(70, 85, 115))

    # 新版卡
    rx, ry, rw, rh = 830, 320, 990, 560
    d.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=22, fill=(18, 30, 48), outline=ACCENT, width=3)
    d.text((rx + 44, ry + 36), "0.2.3", font=f(30, True), fill=ACCENT)
    d.text((rx + 44, ry + 84), "多了四样东西", font=f(34), fill=WHITE)
    new = ["方向盘转角", "三轴 G 力", "世界坐标", "车头朝向"]
    y = ry + 168
    for it in new:
        d.rounded_rectangle([rx + 40, y - 6, rx + rw - 44, y + 74], radius=12, fill=(25, 42, 62))
        d.text((rx + 62, y + 4), "+", font=f(38, True), fill=ACCENT)
        d.text((rx + 112, y + 2), it, font=f(50, True), fill=WHITE)
        y += 88

    d.text((96, 940), "→ 算得出弯道曲率 · 画得出你跑的轨迹 · 认得出打滑失控", font=f(44, True), fill=GOLD)

    os.makedirs(os.path.join(DOCS, "video-assets"), exist_ok=True)
    out = os.path.join(DOCS, "video-assets", "01-data-fields.png")
    img.save(out)
    return out


# ---------------------------------------------------------------- 找弯方法
def make_corner():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(img, d)

    d.text((96, 84), "弯道识别：从「速度下降」到「曲率」", font=f(76, True), fill=WHITE)
    d.text((100, 190), "同一个 S 弯，以前会被当成一个弯", font=f(36), fill=DIM)

    # 旧卡
    lx, ly, lw, lh = 96, 290, 830, 600
    d.rounded_rectangle([lx, ly, lx + lw, ly + lh], radius=22, fill=BG2, outline=LINE, width=2)
    d.text((lx + 44, ly + 32), "旧方法", font=f(30, True), fill=DIM)
    d.text((lx + 44, ly + 84), "按速度下降找弯", font=f(52, True), fill=(190, 200, 215))
    olds = [
        "· S 弯会粘成一段",
        "· 高速全油弯找不到",
        "· 弯数在 14~20 个之间飘",
    ]
    y = ly + 190
    for it in olds:
        d.text((lx + 44, y), it, font=f(38), fill=(150, 162, 182))
        y += 82
    d.text((lx + 44, ly + 470), "结果：说不清算第几个弯", font=f(34, True), fill=RED)

    # 新卡
    rx, ry, rw, rh = 990, 290, 830, 600
    d.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=22, fill=(18, 30, 48), outline=ACCENT, width=3)
    d.text((rx + 44, ry + 32), "0.2.3", font=f(30, True), fill=ACCENT)
    d.text((rx + 44, ry + 84), "按曲率 κ = dψ/ds", font=f(52, True), fill=WHITE)
    news = [
        "· 弯就是弯，跟快慢无关",
        "· 保留左/右符号，S 弯天然断开",
        "· 数量直接对齐官方弯数",
    ]
    y = ry + 190
    for it in news:
        d.text((rx + 44, y), it, font=f(38), fill=(205, 216, 232))
        y += 82
    d.text((rx + 44, ry + 470), "银石 18 个弯，一个不差", font=f(40, True), fill=GOLD)

    d.text((96, 970), "多圈平均曲率：单圈走线差异和 yaw 噪声互相抵消", font=f(38), fill=DIM)

    os.makedirs(os.path.join(DOCS, "video-assets"), exist_ok=True)
    out = os.path.join(DOCS, "video-assets", "02-corner-method.png")
    img.save(out)
    return out


if __name__ == "__main__":
    print("已生成:", make_cover())
    print("已生成:", make_fields())
    print("已生成:", make_corner())
