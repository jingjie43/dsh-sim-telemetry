"""F1 25 全车遥测采集：玩家 + 全部 AI 车（22 辆）。用于"我 vs AI"对比。

每 250ms 记一行，包含所有车的速度/油门/刹车/档位 + 圈速。
"""
import json
import os
import subprocess
import socket
import struct
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
TARGET_LAPS = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # 0 = 不限圈数
OUTDIR = os.environ.get("F1_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "f1data")
os.makedirs(OUTDIR, exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")
out = os.path.join(OUTDIR, f"allcars_{stamp}.jsonl")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", 20777))
sock.settimeout(1.0)

fh = open(out, "w", encoding="utf-8", buffering=1)
print(f"[all] 采集全部车 → {out}  {DURATION:.0f}s  目标圈数={TARGET_LAPS or '不限'}")
start = time.time()
last_write = 0.0
tracks = {}
sess = {}
count = 0

while time.time() - start < DURATION:
    try:
        data, _ = sock.recvfrom(4096)
    except socket.timeout:
        continue
    n = len(data)
    if n < 29:
        continue
    pkt_id = data[5]
    st = struct.unpack_from("<f", data, 15)[0]
    player = data[27]

    if pkt_id == 6 and n >= 29 + 60 * 22:
        now = time.time()
        if now - last_write < 0.25:
            continue
        last_write = now
        rec = {"t": round(st, 3), "p": player, "sp": [], "th": [], "br": [], "g": []}
        for i in range(22):
            b = 29 + i * 60
            rec["sp"].append(struct.unpack_from("<H", data, b)[0])
            rec["th"].append(round(struct.unpack_from("<f", data, b + 2)[0] * 100))
            rec["br"].append(round(struct.unpack_from("<f", data, b + 10)[0] * 100))
            rec["g"].append(struct.unpack_from("<b", data, b + 15)[0] + 1)
        fh.write(json.dumps(rec) + "\n")
        count += 1
        if count % 40 == 0:
            print(f"[all] 已收遥测 {count} 行（t={rec['t']:.0f}s）", flush=True)
    elif pkt_id == 2 and n >= 29 + 57 * 22:
        rec = {"t": round(st, 3), "lap": []}
        for i in range(22):
            b = 29 + i * 57
            rec["lap"].append([struct.unpack_from("<I", data, b)[0], struct.unpack_from("<I", data, b + 4)[0]])
        # 圈数检测：玩家车的 lastLap 变化一次 = 跑完一圈
        pb = 29 + player * 57
        last_ms = struct.unpack_from("<I", data, pb)[0]
        if last_ms and last_ms != globals().get("_seen_lap"):
            globals()["_seen_lap"] = last_ms
            globals()["_laps_done"] = globals().get("_laps_done", 0) + 1
            done = globals()["_laps_done"]
            print(f"[all] 已完成 {done} 圈（目标 {TARGET_LAPS or '不限'}）", flush=True)
            if TARGET_LAPS > 0 and done >= TARGET_LAPS:
                print(f"[all] 达到目标圈数 {TARGET_LAPS}，自动停止采集", flush=True)
                break
        # 每 1 秒记一次圈速
        fh.write(json.dumps(rec) + "\n")
    elif pkt_id == 1 and not sess:
        sess = {
            "trackId": struct.unpack_from("<b", data, 36)[0],
            "trackLen": struct.unpack_from("<H", data, 33)[0],
            "sessionType": data[35],
            "weather": data[29],
        }
        fh.write(json.dumps({"session": sess}) + "\n")
        print("[all] 会话:", sess)

fh.close()
print(f"[all] 结束，遥测行数 {count}")
print("[all] 输出:", out)

# 采集一结束，自动生成摘要 + CSV 表格（达到目标圈数时会自动走到这里）
try:
    here = os.path.dirname(os.path.abspath(__file__))
    print("[all] 生成摘要与表格…", flush=True)
    subprocess.run([sys.executable, os.path.join(here, "f1_summary.py")], timeout=180)
except Exception as exc:  # noqa: BLE001
    print("[all] 摘要生成失败:", exc)
