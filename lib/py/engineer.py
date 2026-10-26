"""比赛工程师分析引擎：距离对齐 + 曲率弯道识别 + 失误检测。

为什么单独一个模块：
  summary.py 以前只会「按时间切段 + 速度谷找弯」，遇到 S 弯会粘、高速全油弯会漏。
  现在采到了 lapDistance / steer / 横向 G / yaw，分析要按这些重做：
    - lapDistance → 多圈按「赛道同一米」对齐，圈速差几秒也不会错位
    - yaw 求曲率  → 弯道有几何定义（κ = dψ/ds），不依赖减速
    - 横向G       → spin / 打滑这些失误有物理特征可自动检出

对外主要入口：
  analyse(path) -> dict    一次性算完，返回可直接排版的结论
"""

import bisect
import json
import math

GRID = 5.0            # 重采样网格（米）
DEFAULT_LEN = 5890.0  # 赛道长度兜底值
MIN_CORNER_M = 25.0   # 弯的最短长度，短于这个当噪声
SPIN_DV = 80          # spin 判据：速度在极短距离内掉这么多（km/h）
                      # 40 太敏感 —— 正常重刹也能掉 40~50，会被误报成 spin（2026-10-26 实测：
                      # 3 圈里 4 处「spin」其实全是刹车，真正的 spin 是 113→8 掉了 105）
SPIN_G_DROP = 1.0     # spin 判据：横向G 掉幅


def load_streams(path):
    """按时间索引三类帧：telemetry(id6) / motion(id0) / lapdata(id2)。"""
    tele, motion, lapd = {}, {}, []
    session = None
    for line in open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        rid = r.get("id")
        st = round(r.get("st", 0.0), 2)
        if rid == 6:
            tele[st] = r
        elif rid == 0:
            motion[st] = r
        elif rid == 2:
            lapd.append(r)
        elif rid == 1 and session is None:
            session = r
    lapd.sort(key=lambda r: r["st"])
    return {"tele": tele, "motion": motion, "lapd": lapd,
            "lap_st": [r["st"] for r in lapd], "session": session or {}}


def dist_at(streams, st):
    """按时间戳查最近的 lapDistance（米）。"""
    lapd, keys = streams["lapd"], streams["lap_st"]
    if not lapd:
        return None
    i = bisect.bisect_left(keys, st)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(lapd):
            p = lapd[j]
            if best is None or abs(p["st"] - st) < abs(best["st"] - st):
                best = p
    if best is None:
        return None
    d = best.get("dist")
    return d if isinstance(d, (int, float)) and d >= 0 else None


def lap_series(lap, streams):
    """把一圈拆成按距离排序的点列。"""
    pts = []
    tele, motion = streams["tele"], streams["motion"]
    for f in lap["fr"]:
        d = dist_at(streams, f["st"])
        if d is None:
            continue
        st = round(f["st"], 2)
        t = tele.get(st)
        m = motion.get(st)
        pts.append({
            "d": d,
            "v": f["speed"],
            "thr": f["throttle"],
            "brk": f["brake"],
            "steer": t.get("steer") if t else None,
            "gx": m.get("gx") if m else None,
            "yaw": m.get("yaw") if m else None,
        })
    pts.sort(key=lambda p: p["d"])
    return pts


def resample(pts, total=DEFAULT_LEN, grid=GRID):
    """按距离网格重采样，返回 dict of list（缺值处为 None）。"""
    n = int(total / grid) + 1
    out = {k: [None] * n for k in ("v", "thr", "brk", "steer", "gx", "yaw")}
    if not pts:
        return out
    j = 0
    for i in range(n):
        target = i * grid
        while j + 1 < len(pts) and pts[j + 1]["d"] < target:
            j += 1
        cand = pts[max(0, j - 1):min(len(pts), j + 3)]
        if not cand:
            continue
        p = min(cand, key=lambda x: abs(x["d"] - target))
        if abs(p["d"] - target) > grid * 3:
            continue
        for k in out:
            out[k][i] = p[k]
    return out


def _yaw_series(series):
    """取车头朝向角。优先 yaw 字段；旧版采集里 gx 存过 yaw（偏移写错那次）。"""
    yaw = series.get("yaw")
    if yaw and any(v is not None for v in yaw):
        return yaw
    return series.get("gx") or []


