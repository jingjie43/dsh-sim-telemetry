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
    "monaco": {
        "track_id": 5,
        "name": "Circuit de Monaco",
        "country": "MC",
        "length_m": 3337,
        "official_turns": 19,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，19/19 弯）：frames_20261105_174656 / 20261107_162059 / 20261107_162850 · 官方弯名来自 F1《How every Monaco corner got its name》",
        # 摩纳哥街道赛，19 弯。连续弯组：Nouvelle Chicane×2、Swimming Pool×4。
        # 数据：174656（4 圈，1:28.3）/ 162059（4 圈，1:17.5）/ 162850（3 圈，1:17.5）
        "detected_corners": [
            {"no":  1, "name": "Sainte Devote",      "entry_m":  140, "apex_m":  233, "exit_m":  300, "dir": "R", "radius_m":  None},
            {"no":  2, "name": "Beau Rivage",        "entry_m":  300, "apex_m":  485, "exit_m":  500, "dir": "L", "radius_m":  None},
            {"no":  3, "name": "Massenet",           "entry_m":  520, "apex_m":  578, "exit_m":  660, "dir": "L", "radius_m":  None},
            {"no":  4, "name": "Casino Square",      "entry_m":  660, "apex_m":  808, "exit_m":  870, "dir": "R", "radius_m":  None},
            {"no":  5, "name": "Mirabeau Superior",  "entry_m":  870, "apex_m":  910, "exit_m": 1085, "dir": "R", "radius_m":  None},
            {"no":  6, "name": "Hairpin",            "entry_m": 1085, "apex_m": 1150, "exit_m": 1250, "dir": "L", "radius_m":  None},
            {"no":  7, "name": "Mirabeau Inferior",  "entry_m": 1250, "apex_m": 1282, "exit_m": 1330, "dir": "R", "radius_m":  None},
            {"no":  8, "name": "Portier",            "entry_m": 1330, "apex_m": 1365, "exit_m": 1520, "dir": "R", "radius_m":  None},
            {"no":  9, "name": "The Tunnel",         "entry_m": 1550, "apex_m": 1767, "exit_m": 1830, "dir": "R", "radius_m":  None},
            {"no": 10, "name": "Nouvelle Chicane",   "entry_m": 2040, "apex_m": 2140, "exit_m": 2160, "dir": "R", "radius_m":  None},
            {"no": 11, "name": "Nouvelle Chicane",   "entry_m": 2160, "apex_m": 2173, "exit_m": 2230, "dir": "L", "radius_m":  None},
            {"no": 12, "name": "Tabac",              "entry_m": 2330, "apex_m": 2407, "exit_m": 2580, "dir": "R", "radius_m":  None},
            {"no": 13, "name": "Swimming Pool",      "entry_m": 2580, "apex_m": 2592, "exit_m": 2660, "dir": "R", "radius_m":  None},
            {"no": 14, "name": "Swimming Pool",      "entry_m": 2660, "apex_m": 2708, "exit_m": 2740, "dir": "L", "radius_m":  None},
            {"no": 15, "name": "Swimming Pool",      "entry_m": 2740, "apex_m": 2753, "exit_m": 2820, "dir": "R", "radius_m":  None},
            {"no": 16, "name": "Swimming Pool",      "entry_m": 2820, "apex_m": 2843, "exit_m": 2900, "dir": "L", "radius_m":  None},
            {"no": 17, "name": "Turn 17",            "entry_m": 2900, "apex_m": 2940, "exit_m": 2950, "dir": "R", "radius_m":  None},
            {"no": 18, "name": "La Rascasse",        "entry_m": 2950, "apex_m": 3033, "exit_m": 3070, "dir": "L", "radius_m":  None},
            {"no": 19, "name": "Antony Noghes",      "entry_m": 3070, "apex_m": 3115, "exit_m": 3200, "dir": "R", "radius_m":  None},
        ],
        "corners": [],
    },
    "melbourne": {
        "track_id": 0,
        "name": "Albert Park Circuit",
        "country": "AU",
        "length_m": 5278,
        "official_turns": 14,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，14/14 弯）：frames_20261113_133103 / 134234 / 134927 · 官方编号 Turn 1-14（Albert Park 2022 改版后无传统弯名）",
        # 数据：133103（4 圈）/ 134234（3 圈）/ 134927（3 圈，1:25.387 最快）
        "detected_corners": [
            {"no":  1, "name": "Turn 1",  "entry_m":  250, "apex_m":  375, "exit_m":  440, "dir": "R"},
            {"no":  2, "name": "Turn 2",  "entry_m":  440, "apex_m":  478, "exit_m":  600, "dir": "L"},
            {"no":  3, "name": "Turn 3",  "entry_m": 1000, "apex_m": 1143, "exit_m": 1180, "dir": "R"},
            {"no":  4, "name": "Turn 4",  "entry_m": 1180, "apex_m": 1235, "exit_m": 1340, "dir": "L"},
            {"no":  5, "name": "Turn 5",  "entry_m": 1370, "apex_m": 1512, "exit_m": 1560, "dir": "R"},
            {"no":  6, "name": "Turn 6",  "entry_m": 1800, "apex_m": 1898, "exit_m": 1960, "dir": "L"},
            {"no":  7, "name": "Turn 7",  "entry_m": 1955, "apex_m": 1973, "exit_m": 2050, "dir": "R"},
            {"no":  8, "name": "Turn 8",  "entry_m": 2380, "apex_m": 2433, "exit_m": 2520, "dir": "L"},
            {"no":  9, "name": "Turn 9",  "entry_m": 2800, "apex_m": 2952, "exit_m": 3070, "dir": "R"},
            {"no": 10, "name": "Turn 10", "entry_m": 3250, "apex_m": 3347, "exit_m": 3390, "dir": "L"},
            {"no": 11, "name": "Turn 11", "entry_m": 3385, "apex_m": 3430, "exit_m": 3530, "dir": "R"},
            {"no": 12, "name": "Turn 12", "entry_m": 3700, "apex_m": 3762, "exit_m": 3840, "dir": "L"},
            {"no": 13, "name": "Turn 13", "entry_m": 4070, "apex_m": 4170, "exit_m": 4230, "dir": "R"},
            {"no": 14, "name": "Turn 14", "entry_m": 4330, "apex_m": 4540, "exit_m": 4550, "dir": "L"},
        ],
        "corners": [],
    },
    "shanghai": {
        "track_id": 2,
        "name": "Shanghai International Circuit",
        "country": "CN",
        "length_m": 5451,
        "official_turns": 16,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，16/16 弯）：frames_20261113_141005 / 141953 / 142632 · 官方编号 Turn 1-16（T1-T2 螺旋弯俗称 Snail）",
        # 数据：141005（4 圈）/ 141953（3 圈，1:39.625 最快）/ 142632（3 圈）
        # 游戏实测 trackId = 2，赛道长度 5441 米（官方 5451）
        "detected_corners": [
            {"no":  1, "name": "Turn 1",  "entry_m":  450, "apex_m":  687, "exit_m":  700, "dir": "R"},
            {"no":  2, "name": "Turn 2",  "entry_m":  650, "apex_m":  822, "exit_m":  880, "dir": "L"},
            {"no":  3, "name": "Turn 3",  "entry_m":  840, "apex_m":  948, "exit_m": 1150, "dir": "R"},
            {"no":  4, "name": "Turn 4",  "entry_m": 1300, "apex_m": 1373, "exit_m": 1460, "dir": "L"},
            {"no":  5, "name": "Turn 5",  "entry_m": 1520, "apex_m": 1620, "exit_m": 1800, "dir": "R"},
            {"no":  6, "name": "Turn 6",  "entry_m": 1860, "apex_m": 2050, "exit_m": 2240, "dir": "L"},
            {"no":  7, "name": "Turn 7",  "entry_m": 2230, "apex_m": 2385, "exit_m": 2490, "dir": "R"},
            {"no":  8, "name": "Turn 8",  "entry_m": 2470, "apex_m": 2582, "exit_m": 2780, "dir": "L"},
            {"no":  9, "name": "Turn 9",  "entry_m": 3060, "apex_m": 3160, "exit_m": 3210, "dir": "R"},
            {"no": 10, "name": "Turn 10", "entry_m": 3180, "apex_m": 3232, "exit_m": 3660, "dir": "L"},
            {"no": 11, "name": "Turn 11", "entry_m": 4400, "apex_m": 4503, "exit_m": 4560, "dir": "R"},
            {"no": 12, "name": "Turn 12", "entry_m": 4600, "apex_m": 4640, "exit_m": 4740, "dir": "L"},
            {"no": 13, "name": "Turn 13", "entry_m": 4730, "apex_m": 4812, "exit_m": 4980, "dir": "R"},
            {"no": 14, "name": "Turn 14", "entry_m": 4970, "apex_m": 5008, "exit_m": 5090, "dir": "L"},
            {"no": 15, "name": "Turn 15", "entry_m": 5080, "apex_m": 5173, "exit_m": 5190, "dir": "R"},
            {"no": 16, "name": "Turn 16", "entry_m": 5180, "apex_m": 5192, "exit_m": 5280, "dir": "L"},
        ],
        "corners": [],
    },
    "suzuka": {
        "track_id": 13,
        "name": "Suzuka International Racing Course",
        "country": "JP",
        "length_m": 5807,
        "official_turns": 18,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，18/18 弯）：frames_20261113_144617 / 145908 / 150728 · 官方弯名（S Curves / Degner 1-2 / Hairpin / Spoon Curve / 130R / Casio Triangle / Last Curve）",
        # 数据：144617（4 圈）/ 145908（3 圈，1:38.228 最快）/ 150728（3 圈）
        # 游戏实测 trackId = 13，赛道长度 5809 米（官方 5807）
        "detected_corners": [
            {"no":  1, "name": "Turn 1",         "entry_m":  600, "apex_m":  792, "exit_m":  800, "dir": "R"},
            {"no":  2, "name": "Turn 2",         "entry_m":  800, "apex_m":  882, "exit_m": 1000, "dir": "L"},
            {"no":  3, "name": "S Curves",       "entry_m": 1000, "apex_m": 1115, "exit_m": 1180, "dir": "R"},
            {"no":  4, "name": "S Curves",       "entry_m": 1180, "apex_m": 1237, "exit_m": 1320, "dir": "L"},
            {"no":  5, "name": "S Curves",       "entry_m": 1320, "apex_m": 1407, "exit_m": 1480, "dir": "R"},
            {"no":  6, "name": "S Curves",       "entry_m": 1480, "apex_m": 1573, "exit_m": 1670, "dir": "L"},
            {"no":  7, "name": "S Curves",       "entry_m": 1670, "apex_m": 1768, "exit_m": 1900, "dir": "R"},
            {"no":  8, "name": "Degner 1",       "entry_m": 1900, "apex_m": 1912, "exit_m": 2200, "dir": "R"},
            {"no":  9, "name": "Degner 2",       "entry_m": 2200, "apex_m": 2330, "exit_m": 2400, "dir": "R"},
            {"no": 10, "name": "Turn 10",        "entry_m": 2400, "apex_m": 2435, "exit_m": 2650, "dir": "L"},
            {"no": 11, "name": "Hairpin",        "entry_m": 2700, "apex_m": 2795, "exit_m": 2860, "dir": "L"},
            {"no": 12, "name": "Spoon Curve",    "entry_m": 2860, "apex_m": 2960, "exit_m": 3020, "dir": "R"},
            {"no": 13, "name": "Spoon Curve",    "entry_m": 3050, "apex_m": 3145, "exit_m": 3400, "dir": "L"},
            {"no": 14, "name": "Turn 14",        "entry_m": 3400, "apex_m": 3495, "exit_m": 3700, "dir": "R"},
            {"no": 15, "name": "130R",           "entry_m": 3730, "apex_m": 3975, "exit_m": 4150, "dir": "L"},
            {"no": 16, "name": "Casio Triangle", "entry_m": 4900, "apex_m": 4965, "exit_m": 5070, "dir": "R"},
            {"no": 17, "name": "Casio Triangle", "entry_m": 5070, "apex_m": 5138, "exit_m": 5230, "dir": "L"},
            {"no": 18, "name": "Last Curve",     "entry_m": 5330, "apex_m": 5492, "exit_m": 5560, "dir": "R"},
        ],
        "corners": [],
    },
    "jeddah": {
        "track_id": 29,
        "name": "Jeddah Corniche Circuit",
        "country": "SA",
        "length_m": 6174,
        "official_turns": 27,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，27/27 弯）：frames_20261113_152919 / 153826 / 154356 · 官方编号 Turn 1-27（吉达无传统弯名）",
        # 数据：152919（4 圈，1:38.434）/ 153826（3 圈，1:35.907）/ 154356（3 圈，1:36.911）
        # 游戏实测 trackId = 29，赛道长度 6175 米（官方 6174）
        "detected_corners": [
            {"no":  1, "name": "Turn 1",  "entry_m":  440, "apex_m":  532, "exit_m":  580, "dir": "R"},
            {"no":  2, "name": "Turn 2",  "entry_m":  560, "apex_m":  605, "exit_m":  700, "dir": "L"},
            {"no":  3, "name": "Turn 3",  "entry_m":  650, "apex_m":  718, "exit_m":  800, "dir": "R"},
            {"no":  4, "name": "Turn 4",  "entry_m":  960, "apex_m": 1037, "exit_m": 1080, "dir": "L"},
            {"no":  5, "name": "Turn 5",  "entry_m": 1080, "apex_m": 1140, "exit_m": 1270, "dir": "R"},
            {"no":  6, "name": "Turn 6",  "entry_m": 1250, "apex_m": 1322, "exit_m": 1470, "dir": "L"},
            {"no":  7, "name": "Turn 7",  "entry_m": 1450, "apex_m": 1480, "exit_m": 1720, "dir": "R"},
            {"no":  8, "name": "Turn 8",  "entry_m": 1700, "apex_m": 1767, "exit_m": 1840, "dir": "L"},
            {"no":  9, "name": "Turn 9",  "entry_m": 2300, "apex_m": 2440, "exit_m": 2500, "dir": "R"},
            {"no": 10, "name": "Turn 10", "entry_m": 2500, "apex_m": 2528, "exit_m": 2690, "dir": "L"},
            {"no": 11, "name": "Turn 11", "entry_m": 2680, "apex_m": 2888, "exit_m": 2970, "dir": "R"},
            {"no": 12, "name": "Turn 12", "entry_m": 2960, "apex_m": 3015, "exit_m": 3060, "dir": "L"},
            {"no": 13, "name": "Turn 13", "entry_m": 3060, "apex_m": 3137, "exit_m": 3190, "dir": "R"},
            {"no": 14, "name": "Turn 14", "entry_m": 3180, "apex_m": 3268, "exit_m": 3470, "dir": "L"},
            {"no": 15, "name": "Turn 15", "entry_m": 3580, "apex_m": 3638, "exit_m": 3700, "dir": "R"},
            {"no": 16, "name": "Turn 16", "entry_m": 3700, "apex_m": 3740, "exit_m": 3890, "dir": "L"},
            {"no": 17, "name": "Turn 17", "entry_m": 3940, "apex_m": 3987, "exit_m": 4090, "dir": "R"},
            {"no": 18, "name": "Turn 18", "entry_m": 4260, "apex_m": 4355, "exit_m": 4400, "dir": "L"},
            {"no": 19, "name": "Turn 19", "entry_m": 4390, "apex_m": 4445, "exit_m": 4650, "dir": "R"},
            {"no": 20, "name": "Turn 20", "entry_m": 4720, "apex_m": 4885, "exit_m": 4960, "dir": "L"},
            {"no": 21, "name": "Turn 21", "entry_m": 4960, "apex_m": 5125, "exit_m": 5210, "dir": "R"},
            {"no": 22, "name": "Turn 22", "entry_m": 5210, "apex_m": 5315, "exit_m": 5400, "dir": "L"},
            {"no": 23, "name": "Turn 23", "entry_m": 5400, "apex_m": 5500, "exit_m": 5510, "dir": "R"},
            {"no": 24, "name": "Turn 24", "entry_m": 5490, "apex_m": 5600, "exit_m": 5620, "dir": "L"},
            {"no": 25, "name": "Turn 25", "entry_m": 5600, "apex_m": 5625, "exit_m": 5700, "dir": "R"},
            {"no": 26, "name": "Turn 26", "entry_m": 5690, "apex_m": 5718, "exit_m": 5800, "dir": "L"},
            {"no": 27, "name": "Turn 27", "entry_m": 5790, "apex_m": 5915, "exit_m": 5960, "dir": "R"},
        ],
        "corners": [],
    },
    "miami": {
        "track_id": 30,
        "name": "Miami International Autodrome",
        "country": "US",
        "length_m": 5412,
        "official_turns": 19,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，19/19 弯）：frames_20261113_155510 / 160309 / 160851 · 官方编号 Turn 1-19（迈阿密无传统弯名）",
        # 数据：155510（4 圈，1:35.665）/ 160309（3 圈，1:33.820）/ 160851（1 圈）
        # 游戏实测 trackId = 30，赛道长度 5410 米（官方 5412）
        "detected_corners": [
            {"no":  1, "name": "Turn 1",  "entry_m":  330, "apex_m":  415, "exit_m":  470, "dir": "R"},
            {"no":  2, "name": "Turn 2",  "entry_m":  450, "apex_m":  503, "exit_m":  570, "dir": "L"},
            {"no":  3, "name": "Turn 3",  "entry_m":  550, "apex_m":  617, "exit_m":  760, "dir": "R"},
            {"no":  4, "name": "Turn 4",  "entry_m":  750, "apex_m":  765, "exit_m":  900, "dir": "L"},
            {"no":  5, "name": "Turn 5",  "entry_m": 1050, "apex_m": 1197, "exit_m": 1240, "dir": "R"},
            {"no":  6, "name": "Turn 6",  "entry_m": 1230, "apex_m": 1270, "exit_m": 1390, "dir": "L"},
            {"no":  7, "name": "Turn 7",  "entry_m": 1380, "apex_m": 1523, "exit_m": 1570, "dir": "R"},
            {"no":  8, "name": "Turn 8",  "entry_m": 1560, "apex_m": 1682, "exit_m": 1740, "dir": "L"},
            {"no":  9, "name": "Turn 9",  "entry_m": 2140, "apex_m": 2200, "exit_m": 2280, "dir": "R"},
            {"no": 10, "name": "Turn 10", "entry_m": 2380, "apex_m": 2415, "exit_m": 2710, "dir": "L"},
            {"no": 11, "name": "Turn 11", "entry_m": 3040, "apex_m": 3155, "exit_m": 3210, "dir": "R"},
            {"no": 12, "name": "Turn 12", "entry_m": 3200, "apex_m": 3290, "exit_m": 3360, "dir": "L"},
            {"no": 13, "name": "Turn 13", "entry_m": 3340, "apex_m": 3480, "exit_m": 3520, "dir": "R"},
            {"no": 14, "name": "Turn 14", "entry_m": 3500, "apex_m": 3608, "exit_m": 3670, "dir": "L"},
            {"no": 15, "name": "Turn 15", "entry_m": 4850, "apex_m": 4935, "exit_m": 5010, "dir": "R"},
            {"no": 16, "name": "Turn 16", "entry_m": 5000, "apex_m": 5005, "exit_m": 5160, "dir": "L"},
            {"no": 17, "name": "Turn 17", "entry_m": 5150, "apex_m": 5248, "exit_m": 5290, "dir": "R"},
            {"no": 18, "name": "Turn 18", "entry_m": 5280, "apex_m": 5310, "exit_m": 5370, "dir": "L"},
            {"no": 19, "name": "Turn 19", "entry_m": 5360, "apex_m": 5373, "exit_m": 5440, "dir": "R"},
        ],
        "corners": [],
    },
    "imola": {
        "track_id": 27,
        "name": "Autodromo Internazionale Enzo e Dino Ferrari",
        "country": "IT",
        "length_m": 4909,
        "official_turns": 19,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，19/19 弯）：frames_20261113_162600 / 163404 / 164430 · 官方弯名（Tamburello ×2 / Villeneuve / Tosa / Piratella ×2 / Acque Minerali ×2 / Variante Alta ×2 / Rivazza ×2）",
        # 数据：162600（L1 1:25.627）/ 163404（L3 1:25.300）/ 164430（3 圈全正常，1:22.457）
        # 游戏实测 trackId = 27，赛道长度 4910 米（官方 4909）
        "detected_corners": [
            {"no":  1, "name": "Tamburello",     "entry_m":  780, "apex_m":  845, "exit_m":  890, "dir": "R"},
            {"no":  2, "name": "Tamburello",     "entry_m":  880, "apex_m":  933, "exit_m":  970, "dir": "L"},
            {"no":  3, "name": "Villeneuve",     "entry_m":  960, "apex_m":  985, "exit_m": 1065, "dir": "R"},
            {"no":  4, "name": "Tosa",           "entry_m": 1070, "apex_m": 1110, "exit_m": 1215, "dir": "L"},
            {"no":  5, "name": "Piratella",      "entry_m": 1480, "apex_m": 1562, "exit_m": 1600, "dir": "R"},
            {"no":  6, "name": "Piratella",      "entry_m": 1600, "apex_m": 1665, "exit_m": 1755, "dir": "L"},
            {"no":  7, "name": "Acque Minerali", "entry_m": 1835, "apex_m": 1948, "exit_m": 2045, "dir": "R"},
            {"no":  8, "name": "Acque Minerali", "entry_m": 2275, "apex_m": 2332, "exit_m": 2395, "dir": "L"},
            {"no":  9, "name": "Variante Alta",  "entry_m": 2475, "apex_m": 2540, "exit_m": 2815, "dir": "R"},
            {"no": 10, "name": "Variante Alta",  "entry_m": 2885, "apex_m": 3105, "exit_m": 3275, "dir": "L"},
            {"no": 11, "name": "Rivazza",        "entry_m": 3500, "apex_m": 3573, "exit_m": 3600, "dir": "L"},
            {"no": 12, "name": "Rivazza",        "entry_m": 3595, "apex_m": 3632, "exit_m": 3705, "dir": "R"},
            {"no": 13, "name": "Turn 13",        "entry_m": 4090, "apex_m": 4163, "exit_m": 4245, "dir": "L"},
            {"no": 14, "name": "Turn 14",        "entry_m": 4295, "apex_m": 4388, "exit_m": 4445, "dir": "R"},
            {"no": 15, "name": "Turn 15",        "entry_m": 4440, "apex_m": 4533, "exit_m": 4585, "dir": "R"},
            {"no": 16, "name": "Turn 16",        "entry_m": 4575, "apex_m": 4602, "exit_m": 4630, "dir": "L"},
            {"no": 17, "name": "Turn 17",        "entry_m": 4760, "apex_m": 4833, "exit_m": 4845, "dir": "R"},
            {"no": 18, "name": "Turn 18",        "entry_m": 4835, "apex_m": 4862, "exit_m": 4880, "dir": "L"},
            {"no": 19, "name": "Turn 19",        "entry_m": 4870, "apex_m": 4885, "exit_m": 4912, "dir": "R"},
        ],
        "corners": [],
    },
    "barcelona": {
        "track_id": 4,
        "name": "Circuit de Barcelona-Catalunya",
        "country": "ES",
        "length_m": 4657,
        "official_turns": 16,
        "status": STATUS_VALIDATED,
        "calibrated_from": "三份实跑数据交叉验证（三取二，16/16 弯）：frames_20261113_170828 / 171611 / 172252 · 官方弯名（T9 Campsa / T10 La Caixa，其余 Turn 编号）",
        # 数据：170828（L1 1:19.027）/ 171611（L1 1:20.079）/ 172252（L3 1:18.374 最快）
        # 游戏实测 trackId = 4，赛道长度 4664 米（官方 4657）
        "detected_corners": [
            {"no":  1, "name": "Turn 1",  "entry_m":  750, "apex_m":  858, "exit_m":  880, "dir": "R"},
            {"no":  2, "name": "Turn 2",  "entry_m":  870, "apex_m":  933, "exit_m":  960, "dir": "L"},
            {"no":  3, "name": "Turn 3",  "entry_m":  950, "apex_m":  965, "exit_m": 1100, "dir": "R"},
            {"no":  4, "name": "Turn 4",  "entry_m": 1090, "apex_m": 1232, "exit_m": 1470, "dir": "L"},
            {"no":  5, "name": "Turn 5",  "entry_m": 1625, "apex_m": 1737, "exit_m": 1765, "dir": "R"},
            {"no":  6, "name": "Turn 6",  "entry_m": 1760, "apex_m": 1805, "exit_m": 1975, "dir": "L"},
            {"no":  7, "name": "Turn 7",  "entry_m": 2025, "apex_m": 2175, "exit_m": 2210, "dir": "R"},
            {"no":  8, "name": "Turn 8",  "entry_m": 2200, "apex_m": 2210, "exit_m": 2480, "dir": "L"},
            {"no":  9, "name": "Campsa",  "entry_m": 2470, "apex_m": 2578, "exit_m": 2640, "dir": "R"},
            {"no": 10, "name": "La Caixa", "entry_m": 2615, "apex_m": 2660, "exit_m": 2725, "dir": "L"},
            {"no": 11, "name": "Turn 11", "entry_m": 2800, "apex_m": 2852, "exit_m": 3040, "dir": "R"},
            {"no": 12, "name": "Turn 12", "entry_m": 3410, "apex_m": 3527, "exit_m": 3560, "dir": "R"},
            {"no": 13, "name": "Turn 13", "entry_m": 3550, "apex_m": 3593, "exit_m": 3695, "dir": "R"},
            {"no": 14, "name": "Turn 14", "entry_m": 3680, "apex_m": 3782, "exit_m": 4010, "dir": "L"},
            {"no": 15, "name": "Turn 15", "entry_m": 4000, "apex_m": 4032, "exit_m": 4310, "dir": "R"},
            {"no": 16, "name": "Turn 16", "entry_m": 4300, "apex_m": 4415, "exit_m": 4480, "dir": "R"},
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
