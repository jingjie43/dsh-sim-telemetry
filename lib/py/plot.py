"""F1 25 速度曲线图 + 弯道拆解（PIL 绘制，无 matplotlib）。

用法: python telemetry_plot.py [frames_xxx.jsonl]
输出: plots/speed_<ts>.png, plots/pedals_<ts>.png, corners_<ts>.md
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

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


def fmt(ms):
    if not ms:
        return "-"
    m, rem = divmod(int(ms), 60000)
    s, msec = divmod(rem, 1000)
    return f"{m}:{s:02d}.{msec:03d}"


def load(path):
    frames, laps, sess = [], [], {}
    for line in open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("id") == 6:
            frames.append(r)
        elif r.get("id") == 2:
            laps.append(r)
        elif r.get("id") == 1 and not sess:
            sess = r
    return frames, laps, sess


def cut_laps(frames, laps):
    """用 currentLapTime 归零作为圈边界，返回 [{n, lap_ms, fr}]"""
    marks = []
    prev = None
    for r in laps:
        c = r.get("curLap", 0)
        if prev is not None and c < prev - 500:
            marks.append(r["st"])
        prev = c
    # 用 lastLap 补圈速
    lts = []
    seen = None
    for r in laps:
        v = r.get("lastLap", 0)
        if v and v != seen:
            seen = v
            lts.append(v)
    laps_out = []
    for i, edge in enumerate(marks):
        nxt = marks[i + 1] if i + 1 < len(marks) else edge + 100
        fr = [f for f in frames if edge - 0.2 <= f["st"] < nxt - 0.2]
        if len(fr) < 500:
            continue
        lap_ms = lts[i + 1] if i + 1 < len(lts) else (lts[-1] if lts else 0)
        laps_out.append({"n": len(laps_out) + 1, "lap_ms": lap_ms, "fr": fr})
    # 用帧数校验（20Hz）
    laps_out = [l for l in laps_out if 900 <= len(l["fr"]) <= 2500]
    return laps_out


def draw_speed(laps, title, out_path):
    W, H = 1600, 800
    L, R, T, B = 90, 40, 70, 70
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f13 = ImageFont.truetype(FONT, 20)
    f11 = ImageFont.truetype(FONT, 15)
    d.text((L, 20), title, font=f13, fill=(20, 20, 20))

    max_t = max(l["fr"][-1]["st"] - l["fr"][0]["st"] for l in laps)
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
        t0 = fr[0]["st"]
        pts = [(X(f["st"], t0), Y(f["speed"])) for f in fr if f["speed"] <= max_v]
        if len(pts) < 2:
            continue
        color = COLORS[i % len(COLORS)]
        width = 3 if l is best else 1
        d.line(pts, fill=color, width=width)
        label = f"L{l['n']} {fmt(l['lap_ms'])}" + (" ★" if l is best else "")
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
    pattern = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "f1data", "frames_*.jsonl")
    files = [f for f in glob.glob(pattern) if os.path.getsize(f) > 100000]
    files.sort(key=os.path.getsize)
    if not files:
        print("没找到数据")
        return 1
    path = files[-1]
    frames, laps, sess = load(path)
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
    print("图1:", p1)
    print("图2:", p2)
    print("弯道:", len(cs), "→", md)
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    sys.exit(main())
