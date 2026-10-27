# -*- coding: utf-8 -*-
"""0.2.3 未来规划图（Roadmap，1920x1080）

三段式：
  左  已完成 0.2.3  —— 比赛工程师
  中  下一步 0.2.4  —— 按性价比排的 5 项
  右  更远          —— 多游戏 + 长期
  底  愿景一句话
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (11, 16, 32)
CARD = (20, 28, 46)
LINE = (40, 52, 78)
ACCENT = (79, 209, 197)
BLUE = (96, 165, 250)
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


def f(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def check(d, x, y, size=22, color=ACCENT, width=5):
    d.line([(x, y + size * 0.55), (x + size * 0.38, y + size)], fill=color, width=width)
    d.line([(x + size * 0.38, y + size), (x + size, y)], fill=color, width=width)


def card(d, x, y, w, h, title, tag, color):
    d.rounded_rectangle([x, y, x + w, y + h], radius=22, fill=CARD, outline=color, width=3)
    d.text((x + 38, y + 30), title, font=f(38, True), fill=color)
    d.text((x + 38, y + 82), tag, font=f(22), fill=DIM)
    d.line([(x + 38, y + 120), (x + w - 38, y + 120)], fill=LINE, width=2)


def item(d, x, y, w, main, sub, color=WHITE, marker=None, sub_color=None):
    """一行：标记 + 主文 + 小字说明。"""
    if marker == "check":
        check(d, x, y + 6, 22, color, 5)
        tx = x + 42
    else:
        d.text((x, y), marker or "·", font=f(30, True), fill=color)
        tx = x + 34
    d.text((tx, y - 2), main, font=f(30, True), fill=color)
    d.text((tx, y + 38), sub, font=f(21), fill=sub_color or DIM)


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for i in range(-H, W, 120):
        d.line([(i, 0), (i + H, H)], fill=(17, 23, 38), width=2)
    for y in range(0, 5):
        d.line([(0, 8 + y), (W, 8 + y)], fill=(44, 76, 118))

    # 标题
    d.text((80, 56), "未来规划", font=f(64, True), fill=WHITE)
    d.text((84, 138), "ROADMAP · 0.2.3 之后", font=f(30, True), fill=ACCENT)
    d.text((W - 520, 110), "dsh-sim-telemetry", font=f(28, True), fill=DIM)

    y0, ch = 210, 620

    # 卡片 1：已完成
    x1, w1 = 80, 500
    card(d, x1, y0, w1, ch, "已完成 0.2.3", "比赛工程师 · 已发布", ACCENT)
    items1 = [
        ("曲率找弯", "银石 18 个弯，一个不差"),
        ("失误检测", "速度断崖 + 横向 G 塌陷"),
        ("轨迹诊断图", "实跑轨迹 + 弯位编号"),
        ("方向性建议", "「方向 多打 −0.36」"),
        ("多圈距离对齐", "按赛道同一米对齐"),
    ]
    yy = y0 + 150
    for i, (m, s) in enumerate(items1):
        item(d, x1 + 38, yy, w1 - 76, m, s, WHITE, "check", (170, 182, 200))
        yy += 92

    # 卡片 2：下一步
    x2, w2 = 628, 620
    card(d, x2, y0, w2, ch, "下一步 0.2.4", "按性价比排序 · 已开工优先做", GOLD)
    items2 = [
        ("理想圈", "各段最好拼起来，看理论上能跑多少", "★"),
        ("分段 S1/S2/S3", "哪一段慢了；无效圈不污染对比", "②"),
        ("出界检测", "已用你的实跑数据验证可行", "③"),
        ("23 条赛道弯位", "跑过就能校准，一条条来", "④"),
        ("AI 车手对比", "AI 在这个弯比你快多少", "⑤"),
    ]
    yy = y0 + 146
    for i, (m, s, mk) in enumerate(items2):
        col = GOLD if i == 0 else WHITE
        item(d, x2 + 38, yy, w2 - 76, m, s, col, mk, (170, 182, 200) if i else GOLD)
        yy += 92

    # 卡片 3：更远
    x3, w3 = 1296, 544
    card(d, x3, y0, w3, ch, "更远", "多游戏 + 长期", BLUE)
    items3 = [
        ("神力科莎竞速 ACC", "采集适配器，分析层共用"),
        ("神力科莎 AC", "同上"),
        ("更多大众赛车", "视需求"),
        ("圈速进步曲线", "跨场次记录，看得到进步"),
        ("实时面板", "已采圈数 / 当前速度"),
    ]
    yy = y0 + 150
    for m, s in items3:
        item(d, x3 + 38, yy, w3 - 76, m, s, WHITE, "·", (170, 182, 200))
        yy += 92

    # 底部愿景条
    by = 880
    d.rounded_rectangle([80, by, W - 80, by + 132], radius=20, fill=(18, 30, 48), outline=GOLD, width=2)
    d.text((112, by + 26), "让每个人都有一个比赛工程师", font=f(44, True), fill=GOLD)
    d.text((112, by + 86), "不用装专业软件、不用懂遥测，跑完圈就知道哪里慢了、怎么改。", font=f(24), fill=(200, 210, 226))
    d.text((W - 640, by + 30), "github.com/jingjie43/dsh-sim-telemetry", font=f(24, True), fill=WHITE)
    d.text((W - 640, by + 74), "开源免费 · 欢迎 star / issue", font=f(22), fill=ACCENT)

    out = os.path.join(DOCS, "roadmap-0.2.3.png")
    img.save(out)
    return out


if __name__ == "__main__":
    print("已生成:", main())
