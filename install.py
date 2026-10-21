#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install the Compass service, CLI shim, and WorkBuddy skill.

  python install.py
  python install.py --skill-dir "C:\\Users\\me\\.workbuddy\\skills\\compass"

Layout after install:
  ~/.compass/app/python/compass/...   service package
  ~/.compass/app/references/...       content references
  ~/.compass/bin/compass.cmd          CLI shim (Windows)
  ~/.compass/bin/compass              CLI shim (bash)
  ~/.compass/compass.db               data (created on first run)
  ~/.workbuddy/skills/compass/SKILL.md
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parent
HOME = Path(os.environ.get("COMPASS_HOME", Path.home() / ".compass")).expanduser()
APP = HOME / "app"
BIN = HOME / "bin"


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def write_shims() -> None:
    BIN.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    cmd = (
        "@echo off\r\n"
        'set "PYTHONPATH=%~dp0..\\app\\python"\r\n'
        f'"{py}" -m compass.cli %*\r\n'
    )
    (BIN / "compass.cmd").write_text(cmd, encoding="utf-8", newline="")
    sh = (
        "#!/usr/bin/env bash\n"
        'COMPASS_PY="$(cd "$(dirname "${BASH_SOURCE[0]}")/../app/python" && pwd)"\n'
        'export PYTHONPATH="$COMPASS_PY${PYTHONPATH:+:$PYTHONPATH}"\n'
        f'exec "{py}" -m compass.cli "$@"\n'
    )
    p = BIN / "compass"
    p.write_text(sh, encoding="utf-8", newline="\n")
    try:
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    except OSError:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", default=str(Path.home() / ".workbuddy" / "skills" / "compass"))
    ap.add_argument("--no-skill", action="store_true")
    args = ap.parse_args()

    HOME.mkdir(parents=True, exist_ok=True)
    APP.mkdir(parents=True, exist_ok=True)

    copy_tree(SRC / "python", APP / "python")
    copy_tree(SRC / "references", APP / "references")
    for name in ("AGENTS.md", "README.md", "使用说明.md"):
        if (SRC / name).exists():
            shutil.copyfile(SRC / name, APP / name)
    write_shims()

    compass_bin = BIN / "compass.cmd"
    ref_dir = APP / "references"

    if not args.no_skill:
        skill_dir = Path(args.skill_dir).expanduser()
        skill_dir.mkdir(parents=True, exist_ok=True)
        tpl = (SRC / "SKILL.md.in").read_text(encoding="utf-8")
        text = tpl.replace("{{COMPASS}}", str(compass_bin)).replace("{{REF}}", str(ref_dir))
        (skill_dir / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"skill: {skill_dir / 'SKILL.md'}")

    print("安装完成 · Compass · Sapphire Jan 设计")
    print(f"app:  {APP}")
    print(f"bin:  {compass_bin}")
    print(f"data: {HOME / 'compass.db'}")
    print("\n下一步：")
    print(f'  1. "{compass_bin}" init --handle your-name')
    print(f'  2. "{compass_bin}" open')
    print("  3. 重启 WorkBuddy，让它加载 compass skill")


if __name__ == "__main__":
    main()
