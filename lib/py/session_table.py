# -*- coding: utf-8 -*-
"""三圈成绩单 + 逐弯 apex 对比（数据驱动，任意赛道/任意次数）。

用法:
    python session_table.py <frames_XXX.jsonl> [--out <dir>]

输出:
    session_<ts>-overview.png   三圈成绩单（圈速/极差/极速/均速/全油/滑行 + 问题标注）
    session_<ts>-corners.png    逐弯 apex 速度对比（每弯每圈 + 标注）
"""
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engineer as E  # noqa: E402
import tracks as T    # noqa: E402

W, H = 1920, 1080
BG = (11, 16, 32)
CARD = (20, 28, 46)
HEAD = (28, 40, 60)
LINE = (40, 52, 78)
ACCENT = (79, 209, 197)
WHITE = (235, 241, 250)
DIM = (140, 152, 172)
GOLD = (250, 204, 120)
RED = (248, 113, 113)
ORANGE = (251, 146, 60)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT

DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
PLOTS = os.path.join(DATA, "plots")
DESK = os.path.join(os.path.expanduser("~"), "Desktop")


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
    tw = d.textlength(str(text), font=f(size, bold)) if text is not None else 0
    if align == "center":
        tx = x + (w - tw) / 2
    elif align == "right":
        tx = x + w - tw - pad
    else:
        tx = x + pad
    d.text((tx, y + (h - size * 1.45) / 2), str(text or ""), font=f(size, bold), fill=color)


def fmt_ms(ms):
    ms = int(ms)
    m = ms // 60000
    s = (ms % 60000) / 1000.0
    return "%d:%06.3f" % (m, s)


def lap_notes(r, best):
    """给每圈生成问题标注：从 incidents + 时间损失最大段。"""
    notes = {}
    laps = r.get("laps") or []
    for lap in laps:
        notes[lap["n"]] = []
    # 失误（按圈）
    for inc in r.get("incidents") or []:
        n = inc.get("lap_n")
        if n in notes:
            notes[n].append("%.0f m spin（%.0f→%.0f）" % (
                inc.get("at_d", 0), inc.get("v_from", 0), inc.get("v_to", 0)))
    # 时间损失最大的两段（按圈）
    segs = r.get("loss_by_segment") or []
    by_lap = {}
    for seg in segs:
        losses = seg.get("loss") or []
        for i, l in enumerate(losses):
            if l is None or i >= len(laps):
                continue
            ln = laps[i]["n"]
            if not isinstance(l, (int, float)) or l >= -0.05:
                continue
            by_lap.setdefault(ln, []).append((l, seg.get("from_m", 0)))
    for ln, items in by_lap.items():
        items.sort()
        for l, d in items[:2]:
            if ln in notes:
                notes[ln].append("%.0f m 丢 %.1fs" % (d, -l))
    return notes