def curvature(yaw, grid=GRID):
    """由朝向角求**带符号**曲率 κ = dψ/ds（rad/m），处理 ±π 过零跳变。

    正值 = 左转，负值 = 右转。带符号很关键：S 弯左右切换会让符号翻转，
    因此即使曲率不归零，也能把两个弯分开。
    """
    n = len(yaw)
    k = [None] * n
    for i in range(1, n):
        a, b = yaw[i - 1], yaw[i]
        if a is None or b is None:
            continue
        d = b - a
        if d > math.pi:
            d -= 2 * math.pi
        elif d < -math.pi:
            d += 2 * math.pi
        k[i] = d / grid
    return k


def _smooth(vals, win=2):
    n = len(vals)
    out = [None] * n
    for i in range(n):
        w = [vals[j] for j in range(max(0, i - win), min(n, i + win + 1)) if vals[j] is not None]
        out[i] = sum(w) / len(w) if w else None
    return out


def average_field(series_list, key, grid=GRID):
    """多圈按距离对齐后取平均（缺值跳过）。用于压低单圈走线差异和抖动。"""
    if not series_list:
        return []
    n = len(series_list[0].get(key) or [])
    out = [None] * n
    for i in range(n):
        vals = [s[key][i] for s in series_list if s.get(key) and i < len(s[key]) and s[key][i] is not None]
        if vals:
            out[i] = sum(vals) / len(vals)
    return out


def average_curvature(series_list, grid=GRID):
    """多圈曲率平均 —— 弯位识别用这个比单圈稳得多。

    每圈的走线略有不同、yaw 也有各自的噪声，但赛道几何是共同的；
    平均之后共同成分（真弯）被强化，各自的噪声互相抵消。
    """
    ks = [curvature(_yaw_series(rs), grid) for rs in series_list]
    ks = [k for k in ks if any(v is not None for v in k)]
    if not ks:
        return []
    n = len(ks[0])
    out = [None] * n
    for i in range(n):
        vals = [k[i] for k in ks if i < len(k) and k[i] is not None]
        if vals:
            out[i] = sum(vals) / len(vals)
    return out


def detect_corners(series, grid=GRID, expected=None, curv=None):
    """识别弯道：找**曲率局部峰值**，每个峰 = 一个弯心。

    为什么不用「曲率超过阈值连成一段」：
      Silverstone 的 Village→The Loop→Aintree、Maggotts→Becketts 这些连续弯，
      曲率始终不归零，按阈值分段会把多个弯粘成一个（实测 18 个官方弯只切出 14 个）。
    峰值法不依赖「回零」：只要曲率在弯心鼓包、弯间回落一点就能各自成峰；
    再叠加**符号翻转**（左弯→右弯）强制切分，S 弯也不会粘。

    expected：**官方弯数**（来自 tracks.py 的 official_turns）。
    给了就强制输出正好这么多个 —— 按曲率强度排序取前 N，再保证最小间距。
    这是「硬性一致性」的实现方式：不靠调参去逼近，而是用已知答案约束。
    没有 expected 时退回纯阈值法（数量不保证）。
    """
    yaw = _yaw_series(series)
    if curv is not None and any(v is not None for v in curv):
        k = curv                              # 调用方已给多圈平均曲率
    elif yaw and any(v is not None for v in yaw):
        k = curvature(yaw, grid)
    else:
        return []
    n = len(k)
    sm = _smooth(k, 5)                     # 较强平滑，压朝向噪声

    THR = 0.005
    WIN = 6                                # ±30 米内取局部最大

    def mag(i):
        v = sm[i]
        return None if v is None else abs(v)

    peaks = []
    for i in range(WIN, n - WIN):
        m = mag(i)
        if m is None or m < THR:
            continue
        window = [mag(j) for j in range(i - WIN, i + WIN + 1) if mag(j) is not None]
        if window and m >= max(window):
            peaks.append(i)

    # 合并 60 米内的同号峰（同一个弯的两个鼓包）；异号绝不合并（那是两个弯）
    merged = []
    for p in peaks:
        if merged:
            last = merged[-1]
            same_sign = (sm[p] is not None and sm[last] is not None and sm[p] * sm[last] > 0)
            if same_sign and (p - last) * grid < 60:
                if abs(sm[p]) > abs(sm[last]):
                    merged[-1] = p
                continue
        merged.append(p)

    # 有官方弯数时：强制取最强的 expected 个峰，并保证相邻弯至少隔 MIN_GAP 米
    if expected and expected > 0 and len(merged) > expected:
        MIN_GAP = 80.0                       # 两个弯心靠得比这更近，说明是同一个弯的两个鼓包
        ranked = sorted(merged, key=lambda p: abs(sm[p]) if sm[p] is not None else 0, reverse=True)
        chosen = []
        for p in ranked:
            if all(abs(p - q) * grid >= MIN_GAP for q in chosen):
                chosen.append(p)
            if len(chosen) >= expected:
                break
        # 万一间距约束让数量不够，就放宽间距补齐
        if len(chosen) < expected:
            for p in ranked:
                if p not in chosen:
                    chosen.append(p)
                if len(chosen) >= expected:
                    break
        merged = sorted(chosen)

    corners = []
    for idx, p in enumerate(merged):
        left = merged[idx - 1] if idx > 0 else max(0, p - int(150 / grid))
        right = merged[idx + 1] if idx + 1 < len(merged) else min(n - 1, p + int(150 / grid))
        start = (p + left) // 2
        end = (p + right) // 2
        if (end - start) * grid < MIN_CORNER_M:
            start = max(0, p - int(MIN_CORNER_M / grid))
            end = min(n - 1, p + int(MIN_CORNER_M / grid))
        apex_v = series["v"][p] if p < len(series["v"]) else None
        if apex_v is None:
            near = [(abs(j - p), series["v"][j]) for j in range(max(0, p - 20), min(n, p + 21))
                    if series["v"][j] is not None]
            apex_v = min(near)[1] if near else None
        kk = sm[p]
        corners.append({
            "start": round(start * grid, 0),
            "end": round(end * grid, 0),
            "apex_d": round(p * grid, 0),
            "apex_v": apex_v,
            "dir": "L" if (kk is not None and kk > 0) else "R",
            "curv": round(abs(kk), 5) if kk else None,
            "radius_m": round(1 / abs(kk), 0) if kk and abs(kk) > 1e-6 else None,
        })
    return corners


