"""比赛工程师报告：按距离对齐多圈，输出圈速、逐弯、失误、时间损失、改进建议。

用法: python report.py [frames_xxx.jsonl]

和 summary.py 的分工：
  summary.py  —— 省 token 的基础摘要（圈速 + CSV + 明细 md）
  report.py   —— 工程师级分析：需要 Motion/steer/lapDistance 才有完整效果，
                 没有这些字段时自动退回只用速度数据。
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.environ.get("SIM_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))

import engineer as E  # noqa: E402
import laps as L  # noqa: E402
import tracks as T  # noqa: E402


def fmt(ms):
    return L.fmt(ms)


def main():
    files = [f for f in glob.glob(os.path.join(HERE, "frames_*.jsonl"))
             if os.path.getsize(f) > 20000]
    if len(sys.argv) > 1:
        files = [sys.argv[1]]
    if not files:
        print("没有可分析的数据")
        return 1
    path = max(files, key=os.path.getmtime)

    r = E.analyse(path)
    laps = r["laps"]
    if not laps:
        print("这轮还没跑出完整圈（或数据太短）")
        return 1

    best_i = r["best_index"]
    best_ms = laps[best_i]["lap_ms"]
    tinfo = T.get_by_track_id(r["session"].get("trackId", -1))
    track = tinfo["name"] if tinfo else "?"

    print(f"[比赛工程师] {track} · {len(laps)} 圈")
    if r["flashbacks"]:
        print(f"（检测到 {len(r['flashbacks'])} 次回退，已按最终时间线去重）")

    # 圈速
    order = sorted(range(len(laps)), key=lambda i: laps[i]["lap_ms"])
    print("\n圈速：")
    for rank, i in enumerate(order):
        l = laps[i]
        gap = (l["lap_ms"] - best_ms) / 1000.0
        tag = " ★最快" if i == best_i else f" (+{gap:.3f})"
        print(f"  L{l['n']}  {l['lap_str']}{tag}   极速{l['max']} 均速{l['avg']} "
              f"全油门{l['full']}% 刹车{l['brake']}% 滑行{l['coast']}%")

    # 失误
    if r["incidents"]:
        print("\n失误：")
        for inc in r["incidents"]:
            print(f"  L{inc['lap_n']}  {inc['at_d']:.0f} m  {inc['type']}："
                  f"速度 {inc['from_v']}→{inc['to_v']} km/h，横向G 掉 {inc['g_drop']}")
        print("  → 位置看轨迹诊断图最直观：plots/track_*.png（红点=出问题的弯）")
        # 主动告诉用户「可以深挖」——别让他自己猜要问什么
        print("\n想知道这一下到底怎么发生的、下次怎么避免吗？")
        print("  直接跟我说「这次 spin 怎么回事」就行 —— 我会把这一圈和你的最快圈逐秒拉出来对比，")
        print("  告诉你：是第几弯、哪一脚刹车踩重了、哪一次方向打多了、该提前还是推后多少米。")
    else:
        print("\n失误：未检出（横向G 无骤降）")
        print("  想深挖每个弯还差多少？问我「我哪个弯最慢」或「帮我看逐弯对比」。")

    # 时间损失
    losses = []
    for seg in r["loss_by_segment"]:
        for i, v in enumerate(seg["loss"]):
            if i != best_i and v and v > 0.05:
                losses.append((v, seg["from_m"], seg["to_m"], laps[i]["n"]))
    losses.sort(reverse=True)
    if losses:
        print("\n时间损失（相对最快圈，>0.05s 的段）：")
        for v, a, b, n in losses[:8]:
            print(f"  {a:4.0f}-{b:4.0f} m   L{n}  -{v:.3f}s")

    # 逐弯
    rows = r.get("corner_rows") or []
    if rows:
        print(f"\n逐弯（共 {len(rows)} 个弯，apex 速度 km/h；编号见轨迹图）：")
        head = "  第N弯 方向 " + "  ".join(f"L{l['n']:>1}" for l in laps) + "   差距"
        print(head)
        for row in rows:
            vals = [x["apex"] if x else None for x in row["laps"]]
            ok = [v for v in vals if v]
            spread = (max(ok) - min(ok)) if len(ok) > 1 else 0
            cells = "  ".join(f"{v:>3}" if v else "  -" for v in vals)
            flag = f"  ← 差 {spread}" if spread >= 25 else ""
            print(f"  {row['no']:>3}   {row['dir']:>2}   {cells}{flag}")

    # 建议
    tips = []
    if r["incidents"]:
        inc = r["incidents"][0]
        tips.append(f"先修失误：{inc['at_d']:.0f} m 处那一下丢了最多时间，"
                    f"（{inc['type']}）先保住不失控，比抠细节值钱得多")
    if rows:
        worst = None
        for row in rows:
            vals = [x["apex"] if x else None for x in row["laps"]]
            ok = [v for v in vals if v]
            if len(ok) > 1:
                sp = max(ok) - min(ok)
                if worst is None or sp > worst[0]:
                    worst = (sp, row)
        if worst and worst[0] >= 25:
            row = worst[1]
            tips.append(f"最不稳的是 {row['start']:.0f}-{row['end']:.0f} m 这个弯，"
                        f"各圈 apex 差了 {worst[0]} km/h —— 同一个弯能跑出两个水平，先把这里做稳")
    slow = [l for l in laps if l["coast"] >= 11]
    if slow:
        tips.append("滑行占比偏高（≥11%）：弯中别把油门全松，保持轻油门过弯")
    if laps[0]["full"] < 60:
        tips.append("全油门占比偏低：出弯给油可以更早更坚决")

    if tips:
        print("\n该改什么：")
        for t in tips:
            print(f"  → {t}")

    # 产出提示：让用户知道去哪里看图和明细
    print("\n本次产出：")
    print("  · 圈速表      laps_*.csv")
    print("  · 完整明细    summary_full_*.md")
    print("  · 速度/油门图  plots/speed_*.png · plots/pedals_*.png")
    print("  · 轨迹诊断图   plots/track_*.png  ← 弯位编号 + 问题标注")
    print("  · 想要更多：直接问「我哪个弯最慢」「帮我看看这次的图」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
