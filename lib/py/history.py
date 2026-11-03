# -*- coding: utf-8 -*-
"""历史采集记录管理：扫描 / 删除 / 打包。

JSON 输出，给插件后端（index.js）调用：
  python history.py list   [data_dir]
  python history.py delete [data_dir] <ts>[,<ts>...] [lap_no]
  python history.py export [data_dir] <zip_path> <ts>[,<ts>...]
"""
import csv
import json
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("SIM_DATA_DIR") or os.path.expanduser(r"~\.dsh\sim-telemetry")


def read_track_id(path):
    """只读前几行，找 Session 包（id=1）的 trackId。"""
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 200:
                    break
                if '"id": 1' in line or '"id":1' in line:
                    r = json.loads(line)
                    return r.get("trackId")
    except Exception:
        pass
    return None


def read_laps(path):
    rows = []
    try:
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                try:
                    rows.append({
                        "lap": int(r["lap"]),
                        "lap_ms": int(r["lapTimeMs"]),
                        "max": int(r["maxSpeed"]),
                        "avg": int(r["avgSpeed"]),
                    })
                except Exception:
                    continue
    except Exception:
        pass
    return rows


def track_name(track_id):
    try:
        sys.path.insert(0, os.path.join(HERE, "..", "lib", "py"))
        import tracks as T
        t = T.get_by_track_id(track_id)
        if t:
            return t["name"]
    except Exception:
        pass
    return "track%s" % track_id if track_id is not None else "?"


def scan(data_dir):
    out = []
    if not os.path.isdir(data_dir):
        return out
    for name in sorted(os.listdir(data_dir), reverse=True):
        m = re.match(r"frames_(\d{8}_\d{6})\.jsonl$", name)
        if not m:
            continue
        ts = m.group(1)
        path = os.path.join(data_dir, name)
        try:
            size = os.path.getsize(path)
        except Exception:
            size = 0
        if size < 10000:
            continue
        tid = read_track_id(path)
        laps = read_laps(os.path.join(data_dir, "laps_%s.csv" % ts))
        best = min((l["lap_ms"] for l in laps), default=None)
        out.append({
            "ts": ts,
            "file": name,
            "size": size,
            "trackId": tid,
            "track": track_name(tid),
            "laps": laps,
            "lapCount": len(laps),
            "bestMs": best,
            "bestStr": fmt_ms(best) if best else None,
            "time": fmt_ts(ts),
        })
    return out


def fmt_ms(ms):
    if not ms:
        return None
    s = ms / 1000.0
    return "%d:%06.3f" % (int(s // 60), s % 60)


def fmt_ts(ts):
    # 20261103_142238 -> 2026-11-03 14:22
    try:
        return "%s-%s-%s %s:%s" % (ts[0:4], ts[4:6], ts[6:8], ts[9:11], ts[11:13])
    except Exception:
        return ts


def related_files(data_dir, ts):
    """一份采集对应的所有文件。"""
    return [
        "frames_%s.jsonl" % ts,
        "allcars_%s.jsonl" % ts,
        "laps_%s.csv" % ts,
        "summary_full_%s.md" % ts,
        "corners_%s.md" % ts,
        "state_summary_%s.json" % ts,
        "state_summary.json" if False else None,
        "collect_%s.log" % ts,
    ]


def do_delete(data_dir, ts_list):
    deleted = []
    for ts in ts_list:
        candidates = related_files(data_dir, ts) + [
            "collect_%s.log" % ts,
            "plots/speed_%s.png" % ts,
            "plots/pedals_%s.png" % ts,
            "plots/track_%s.png" % ts,
            "plots/corners_%s.png" % ts,
        ]
        for fn in candidates:
            if not fn:
                continue
            p = os.path.join(data_dir, fn)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    deleted.append(fn)
                except Exception as e:
                    deleted.append("%s: %s" % (fn, e))
    return deleted


def do_export(data_dir, zip_path, ts_list):
    added = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for ts in ts_list:
            files = [f for f in related_files(data_dir, ts) if f] + [
                "plots/speed_%s.png" % ts,
                "plots/pedals_%s.png" % ts,
                "plots/track_%s.png" % ts,
            ]
            for fn in files:
                p = os.path.join(data_dir, fn)
                if os.path.isfile(p):
                    z.write(p, fn)
                    added.append(fn)
    return added


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "need action"}, ensure_ascii=False))
        return 1
    action = sys.argv[1]
    data_dir = DATA
    if len(sys.argv) > 2 and os.path.isdir(sys.argv[2]):
        data_dir = sys.argv[2]

    if action == "list":
        print(json.dumps({"ok": True, "items": scan(data_dir)}, ensure_ascii=False))
        return 0
    if action == "delete":
        ts_arg = sys.argv[2] if len(sys.argv) > 2 and not os.path.isdir(sys.argv[2]) else sys.argv[3]
        ts_list = [t.strip() for t in ts_arg.split(",") if t.strip()]
        print(json.dumps({"ok": True, "deleted": do_delete(data_dir, ts_list)}, ensure_ascii=False))
        return 0
    if action == "export":
        zpath = sys.argv[2]
        ts_arg = sys.argv[3]
        ts_list = [t.strip() for t in ts_arg.split(",") if t.strip()]
        print(json.dumps({"ok": True, "zip": zpath, "files": do_export(data_dir, zpath, ts_list)}, ensure_ascii=False))
        return 0
    print(json.dumps({"error": "unknown action"}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
