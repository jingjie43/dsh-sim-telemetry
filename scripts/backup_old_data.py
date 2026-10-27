# -*- coding: utf-8 -*-
"""清理旧版（0.2.2 / 0.2.3 开发期）遥测数据：先备份成 zip，校验通过再删原文件。

只清 2026-10-26 00:00 之前的，今天（10-26）的数据一律不动。

用法: python scripts/backup_old_data.py          # 备份 + 删除
      python scripts/backup_old_data.py --dry    # 只看会删什么
"""
import glob
import os
import sys
import time
import zipfile

DATA = os.path.expanduser(r"~\.dsh\sim-telemetry")
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BK = os.path.join(PROJ, "backup")
OUT = os.path.join(BK, "旧遥测数据-1024-1025.zip")
CUT = time.mktime(time.strptime("2026-10-26 00:00", "%Y-%m-%d %H:%M"))
DRY = "--dry" in sys.argv


def old_files():
    files = [f for f in glob.glob(os.path.join(DATA, "*")) if os.path.isfile(f)]
    files += [f for f in glob.glob(os.path.join(DATA, "plots", "*")) if os.path.isfile(f)]
    files = [f for f in files if os.path.getmtime(f) < CUT]
    files.sort()
    return files


def main():
    files = old_files()
    if not files:
        print("没有需要清理的旧文件。")
        return 0
    total = sum(os.path.getsize(f) for f in files)
    print("待清理 %d 个文件，合计 %.2f MB" % (len(files), total / 1048576))
    for f in files:
        print("  ", os.path.relpath(f, DATA))
    if DRY:
        return 0

    os.makedirs(BK, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.relpath(f, DATA))

    # 校验：压缩包能读、条目数一致，才允许删
    with zipfile.ZipFile(OUT) as z:
        bad = z.testzip()
        n = len(z.namelist())
    if bad is not None:
        print("备份校验失败（坏条目 %s），不删除任何文件。" % bad)
        return 1
    if n != len(files):
        print("备份条目数不符（%d vs %d），不删除任何文件。" % (n, len(files)))
        return 1

    print("备份完成: %s (%.2f MB)" % (OUT, os.path.getsize(OUT) / 1048576))
    removed = 0
    for f in files:
        try:
            os.remove(f)
            removed += 1
        except OSError as exc:
            print("  删除失败:", f, exc)
    print("已删除 %d/%d 个旧文件，释放 %.2f MB" % (removed, len(files), total / 1048576))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
