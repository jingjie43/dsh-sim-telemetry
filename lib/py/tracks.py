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
        "calibrated_from": "三份实跑数据交叉验证（三取二）：frames_20261026_122836 / 131106 / 143303 · 官方弯名核对（2026-10-28 重建）",
        # ⚠️ 2026-10-28 重建：旧表用 detect_corners「取最强 18 个峰」凑弯数 —— 同一赛道两份数据
        #    （131106 / 143303）跑出的第 6 弯差 740 米、第 8 弯差 870 米，数据稍有不同就整体错位。
        # 新做法：转角法找稳定弯段（三份数据一致）→ 段内平均曲率找 apex → 三份三取二（差 ≤40 米），
        #    18 个弯全部通过。弯名来源：F1 官方《How every Silverstone corner got its name》（2026-07-01），
        #    方向按官方布局（数据在高速大半径弯上的左右判断不可靠，如 Copse / Maggotts）。
        # 弯位说明：entry/exit = 转角法弯段区间，apex = 区间内曲率峰（三取二）。
        "detected_corners": [
            {"no": 1,  "name": "Abbey",       "entry_m": 345,  "apex_m": 373,  "exit_m": 550,  "dir": "R", "radius_m": 91},
            {"no": 2,  "name": "Farm Curve",  "entry_m": 580,  "apex_m": 602,  "exit_m": 760,  "dir": "L", "radius_m": 114},
            {"no": 3,  "name": "Village",     "entry_m": 835,  "apex_m": 943,  "exit_m": 990,  "dir": "R", "radius_m": 33},
            {"no": 4,  "name": "The Loop",    "entry_m": 1000, "apex_m": 1082, "exit_m": 1250, "dir": "L", "radius_m": 25},
            {"no": 5,  "name": "Aintree",     "entry_m": 1250, "apex_m": 1283, "exit_m": 1350, "dir": "L", "radius_m": 98},
            {"no": 6,  "name": "Brooklands",  "entry_m": 1885, "apex_m": 2025, "exit_m": 2090, "dir": "R", "radius_m": 53},
            {"no": 7,  "name": "Luffield",    "entry_m": 2105, "apex_m": 2203, "exit_m": 2345, "dir": "R", "radius_m": 40},
            {"no": 8,  "name": "Woodcote",    "entry_m": 2470, "apex_m": 2622, "exit_m": 2700, "dir": "R", "radius_m": 208},
            {"no": 9,  "name": "Copse",       "entry_m": 3015, "apex_m": 3042, "exit_m": 3240, "dir": "R", "radius_m": 94},
            {"no": 10, "name": "Maggotts",    "entry_m": 3550, "apex_m": 3565, "exit_m": 3635, "dir": "R", "radius_m": 216},
            {"no": 11, "name": "Maggotts",    "entry_m": 3685, "apex_m": 3772, "exit_m": 3810, "dir": "R", "radius_m": 84},
            {"no": 12, "name": "Becketts",    "entry_m": 3830, "apex_m": 3888, "exit_m": 3960, "dir": "L", "radius_m": 84},
            {"no": 13, "name": "Becketts",    "entry_m": 3970, "apex_m": 4073, "exit_m": 4150, "dir": "L", "radius_m": 66},
            {"no": 14, "name": "Chapel",      "entry_m": 4170, "apex_m": 4202, "exit_m": 4285, "dir": "R", "radius_m": 125},
            {"no": 15, "name": "Stowe",       "entry_m": 4950, "apex_m": 5022, "exit_m": 5220, "dir": "R", "radius_m": 78},
            {"no": 16, "name": "Vale",        "entry_m": 5480, "apex_m": 5550, "exit_m": 5575, "dir": "R", "radius_m": 38},
            {"no": 17, "name": "Club",        "entry_m": 5585, "apex_m": 5625, "exit_m": 5730, "dir": "R", "radius_m": 39},
            {"no": 18, "name": "Club",        "entry_m": 5730, "apex_m": 5800, "exit_m": 5880, "dir": "R", "radius_m": 46},
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
    # ——— 蒙扎（Monza）：三次实跑 + 官方命名核对完成（2026-10-28 validated）———
    # 实测确认：trackId=11、Session 报告长度 5798 米、弯数 = 官方 11
    # 弯名来源：F1 官方《How every corner at Monza got its name》（2026-09-03）
    #   Turns 1/2 Prima Variante（旧名 Variante del Rettifilo）· Turn 3 Biassono（旧名 Curva Grande）
    #   Turns 4/5 Seconda Variante（旧名 Curva della Roggia）· Turns 6/7 Lesmo 1 & 2
    #   Turns 8/9/10 Variante Ascari（前有 Curva del Serraglio，非官方弯）· Turn 11 Curva Alboreto（Parabolica）
    # 弯位算法：用「累计转角」找弯（scripts/corners_by_angle.py）—— 比曲率峰值法多抓到了
    #   Curva Grande 这个大半径长弯（半径 216 米，曲率低于原阈值 0.005，之前整个漏掉）
    # 稳定性：10-28 两份独立数据（早/午）用转角法互相对比，11 个弯的 entry 差全部 ≤ 25 米
    # 判定依据：形状（转角/半径/apex 速度）与官方布局一一对应 ——
    #   T1/2 低速 chicane（apex 80/75、半径 37/27）
    #   T3 大半径长弯（半径 216、长 565 米、全油段速度 272~295）
    #   T4/5 中速 chicane（apex 118/112、半径 59/53）
    #   T6/7 两个连续右弯（101°/67°、半径 77/76）
    #   T8/9/10 三连弯（47°/41°/38°、半径 90/122/120）
    #   T11 长弯（161°、半径 78，出弯接主直道）
    # 注：F1 25 是 2025 赛制布局，T3 按数据是左弯（2026 官方文章称 Biassono 为右弯，属 2026 改版/表述差异）
    "monza": {
        "track_id": 11,
        "name": "Monza",
        "country": "IT",
        "length_m": 5798,
        "official_turns": 11,
        "status": STATUS_VALIDATED,
        "calibrated_from": "frames_20261028_120920 + 20261028_123025（转角法，两份互验）+ 官方弯名核对（2026-10-28）",
        "detected_corners": [
            {"no": 1,  "name": "Prima Variante",      "entry_m": 890,  "apex_m": 920,  "exit_m": 950,  "dir": "R", "radius_m": 37,  "angle_deg": 60},
            {"no": 2,  "name": "Prima Variante",      "entry_m": 960,  "apex_m": 990,  "exit_m": 1020, "dir": "L", "radius_m": 27,  "angle_deg": 80},
            {"no": 3,  "name": "Curva Grande",        "entry_m": 1090, "apex_m": 1370, "exit_m": 1655, "dir": "L", "radius_m": 216, "angle_deg": 78},
            {"no": 4,  "name": "Seconda Variante",    "entry_m": 2105, "apex_m": 2140, "exit_m": 2180, "dir": "R", "radius_m": 59,  "angle_deg": 50},
            {"no": 5,  "name": "Seconda Variante",    "entry_m": 2190, "apex_m": 2215, "exit_m": 2240, "dir": "L", "radius_m": 53,  "angle_deg": 42},
            {"no": 6,  "name": "Lesmo 1",             "entry_m": 2460, "apex_m": 2560, "exit_m": 2665, "dir": "R", "radius_m": 77,  "angle_deg": 102},
            {"no": 7,  "name": "Lesmo 2",             "entry_m": 2820, "apex_m": 2890, "exit_m": 2955, "dir": "R", "radius_m": 76,  "angle_deg": 67},
            {"no": 8,  "name": "Ascari",              "entry_m": 3905, "apex_m": 3950, "exit_m": 4000, "dir": "L", "radius_m": 90,  "angle_deg": 47},
            {"no": 9,  "name": "Ascari",              "entry_m": 4015, "apex_m": 4065, "exit_m": 4115, "dir": "R", "radius_m": 122, "angle_deg": 41},
            {"no": 10, "name": "Ascari",              "entry_m": 4130, "apex_m": 4180, "exit_m": 4235, "dir": "L", "radius_m": 120, "angle_deg": 38},
            {"no": 11, "name": "Parabolica (Alboreto)", "entry_m": 5100, "apex_m": 5280, "exit_m": 5460, "dir": "R", "radius_m": 78, "angle_deg": 161},
        ],
        "corners": [],
    },
    "spa": {
        "track_id": 10,
        "name": "Spa-Francorchamps",
        "country": "BE",
        "length_m": 7007,
        "official_turns": 19,   # F1 官方计数（Eau Rouge 2-4 / Les Combes 5-6 等弯组拆分）
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二）：frames_20261103_142238 / 143320 / 144227 · 官方弯名核对（2026-11-03）",
        # 弯名来源：F1 官方《How every corner at the Circuit de Spa-Francorchamps got its name》（2026-07-15）
        # ⚠️ 2026-11-03 修了赛道长度 bug：之前所有赛道共用 DEFAULT_LEN=5890（银石长度），
        #    Spa 7007 米后段（Blanchimont/Bus Stop）被整段丢弃。现在按 Session 包 trackLen 检测。
        # 弯位说明：entry/exit = 转角法弯段区间，apex = 区间内平均曲率峰（三份三取二，差 ≤40 米）。
        "detected_corners": [
            {"no": 1,  "name": "La Source",        "entry_m": 330,  "apex_m": 422,  "exit_m": 480,  "dir": "R", "radius_m": 21},
            {"no": 2,  "name": "Eau Rouge",        "entry_m": 1120, "apex_m": 1150, "exit_m": 1190, "dir": "L", "radius_m": 84},
            {"no": 3,  "name": "Eau Rouge",        "entry_m": 1192, "apex_m": 1207, "exit_m": 1260, "dir": "R", "radius_m": 189},
            {"no": 4,  "name": "Raidillon",        "entry_m": 1280, "apex_m": 1327, "exit_m": 1380, "dir": "L", "radius_m": 178},
            {"no": 5,  "name": "Les Combes",       "entry_m": 2370, "apex_m": 2435, "exit_m": 2478, "dir": "L", "radius_m": 45},
            {"no": 6,  "name": "Les Combes",       "entry_m": 2482, "apex_m": 2520, "exit_m": 2600, "dir": "R", "radius_m": 45},
            {"no": 7,  "name": "Malmedy",          "entry_m": 2605, "apex_m": 2662, "exit_m": 2765, "dir": "R", "radius_m": 76},
            {"no": 8,  "name": "Bruxelles",        "entry_m": 2955, "apex_m": 3065, "exit_m": 3205, "dir": "R", "radius_m": 33},
            {"no": 9,  "name": "Jacky Ickx Curve", "entry_m": 3215, "apex_m": 3333, "exit_m": 3400, "dir": "L", "radius_m": 61},
            {"no": 10, "name": "Pouhon",           "entry_m": 3755, "apex_m": 3798, "exit_m": 3990, "dir": "L", "radius_m": 92},
            {"no": 11, "name": "Pouhon",           "entry_m": 3995, "apex_m": 4052, "exit_m": 4230, "dir": "L", "radius_m": 96},
            {"no": 12, "name": "Fagnes",           "entry_m": 4425, "apex_m": 4482, "exit_m": 4612, "dir": "R", "radius_m": 86},
            {"no": 13, "name": "Fagnes",           "entry_m": 4425, "apex_m": 4548, "exit_m": 4612, "dir": "R", "radius_m": 86},
            {"no": 14, "name": "Campus",           "entry_m": 4875, "apex_m": 4993, "exit_m": 5150, "dir": "L", "radius_m": 47},
            {"no": 15, "name": "Curve Paul Frere", "entry_m": 5155, "apex_m": 5177, "exit_m": 5400, "dir": "R", "radius_m": 86},
            {"no": 16, "name": "Blanchimont",      "entry_m": 5790, "apex_m": 5818, "exit_m": 6055, "dir": "L", "radius_m": 177},
            {"no": 17, "name": "Blanchimont",      "entry_m": 6060, "apex_m": 6213, "exit_m": 6300, "dir": "L", "radius_m": 106},
            {"no": 18, "name": "Bus Stop",         "entry_m": 6700, "apex_m": 6770, "exit_m": 6798, "dir": "R", "radius_m": 21},
            {"no": 19, "name": "Bus Stop",         "entry_m": 6802, "apex_m": 6832, "exit_m": 6895, "dir": "L", "radius_m": 18},
        ],
        "corners": [],
    },
    "bahrain": {
        "track_id": 3,
        "name": "Bahrain International Circuit",
        "country": "BH",
        "length_m": 5412,
        "official_turns": 15,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二）：frames_20261105_164654 / 170036 / 171819 · 官方弯名（Turn 1-15，巴林无传统弯名）",
        # 巴林 Sakhir 布局，官方 15 弯。方向按实测 steer 判断（连续弯组 T1/T2、T5/T6、T11/T12 为同区间拆分）。
        # 数据：164654（2 圈）/ 170036（3 圈，含慢圈）/ 171819（3 圈全正常，最快 1:36.799）
        "detected_corners": [
            {"no":  1, "name": "Turn 1",  "entry_m":  680, "apex_m":  705, "exit_m":  800, "dir": "R", "radius_m":  93},
            {"no":  2, "name": "Turn 2",  "entry_m":  680, "apex_m":  760, "exit_m":  800, "dir": "L", "radius_m":  93},
            {"no":  3, "name": "Turn 3",  "entry_m":  800, "apex_m":  863, "exit_m":  915, "dir": "R", "radius_m":  33},
            {"no":  4, "name": "Turn 4",  "entry_m":  940, "apex_m":  985, "exit_m": 1070, "dir": "L", "radius_m": 149},
            {"no":  5, "name": "Turn 5",  "entry_m": 1470, "apex_m": 1560, "exit_m": 1670, "dir": "R", "radius_m":  31},
            {"no":  6, "name": "Turn 6",  "entry_m": 1470, "apex_m": 1622, "exit_m": 1670, "dir": "L", "radius_m":  31},
            {"no":  7, "name": "Turn 7",  "entry_m": 1690, "apex_m": 1793, "exit_m": 1830, "dir": "R", "radius_m": 107},
            {"no":  8, "name": "Turn 8",  "entry_m": 1835, "apex_m": 1920, "exit_m": 1980, "dir": "L", "radius_m":  54},
            {"no":  9, "name": "Turn 9",  "entry_m": 1985, "apex_m": 2035, "exit_m": 2160, "dir": "R", "radius_m":  87},
            {"no": 10, "name": "Turn 10", "entry_m": 2180, "apex_m": 2295, "exit_m": 2400, "dir": "L", "radius_m":  18},
            {"no": 11, "name": "Turn 11", "entry_m": 2540, "apex_m": 2710, "exit_m": 2820, "dir": "R", "radius_m":  51},
            {"no": 12, "name": "Turn 12", "entry_m": 2540, "apex_m": 2770, "exit_m": 2820, "dir": "L", "radius_m":  51},
            {"no": 13, "name": "Turn 13", "entry_m": 3380, "apex_m": 3478, "exit_m": 3700, "dir": "R", "radius_m":  37},
            {"no": 14, "name": "Turn 14", "entry_m": 3705, "apex_m": 4160, "exit_m": 4260, "dir": "L", "radius_m":  50},
            {"no": 15, "name": "Turn 15", "entry_m": 4860, "apex_m": 4952, "exit_m": 5100, "dir": "L", "radius_m":  34},
        ],
        "corners": [],
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
    优先用**实测弯位** `detected_corners`（实测出来的，pending 阶段也能用 —— 只是没二次验证），
    没有才退回命名弯 `corners`（命名弯的距离字段通常是空的，得 validated 才有意义）。
    """
    if not track:
        return None, None
    src = track.get("detected_corners") or track.get("corners") or []
    # 命名弯表的距离可能还没填（全 None），这种情况直接返回，别浪费时间
    if not src or all(c.get("entry_m") is None for c in src):
        return None, None
    for c in src:
        if c.get("entry_m") is None:
            continue
        if c.get("exit_m") is not None and c["entry_m"] <= dist_m <= c["exit_m"]:
            if c.get("apex_m") is not None and abs(dist_m - c["apex_m"]) <= 15:
                return c, "apex"
            return c, "entry" if dist_m < (c["apex_m"] or c["entry_m"]) else "exit"
    return None, None
