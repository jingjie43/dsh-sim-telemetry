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

# 日志自己写文件，不依赖宿主的 stdio（2026-10-26 踩坑）：
#   采集器是 detached 启动的，脱离宿主进程树后 stdout 没人接 —— 宿主那边
#   无论是 pipe 还是裸 fd 都拿不到内容（pipe 会在宿主退出时断掉，裸 fd 在 Windows 上不生效）。
#   所以由 Python 自己把 stdout/stderr 重定向到日志文件，路径由 SIM_LOG 传进来。
_log_path = os.environ.get("SIM_LOG") or os.path.join(OUTDIR, f"collect_{stamp}.log")
try:
    _log_fh = open(_log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = _log_fh
    sys.stderr = _log_fh
except Exception:
    pass

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
motions = 0             # Motion 包（坐标 + 三轴 G）写入行数
last_motion_t = 0.0


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
                # m_steer（float @6，-1..1）：方向盘转角。
                # 识别弯道靠它才靠谱 —— 高速弯/全油弯速度上没谷，但方向照样打；
                # S 弯靠它的正负翻转天然分开。以前只收不记，等于白扔。
                "steer": round(struct.unpack_from("<f", data, pb + 6)[0], 3),
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

    elif pkt_id == 0 and n >= 29 + 60 * 22:
        # Motion 包（packetId 0）：每车 60 字节 = 15 个 float。
        #   @0/@4/@8   worldPosition X/Y/Z（米）—— 实跑轨迹，能反推赛道几何、画赛道图
        #   @12..@23   worldVelocity
        #   @24..@35   forwardDir
        #   @36..@47   rightDir
        #   @48 横向G · @52 纵向G · @56 垂直G
        # 横向 G 有什么用：弯半径 R = v²/a、左右方向、推头/甩尾、trail braking、抓地极限。
        # 世界坐标有什么用：用自己的轨迹重建赛道形状和弯位，不必去逆拆游戏的 ERPK 资源包。
        if now - last_motion_t >= FRAME_DT:
            last_motion_t = now
            pb = 29 + player * 60
            vals = struct.unpack_from("<15f", data, pb)
            # ⚠️ F1 22+ 的 CarMotionData 里方向向量是 **int16**（@24..@35 共 12 字节），
            #    不是 float。所以三个 float 的 G 在 @36/@40/@44，yaw/pitch/roll 在 @48/@52/@56。
            #    2026-10-25 就是按 float 算错了：把 yaw 当成横向 G 写进 gx（表现是直道也不归零、
            #    范围正好 ±π）。修正后 gx 是真横向 G，另存 yaw 用于算曲率。
            fh_fr.write(json.dumps({
                "id": 0, "st": round(st, 3),
                "x": round(vals[0], 2), "y": round(vals[1], 2), "z": round(vals[2], 2),
                "gx": round(vals[9], 3),     # @36 横向 G
                "gy": round(vals[10], 3),    # @40 纵向 G
                "gz": round(vals[11], 3),    # @44 垂直 G
                "yaw": round(vals[12], 4),   # @48 车头朝向（弧度，-π..π）
            }) + "\n")
            motions += 1
            if motions % 200 == 0:
                print(f"[sim] 运动帧 {motions} 行（横向G {vals[12]:+.2f}）", flush=True)

    elif pkt_id == 2 and n >= 29 + 57 * 22:
        pb = 29 + player * 57
        last_ms = struct.unpack_from("<I", data, pb)[0]
        cur_ms = struct.unpack_from("<I", data, pb + 4)[0]
        # F1 24/25 的 LapData 单包 57 字节布局（偏移别写错，2026-10-24 踩过）：
        #   @0 lastLapTime u32 · @4 currentLapTime u32
        #   @8..19 sector1/2 与 delta（uint16 + uint8 混合，不是纯 u16/u32）
        #   @20 lapDistance f32 · @24 totalDistance f32 · @28 safetyCarDelta f32
        #   @32 carPosition u8 · @33 currentLapNum u8
        lap_num = data[pb + 33]
        # m_lapDistance（float @20）：本圈已行驶距离（米）。有了它，分析层就能按
        # 「赛道位置」对齐多圈做逐弯对比；只靠速度积分反推误差 -1.4%~-3.7%，弯道对不齐。
        lap_dist = struct.unpack_from("<f", data, pb + 20)[0]
        # --- 玩家圈数据帧（切圈/圈速的权威来源）---
        fh_fr.write(json.dumps({
            "id": 2, "st": round(st, 3),
            "lastLap": last_ms, "curLap": cur_ms, "lapNum": lap_num,
            "dist": round(lap_dist, 1),
        }) + "\n")
        # --- 圈数检测：lastLap 变化 = 跑完一圈 ---
        # ⚠️ 采集刚开头那几秒 lastLap 会抖一两下（刚过线 / 刚从维修区出来 / 重进赛道），
        #    那不是「跑完的圈」。以前把抖的那两下也算进去，于是 autoReportLaps=3
        #    实际只跑完 1 圈就提前停了（2026-10-24 实测踩到）。
        if last_ms and last_ms != seen_last_lap:
            first_seen = seen_last_lap is None
            seen_last_lap = last_ms
            if not first_seen and time.time() - start > 3.0:
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
print(f"[sim] 结束：标准帧 {frames} 行 · 运动帧 {motions} 行 · 全车 {allcars_rows} 行 · 完成 {laps_done} 圈")
print("[sim] 输出:", lane)

# 采集一结束（跑满设定圈数时会自动走到这里），把摘要、表格、图一次出全。
# 静戒 2026-10-24 要求：图片也要跟着圈数设定自动生成，不用再手动喊。
here = os.path.dirname(os.path.abspath(__file__))
for script, label in (("summary.py", "摘要与表格"),
                      ("plot.py", "速度曲线图与油门刹车图"),
                      ("trackmap.py", "赛道轨迹图（带弯位编号）"),
                      ("report.py", "比赛工程师报告")):
    try:
        print(f"[sim] 生成{label}…", flush=True)
        subprocess.run([sys.executable, os.path.join(here, script)], timeout=240)
    except Exception as exc:  # noqa: BLE001
        print(f"[sim] {label}生成失败:", exc)
