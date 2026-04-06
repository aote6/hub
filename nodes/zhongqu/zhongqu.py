#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具中枢 v2.4 —— 终极内核
此文件轻易不改，改必有充分理由。
所有功能、菜单、配置全在 zhongqu_data.json 里。

v2.3 修复记录：
- [安全] _atomic_save 改用 os.replace 消除 remove+rename 断档窗口
- [安全] _atomic_save 加 fcntl.flock 排他锁，防并发写损坏数据
- [安全] CORE_ENV 传入 exec 时传副本，防模块篡改全局环境
- [逻辑] main() 捕获 SystemExit，模块内 exit() 不再终止整个程序
- [逻辑] 快照时间戳精确到毫秒，避免同秒覆盖
- [逻辑] 操作日志时间戳补全年份
- [清理] _atomic_save 失败时清理残留临时文件

v2.4 修复记录：
- [安全] _atomic_save 的 fcntl.flock 改锁目标文件，修复原先锁 tmp 文件导致锁形同虚设的问题
- [安全] SYSTEM_KEYS 改为 tuple，防模块通过 .append()/.clear() 篡改原始对象
- [体验] load() 数据文件损坏时提示快照目录，用户知道有恢复手段
"""

import json
import os
import traceback
import re
import shutil
import fcntl
from datetime import datetime

VERSION  = "2.7"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "zhongqu_data.json")
SNAP_DIR  = os.path.join(BASE_DIR, "zhongqu_snapshots")

# v2.4: 改为 tuple，防止模块通过 .append()/.clear() 篡改原始对象
SYSTEM_KEYS = ("1", "2", "3", "4", "5", "6", "7", "8", "9")
OPERATION_LOG_MAX = 300

def load():
    if not os.path.exists(DATA_FILE):
        print("❌ 找不到 zhongqu_data.json")
        input("回车退出..."); exit(1)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 数据文件损坏：{e}")
        # v2.4: 告知用户快照位置，有恢复手段
        print(f"   💡 快照目录：{SNAP_DIR}")
        print(f"   可手动复制快照文件替换 zhongqu_data.json 后重启")
        input("回车退出..."); exit(1)

# ==================== 内核基础设施 ====================

def _atomic_save(data, filepath=None):
    """
    原子写入。v2.4 修正：
    1. os.replace 替代 remove+rename，消除断档窗口（POSIX 原子，Termux 支持）
    2. fcntl.flock 排他锁改锁目标文件（v2.3 锁 tmp 文件，每进程各锁各的，锁形同虚设）
    3. 失败时清理残留 .tmp 文件
    """
    if filepath is None:
        filepath = DATA_FILE
    tmp = filepath + ".tmp." + str(os.getpid())
    try:
        # v2.4: 锁目标文件，真正排他；写完后 replace 进去
        with open(filepath, "a", encoding="utf-8") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, filepath)
        return True
    except Exception as e:
        print(f"⚠️ 原子写入失败：{e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False

def _snap():
    """
    快照。v2.3：时间戳精确到毫秒，避免同秒多次快照互相覆盖。
    """
    os.makedirs(SNAP_DIR, exist_ok=True)
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"
    shutil.copy2(DATA_FILE, os.path.join(SNAP_DIR, f"snapshot_{ts}.json"))
    return ts

def _get_base_dir():
    return BASE_DIR

def _get_data_file():
    return DATA_FILE

def _log(data, message):
    """v2.3：时间戳补全年份，跨年后仍能区分日志条目。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    log = data.setdefault("operation_log", [])
    log.append(f"{ts} {message}")
    if len(log) > OPERATION_LOG_MAX:
        data["operation_log"] = log[-OPERATION_LOG_MAX:]


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _today():
    return datetime.now().strftime("%Y-%m-%d")

def _parse_memo(code):
    m = re.search(r'#\s*@记\s*\n(.*?)#\s*@毕', code, re.DOTALL)
    if m:
        block = m.group(1)
        result = {}
        for line in block.splitlines():
            line = line.strip().lstrip("#").strip()
            if "：" in line:
                k, _, v = line.partition("：")
                k = k.strip()
                if k:
                    result[k] = v.strip()
        if result.get("需求"):
            return result
    m = re.search(r'@AI_MEMO_START\s*\n(.*?)@AI_MEMO_END', code, re.DOTALL)
    if m:
        block = m.group(1)
        result = {}
        for line in block.splitlines():
            line = line.strip().lstrip("#").strip()
            if "：" in line:
                k, _, v = line.partition("：")
                k = k.strip()
                if k and k != "功能名称":
                    result[k] = v.strip()
        mapped = {}
        field_map = {"原始需求": "需求", "注意事项": "注意", "设计思路": "思路", "后续优化": "优化"}
        for k, v in result.items():
            mapped[field_map.get(k, k)] = v
        if mapped.get("需求"):
            return mapped
    m = re.search(r'#\s*@MEMO\s+(.*)', code)
    if m:
        result = {}
        for part in m.group(1).split("|"):
            part = part.strip()
            if "：" in part:
                k, _, v = part.partition("：")
                k = k.strip()
                field_map = {"需求": "需求", "原始需求": "需求", "注意事项": "注意", "注意": "注意"}
                mapped_k = field_map.get(k, k)
                if mapped_k:
                    result[mapped_k] = v.strip()
        if result.get("需求"):
            return result
    return None


# ==================== 内核执行环境 ====================

CORE_ENV = {
    "__name__": "__main__",
    "_data_file":    DATA_FILE,
    "_base_dir":     BASE_DIR,
    "_snap_dir":     SNAP_DIR,
    "_version":      VERSION,
    "_SYSTEM_KEYS":  SYSTEM_KEYS,
    "_atomic_save":  _atomic_save,
    "_snap":         _snap,
    "_get_base_dir": _get_base_dir,
    "_get_data_file": _get_data_file,
    "_log":          _log,
    "_now":          _now,
    "_today":        _today,
    "_parse_memo":   _parse_memo,
    "json":          json,
    "os":            os,
    "shutil":        shutil,
    "datetime":      datetime,
    "traceback":     traceback,
}

def main():
    while True:
        data = load()
        os.system("clear")
        for line in data.get("banner", []): print(line.replace("{version}", VERSION))
        for line in data.get("menu", []): print(line)
        for line in data.get("footer", []): print(line)

        choice = input("输入数字：").strip()
        if choice == data.get("exit_key", "0"):
            print("\n👋 再见。"); break

        action = data.get("actions", {}).get(choice)
        if not action:
            input("⚠️  无效选项，回车继续..."); continue

        try:
            # v2.3: 传入 CORE_ENV 副本，防模块篡改全局环境
            exec_env = {**CORE_ENV, "data": data, "CORE_ENV": dict(CORE_ENV)}
            exec(action["code"], exec_env)
        except SystemExit:
            # v2.3 修复：捕获模块内 exit()/exit(0)，回到主菜单而非终止程序
            pass
        except Exception as e:
            print(f"\n❌ 执行出错：{e}")
            print(traceback.format_exc())
            input("回车继续...")

if __name__ == "__main__":
    main()
