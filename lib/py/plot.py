"""F1 25 速度曲线图 + 弯道拆解（PIL 绘制，无 matplotlib）。

用法: python plot.py [frames_xxx.jsonl]
输出: plots/speed_<ts>.png, plots/pedals_<ts>.png, corners_<ts>.md
"""
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from laps import cut_laps, fmt, load

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FONT = r"C:\Windows\Fonts\msyh.ttc"
if not os.path.exists(FONT):
    FONT = r"C:\Windows\Fonts\simhei.ttf"

TRACKS = {0: "Melbourne", 1: "Shanghai", 2: "Bahrain", 3: "Jeddah", 4: "Imola", 5: "Monza",
          6: "Monaco", 7: "Silverstone", 8: "Spa", 9: "Suzuka", 10: "Zandvoort", 11: "Austin",
          12: "Mexico", 13: "Brazil", 14: "Baku", 15: "Las Vegas", 16: "Qatar", 17: "Austria",
          18: "Hungary", 19: "Singapore", 20: "Spain", 21: "Canada", 22: "France", 23: "Netherlands",
          24: "USA", 25: "Abu Dhabi", 26: "Miami", 27: "Portugal", 28: "Saudi", 29: "Mugello"}
COLORS = [(60, 120, 255), (255, 110, 60), (40, 180, 120), (200, 90, 220), (230, 180, 40), (120, 120, 120)]


def draw_speed(laps, title, out_path):
    W, H = 1600, 800
    L, R, T, B = 90, 40, 70, 70
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f13 = ImageFont.truetype(FONT, 20)
    f11 = ImageFont.truetype(FONT, 15)
    d.text((L, 20), title, font=f13, fill=(20, 20, 20))

    # 横轴按「圈内时间」对齐：以每圈真实起点（end - lap_ms）为 0，缺开头的圈曲线自然短一截
    max_t = max(l["lap_ms"] for l in laps) / 1000.0
    max_v = 360

    def X(t, t0):
        return L + (t - t0) / max_t * (W - L - R)

    def Y(v):
        return H - B - v / max_v * (H - T - B)

    # 网格
    for v in range(0, 361, 60):
        y = Y(v)
        d.line([(L, y), (W - R, y)], fill=(230, 230, 230))
        d.text((L - 45, y - 8), str(v), font=f11, fill=(120, 120, 120))
    for t in range(0, int(max_t) + 1, 10):
        x = L + t / max_t * (W - L - R)
        d.line([(x, T), (x, H - B)], fill=(240, 240, 240))
        d.text((x - 10, H - B + 8), str(t), font=f11, fill=(120, 120, 120))
    d.text((W - 260, H - 40), "圈内时间 (s) / 速度 (km/h)", font=f11, fill=(120, 120, 120))

    best = min(laps, key=lambda l: l["lap_ms"]) if any(l["lap_ms"] for l in laps) else laps[0]
    for i, l in enumerate(laps):
        fr = l["fr"]
        t0 = l["start"]
        pts = [(X(f["st"], t0), Y(f["speed"])) for f in fr if f["speed"] <= max_v]
        if len(pts) < 2:
            continue
        color = COLORS[i % len(COLORS)]
        width = 3 if l is best else 1
        d.line(pts, fill=color, width=width)
        label = f"L{l['n']} {fmt(l['lap_ms'])}" + (" ★" if l is best else "")
        if not l.get("full", True):
            label += " (缺开头)"
        d.text((W - 240 + (i % 2) * 0, 55 + i * 22), label, font=f11, fill=color)

    img.save(out_path)
    return out_path


