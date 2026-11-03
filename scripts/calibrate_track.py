# -*- coding: utf-8 -*-
"""赛道弯位校准：用实跑遥测生成 tracks.py 的赛道条目。

用法:
  python scripts/calibrate_track.py <key> <official_turns> [frames_xxx.jsonl]

例:
  python scripts/calibrate_track.py monza 11
  python scripts/calibrate_track.py monza 11 frames_20261027_213540.jsonl

输出：可直接粘进 tracks.py 的 Python 字典片段（含 track_id / 赛道长度 / 官方弯数 /
      detected_corners 实测弯位）。多圈数据会自动取平均曲率，单圈会提示不够稳。

判定口径与 engineer.py 一致：
  - 曲率 κ = dψ/ds（保留符号，左正右负）
  - 多圈按距离对齐后取平均曲率（单圈走线差异和 yaw 噪声互相抵消）
  - 官方弯数 official_turns 当硬约束：按曲率强度排序取前 N + 最小间距 80 米
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import engineer as E  # noqa: E402
import laps as L      # noqa: E402
import tracks as T    # noqa: E402

DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")
GRID = E.GRID


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    key = sys.argv[1].lower()
    expected = int(sys.argv[2])
    args = [a for a in sys.argv[3:] if not a.startswith("--")]
    path = args[0] if args else max(
        glob.glob(os.path.join(DATA, "frames_*.jsonl")), key=os.path.getmtime)
    drop_slow = "--drop-slow" in sys.argv
    if not os.path.exists(path):
        print("找不到数据文件:", path)
        return 1

    frames, laps_pkts, sess, flashbacks = L.load(path)
    lap_objs = L.cut_laps(frames, laps_pkts)
    if drop_slow and len(lap_objs) > 1:
        best_ms = min(l["lap_ms"] for l in lap_objs)
        kept = [l for l in lap_objs if l["lap_ms"] <= best_ms * 1.05]
        if kept and len(kept) != len(lap_objs):
            print("已排除 %d 个慢圈（比最快圈慢 >5%%，多半是暖胎/出场圈）"
                  % (len(lap_objs) - len(kept)))
            lap_objs = kept
    if not lap_objs:
        print("这份数据里还没有完整圈 —— 至少跑满 1 圈再校准（建议 3 圈，取平均更稳）")
        print("  文件:", os.path.basename(path))
        return 2

    streams = E.load_streams(path)
    track_id = sess.get("trackId")
    existing = T.get_by_track_id(track_id) if track_id is not None else None
    if existing:
        print("⚠️ trackId %s 已存在条目: %s「%s」" % (track_id, existing.get("key", "?"),
                                                    existing.get("name", "?")))
    series = [E.resample(E.lap_series(l, streams)) for l in lap_objs]
    total = E.detect_track_len(laps_pkts, sess)
    if track_id is not None:
        track_len = sess.get("trackLen") or total
        if track_len and abs(track_len - total) > 200:
            print("提示：Session 报告赛道长度 %s 米，与默认 %s 米差得多，"
                  "重采样按 %s 米做，超出部分会被截断" % (track_len, total, total))

    if len(series) > 1:
        cur = E.average_curvature(series)
        avg_v = E.average_field(series, "v")
        corners = E.detect_corners({"v": avg_v}, expected=expected, curv=cur)
        source = "multi_lap_avg"
    else:
        cur = E.curvature(E._yaw_series(series[0]))
        corners = E.detect_corners(series[0], expected=expected)
        source = "single_lap"
        print("⚠️ 只有 1 圈：弯位可先填，但建议再跑一次多圈平均后覆盖（单圈走线会影响弯位）")

    print()
    print("=" * 68)
    print("识别结果：%d 圈 · 弯道 %d 个（官方弯数 %d）· 来源 %s · 回退 %d 次"
          % (len(lap_objs), len(corners), expected, source, len(flashbacks)))
    for lap in lap_objs:
        print("  L%d  %s" % (lap["n"], L.fmt(lap["lap_ms"])))
    print()
    print("弯位表：")
    print("  第N弯  方向  entry      apex       exit       半径")
    for i, c in enumerate(corners, 1):
        print("  %3d    %s   %6.0f    %6.0f    %6.0f    %5s"
              % (i, c["dir"], c["start"], c["apex_d"], c["end"], c.get("radius_m") or "-"))

    print()
    print("=" * 68)
    print("粘进 tracks.py 的条目（把 name/country 改成正确的）：")
    print()
    print('    "%s": {' % key)
    print('        "track_id": %s,' % track_id)
    print('        "name": "%s",' % key.capitalize())
    print('        "country": "",')
    print('        "length_m": %s,' % (sess.get("trackLen") or int(total)))
    print('        "official_turns": %d,' % expected)
    print('        "status": STATUS_PENDING,')
    print('        "calibrated_from": "%s · %d 圈%s（%s）",'
          % (os.path.basename(path), len(lap_objs),
             "多圈平均曲率" if source == "multi_lap_avg" else "单圈",
             "2026-10-27"))
    print('        "detected_corners": [')
    for i, c in enumerate(corners, 1):
        print('            {"no": %d, "entry_m": %.0f, "apex_m": %.0f, "exit_m": %.0f, '
              '"dir": "%s", "radius_m": %s},'
              % (i, c["start"], c["apex_d"], c["end"], c["dir"],
                 ("%.0f" % c["radius_m"]) if c.get("radius_m") else "None"))
    print('        ],')
    print('        "corners": [],   # 命名弯待补')
    print('    },')
    print()
    print("注意：单次校准先标 status=STATUS_PENDING；再跑一次同样数据验证弯位"
          "（相邻两次 apex 差 < 30 米）后再改 STATUS_VALIDATED。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