def detect_incidents(series, grid=GRID):
    """检出 spin / 打滑：**横向G 骤降** + 速度断崖。

    关键：正常刹车时速度也掉得很快，但横向 G 不会塌。判据必须是
    「速度断崖 **且** G 掉幅 > 阈值」才算失控 —— 否则每个重刹弯都会被误报。
    """
    v, gx = series["v"], series["gx"]
    n = len(v)
    out = []
    i = 5
    while i < n - 5:
        a, b = v[i - 3], v[i + 3]
        if a and b and b < a - SPIN_DV:
            g0 = gx[i - 3] if gx else None
            g1 = gx[i + 3] if gx else None
            drop = (abs(g0) - abs(g1)) if (g0 is not None and g1 is not None) else 0
            if drop > SPIN_G_DROP:
                out.append({
                    "at_d": round(i * grid, 0),
                    "type": "spin",
                    "from_v": a,
                    "to_v": b,
                    "g_drop": round(drop, 2),
                })
                i += 30
                continue
        i += 1
    return out


def cum_time(series, grid=GRID):
    """按距离累计用时（秒），用于时间损失归因。"""
    v = series["v"]
    n = len(v)
    t = [0.0] * n
    for i in range(1, n):
        a, b = v[i - 1], v[i]
        if a and b and a > 5 and b > 5:
            t[i] = t[i - 1] + grid / ((a + b) / 2 / 3.6)
        else:
            t[i] = t[i - 1]
    return t


def ran_ge(rs, lo_i, d_from, d_to, grid=GRID):
    """取某个距离区间内的最高速度。"""
    a = max(0, int(d_from / grid))
    b = min(len(rs["v"]) - 1, int(d_to / grid))
    vals = [rs["v"][i] for i in range(a, b + 1) if rs["v"][i]]
    return max(vals) if vals else None


