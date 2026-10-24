# Changelog

## 0.1.0 — 2026-10-24

首个可发布版本。

- F1 25 UDP 遥测采集（端口 20777，玩家 + 全部 22 辆车）
- 自动切圈、圈速、分段、按速度曲线识别弯道
- 「跑到第 N 圈自动出报告」：跑满自动停，立即生成报告
- 三种产出：文字摘要 / `laps_*.csv` 表格 / `summary_full_*.md` 完整明细
- 速度曲线图、油门刹车图（Pillow 绘制，无需 matplotlib）
- 设置面板：启用开关、默认时长、自动报告圈数、Python 路径
- 工具：`f1_start` / `f1_stop` / `f1_summary` / `f1_plot`
- Python 自动探测（python / python3 / py），找不到可在面板手填
