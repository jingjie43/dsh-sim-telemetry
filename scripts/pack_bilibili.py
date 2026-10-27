# -*- coding: utf-8 -*-
"""把 B站 0.2.3 更新日志包打成一个 zip，方便发微信/传别的机器。

用法: python scripts/pack_bilibili.py
输出: 项目根目录 dsh-sim-telemetry-0.2.3-B站更新日志包.zip
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
NAME = "dsh-sim-telemetry-0.2.3-B站更新日志包"
OUT = os.path.join(ROOT, NAME + ".zip")

FILES = [
    ("bilibili-0.2.3-log.md", "01-更新日志（标题简介标签置顶评论答疑）.md"),
    ("bilibili-0.2.3-video.md", "02-视频分镜与口播全稿.md"),
    ("bilibili-0.2.3.md", "03-发布包总览与演示流程.md"),
    ("cover-0.2.3.png", "封面-cover-0.2.3.png"),
    ("video-assets/01-data-fields.png", "图01-数据字段对比.png"),
    ("video-assets/02-corner-method.png", "图02-找弯方法对比.png"),
    ("session-20261026-overview.png", "图03-三圈成绩单.png"),
    ("session-20261026-corners.png", "图04-逐弯apex对比.png"),
    ("roadmap-0.2.3.png", "图05-未来规划-roadmap.png"),
    ("silverstone-2026-fia-map.png", "图06-银石官方赛道图.png"),]

README = """dsh-sim-telemetry 0.2.3 · B站更新日志包
=========================================

里面有什么
----------
01 更新日志   → 标题三选一、简介、标签、更新日志长版（可直接发专栏）、
                短版动态、置顶评论、评论区 8 条答疑模板、发布顺序
02 视频制作   → 第二期分镜（约 3 分钟）、口播全稿、素材清单
03 发布总览   → 演示流程、用户安装使用说明、限制说明
封面 / 图01~06 → 已做好的 16:9 素材，直接插视频或投稿

还差什么
--------
只有「实跑录像」需要自己录：上期片段、报告画面、跑圈、对话演示、GitHub 页。

一句话卖点
----------
从「报圈速」升级成「比赛工程师」：它会告诉你第几弯出问题了。
"""


def main():
    if not os.path.isdir(DOCS):
        print("找不到 docs 目录:", DOCS)
        return 1
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(NAME + "/README.txt", README.encode("utf-8"))
        for src, dst in FILES:
            p = os.path.join(DOCS, src)
            if not os.path.exists(p):
                print("跳过（不存在）:", src)
                continue
            z.write(p, NAME + "/" + dst)
            print("加入:", dst)
    size = os.path.getsize(OUT)
    print("\n已生成:", OUT)
    print("大小: %.2f MB · 共 %d 个文件" % (size / 1048576,
                                          len([n for n in zipfile.ZipFile(OUT).namelist()])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
