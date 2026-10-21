#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build compass-install.py: a single-file, self-extracting installer.

Usage:
  python build_single.py
Produces ../compass-install.py
"""
from __future__ import annotations

import base64
import io
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "compass-install.py"

FILES = ["README.md", "使用说明.md", "AGENTS.md", "CLAUDE.md", "install.py",
         "install.ps1", "install.bat", "open-compass.bat", "compass.cmd", "SKILL.md.in"]
DIRS = ["python", "references"]

TEMPLATE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compass one-file installer.

Run:
  python compass-install.py
  python compass-install.py --handle xiaoyu
  python compass-install.py --handle xiaoyu --open

It unpacks the bundled service into ~/.compass, writes the CLI shim, and
installs the WorkBuddy skill. No network access, no model calls.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PAYLOAD_B64 = "__PAYLOAD__"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", default="", help="dashboard name (lowercase)")
    ap.add_argument("--open", action="store_true", help="open the dashboard after install")
    ap.add_argument("--skill-dir", default="")
    args = ap.parse_args()

    raw = base64.b64decode(PAYLOAD_B64)
    tmp = Path(tempfile.mkdtemp(prefix="compass_install_"))
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            z.extractall(tmp)
        root = tmp / "compass"
        if not (root / "install.py").exists():
            raise SystemExit("安装包损坏：找不到 install.py")
        cmd = [sys.executable, str(root / "install.py")]
        if args.skill_dir:
            cmd += ["--skill-dir", args.skill_dir]
        code = subprocess.call(cmd)
        if code != 0:
            raise SystemExit(code)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    home = Path(os.environ.get("COMPASS_HOME", Path.home() / ".compass")).expanduser()
    compass = home / "bin" / ("compass.cmd" if os.name == "nt" else "compass")
    if args.handle:
        subprocess.call([str(compass), "init", "--handle", args.handle])
    if args.open:
        subprocess.call([str(compass), "open"])
    print()
    print("下一步：")
    print("  1. 完全退出 WorkBuddy，再打开一次（加载 compass skill）")
    print("  2. 对它说：我不知道自己想做什么")
    print(f"  重新打开看板：\\"{compass}\\" open")


if __name__ == "__main__":
    main()
'''


def build_payload() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(ROOT / f, arcname=f"compass/{f}")
        for d in DIRS:
            for p in sorted((ROOT / d).rglob("*")):
                if p.is_file() and p.suffix != ".pyc" and "__pycache__" not in str(p):
                    z.write(p, arcname=f"compass/{p.relative_to(ROOT).as_posix()}")
    return buf.getvalue()


def wrap(text: str, width: int = 100) -> str:
    # Python can handle a single long literal; keep it on one line so the file
    # stays valid without concatenation syntax.
    return text


def main() -> None:
    payload = base64.b64encode(build_payload()).decode("ascii")
    OUT.write_text(TEMPLATE.replace("__PAYLOAD__", wrap(payload)), encoding="utf-8", newline="\n")
    print(OUT.resolve(), OUT.stat().st_size)


if __name__ == "__main__":
    main()
