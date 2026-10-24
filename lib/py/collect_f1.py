"""F1 25 遥测采集：玩家标准帧（给摘要/画图分析）+ 全车数据（给"我 vs AI"）。

产出两个文件（都在 SIM_DATA_DIR 下）：
  frames_<ts>.jsonl   玩家车标准帧，分析层（summary.py / plot.py）读这个
                      {"id":6,"st":..,"speed":..,"throttle":..,"brake":..,"gear":..}
                      {"id":2,"st":..,"lastLap":..,"curLap":..,"lapNum":..}
                      {"id":1,"st":..,"trackId":..,"sessionType":..,"trackLen":..}
  allcars_<ts>.jsonl  每 250ms 一行的全车摘要（速度/油门/刹车/档位 × 22 车）

历史教训（别再踩）：
- 以前只写 allcars 缩写格式（t/p/sp/th/br/g），分析层一个字段都认不出来，
  等于采了一轮白跑。玩家标准帧必须和 load() 认的字段名保持一致。
- 以前速度帧限流到 0.25s（4Hz），曲线画出来全是棱角、刹车点判断不了。
  画图要 20Hz 才够用。
"""
import json
import os
import socket
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
TARGET_LAPS = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # 0 = 不限圈数
UDP_PORT = int(os.environ.get("SIM_UDP_PORT") or "20777")
OUTDIR = os.environ.get("SIM_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUTDIR, exist_ok=True)

FRAME_HZ = 20.0        # 标准帧采样率（分析/画图用）
FRAME_DT = 1.0 / FRAME_HZ
ALL_CARS_DT = 0.25     # 全车摘要采样间隔

stamp = time.strftime("%Y%m%d_%H%M%S")
lane = os.path.join(OUTDIR, f"frames_{stamp}.jsonl")
out = os.path.join(OUTDIR, f"allcars_{stamp}.jsonl")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", UDP_PORT))
sock.settimeout(1.0)

fh_fr = open(lane, "w", encoding="utf-8", buffering=1)
fh_all = open(out, "w", encoding="utf-8", buffering=1)

print(f"[sim] 采集 → {lane}")
print(f"[sim]         {out}")
print(f"[sim] 时长 {DURATION:.0f}s · 目标圈数 {TARGET_LAPS or '不限'} · UDP 端口 {UDP_PORT} · 标准帧 {FRAME_HZ:.0f}Hz")

start = time.time()
last_frame_t = 0.0
last_all_t = 0.0
sess = {}
frames = 0
allcars_rows = 0
laps_done = 0
seen_last_lap = None
sess_saved = False
main_player = None      # 第一次收到的 playerCarIndex，用来发现切换
player_switches = 0


def save_session(st, payload):
    global sess_saved
    sess = payload
    fh_fr.write(json.dumps({"id": 1, "st": round(st, 3), **payload}) + "\n")
    sess_saved = True
    print("[sim] 会话:", payload, flush=True)


while time.time() - start < DURATION:
    try:
        data, _ = sock.recvfrom(4096)
    except socket.timeout:
        continue
    n = len(data)
    if n < 29:
        continue
    # ⚠️ packetId 在 header 的 data[6]：data[0..1] format、[2] gameYear、[3][4] 版本、
    #    [5] packetVersion（F1 25 恒为 1）、[6] packetId。以前写成 data[5]，
    #    于是每个包都被当成 packetId=1 的 session 包，速度帧和圈数据一个都进不来。
    pkt_id = data[6]
    st = struct.unpack_from("<f", data, 15)[0]
    player = data[27] if n > 27 else 0
    now = time.time()

    # m_playerCarIndex 在观战 / 切镜头时会变。变了还照收，就会把两辆车的数据
    # 交替写进同一圈，速度曲线变成来回抖的毛刺。提醒一句，别让它悄悄发生。
    if pkt_id == 6 and player != main_player:
        if main_player is None:
            main_player = player
        else:
            player_switches += 1
            if player_switches == 1:
                print(f"[sim] ⚠ playerCarIndex 变了（{main_player} → {player}），"
                      f"可能是观战/切镜头，这之后的帧会混车", flush=True)

    if pkt_id == 6 and n >= 29 + 60 * 22:
        # --- 玩家标准帧（画图/摘要用）---
        if now - last_frame_t >= FRAME_DT:
            last_frame_t = now
            pb = 29 + player * 60
            fh_fr.write(json.dumps({
                "id": 6,
                "p": player,
                "st": round(st, 3),
                "speed": struct.unpack_from("<H", data, pb)[0],
                "throttle": round(struct.unpack_from("<f", data, pb + 2)[0] * 100),
                "brake": round(struct.unpack_from("<f", data, pb + 10)[0] * 100),
                "gear": struct.unpack_from("<b", data, pb + 15)[0] + 1,
            }) + "\n")
            frames += 1
            if frames % 200 == 0:
                print(f"[sim] 标准帧 {frames} 行", flush=True)
        # --- 全车摘要（我 vs AI 用）---
        if now - last_all_t >= ALL_CARS_DT:
            last_all_t = now
            rec = {"t": round(st, 3), "p": player, "sp": [], "th": [], "br": [], "g": []}
            for i in range(22):
                b = 29 + i * 60
                rec["sp"].append(struct.unpack_from("<H", data, b)[0])
                rec["th"].append(round(struct.unpack_from("<f", data, b + 2)[0] * 100))
                rec["br"].append(round(struct.unpack_from("<f", data, b + 10)[0] * 100))
                rec["g"].append(struct.unpack_from("<b", data, b + 15)[0] + 1)
            fh_all.write(json.dumps(rec) + "\n")
            allcars_rows += 1

    elif pkt_id == 2 and n >= 29 + 57 * 22:
        pb = 29 + player * 57
        last_ms = struct.unpack_from("<I", data, pb)[0]
        cur_ms = struct.unpack_from("<I", data, pb + 4)[0]
        lap_num = data[pb + 25]
        # --- 玩家圈数据帧（切圈/圈速的权威来源）---
        fh_fr.write(json.dumps({
            "id": 2, "st": round(st, 3),
            "lastLap": last_ms, "curLap": cur_ms, "lapNum": lap_num,
        }) + "\n")
        # --- 圈数检测：lastLap 变化一次 = 跑完一圈 ---
        if last_ms and last_ms != seen_last_lap:
            seen_last_lap = last_ms
            laps_done += 1
            print(f"[sim] 已完成 {laps_done} 圈（目标 {TARGET_LAPS or '不限'}）", flush=True)
            if TARGET_LAPS > 0 and laps_done >= TARGET_LAPS:
                print(f"[sim] 达到目标圈数 {TARGET_LAPS}，自动停止采集", flush=True)
                break

    elif pkt_id == 1:
        payload = {
            "trackId": struct.unpack_from("<b", data, 36)[0],
            "trackLen": struct.unpack_from("<H", data, 33)[0],
            "sessionType": data[35],
            "weather": data[29],
        }
        if not sess_saved:
            save_session(st, payload)

fh_fr.close()
fh_all.close()
print(f"[sim] 结束：标准帧 {frames} 行 · 全车 {allcars_rows} 行 · 完成 {laps_done} 圈")
print("[sim] 输出:", lane)

# 采集一结束，自动生成摘要 + CSV 表格
try:
    here = os.path.dirname(os.path.abspath(__file__))
    print("[sim] 生成摘要与表格…", flush=True)
    subprocess.run([sys.executable, os.path.join(here, "summary.py")], timeout=180)
except Exception as exc:  # noqa: BLE001
    print("[sim] 摘要生成失败:", exc)
