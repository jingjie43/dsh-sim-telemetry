"""F1 25 摘要分析（省 token 模式）：只输出结论，完整表格落文件。

- 每次只分析**新出现的圈**，已分析过的记在 state_summary.json
- 打印 ≤ 15 行：圈速、与最佳圈的差、损失最大的 3 段、最差的 3 个弯、一句该改什么
- 完整明细写到 summary_full_<ts>.md，不打印

用法: python telemetry_summary.py [frames_xxx.jsonl]
"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.environ.get("SIM_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state_summary.json")
NSEG = 20
TRACKS = {0: "Melbourne", 1: "Shanghai", 2: "Bahrain", 3: "Jeddah", 4: "Imola", 5: "Monza",
          6: "Monaco", 7: "Silverstone", 8: "Spa", 9: "Suzuka", 10: "Zandvoort", 11: "Austin",
          12: "Mexico", 13: "Brazil", 14: "Baku", 15: "Las Vegas", 16: "Qatar", 17: "Austria",
          18: "Hungary", 19: "Singapore", 20: "Spain", 21: "Canada", 22: "France", 23: "Netherlands",
          24: "USA", 25: "Abu Dhabi", 26: "Miami", 27: "Portugal", 28: "Saudi", 29: "Mugello"}

CORNER_NAMES = {  # 按出现顺序给 Silverstone 的弯起个名字（仅用于摘要可读性）
    "Silverstone": ["Abbey", "Village", "TheLoop", "Luffield", "Copse", "Maggotts",
                    "Becketts", "Stowe", "Club"],
}


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
    """用 lastLap 变化切圈：每次 lastLap 变化（或同值但时间间隔足够）= 一圈跑完。"""
    events, seen, last_st = [], None, None
    for r in laps:
        v = r.get("lastLap", 0)
        if not v:
            continue
        new_lap = v != seen
        if not new_lap and last_st is not None and r["st"] - last_st > (v / 1000.0) * 0.8:
            new_lap = True
        if new_lap:
            events.append({"end": r["st"], "lap": v})
            seen = v
        last_st = r["st"]
    out = []
    for ev in events:
        a = ev["end"] - ev["lap"] / 1000.0
        fr = [f for f in frames if a <= f["st"] <= ev["end"]]
        if not (1500 <= len(fr) <= 2350):
            continue
        out.append({"n": len(out) + 1, "lap_ms": ev["lap"], "fr": fr,
                    "key": f"{ev['lap']}_{round(ev['end'])}"})
    return out


def stats(fr):
    n = len(fr)
    sp = [f["speed"] for f in fr]
    thr = [f["throttle"] for f in fr]
    brk = [f["brake"] for f in fr]
    return {
        "max": max(sp), "avg": round(sum(sp) / n),
        "full": round(100 * sum(1 for t in thr if t >= 95) / n),
        "brake": round(100 * sum(1 for b in brk if b >= 5) / n),
        "coast": round(100 * sum(1 for t, b in zip(thr, brk) if t < 5 and b < 5) / n),
    }


def segments(fr, nseg=NSEG):
    t0, t1 = fr[0]["st"], fr[-1]["st"]
    span = max(t1 - t0, 0.001)
    rates = [0.0] * nseg
    for f in fr:
        i = min(nseg - 1, int((f["st"] - t0) / span * nseg))
        rates[i] += f["speed"]
    cnt = [0] * nseg
    for f in fr:
        i = min(nseg - 1, int((f["st"] - t0) / span * nseg))
        cnt[i] += 1
    return [round(rates[i] / cnt[i], 1) if cnt[i] else 0 for i in range(nseg)]


def corners(fr):
    n = len(fr)
    win = 10
    cand = []
    for i in range(win, n - win):
        w = [fr[j]["speed"] for j in range(i - win, i + win + 1)]
        s = fr[i]["speed"]
        if s > min(w):
            continue
        if max(w) - s < 8:
            continue
        cand.append(i)
    merged = []
    for i in cand:
        if merged and i - merged[-1] <= 25:
            if fr[i]["speed"] < fr[merged[-1]]["speed"]:
                merged[-1] = i
        else:
            merged.append(i)
    t0 = fr[0]["st"]
    return [(round(fr[i]["st"] - t0, 2), fr[i]["speed"]) for i in merged]


def main():
    files = [f for f in glob.glob(os.path.join(HERE, "frames_*.jsonl")) if os.path.getsize(f) > 100000]
    files += [f for f in glob.glob(os.path.join(HERE, "allcars_*.jsonl")) if os.path.getsize(f) > 100000]
    if len(sys.argv) > 1:
        files = [sys.argv[1]]
    if not files:
        print("没有可分析的数据")
        return 1
    path = max(files, key=os.path.getsize)
    frames, laps, sess = load(path)
    all_laps = cut_laps(frames, laps)
    if not all_laps:
        print("这轮还没跑出完整圈（或数据太短）")
        return 1

    track = TRACKS.get(sess.get("trackId", -1), "?")
    names = CORNER_NAMES.get(track, [])

    # 增量：只报新圈
    state = {}
    if os.path.exists(STATE):
        try:
            state = json.load(open(STATE, encoding="utf-8"))
        except ValueError:
            state = {}
    done = set(state.get("keys", [])) if state.get("path") == path else set()
    new_laps = [l for l in all_laps if l["key"] not in done]

    best = min(all_laps, key=lambda l: l["lap_ms"])
    best_seg = segments(best["fr"])
    best_cor = corners(best["fr"])

    lines = [f"[F1 {track}] 已有 {len(all_laps)} 圈，最快 {fmt(best['lap_ms'])}"]
    if not new_laps:
        lines.append("没有新圈（数据没变）")
    for l in new_laps:
        st = stats(l["fr"])
        seg = segments(l["fr"])
        cor = corners(l["fr"])
        cor = corners(l["fr"])
        cor_pairs = []
        for i, (bt, bv) in enumerate(best_cor):
            nm = names[i] if i < len(names) else f"弯{i + 1}"
            cand = [(abs(t - bt), v) for t, v in cor if abs(t - bt) < 2.0]
            if not cand:
                continue
            v = min(cand, key=lambda x: x[0])[1]
            cor_pairs.append((v - bv, i, v, bv, nm))
        cor_pairs.sort()
        loss_cor_txt = " / ".join(f"{nm} {v}({d:+d})" for d, i, v, bv, nm in cor_pairs[:3])
        lines.append("")
        lines.append(f"第 {l['n']} 圈 {fmt(l['lap_ms'])}（{'+' if l['lap_ms'] >= best['lap_ms'] else ''}"
                     f"{(l['lap_ms'] - best['lap_ms']) / 1000:.3f}s vs 最佳）")
        if cor_pairs:
            lines.append(f"  弯心：{loss_cor_txt}")
        lines.append(f"  全油门 {st['full']}% · 刹车 {st['brake']}% · 滑行 {st['coast']}% · 极速 {st['max']}")

        advice = []
        if cor_pairs and cor_pairs[0][0] < -12:
            advice.append(f"{cor_pairs[0][4]} 敢带油/晚刹车")
        if st["full"] < 60:
            advice.append("全油门占比偏低，高速弯别全松")
        if st["coast"] > 8:
            advice.append("滑行多：松油太早")
        if st["brake"] > 18:
            advice.append("刹车时间偏长：渐进刹车")
        if advice:
            lines.append("  → " + "；".join(advice))

    print("\n".join(lines))

    # 完整明细落文件
    full = [f"# {track} 明细", "", "| 圈 | 圈速 | 极速 | 均速 | 全油门 | 刹车 | 滑行 |",
            "|---|---|---|---|---|---|---|"]
    for l in all_laps:
        st = stats(l["fr"])
        full.append(f"| {l['n']} | {fmt(l['lap_ms'])} | {st['max']} | {st['avg']} | "
                    f"{st['full']}% | {st['brake']}% | {st['coast']}% |")
    for l in all_laps:
        full.append("")
        full.append(f"## 第 {l['n']} 圈 分段速度")
        full.append("| 段 | " + " | ".join(str(i + 1) for i in range(NSEG)) + " |")
        full.append("|---|" + "---|" * NSEG)
        full.append("| km/h | " + " | ".join(f"{v:.0f}" for v in segments(l["fr"])) + " |")
    full_path = os.path.join(HERE, f"summary_full_{os.path.basename(path).replace('frames_', '').replace('.jsonl', '')}.md")
    open(full_path, "w", encoding="utf-8").write("\n".join(full) + "\n")

    # 表格数据（CSV）
    try:
        import csv
        csv_path = os.path.join(HERE, f"laps_{os.path.basename(path).replace('frames_', '').replace('allcars_', '').replace('.jsonl', '')}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["lap", "lapTimeMs", "maxSpeed", "avgSpeed", "fullThrottlePct", "brakePct", "coastPct"])
            for l in all_laps:
                st = stats(l["fr"])
                w.writerow([l["n"], l["lap_ms"], st["max"], st["avg"], st["full"], st["brake"], st["coast"]])
        print(f"表格：{csv_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"（CSV 生成失败：{exc}）")

    state = {"path": path, "keys": sorted(done | {l["key"] for l in all_laps})}
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
