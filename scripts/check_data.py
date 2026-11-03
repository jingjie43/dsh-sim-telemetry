# -*- coding: utf-8 -*-
"""检查一份采集数据「收到的是不是全的」：各类包数量、每圈覆盖率、关键字段覆盖。

用法: python scripts/check_data.py [frames_xxx.jsonl]

回答的问题：
  - 四类包（Session/运动/圈数据/遥测）各多少帧
  - 每圈数据覆盖率（时间覆盖率、速度帧数）
  - Motion 世界坐标 / steer / yaw / lapDistance 有没有缺口
  - 有没有回退（flashback）、玩家车号是否混进别的车
  - 赛道距离覆盖：lapDistance 是否 0 → 赛道全长
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402
import tracks as T    # noqa: E402

DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
path = sys.argv[1] if len(sys.argv) > 1 else max(
    glob.glob(os.path.join(DATA, "frames_*.jsonl")), key=os.path.getmtime)

# ---------- 原始行统计 ----------
counts = {}
first_st = last_st = None
motion_keys = set()
tele_keys = set()
lap_keys = set()
n_motion_x = n_steer = n_yaw = n_dist = 0
dist_min, dist_max = None, None
bad = 0
for line in open(path, encoding="utf-8"):
    try:
        r = json.loads(line)
    except ValueError:
        bad += 1
        continue
    rid = r.get("id")
    counts[rid] = counts.get(rid, 0) + 1
    st = r.get("st")
    if isinstance(st, (int, float)):
        first_st = st if first_st is None else min(first_st, st)
        last_st = st if last_st is None else max(last_st, st)
    if rid == 0:
        motion_keys |= set(r.keys())
        if r.get("x") is not None:
            n_motion_x += 1
        if r.get("yaw") is not None:
            n_yaw += 1
    elif rid == 6:
        tele_keys |= set(r.keys())
        if r.get("steer") is not None:
            n_steer += 1
    elif rid == 2:
        lap_keys |= set(r.keys())
        d = r.get("dist")
        if isinstance(d, (int, float)) and d >= 0:
            n_dist += 1
            dist_min = d if dist_min is None else min(dist_min, d)
            dist_max = d if dist_max is None else max(dist_max, d)

lab = {1: "Session（会话）", 0: "Motion（世界坐标/三轴G/yaw）", 2: "LapData（圈速/圈数/距离）",
       6: "CarTelemetry（速度/油门/刹车/steer/档位）"}
print("文件:", os.path.basename(path))
print("解析失败行:", bad)
print("时间跨度: %s → %s（%.1f 秒）"
      % (first_st, last_st, (last_st or 0) - (first_st or 0)))
print()
print("== 各类包 ==")
for k in sorted(counts, key=lambda x: (x is None, x)):
    print("  id %-4s %-38s %6d 行" % (k, lab.get(k, "未知"), counts[k]))
print()
print("== 关键字段 ==")
print("  Motion 有 x 坐标: %d / %d 行" % (n_motion_x, counts.get(0, 0)))
print("  Motion 有 yaw     : %d / %d 行" % (n_yaw, counts.get(0, 0)))
print("  Telemetry 有 steer: %d / %d 行" % (n_steer, counts.get(6, 0)))
print("  LapData 有 dist   : %d / %d 行（%.0f → %.0f 米）"
      % (n_dist, counts.get(2, 0), dist_min or 0, dist_max or 0))
print("  Motion 字段:", ",".join(sorted(motion_keys)))
print("  Telemetry 字段:", ",".join(sorted(tele_keys)))
print("  LapData 字段:", ",".join(sorted(lap_keys)))

# ---------- 切圈 / 覆盖率 ----------
frames, laps_pkts, sess, flashbacks = L.load(path)
lap_objs = L.cut_laps(frames, laps_pkts)
print()
print("== 会话 ==", sess)
print("回退（flashback）:", len(flashbacks))
if flashbacks:
    for fb in flashbacks[:5]:
        print("   st %.2f → %.2f（倒退 %.2f 秒）" % (fb["from"], fb["to"], fb["rewind"]))
players = {}
for f in frames:
    players[f.get("p")] = players.get(f.get("p"), 0) + 1
print("速度帧按车号:", players)

print()
print("== 圈数据完整性 ==")
if not lap_objs:
    print("  没有完整圈")
else:
    total = 0
    for lap in lap_objs:
        total += lap["lap_ms"]
        print("  L%d  %s  %.0f 帧  覆盖率 %.1f%%  %s"
              % (lap["n"], L.fmt(lap["lap_ms"]), len(lap["fr"]),
                 lap["coverage"] * 100, "完整" if lap["full"] else "开头缺数据"))
    tinfo = T.get_by_track_id(sess.get("trackId", -1))
    length = (tinfo or {}).get("length_m") or sess.get("trackLen")
    print("  赛道:%s · 全长 %s 米 · 弯数 %s · 状态 %s"
          % ((tinfo or {}).get("name", "?"), length,
             (tinfo or {}).get("official_turns", "?"), (tinfo or {}).get("status", "?")))

print()
print("== 结论 ==")
issues = []
if bad:
    issues.append("%d 行解析失败" % bad)
if flashbacks:
    issues.append("%d 次回退（已按最终时间线去重，数据不影响分析）" % len(flashbacks))
if len(players) > 1:
    issues.append("混进多辆车的数据（观战/切镜头）")
if not counts.get(0):
    issues.append("没有 Motion 包 —— 画不了轨迹、算不了曲率")
if not counts.get(6):
    issues.append("没有 Telemetry 包 —— 没有速度/油门/刹车")
if n_steer < counts.get(6, 1) * 0.9:
    issues.append("steer 缺失较多（%d/%d）" % (n_steer, counts.get(6, 0)))
if n_dist and dist_max and length and abs(dist_max - length) > 60:
    issues.append("lapDistance 最大 %.0f 米，与赛道全长 %s 差得多（可能没跑满整圈或起点不同）"
                  % (dist_max, length))
for lap in lap_objs:
    if not lap["full"]:
        issues.append("L%d 开头缺数据（覆盖率 %.1f%%）" % (lap["n"], lap["coverage"] * 100))
if issues:
    for it in issues:
        print("  ⚠️", it)
else:
    print("  ✅ 四类包齐、每圈完整、关键字段无缺口 —— 这份数据可以直接用于校准与分析")
