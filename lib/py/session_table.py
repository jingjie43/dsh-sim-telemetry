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
    """给每圈生成问题标注：相对最快圈差 + 逐弯慢点 + 失误。"""
    laps = r.get("laps") or []
    rows = r.get("corner_rows") or []
    notes = {l["n"]: [] for l in laps}
    if not laps or not best:
        return notes
    best_ms = best["lap_ms"]
    for lap in laps:
        gap = (lap["lap_ms"] - best_ms) / 1000.0
        if gap > 3.0:
            notes[lap["n"]].append("慢 %.1fs" % gap)
        elif gap > 1.0:
            notes[lap["n"]].append("慢 %.1fs" % gap)
    # 逐弯：该圈 apex 比该弯最好低多少
    for row in rows:
        per = row.get("laps") or []
        vals = [(i, p.get("apex")) for i, p in enumerate(per) if p and p.get("apex")]
        if len(vals) < 2:
            continue
        best_apex = max(v for _, v in vals)
        for i, val in vals:
            if i >= len(laps):
                continue
            diff = best_apex - val
            if diff >= 25:
                notes[laps[i]["n"]].append("T%s 慢 %d" % (row.get("no"), diff))
    # 失误（按合并后的圈号，incidents 的 lap_n 已重映射）
    for inc in r.get("incidents") or []:
        n = inc.get("lap_n")
        if n in notes and len(notes[n]) < 3:
            notes[n].append("%.0f m spin" % (inc.get("at_d") or 0))
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

    d.text((80, 64), "%s · 成绩单" % track, font=f(60, True), fill=WHITE)
    d.text((82, 146), "F1 25 · %d 圈 · 极速 %d km/h" % (
        len(laps), max((l["max"] or 0) for l in laps) if laps else 0), font=f(28), fill=DIM)
    d.text((W - 460, 108), "dsh-sim-telemetry", font=f(30, True), fill=ACCENT)

    nrows_tmp = max(1, len(laps))
    rh = min(92, max(46, int((H - 250 - 64 - 210) / nrows_tmp)))
    cols = [("圈次", 130), ("圈速", 220), ("与最快差", 200), ("极速", 140),
            ("均速", 140), ("全油门", 150), ("滑行", 130), ("问题标注", 650)]
    x0, y0, hh = 80, 250, 64
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
        items = (notes.get(lap["n"]) or [])[:2]
        note = "；".join(items) or "—"
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

    # 结论：最快与最慢差
    y = y0 + hh + rh * nrows + 26
    d.text((80, y), "结论", font=f(30, True), fill=ACCENT)
    if laps and len(laps) > 1:
        spread = (laps[-1]["lap_ms"] - best_ms) / 1000
        d.text((80, y + 52), "%d 圈差 %.3f 秒（最快 L%d %s，最慢 L%d %s）" % (
            len(laps),
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

    y = H - 76
    d.line([(80, y), (W - 80, y)], fill=LINE, width=2)
    d.text((80, y + 22), "数据：%s · 弯位编号见轨迹诊断图" % os.path.basename(
        (r.get("_source") or "frames.jsonl")), font=f(24), fill=DIM)
    d.text((W - 690, y + 22), "红=失误/丢秒   橙=时间损失   青=亮点", font=f(24), fill=DIM)

    img.save(path)
    return path


def corner_advice(row):
    """根据各圈操作差异给出问题 + 怎么改。"""
    per = [p for p in (row.get("laps") or []) if p and p.get("apex")]
    if len(per) < 2:
        return "数据不足", ""
    vals = [p["apex"] for p in per]
    spread = max(vals) - min(vals)
    if spread >= 30:
        problem = "极差 %d，跑法不一致" % spread
    elif spread >= 15:
        problem = "差 %d km/h" % spread
    else:
        problem = "稳定"
    if problem == "稳定":
        return problem, "保持这个节奏"
    tips = []
    brake = [p.get("brake_d") for p in per if p.get("brake_d")]
    if len(brake) >= 2 and max(brake) - min(brake) > 10:
        tips.append("刹车点固定到 %.0f m" % min(brake))
    gas = [p.get("gas_d") for p in per if p.get("gas_d")]
    if len(gas) >= 2 and max(gas) - min(gas) > 20:
        tips.append("给油点统一到 %.0f m" % min(gas))
    steer = [p.get("steer_peak") for p in per if p.get("steer_peak")]
    if len(steer) >= 2 and max(steer) - min(steer) > 0.08:
        tips.append("方向给到 %.2f" % max(steer))
    if not tips:
        tips.append("保持这个节奏" if spread < 10 else "先固定走线")
    return problem, tips[0] if tips else "先固定走线"


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
    fixed_w = 90 + 60 + 190 + 240
    lap_w = max(60, min(175, int((1920 - 160 - fixed_w) / max(1, n_laps))))
    cols = ([("第N弯", 90), ("方向", 60)] + [("L%d" % l["n"], lap_w) for l in laps]
            + [("问题", 190), ("怎么改", 240)])
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
        while len(per) < n_laps:
            per.append({})
        best_apex = max((p.get("apex") or 0) for p in per) if per else 0
        x = x0
        cell(d, x, y, 90, rh, row["no"], 24, True, WHITE, "center", 6)
        x += 90
        cell(d, x, y, 60, rh, row.get("dir") or "", 22, False, DIM, "center", 4)
        x += 60
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
        # 问题 + 怎么改
        problem, advice = corner_advice(row)
        pcol = RED if "极差" in problem else (ORANGE if "差" in problem else DIM)
        cell(d, x, y, 190, rh, problem[:15], 19, False, pcol, "left", 8)
        x += 190
        cell(d, x, y, 240, rh, advice[:24], 19, False, (ACCENT if "保持" in advice else WHITE), "left", 8)

    img.save(path)
    return path


def _remap_incidents(results):
    """把每个文件里的 incidents.lap_n 映射成合并后的圈号。"""
    out = []
    n = 0
    for r in results:
        for inc in r.get("incidents") or []:
            out.append({**inc, "lap_n": (inc.get("lap_n") or 0) + n})
        n += len(r.get("laps") or [])
    return out


def analyse_multi(paths, want=None):
    """多个数据文件 → 合并所有圈 + 逐弯行；want = 只保留这些圈号（合并后的 1..N）。"""
    results = [E.analyse(p) for p in paths]
    laps = []
    n = 0
    for r, p in zip(results, paths):
        for lap in r.get("laps") or []:
            n += 1
            laps.append({**lap, "n": n, "_src": os.path.basename(p)})
    corners = {}
    for r in results:
        for row in r.get("corner_rows") or []:
            key = row.get("no")
            if key is None:
                continue
            if key not in corners:
                corners[key] = {"no": key, "dir": row.get("dir"), "laps": []}
            corners[key]["laps"].extend(row.get("laps") or [])
    if want:
        keep = [i for i, l in enumerate(laps) if l["n"] in want]
        laps = [laps[i] for i in keep]
        for no in range(1, len(laps) + 1):
            laps[no - 1]["n"] = no
        for key in corners:
            src = corners[key]["laps"]
            corners[key]["laps"] = [src[i] for i in keep if i < len(src)]
    return {
        "laps": laps,
        "corner_rows": list(corners.values()),
        "session": results[0].get("session") if results else {},
        "incidents": _remap_incidents(results),
        "loss_by_segment": [],
        "_sources": [os.path.basename(p) for p in paths],
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python session_table.py <frames_1.jsonl> [frames_2.jsonl ...] [--out <dir>] [--only overview|corners]")
        return 1
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and os.path.isfile(a)]
    if not paths:
        print("没有有效的 frames 文件")
        return 1
    outdir = PLOTS
    if "--out" in sys.argv:
        outdir = sys.argv[sys.argv.index("--out") + 1]

    want = None
    if "--laps" in sys.argv:
        raw = sys.argv[sys.argv.index("--laps") + 1]
        want = set()
        for part in raw.replace("，", ",").split(","):
            part = part.strip()
            if part.isdigit():
                want.add(int(part))
        if not want:
            want = None
    if len(paths) > 1 or want:
        r = analyse_multi(paths, want)
    else:
        r = E.analyse(paths[0])
    if len(paths) == 1:
        r["_source"] = paths[0]
    ts = os.path.basename(paths[0]).replace("frames_", "").replace(".jsonl", "")
    if len(paths) > 1:
        ts = ts + "_multi" + str(len(paths))
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