def make_overview(r, path):
    laps = sorted(r.get("laps") or [], key=lambda x: x["lap_ms"])
    best = laps[0] if laps else None
    best_ms = best["lap_ms"] if best else 0
    notes = lap_notes(r, best)
    tinfo = T.get_by_track_id((r.get("session") or {}).get("trackId", -1))
    track = tinfo["name"] if tinfo else "Track"

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d)

    d.text((80, 64), "%s · 三圈成绩单" % track, font=f(60, True), fill=WHITE)
    d.text((82, 146), "F1 25 · %d 圈 · 极速 %d km/h" % (
        len(laps), max((l["max"] or 0) for l in laps) if laps else 0), font=f(28), fill=DIM)
    d.text((W - 460, 108), "dsh-sim-telemetry", font=f(30, True), fill=ACCENT)

    cols = [("圈次", 150), ("圈速", 240), ("与最快差", 210), ("极速", 150),
            ("均速", 150), ("全油门", 170), ("滑行", 150), ("问题标注", 570)]
    x0, y0, rh, hh = 80, 250, 92, 64
    total_w = sum(c[1] for c in cols)
    nrows = max(1, len(laps))
    d.rounded_rectangle([x0, y0, x0 + total_w, y0 + hh + rh * nrows + 8],
                        radius=16, fill=CARD, outline=LINE, width=2)
    x = x0
    for name, w in cols:
        cell(d, x, y0, w, hh, name, 28, True, DIM, "center" if name != "问题标注" else "left", 18, HEAD)
        x += w
    for ri, lap in enumerate(laps):
        y = y0 + hh + ri * rh
        if ri % 2 == 0:
            d.rectangle([x0 + 2, y, x0 + total_w - 2, y + rh], fill=(23, 33, 52))
        is_best = ri == 0
        gap = "★ 最快" if is_best else "+%.3f" % ((lap["lap_ms"] - best_ms) / 1000)
        note = "；".join(notes.get(lap["n"]) or []) or "—"
        x = x0
        cell(d, x, y, 150, rh, "L%d" % lap["n"], 34, True, ACCENT if is_best else WHITE, "center", 18)
        x += 150
        cell(d, x, y, 240, rh, lap["lap_str"], 38, True, GOLD if is_best else WHITE, "center", 18)
        x += 240
        cell(d, x, y, 210, rh, gap, 30, True, GOLD if is_best else (RED if (lap["lap_ms"] - best_ms) > 3000 else WHITE), "center", 18)
        x += 210
        cell(d, x, y, 150, rh, lap["max"], 28, False, WHITE, "center", 8)
        x += 150
        cell(d, x, y, 150, rh, lap["avg"], 28, False, WHITE, "center", 8)
        x += 150
        cell(d, x, y, 170, rh, "%d%%" % (lap["full"] or 0), 28, False, WHITE, "center", 8)
        x += 170
        cell(d, x, y, 150, rh, "%d%%" % (lap["coast"] or 0), 28, False, WHITE, "center", 8)
        x += 150
        color = RED if ("spin" in note or "出界" in note) else (ORANGE if ("丢" in note) else DIM)
        cell(d, x, y, 570, rh, note[:34], 26, False, color, "left", 14)

    # 结论：最快与最慢差 + 最大损失段
    y = y0 + hh + rh * nrows + 44
    d.text((80, y), "结论", font=f(30, True), fill=ACCENT)
    if laps and len(laps) > 1:
        spread = (laps[-1]["lap_ms"] - best_ms) / 1000
        d.text((80, y + 52), "三圈差 %.3f 秒（最快 L%d %s，最慢 L%d %s）" % (
            spread, best["n"], best["lap_str"], laps[-1]["n"], laps[-1]["lap_str"]),
            font=f(36, True), fill=WHITE)
        segs = r.get("loss_by_segment") or []
        worst = None
        for seg in segs:
            for l in (seg.get("loss") or []):
                if isinstance(l, (int, float)) and (worst is None or l < worst[0]):
                    worst = (l, seg.get("from_m", 0), seg.get("to_m", 0))
        y += 128
        if worst:
            d.text((80, y), "最大损失段：%.0f~%.0f m（丢 %.2f 秒）" % (worst[1], worst[2], -worst[0]),
                   font=f(30), fill=(200, 210, 226))

    y = H - 110
    d.line([(80, y), (W - 80, y)], fill=LINE, width=2)
    d.text((80, y + 22), "数据：%s · 弯位编号见轨迹诊断图" % os.path.basename(
        (r.get("_source") or "frames.jsonl")), font=f(24), fill=DIM)
    d.text((W - 690, y + 22), "红=失误/丢秒   橙=时间损失   青=亮点", font=f(24), fill=DIM)

    img.save(path)
    return path


