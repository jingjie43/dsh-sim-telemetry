"""共用切圈 / 载入 / 格式化：summary 和 plot 必须用同一个口径。

为什么单独一个文件：以前两个脚本各写一份切圈，结果同一份数据
summary 报 2 圈、plot 报 3 圈，圈速还配错位。口径只能有一份。

切圈原则：
- **圈速只信 `lastLap`**（游戏自己算的），每次变化 = 跑完一圈，圈速就是它。
- 不再用 `curLap` 归零判圈边界 —— UDP 包会乱序，`curLap` 会出现 5~13 秒的
  假回退，拿它切圈会切出假圈、还会把圈速配到别的圈上。
- 判定「这是不是一个完整可用的圈」用**时间覆盖率**，不用帧数：
  帧率会随游戏负载在 20~28Hz 之间抖，用绝对帧数当闸门必然误杀真圈。
"""
import json

MIN_COVERAGE = 0.90   # 时间覆盖率低于这个 = 采集从圈中间开始，不算一圈
FULL_COVERAGE = 0.98  # 达到这个才算曲线完整（开头不缺数据）
GRID = 0.5            # 覆盖率按 0.5 秒一格统计
MIN_FRAMES = 100      # 兜底：帧数太少说明基本没数据
FLASHBACK_MIN = 0.5   # st 倒退超过这个秒数 = 玩家用了回退（F1 25 的 flashback）


def fmt(ms):
    if not ms:
        return "-"
    m, rem = divmod(int(ms), 60000)
    s, msec = divmod(rem, 1000)
    return f"{m}:{s:02d}.{msec:03d}"


def detect_flashbacks(items, min_rewind=FLASHBACK_MIN):
    """找 F1 25 的回退（flashback）：按**接收顺序**扫 sessionTime 的倒退点。

    怎么和「UDP 迟到包」区分（实测这份银石数据 7 处，全是回退不是迟到）：
    - 回退：st 倒退之后，后续数据**继续从倒退点往前走**，且 `curLap` 倒退的
      幅度和 st 倒退几乎一致（差几毫秒）。游戏是真的把时钟倒回去了。
    - 迟到包：单个包的 st 偏小，下一包立刻恢复，不成段。
    两种都靠 trim_flashback() 兜住，这里只负责报告。
    """
    out = []
    for i in range(1, len(items)):
        d = items[i - 1]["st"] - items[i]["st"]
        if d > min_rewind:
            out.append({
                "from": round(items[i - 1]["st"], 2),
                "to": round(items[i]["st"], 2),
                "rewind": round(d, 2),
            })
    return out


def trim_flashback(items):
    """重建「最终时间线」：同一个时刻以最后一次经过的数据为准。

    F1 25 回退后，回退点之前已经跑过的那段会被重跑一遍，原始数据里
    同一段时间就有两套速度/油门 —— 不对，原样的曲线会来回抖成毛刺、
    圈速也会被算到错误的数据上。

    做法：按接收顺序从后往前扫，记录见过的较早时刻；只要这帧的时刻
    >= 已经见过的时刻，说明它属于"被回退覆盖掉的旧跑法"，丢掉。
    """
    kept = []
    min_seen = float("inf")
    for f in reversed(items):
        if f["st"] >= min_seen:
            continue
        kept.append(f)
        min_seen = f["st"]
    kept.reverse()
    return kept


def load(path):
    """读 jsonl → (frames, laps, sess)。frames=速度帧(id 6)，laps=圈数据(id 2)。

    ⚠️ 读完必须按 st 排序：UDP 会送来「迟到包」（实测 7 个包晚了 4.5~13 秒），
    不排序的话 plot 会照着列表顺序连线、把曲线往回画成锯齿，
    summary 的弯道窗口也会把「前一个点」认错。
    """
    frames, laps, sess = [], [], {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            rid = r.get("id")
            if rid == 6:
                frames.append(r)
            elif rid == 2:
                laps.append(r)
            elif rid == 1 and not sess:
                sess = r
    # 回退检测必须在排序前做完：回退信息藏在「接收顺序」里，排完序就没了
    flashbacks = detect_flashbacks(frames)
    if flashbacks:
        frames = trim_flashback(frames)
        laps = trim_flashback(laps)

    frames.sort(key=lambda f: f["st"])
    laps.sort(key=lambda r: r["st"])

    # 防御：观战切镜头会让 m_playerCarIndex 变，帧里混进两辆车的数据，
    # 速度曲线就会来回抖成毛刺。只留出现最多的那辆车（正常驾驶时只有一辆）。
    players = [f["p"] for f in frames if "p" in f]
    if players:
        main_p = max(set(players), key=players.count)
        if len(set(players)) > 1:
            frames = [f for f in frames if f.get("p", main_p) == main_p]
    return frames, laps, sess, flashbacks


def time_coverage(fr, a, end, grid=GRID):
    """窗口 [a, end] 里有数据覆盖的时间比例（与帧率无关）。"""
    if end <= a or not fr:
        return 0.0
    cells = max(1, int((end - a) / grid))
    hits = {min(cells - 1, int((f["st"] - a) / grid)) for f in fr}
    return len(hits) / cells


def lap_events(laps):
    """从 lastLap 变化里取「跑完一圈」事件，保持时间顺序，去掉重复值。"""
    events, seen = [], None
    for r in laps:
        v = r.get("lastLap", 0)
        if not v or v == seen:
            continue
        events.append({"end": r["st"], "lap": v})
        seen = v
    return events


def cut_laps(frames, laps):
    """切圈。返回按时间顺序、只含数据够用的圈。

    每圈 dict:
      n        序号（1 起）
      lap_ms   圈速毫秒（游戏给的）
      key      增量去重用的稳定键
      start/end 这一圈在采集时间轴上的起止
      fr       圈内速度帧
      coverage 时间覆盖率 0~1
      full     coverage >= FULL_COVERAGE，曲线开头不缺数据
    """
    out = []
    for ev in lap_events(laps):
        a = ev["end"] - ev["lap"] / 1000.0
        fr = [f for f in frames if a <= f["st"] <= ev["end"]]
        cov = time_coverage(fr, a, ev["end"])
        if cov < MIN_COVERAGE or len(fr) < MIN_FRAMES:
            continue
        out.append({
            "n": len(out) + 1,
            "lap_ms": ev["lap"],
            "key": f"{ev['lap']}_{round(ev['end'])}",
            "start": a,
            "end": ev["end"],
            "fr": fr,
            "coverage": round(cov, 3),
            "full": cov >= FULL_COVERAGE,
        })
    return out
