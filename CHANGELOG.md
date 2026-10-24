# Changelog

## 0.1.0 — 2026-10-24

首个可发布版本。

- F1 25 UDP 遥测采集（端口 20777，玩家 + 全部 22 辆车）
- 自动切圈、圈速、分段、按速度曲线识别弯道
- 「跑到第 N 圈自动出报告」：跑满自动停，立即生成报告
- 三种产出：文字摘要 / `laps_*.csv` 表格 / `summary_full_*.md` 完整明细
- 速度曲线图、油门刹车图（Pillow 绘制，无需 matplotlib）
- 设置面板：启用开关、默认时长、自动报告圈数、Python 路径
- 工具：`telemetry_start` / `telemetry_stop` / `telemetry_summary` / `telemetry_plot`
- Python 自动探测（python / python3 / py），找不到可在面板手填

## 0.2.0 — 2026-10-24

- UDP 端口可配置（默认 20777，与 F1 25 游戏设置一致）
- Python 环境自动检测：要求 >= 3.10，不再硬编码某台机器的安装路径
- 设置页显示 Python 版本/路径/是否缺 Pillow，支持一键安装 Python 3.12（winget 优先，失败退回 python.org 官方静默安装）与一键补 Pillow
- 修复采集结束后调用不存在的 telemetry_summary.py（改为 summary.py）