def analyse(path, total=DEFAULT_LEN):
    """一次性算完，返回结论 dict。"""
    import laps as L
    import summary as S

    frames, laps_pkts, sess, flashbacks = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    streams = load_streams(path)

    result = {
        "session": sess,
        "flashbacks": flashbacks,
        "laps": [],
        "corners": [],
        "incidents": [],
        "loss_by_segment": [],
    }

    series_list = []
    for lap in lap_objs:
        pts = lap_series(lap, streams)
        series_list.append(resample(pts, total=total))
        st = S.stats(lap["fr"])
        result["laps"].append({
            "n": lap["n"],
            "lap_ms": lap["lap_ms"],
            "lap_str": L.fmt(lap["lap_ms"]),
            "max": st["max"], "avg": st["avg"],
            "full": st["full"], "brake": st["brake"], "coast": st["coast"],
            "coverage_m": round(pts[-1]["d"] - pts[0]["d"], 0) if pts else 0,
        })

    if not series_list:
        return result

    best_i = min(range(len(result["laps"])), key=lambda i: result["laps"][i]["lap_ms"])
    result["best_index"] = best_i
    # 官方弯数作为硬约束（tracks.py 里每个赛道都有 official_turns）
    expected = None
    try:
        import tracks as T
        tinfo = T.get_by_track_id(sess.get("trackId", -1))
        if tinfo:
            expected = tinfo.get("official_turns")
    except Exception:
        expected = None
    result["expected_turns"] = expected
    # 弯道识别用**多圈平均曲率**：单圈走线差异和 yaw 噪声会互相抵消，比最快圈单圈稳
    if len(series_list) > 1:
        avg_k = average_curvature(series_list, GRID)
        avg_v = average_field(series_list, "v", GRID)
        result["corners"] = detect_corners({"v": avg_v}, expected=expected, curv=avg_k)
        result["corner_source"] = "multi_lap_avg"
    else:
        result["corners"] = detect_corners(series_list[best_i], expected=expected)
        result["corner_source"] = "single_lap"

    for i, rs in enumerate(series_list):
        for inc in detect_incidents(rs):
            inc["lap_n"] = result["laps"][i]["n"]
            result["incidents"].append(inc)

    times = [cum_time(rs) for rs in series_list]
    n = len(times[best_i])
    seg = []
    for start in range(0, int(total), 100):
        lo = int(start / GRID)
        hi = min(n - 1, int((start + 100) / GRID))
        if hi <= lo:
            continue
        row = {"from_m": start, "to_m": start + 100, "loss": []}
        for i in range(len(times)):
            if i == best_i:
                row["loss"].append(0.0)
            else:
                row["loss"].append(round(times[i][hi] - times[i][lo]
                                         - (times[best_i][hi] - times[best_i][lo]), 3))
        seg.append(row)
    result["loss_by_segment"] = seg

    rows = []
    for k, c in enumerate(result["corners"], 1):
        lo = int(c["start"] / GRID)
        hi = int(c["end"] / GRID)
        row = {"no": k, "start": c["start"], "end": c["end"],
               "dir": c["dir"], "apex_d": c["apex_d"], "laps": []}
        for rs in series_list:
            seg_v = [rs["v"][i] for i in range(lo, min(hi + 1, n)) if rs["v"][i]]
            if not seg_v:
                row["laps"].append(None)
                continue
            # 方向盘峰值：这个弯里方向打最多的那一瞬
            lo2 = max(0, lo)
            hi2 = min(hi + 1, n)
            st_vals = [abs(rs["steer"][i]) for i in range(lo2, hi2)
                       if rs["steer"][i] is not None]
            # 出弯给油点：弯末之后第一次油门 ≥90%，用距离表示
            gas_d = None
            for i in range(lo2, min(hi2 + int(80 / GRID), n)):
                if rs["thr"][i] is not None and rs["thr"][i] >= 90:
                    gas_d = round(i * GRID, 0)
                    break
            # 刹车点：弯前第一次刹车 ≥20%
            brk_d = None
            for i in range(max(0, lo - int(100 / GRID)), hi2):
                if rs["brk"][i] is not None and rs["brk"][i] >= 20:
                    brk_d = round(i * GRID, 0)
                    break
            row["laps"].append({
                "apex": min(seg_v),
                "entry": ran_ge(rs, lo, c["start"] - 60, c["start"]),
                "exit": ran_ge(rs, hi, c["end"], c["end"] + 60),
                "steer_peak": round(max(st_vals), 2) if st_vals else None,
                "gas_d": gas_d,
                "brake_d": brk_d,
            })
        rows.append(row)
    result["corner_rows"] = rows
    return result
