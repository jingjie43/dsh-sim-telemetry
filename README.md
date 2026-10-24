# dsh-f1-telemetry

给 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（DSH）用的 **F1 25 遥测插件**：边跑边记，跑完自动出圈速、弯道和"该改哪儿"。

> 不用第三方遥测软件，不用上传数据 —— 全部在本机，插件只是一个壳，按需开、不跑车就不监听。

## 功能

- **记录遥测**：F1 25 的 UDP 遥测（默认端口 `20777`），玩家 + 全部 22 辆车
- **自动分析**：切圈、圈速、分段、按速度曲线识别弯道（apex / 入弯 / 出弯速度）
- **自动收工**：设置"跑到第 N 圈自动出报告"，跑满就停、立刻生成报告
- **三种产出**：
  - 文字摘要（圈速、与最佳圈的差、最慢的弯、该改什么）
  - `laps_*.csv` 表格（每圈：圈速 / 极速 / 均速 / 全油门% / 刹车% / 滑行%）
  - `summary_full_*.md` 完整明细（每圈 + 每段速度表）
- **图表**：速度曲线（多圈对比）+ 最快圈的油门/刹车曲线（Pillow 绘制，不需要 matplotlib）
- **省 token**：分析全在本地 Python 里做，模型只读结论那几行

## 安装

在 DSH 的「设置 → 插件」里，输入下面任意一种：

| 方式 | 填什么 |
|---|---|
| GitHub（推荐） | `https://github.com/jingjie43/dsh-f1-telemetry` |
| npm | `dsh-f1-telemetry`（需要先发布到 npm） |
| 本地 | 插件目录的绝对路径 |

装完**重启 DSH**，设置左侧会出现「F1 遥测」。

## 环境依赖

- **Python 3.10+**（开发和测试用 3.12）
- Python 包：`Pillow`（画图用）

```bash
pip install Pillow
```

插件会自动探测 `python` / `python3` / `py`；找不到可以在设置面板里手填 Python 路径。

## 使用

1. **游戏里开启遥测**：F1 25 → 设置 → 遥测 → UDP 开启，端口 `20777`
2. **DSH 设置 → F1 遥测**：
   - 打开「启用插件功能」
   - 设「默认记录时长」（分钟）
   - 想自动收工就设「跑到第几圈自动出报告」（0 = 不自动停）
   - 点「开始记录」
3. **进赛道跑**，跑完点「停止记录」（或等它自动停）
4. **看报告**：`~/.dsh/f1-telemetry/`

也可以在对话里直接让 AI 操作：`f1_start`、`f1_stop`、`f1_summary`、`f1_plot`。

## 数据目录

```
~/.dsh/f1-telemetry/
├── allcars_*.jsonl     # 原始遥测（4Hz，22 辆车）
├── laps_*.csv          # 每圈汇总表
├── summary_full_*.md   # 完整明细
├── plots/              # 速度曲线图 / 油门刹车图
├── settings.json       # 面板设置
└── debug.log           # 插件加载日志（排错用）
```

## 已知限制

- 同时只能跑一个采集任务
- 只支持 F1 25（UDP 包格式 2025）
- 端口固定 `20777`（F1 25 默认）
- 弯道是按速度曲线的局部最低点识别的，**不知道真实弯名**，编号按出现顺序
- 遥测本身不含位置数据，所以"逐弯对比"是按速度谷对齐的近似

## 开发

```
index.js            # 插件主体（工具 + 设置页路由）
client.js           # 设置面板（浏览器端自注册脚本）
lib/py/
  f1_collect_all.py # 采集（UDP → JSONL）
  f1_summary.py     # 摘要 + CSV
  f1_plot.py        # 画图（Pillow）
cordis.patch.yml    # DSH 插件挂载声明
```

改完脚本后把插件目录重新装一次（或在「本地目录」模式下直接生效）。

## License

MIT
