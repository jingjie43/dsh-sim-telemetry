"""赛道弯位表：把遥测落到「赛道第几米」，再映射到官方弯号 / 弯名。

⚠️ 数据来源规则（别乱填，错一个比没有更糟）
- **弯名与顺序**：公开的赛道命名，这部分可靠。
- **距离（entry_m / apex_m / exit_m）**：必须用**实测遥测校准**。
  原因：
    1. 公开资料没有「每个弯第几米」的权威表（查过 F1 官方 / Autosport / sim racing 社区，都只有弯名和赛道全长）
    2. F1 25 的游戏数据打不开 —— 赛道几何在 `silverstone_common.erp`（ERPK 私有打包格式），
       赛道数据库 `gamedatabases.2025.bin` 是加密二进制（无标准魔数）
    3. 唯一可靠的是玩家实跑一圈的 `m_lapDistance`（游戏内定义 = 官方定义）
- 校准流程：
    跑一圈 → 按 dist 找速度谷 / 刹车点 → 得到候选弯位 → 按弯名顺序对应 → 人工核对 → 把 validated 置 True

为什么要有这张表（解决什么）：
  仅靠「速度波谷识别弯道」在连续 S 弯上会把几个弯粘成一段（Silverstone 实测：18 个官方弯只识别出
  6~7 个）。有了位置就不用"识别"了 —— 直接查表：第 4730 米 = Maggotts，没有第二种可能。
"""

STATUS_PENDING = "pending"      # 距离未校准，只有弯名
STATUS_VALIDATED = "validated"  # 距离已用实测数据校准并核对

TRACKS = {
    # F1 25 内部赛道名 / trackId（Session 包里的 m_trackId）
    "silverstone": {
        "track_id": 7,
        "name": "Silverstone",
        "country": "GB",
        "length_m": 5890,
        "official_turns": 18,   # F1 官方计数（含弯组拆分）
        "status": STATUS_VALIDATED,
        "calibrated_from": "frames_20261026_131106.jsonl · 3 圈多圈平均（2026-10-26）",
        # ✅ 实测弯位（曲率识别 + 3 圈平均）：赛道第几米到第几米是一个弯。
        #    报告里的「第 N 弯」编号就是这里的 no，可直接拿来定位、画图、做逐弯统计。
        #    误差量级：几十米（算的是玩家实际走线，不是赛道中心线）。
        "detected_corners": [
            {"no": 1,  "entry_m": 320,  "apex_m": 395,  "exit_m": 505,  "dir": "R", "radius_m": 139},
            {"no": 2,  "entry_m": 505,  "apex_m": 620,  "exit_m": 780,  "dir": "L", "radius_m": 160},
            {"no": 3,  "entry_m": 780,  "apex_m": 945,  "exit_m": 1005, "dir": "R", "radius_m": 49},
            {"no": 4,  "entry_m": 1005, "apex_m": 1070, "exit_m": 1155, "dir": "L", "radius_m": 34},
            {"no": 5,  "entry_m": 1155, "apex_m": 1245, "exit_m": 1640, "dir": "L", "radius_m": 124},
            {"no": 6,  "entry_m": 1640, "apex_m": 2035, "exit_m": 2120, "dir": "L", "radius_m": 65},
            {"no": 7,  "entry_m": 2120, "apex_m": 2210, "exit_m": 2640, "dir": "R", "radius_m": 45},
            {"no": 8,  "entry_m": 2640, "apex_m": 3070, "exit_m": 3105, "dir": "R", "radius_m": 136},
            {"no": 9,  "entry_m": 3105, "apex_m": 3145, "exit_m": 3455, "dir": "R", "radius_m": 142},
            {"no": 10, "entry_m": 3455, "apex_m": 3770, "exit_m": 3830, "dir": "R", "radius_m": 164},
            {"no": 11, "entry_m": 3830, "apex_m": 3895, "exit_m": 3980, "dir": "L", "radius_m": 123},
            {"no": 12, "entry_m": 3980, "apex_m": 4065, "exit_m": 4130, "dir": "R", "radius_m": 88},
            {"no": 13, "entry_m": 4130, "apex_m": 4195, "exit_m": 4625, "dir": "L", "radius_m": 184},
            {"no": 14, "entry_m": 4625, "apex_m": 5055, "exit_m": 5295, "dir": "R", "radius_m": 101},
            {"no": 15, "entry_m": 5295, "apex_m": 5540, "exit_m": 5580, "dir": "L", "radius_m": 47},
            {"no": 16, "entry_m": 5580, "apex_m": 5625, "exit_m": 5685, "dir": "R", "radius_m": 54},
            {"no": 17, "entry_m": 5685, "apex_m": 5745, "exit_m": 5780, "dir": "R", "radius_m": 116},
            {"no": 18, "entry_m": 5780, "apex_m": 5820, "exit_m": 5855, "dir": "R", "radius_m": 135},
        ],
        # 15 个公认命名弯。官方 18 是把这个列表里的弯组再拆开计数
        # （Maggotts / Becketts / Club 等是连续弯组，位置确定后再决定拆不拆）
        "corners": [
            {"no": 1,  "name": "Abbey",       "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 2,  "name": "Farm Curve",  "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 3,  "name": "Village",     "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 4,  "name": "The Loop",    "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 5,  "name": "Aintree",     "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 6,  "name": "Brooklands",  "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 7,  "name": "Luffield",    "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 8,  "name": "Woodcote",    "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 9,  "name": "Copse",       "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 10, "name": "Maggotts",    "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 11, "name": "Becketts",    "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 12, "name": "Chapel",      "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 13, "name": "Stowe",       "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 14, "name": "Vale",        "entry_m": None, "apex_m": None, "exit_m": None},
            {"no": 15, "name": "Club",        "entry_m": None, "apex_m": None, "exit_m": None},
        ],
    },
}

# trackId → 内部 key 的反查表（Session 包只给数字 trackId）
BY_TRACK_ID = {v["track_id"]: k for k, v in TRACKS.items()}


def get_by_track_id(track_id):
    key = BY_TRACK_ID.get(track_id)
    return TRACKS.get(key) if key else None


def corner_at(track, dist_m):
    """给一个赛道位置（米），返回落在哪个弯里；(corner, phase) 或 (None, None)。

    phase: 'entry' / 'apex' / 'exit'。
    优先用**实测弯位** `detected_corners`（已校准），没有才退回命名弯 `corners`。
    """
    if not track or track.get("status") != STATUS_VALIDATED:
        return None, None
    src = track.get("detected_corners") or track.get("corners") or []
    for c in src:
        if c.get("entry_m") is None:
            continue
        if c.get("exit_m") is not None and c["entry_m"] <= dist_m <= c["exit_m"]:
            if c.get("apex_m") is not None and abs(dist_m - c["apex_m"]) <= 15:
                return c, "apex"
            return c, "entry" if dist_m < (c["apex_m"] or c["entry_m"]) else "exit"
    return None, None
