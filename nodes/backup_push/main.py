#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @记
# 需求：把整个 Hub 目录（core.py + nodes/）备份到 Git 仓库
# 注意：首次运行前需要配置仓库地址，支持 GitHub/Gitee
# @毕

import os
import subprocess
import json
import shutil
from datetime import datetime
from pathlib import Path

# ========== 配置区域 ==========
CONF_FILE = Path.home() / ".hub_backup.conf"
HUB_DIR   = Path(__file__).parent.parent.parent  # hub/
# =============================

def load_conf():
    if not CONF_FILE.exists():
        return None
    with open(CONF_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_conf(conf):
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)

def run_cmd(cmd, cwd=None):
    """执行命令，返回 (成功?, 输出)"""
    try:
        r = subprocess.run(cmd, shell=False, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return False, str(e)

def main():
    print("\n📦 Hub 备份推送工具")
    print("=" * 45)

    # 1. 读取或创建配置
    conf = load_conf()
    if not conf:
        print("\n首次运行，需要配置 Git 仓库：")
        print("  示例：https://github.com/你的用户名/hub-backup.git")
        repo = input("Git 仓库地址：").strip()
        if not repo:
            print("❌ 仓库地址不能为空")
            input("回车退出...")
            return
        conf = {"repo": repo, "last_push": None}
        save_conf(conf)
        print(f"✅ 配置已保存到 {CONF_FILE}")

    # 2. 准备备份目录
    backup_dir = HUB_DIR.parent / "hub_backup"  # 与 hub/ 同级
    backup_dir.mkdir(exist_ok=True)

    # 3. 克隆或拉取
    git_dir = backup_dir / ".git"
    if not git_dir.exists():
        print(f"\n📥 克隆仓库到 {backup_dir}...")
        ok, out = run_cmd(["git", "clone", conf["repo"], str(backup_dir)])
        if not ok:
            print(f"❌ 克隆失败：{out}")
            input("回车退出...")
            return
    else:
        print(f"\n🔄 拉取最新...")
        ok, out = run_cmd(["git", "pull"], cwd=backup_dir)
        if not ok:
            print(f"⚠️ 拉取失败：{out}")

    # 4. 复制 Hub 文件
    print(f"\n📋 复制 Hub 文件...")
    # 复制 core.py
    shutil.copy2(HUB_DIR / "core.py", backup_dir / "core.py")
    # 复制整个 nodes/ 目录
    if (HUB_DIR / "nodes").exists():
        shutil.copytree(HUB_DIR / "nodes", backup_dir / "nodes", dirs_exist_ok=True)
    # 复制 hub.db（如果存在）
    if (HUB_DIR / "hub.db").exists():
        shutil.copy2(HUB_DIR / "hub.db", backup_dir / "hub.db")

    # 5. 提交并推送
    print(f"\n📤 提交并推送...")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    run_cmd(["git", "add", "."], cwd=backup_dir)
    ok, out = run_cmd(["git", "commit", "-m", f"Hub backup {ts}"], cwd=backup_dir)
    if "nothing to commit" in out.lower():
        print("✅ 无新变更，无需推送")
    else:
        if ok:
            ok2, out2 = run_cmd(["git", "push"], cwd=backup_dir)
            if ok2:
                print(f"✅ 推送成功！({ts})")
                conf["last_push"] = ts
                save_conf(conf)
            else:
                print(f"❌ 推送失败：{out2}")
        else:
            print(f"⚠️ 提交失败：{out}")

    print("\n✅ 备份完成")
    input("\n回车返回...")

if __name__ == "__main__":
    main()
