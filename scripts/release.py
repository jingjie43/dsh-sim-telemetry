#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键发布脚本：升版本 → 写 CHANGELOG → 提交 → 打 tag → 推送。

用法：
    python scripts/release.py 0.1.1 "修了弯道识别"
    python scripts/release.py 0.1.1 "修了弯道识别" --no-push   # 只本地，不推

它会做这些事：
1. 改 package.json 的 version
2. 在 CHANGELOG.md 顶部插一条更新记录
3. git add -A && git commit
4. git tag v<版本>
5. git push（含 tag）—— 需要联网 + GitHub 凭据
"""
import json
import os
import shutil
import subprocess
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_git():
    candidates = [
        shutil.which("git"),
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\github-copilot-git-2.56.0-1\cmd\git.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def run(cmd, check=True):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        print("命令失败，退出。")
        sys.exit(r.returncode)
    return r.returncode


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    version = sys.argv[1].lstrip("v")
    note = sys.argv[2]
    no_push = "--no-push" in sys.argv

    git = find_git()
    if not git:
        print("找不到 git，请先安装 Git 或把它加进 PATH")
        return 1

    # 1) 版本号
    pkg_path = os.path.join(ROOT, "package.json")
    pkg = json.load(open(pkg_path, encoding="utf-8-sig"))
    old = pkg.get("version", "0.0.0")
    pkg["version"] = version
    with open(pkg_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")
    print(f"版本: {old} -> {version}")

    # 2) CHANGELOG
    cl_path = os.path.join(ROOT, "CHANGELOG.md")
    cl = open(cl_path, encoding="utf-8").read() if os.path.exists(cl_path) else "# Changelog\n\n"
    today = datetime.date.today().isoformat()
    entry = f"## {version} — {today}\n\n- {note}\n\n"
    if f"## {version} " not in cl:
        idx = cl.find("## ")
        if idx >= 0:
            cl = cl[:idx] + entry + cl[idx:]
        else:
            cl = cl + "\n" + entry
        open(cl_path, "w", encoding="utf-8", newline="\n").write(cl)
        print("CHANGELOG 已更新")

    # 3) 提交
    run([git, "add", "-A"])
    run([git, "commit", "-m", f"release: v{version} - {note}"], check=False)

    # 4) tag
    tag = f"v{version}"
    run([git, "tag", "-a", tag, "-m", f"v{version}: {note}"], check=False)

    # 5) 推送
    if not no_push:
        run([git, "push", "origin", "HEAD"])
        run([git, "push", "origin", tag])

    print(f"\n完成：v{version}")
    if not no_push:
        print("记得去 GitHub 的 Releases 页面点「Draft a new release」，选 tag，写上更新说明。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
