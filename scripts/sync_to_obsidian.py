#!/usr/bin/env python3
"""将 notes/ 下的笔记同步到 Obsidian vault。"""
import shutil
import subprocess
from pathlib import Path

REPO_NOTES = Path(__file__).parent.parent / "notes"
VAULT = Path("/Users/wxhu/Documents/Obsidian_workspace/OpencodeDev")

def sync():
    if not VAULT.exists():
        print(f"❌ Obsidian vault 不存在: {VAULT}")
        return

    shutil.copytree(REPO_NOTES / "八股文", VAULT / "八股文", dirs_exist_ok=True)
    shutil.copytree(REPO_NOTES / "项目技术栈", VAULT / "项目技术栈", dirs_exist_ok=True)

    print(f"✅ 已同步到 {VAULT}")

if __name__ == "__main__":
    sync()
