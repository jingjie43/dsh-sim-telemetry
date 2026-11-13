# v0.3.0 — 12 条赛道 / 211 个弯 + 数据管理

> 从「两条赛道」到「十二条赛道」，加上你要的「跑过的圈能翻出来比」。
> 这一版是赛道校准 + 数据管理的双里程碑。

---

## 新增

### 赛道：2 → 12 条，211 个弯全部实跑校准

| 赛道 | trackId | 弯数 | 弯名来源 |
|---|---|---|---|
| 银石 Silverstone | 7 | 18 | F1 官方（Abbey / Copse / Club…） |
| 蒙扎 Monza | 11 | 11 | F1 官方（Parabolica / Lesmo…） |
| 斯帕 Spa-Francorchamps | 10 | 19 | F1 官方（Eau Rouge / Pouhon…） |
| 巴林 Bahrain | 3 | 15 | 官方编号 Turn 1-15 |
| 摩纳哥 Monaco | 5 | 19 | F1 官方（Hairpin / Rascasse…） |
| 澳大利亚 Albert Park | 0 | 14 | 官方编号 Turn 1-14 |
| 上海 Shanghai | 2 | 16 | 官方编号 Turn 1-16 |
| 铃鹿 Suzuka | 13 | 18 | F1 官方（S Curves / Degner / 130R…） |
| 吉达 Jeddah | 29 | 27 | 官方编号 Turn 1-27 |
| 迈阿密 Miami | 30 | 19 | 官方编号 Turn 1-19 |
| 伊莫拉 Imola | 27 | 19 | F1 官方（Tamburello / Tosa / Rivazza…） |
| 巴塞罗那 Catalunya | 4 | 16 | F1 官方（Campsa / La Caixa） |

> 每条赛道用 3 份独立实跑数据做**三取二交叉验证**（每弯位置差 ≤40 米），
> 不是单份数据凑数。

### 历史记录管理（设置页）

- 按赛道 / 时间 / 圈数分组列出所有采集
- 显示每圈时间
- 勾选多份：对比 / 打包 zip / 删除（二次确认）
- 数据全在本机，不上传

### 出图：8 种

**单份图**（勾 1 份）：
1. 速度曲线
2. 油门刹车
3. 轨迹诊断（弯位编号 + 失误标注）
4. 赛道图（官方弯名）
5. 弯位表
6. 逐弯细节（每弯三圈叠加）

**圈速对比**（勾多份，可填圈号过滤）：
7. 成绩单（圈速/极差/极速/均速/全油/滑行 + 自动问题标注）
8. 逐弯 apex 对比（含「问题」和「**怎么改**」两列）

### 直道漂移检测

- 高速直道（>280 km/h）用世界坐标拟合直线，算横向偏移 + 方向盘抖动
- 自动标出「发飘」的直道段（偏移 > 0.5m）
- 区分是车/路面在飘，还是驾驶输入问题

### 图片保存位置可配

数据目录 + 桌面（默认）/ 仅数据目录 / 仅桌面 / 自定义目录
（含对比图——之前漏了复制，已修）

---

## 修复

- **赛道长度 bug（重要）**：`DEFAULT_LEN=5890` 被所有赛道共用，导致 7007 米的斯帕后段
  （Blanchimont / Bus Stop）数据被整段丢弃；现在按 Session 包 `trackLen` 自动检测
- `plot.py` 赛道名错误：老 trackId 表把 10 写成 Zandvoort（实际是 Spa）
- 对比图未复制到「图片保存位置」设置目录
- 圈速 CSV 的 BOM 兼容

---

## 安装

```bash
# npm 包名（推荐）
dsh plugin --profile web add dsh-sim-telemetry
```

或从 [Releases](https://github.com/jingjie43/dsh-sim-telemetry/releases) 下载
`dsh-sim-telemetry-0.3.0.tgz` 本地安装。

装完重启 DSH → 设置左侧出现「赛车遥测」。

---

## 完整变更

见 [CHANGELOG.md](https://github.com/jingjie43/dsh-sim-telemetry/blob/main/CHANGELOG.md)

**全部变更**：v0.2.4...v0.3.0
