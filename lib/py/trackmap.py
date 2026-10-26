"""赛道轨迹诊断图：实跑轨迹 + 弯位编号 + 具体问题标注。

为什么需要它：
  报告说「第 4 弯」，用户光看数字不知道在哪。这张图画的是**他自己跑过的线**，
  形状一眼认得出，编号对上就落到了具体位置 —— 不需要弯名表，米数也不用记。

图上会标什么：
  - 红点：出过 spin / 失控的弯
  - 橙点：各圈差异大的弯（速度 / 方向盘 / 给油点）
  - 灰点：跑得比较一致的弯
  - 箭头：从结论框指向对应的弯心

用法: python trackmap.py [frames_xxx.jsonl]
输出: plots/track_<ts>.png
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.environ.get("SIM_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))

import engineer as E  # noqa: E402
import laps as L  # noqa: E402

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
if not os.path.exists(FONT_PATH):
    FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"

# 严重程度阈值
DV_APEX = 25        # 各圈 apex 差多少 km/h 算不稳
DSTEER = 0.15       # 方向盘峰值差多少算过火
DGAS = 30           # 出弯给油点差多少米算明显


def pick_data():
    files = [f for f in glob.glob(os.path.join(HERE, "frames_*.jsonl"))
             if os.path.getsize(f) > 20000]
    return max(files, key=os.path.getmtime) if files else None


def trajectory(best_lap, path):
    pts = []
    for line in open(path, encoding="utf-8"):
        if '"id": 0' not in line:
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if best_lap["start"] <= m.get("st", 0) <= best_lap["end"]:
            pts.append((m["st"], m["x"], m["z"]))
    pts.sort()
    return pts


def worst_note(row, best_idx):
    """挑最值得说的一句话，**带方向性**：多打/少打、晚/早，以及带符号的调整量。

    符号约定（表示「你该往哪调」）：
      -0.36 = 方向打多了 0.36，要**收**回来
      +0.15 = 方向打少了 0.15，要**加**上去
      -125m = 给油晚了 125 米，要**提前**
      +20m  = 给油早了 20 米，要**推后**
    """
    laps = row.get("laps") or []
    if len(laps) < 2 or best_idx >= len(laps) or not laps[best_idx]:
        return None, 0
    base = laps[best_idx]                 # 基准 = 最快圈
    cands = []
    for i, l in enumerate(laps):
        if i == best_idx or not l:
            continue
        # apex 速度
        if l.get("apex") and base.get("apex"):
            d = base["apex"] - l["apex"]          # 正 = 你慢
            if d >= DV_APEX:
                cands.append((d / DV_APEX, "apex 慢 %d km/h" % d, 3))
        # 方向盘峰值
        sp, bp = l.get("steer_peak"), base.get("steer_peak")
        if sp is not None and bp is not None:
            d = sp - bp                            # 正 = 你多打
            if abs(d) >= DSTEER:
                adj = -abs(d) if d > 0 else abs(d)
                cands.append((abs(d) / DSTEER,
                              "方向 %s %+.2f" % ("多打" if d > 0 else "少打", adj), 2))
        # 出弯给油点
        gd, bg = l.get("gas_d"), base.get("gas_d")
        if gd is not None and bg is not None:
            d = gd - bg                            # 正 = 你晚了
            if abs(d) >= DGAS:
                adj = -abs(d) if d > 0 else abs(d)
                cands.append((abs(d) / DGAS,
                              "给油 %s %+.0f m" % ("晚" if d > 0 else "早", adj), 2))
    if not cands:
        return None, 0
    cands.sort(reverse=True)
    return cands[0][1], cands[0][2]


def _overlap(a, b):
    """两个矩形是否重叠（x1,y1,x2,y2）。"""
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def draw(traj, corners, rows, incidents, out_path, track_name="?", best_idx=0):
    W, H = 1500, 1150
    M = 100
    xs = [t[1] for t in traj]
    zs = [t[2] for t in traj]
    minx, maxx, minz, maxz = min(xs), max(xs), min(zs), max(zs)
    span = max(maxx - minx, maxz - minz, 1)
    cx, cz = (minx + maxx) / 2, (minz + maxz) / 2

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f24 = ImageFont.truetype(FONT_PATH, 24)
    f16 = ImageFont.truetype(FONT_PATH, 16)
    f14 = ImageFont.truetype(FONT_PATH, 14)

    def P(x, z):
        return (W / 2 + (x - cx) / span * (W - 2 * M),
                H / 2 - (z - cz) / span * (H - 2 * M) * 0.92)

    line = [P(t[1], t[2]) for t in traj]
    if len(line) < 3:
        return None
    d.line(line, fill=(40, 40, 40), width=7)
    d.line(line, fill=(232, 232, 232), width=3)

    cum = [0.0]
    for i in range(1, len(traj)):
        dx = traj[i][1] - traj[i - 1][1]
        dz = traj[i][2] - traj[i - 1][2]
        cum.append(cum[-1] + (dx * dx + dz * dz) ** 0.5)
    total = cum[-1] or 1.0
    norm = [c / total * 5890.0 for c in cum]

    def at_dist(dm):
        idx = min(range(len(norm)), key=lambda i: abs(norm[i] - dm))
        return P(traj[idx][1], traj[idx][2])

    spin_at = incidents[0]["at_d"] if incidents else None
    notes = 0
    placed = []                     # 已放置的文字框，用于避让
    # 先画点和编号
    for k, c in enumerate(corners, 1):
        px, py = at_dist(c["apex_d"])
        is_spin = spin_at is not None and abs(c["apex_d"] - spin_at) < 120
        row = rows[k - 1] if k - 1 < len(rows) else None
        note, sev = worst_note(row, best_idx) if row else (None, 0)
        if is_spin:
            color = (215, 30, 30)
        elif sev >= 2:
            color = (240, 120, 40)
        else:
            color = (150, 150, 150)
        d.ellipse([px - 12, py - 12, px + 12, py + 12], fill=color, outline="white", width=2)
        d.text((px - 6, py - 8), str(k), font=f14, fill="white")

        # 标注：只标 spin 和严重度≥2 的弯，最多 5 个，避免图被文字淹没
        text = "方向反打 + 松油 → spin" if is_spin else note
        if text and notes < 5:
            notes += 1
            tw = d.textlength(text, font=f14)
            bx = px + 20 if px < W * 0.55 else px - tw - 30
            by = py - 10
            # 避让：和已放的框重叠就往上挪，最多挪 24 次
            for _ in range(24):
                box = (bx - 5, by - 3, bx + tw + 7, by + 21)
                if not any(_overlap(box, b) for b in placed):
                    break
                by -= 27
            placed.append((bx - 5, by - 3, bx + tw + 7, by + 21))
            d.rectangle([bx - 5, by - 3, bx + tw + 7, by + 21],
                        fill=(255, 245, 235), outline=color)
            d.text((bx, by), text, font=f14, fill=(150, 30, 20))
            # 箭头：从框边缘指向弯心
            ax = bx - 2 if bx < px else bx + tw + 4
            ay = by + 9
            d.line([(ax, ay), (px, py)], fill=color, width=1)
            d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=color)

    p0 = P(traj[0][1], traj[0][2])
    d.ellipse([p0[0] - 9, p0[1] - 9, p0[0] + 9, p0[1] + 9], fill=(0, 110, 240))
    d.text((p0[0] + 13, p0[1] - 12), "起点", font=f14, fill=(0, 110, 240))

    d.text((M, 24), "%s · 弯位诊断图" % track_name, font=f24, fill=(20, 20, 20))
    d.text((M, 58), "红=失控  橙=各圈差异大  灰=稳定；框里是具体差多少", font=f16, fill=(110, 110, 110))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    return out_path, notes


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else pick_data()
    if not path:
        print("没有可画的数据")
        return 1
    result = E.analyse(path)
    if not result["laps"]:
        print("没有完整圈，画不了轨迹")
        return 1

    frames, laps_pkts, sess, fb = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    best = min(lap_objs, key=lambda x: x["lap_ms"])
    traj = trajectory(best, path)
    if len(traj) < 50:
        print("Motion 数据不足（没采到坐标），跳过轨迹图")
        return 0

    import tracks as T
    tinfo = T.get_by_track_id(sess.get("trackId", -1))
    name = tinfo["name"] if tinfo else "?"

    ts = os.path.basename(path).replace("frames_", "").replace(".jsonl", "")
    out = os.path.join(HERE, "plots", "track_%s.png" % ts)
    p, notes = draw(traj, result["corners"], result.get("corner_rows") or [],
                    result.get("incidents") or [], out, name,
                    best_idx=result.get("best_index", 0))
    if p:
        print("轨迹诊断图:", p)
        print("弯位:", len(result["corners"]), "个 · 标出的问题:", notes, "处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