def make_corners(r, path):
    rows = r.get("corner_rows") or []
    laps = r.get("laps") or []
    if not rows or not laps:
        return None
    best_i = r.get("best_index", 0)
    best_lap = laps[best_i] if best_i < len(laps) else laps[0]
    tinfo = T.get_by_track_id((r.get("session") or {}).get("trackId", -1))
    track = tinfo["name"] if tinfo else "Track"

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    background(d)

    d.text((80, 54), "逐弯 apex 速度对比（km/h）", font=f(52, True), fill=WHITE)
    d.text((82, 126), "%s %d 个弯 · 各圈同弯 apex · 标注 = 相对最快圈 L%d 的问题"
           % (track.split(" ")[0], len(rows), best_lap["n"]), font=f(26), fill=DIM)

    n_laps = len(laps)
    lap_w = 175
    cols = [("第N弯", 160), ("方向", 120)] + [("L%d" % l["n"], lap_w) for l in laps] + [("标注", 1920 - 80 - 160 - 120 - lap_w * n_laps - 80)]
    x0, y0, hh = 80, 186, 52
    rh = min(42, int((H - 220 - hh) / max(1, len(rows))))
    total_w = sum(c[1] for c in cols)
    d.rounded_rectangle([x0, y0, x0 + total_w, y0 + hh + rh * len(rows) + 4],
                        radius=14, fill=CARD, outline=LINE, width=2)
    x = x0
    for name, w in cols:
        cell(d, x, y0, w, hh, name, 26, True, DIM, "center" if name != "标注" else "left", 14, HEAD)
        x += w
    for ri, row in enumerate(rows):
        y = y0 + hh + ri * rh
        if ri % 2 == 0:
            d.rectangle([x0 + 2, y, x0 + total_w - 2, y + rh], fill=(23, 33, 52))
        per = row.get("laps") or []
        best_apex = max((p.get("apex") or 0) for p in per) if per else 0
        x = x0
        cell(d, x, y, 160, rh, row["no"], 25, True, WHITE, "center", 8)
        x += 160
        cell(d, x, y, 120, rh, row.get("dir") or "", 24, False, DIM, "center", 8)
        x += 120
        for p in per[:n_laps]:
            val = p.get("apex") or 0
            col = WHITE
            diff = val - best_apex
            if diff <= -15:
                col = RED
            elif diff <= -8:
                col = ORANGE
            elif diff >= 10:
                col = ACCENT
            cell(d, x, y, lap_w, rh, val, 26, False, col, "center", 8)
            x += lap_w
        # 标注：最快圈 vs 最慢圈差
        note = ""
        if per:
            vals = [p.get("apex") or 0 for p in per]
            mx, mn = max(vals), min(vals)
            if mx - mn >= 30:
                note = "极差 %d km/h" % (mx - mn)
            elif mx - mn >= 15:
                note = "差 %d km/h" % (mx - mn)
        cell(d, x, y, cols[-1][1], rh, note, 22, False, DIM, "left", 12)

    img.save(path)
    return path


def main():
    if len(sys.argv) < 2:
        print("用法: python session_table.py <frames_XXX.jsonl> [--out <dir>]")
        return 1
    path = sys.argv[1]
    outdir = PLOTS
    if "--out" in sys.argv:
        outdir = sys.argv[sys.argv.index("--out") + 1]

    r = E.analyse(path)
    r["_source"] = path
    ts = os.path.basename(path).replace("frames_", "").replace(".jsonl", "")
    os.makedirs(outdir, exist_ok=True)

    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    outs = []
    if only != "corners":
        p1 = os.path.join(outdir, "session_%s-overview.png" % ts)
        outs.append(make_overview(r, p1))
    if only != "overview":
        p2 = os.path.join(outdir, "session_%s-corners.png" % ts)
        p2 = make_corners(r, p2)
        if p2:
            outs.append(p2)

    for o in outs:
        print("已保存:", o)
        if outdir == PLOTS and os.path.isdir(DESK):
            try:
                import shutil
                shutil.copy(o, os.path.join(DESK, os.path.basename(o)))
                print("已保存:", os.path.join(DESK, os.path.basename(o)))
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