def draw_pedals(lap, title, out_path):
    W, H = 1600, 700
    L, R, T, B = 90, 40, 70, 70
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f13 = ImageFont.truetype(FONT, 20)
    f11 = ImageFont.truetype(FONT, 15)
    d.text((L, 20), title, font=f13, fill=(20, 20, 20))
    fr = lap["fr"]
    t0 = fr[0]["st"]
    dur = fr[-1]["st"] - t0

    def X(t):
        return L + (t - t0) / dur * (W - L - R)

    def Y(p):
        return H - B - p / 100 * (H - T - B)

    for p in range(0, 101, 20):
        y = Y(p)
        d.line([(L, y), (W - R, y)], fill=(232, 232, 232))
        d.text((L - 40, y - 8), str(p), font=f11, fill=(120, 120, 120))
    for t in range(0, int(dur) + 1, 10):
        x = X(t0 + t)
        d.line([(x, T), (x, H - B)], fill=(244, 244, 244))
        d.text((x - 10, H - B + 8), str(t), font=f11, fill=(120, 120, 120))

    thr = [(X(f["st"]), Y(f["throttle"])) for f in fr]
    brk = [(X(f["st"]), Y(f["brake"])) for f in fr]
    d.line(thr, fill=(40, 150, 60), width=2)
    d.line(brk, fill=(200, 40, 40), width=2)
    d.text((W - 260, 55), "绿=油门  红=刹车", font=f11, fill=(80, 80, 80))
    img.save(out_path)
    return out_path


def corners_of(lap):
    fr = lap["fr"]
    t0 = fr[0]["st"]
    n = len(fr)
    win = 10
    cand = []
    for i in range(win, n - win):
        window = [fr[j]["speed"] for j in range(i - win, i + win + 1)]
        s = fr[i]["speed"]
        if s > min(window):
            continue
        if max(window) - s < 8:
            continue
        cand.append(i)
    merged = []
    for i in cand:
        if merged and i - merged[-1] <= 25:
            if fr[i]["speed"] < fr[merged[-1]]["speed"]:
                merged[-1] = i
        else:
            merged.append(i)
    out = []
    for k, i in enumerate(merged, 1):
        lo, hi = max(0, i - 90), min(n, i + 90)
        out.append({
            "no": k, "t": round(fr[i]["st"] - t0, 1), "apex": fr[i]["speed"],
            "entry": max(f["speed"] for f in fr[lo:i]) if i > lo else fr[i]["speed"],
            "exit": max(f["speed"] for f in fr[i:hi]) if hi > i else fr[i]["speed"],
            "gear": fr[i]["gear"],
        })
    return out


def main():
    here = os.environ.get("SIM_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
    # 数据就落在 <数据目录>/frames_*.jsonl，别再往下找 f1data 那一层（旧目录结构，早没了）
    pattern = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "frames_*.jsonl")
    files = [f for f in glob.glob(pattern) if os.path.getsize(f) > 20000]
    if not files:
        print(f"没找到数据（找的是 {pattern}）")
        return 1
    # 按修改时间取最新一份，不是按体积
    path = max(files, key=os.path.getmtime)
    frames, laps, sess, flashbacks = load(path)
    laps_out = cut_laps(frames, laps)
    if not laps_out:
        print("切不出完整圈")
        return 1
    track = TRACKS.get(sess.get("trackId", -1), "?")
    ts = os.path.basename(path).replace("frames_", "").replace(".jsonl", "")
    plots = os.path.join(here, "plots")
    os.makedirs(plots, exist_ok=True)

    p1 = draw_speed(laps_out, f"{track} · 速度曲线（{len(laps_out)} 圈）", os.path.join(plots, f"speed_{ts}.png"))
    best = min((l for l in laps_out if l["lap_ms"]), key=lambda l: l["lap_ms"], default=laps_out[0])
    p2 = draw_pedals(best, f"{track} · 最快圈 {fmt(best['lap_ms'])} 油门/刹车", os.path.join(plots, f"pedals_{ts}.png"))

    cs = corners_of(best)
    lines = [f"# {track} · 弯道拆解（最快圈 {fmt(best['lap_ms'])}）\n",
             "| 弯 | 圈内秒 | apex | 入弯最高 | 出弯最高 | 档位 |", "|---|---|---|---|---|---|"]
    for c in cs:
        lines.append(f"| {c['no']} | {c['t']} | {c['apex']} | {c['entry']} | {c['exit']} | {c['gear']} |")
    md = os.path.join(here, f"corners_{ts}.md")
    open(md, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print("圈数:", len(laps_out), "最快:", fmt(best["lap_ms"]))
    if flashbacks:
        print(f"回退: {len(flashbacks)} 次，已按最终时间线去重")
    print("图1:", p1)
    print("图2:", p2)
    print("弯道:", len(cs), "→", md)
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    sys.exit(main())
