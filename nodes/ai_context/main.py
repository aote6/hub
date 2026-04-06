#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @记
# 需求：生成 Hub 完整上下文，供 AI 理解整个系统状态
# 注意：作为 task 节点运行，输出纯文本，可复制给 AI
# @毕

import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR  = Path(__file__).parent.parent.parent  # hub/
NODES_DIR = BASE_DIR / "nodes"
DB_FILE   = BASE_DIR / "hub.db"
OUT_FILE  = BASE_DIR / "hub_context.txt"

CORE_FILE = BASE_DIR / "core.py"


def read_db():
    if not DB_FILE.exists():
        return {}, [], []
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    # 状态
    state = {}
    try:
        for row in conn.execute("SELECT key, value, updated FROM state"):
            try:    state[row["key"]] = {"value": json.loads(row["value"]), "updated": row["updated"]}
            except: state[row["key"]] = {"value": row["value"],             "updated": row["updated"]}
    except: pass

    # 日志（最近50条）
    logs = []
    try:
        for row in conn.execute("SELECT ts, msg FROM logs ORDER BY id DESC LIMIT 50"):
            logs.append((row["ts"], row["msg"]))
        logs.reverse()
    except: pass

    # 待处理事件
    events = []
    try:
        for row in conn.execute("SELECT ts, name, data FROM events WHERE consumed=0 ORDER BY id"):
            events.append({"ts": row["ts"], "name": row["name"], "data": row["data"]})
    except: pass

    conn.close()
    return state, logs, events


def read_nodes():
    nodes = []
    if not NODES_DIR.exists():
        return nodes
    for node_dir in sorted(NODES_DIR.iterdir()):
        if not node_dir.is_dir():
            continue
        meta_file = node_dir / "node.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["_dir"] = str(node_dir)

            # 读节点入口的 @记 备忘录
            entry = node_dir / meta.get("entry", "main.py")
            if entry.exists():
                code = entry.read_text(encoding="utf-8")
                meta["_memo"] = parse_memo(code)
                meta["_lines"] = len(code.splitlines())
            else:
                meta["_memo"] = None
                meta["_lines"] = 0

            nodes.append(meta)
        except Exception as e:
            nodes.append({"name": node_dir.name, "_error": str(e)})
    return nodes


def parse_memo(code):
    import re
    m = re.search(r'#\s*@记\s*\n(.*?)#\s*@毕', code, re.DOTALL)
    if not m:
        return None
    result = {}
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("#").strip()
        if "：" in line:
            k, _, v = line.partition("：")
            k = k.strip()
            if k:
                result[k] = v.strip()
    return result if result else None


def read_core_version():
    if not CORE_FILE.exists():
        return "未知"
    for line in CORE_FILE.read_text(encoding="utf-8").splitlines():
        if "VERSION" in line and "=" in line and '"' in line:
            try:
                return line.split('"')[1]
            except:
                pass
    return "未知"


def build_context(nodes, state, logs, events):
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hub_version = read_core_version()

    lines += [
        "=" * 55,
        f"Hub 系统上下文",
        f"生成时间: {now}",
        f"Hub 版本: v{hub_version}",
        f"节点数量: {len(nodes)}",
        f"Hub 根目录: {BASE_DIR}",
        "=" * 55,
        "",
    ]

    # ── 节点列表 ──
    lines += ["【节点列表】", ""]
    if not nodes:
        lines.append("  （无节点）")
    for node in nodes:
        if "_error" in node:
            lines.append(f"  ❌ {node['name']} — 加载失败: {node['_error']}")
            continue
        ntype   = node.get("type", "interactive")
        name    = node.get("name", "未知")
        desc    = node.get("desc", "")
        version = node.get("version", "")
        entry   = node.get("entry", "main.py")
        nlines  = node.get("_lines", 0)
        icon    = {"interactive": "🖥 ", "service": "⚙️ ", "task": "▶️ "}.get(ntype, "  ")

        lines.append(f"  {icon} {name}  [{ntype}]  {('v' + version) if version else ''}")
        if desc:
            lines.append(f"       描述: {desc}")
        lines.append(f"       入口: {entry}  ({nlines} 行)")
        lines.append(f"       路径: {node['_dir']}")

        memo = node.get("_memo")
        if memo:
            lines.append("       备忘录:")
            for k, v in memo.items():
                lines.append(f"         {k}：{v}")

        lines.append("")

    # ── 系统状态（hub.db）──
    lines += ["【系统状态（hub.db）】", ""]
    if not state:
        lines.append("  （无状态数据）")
    else:
        for key, info in state.items():
            val = info["value"]
            updated = info["updated"]
            val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
            if len(val_str) > 80:
                val_str = val_str[:77] + "..."
            lines.append(f"  {key}")
            lines.append(f"    值: {val_str}")
            lines.append(f"    更新: {updated}")
    lines.append("")

    # ── 待处理事件 ──
    lines += ["【待处理事件】", ""]
    if not events:
        lines.append("  （无待处理事件）")
    else:
        for ev in events:
            lines.append(f"  [{ev['ts']}] {ev['name']}")
            if ev["data"] and ev["data"] != "{}":
                lines.append(f"    数据: {ev['data']}")
    lines.append("")

    # ── 操作日志 ──
    lines += ["【最近操作日志（最新50条）】", ""]
    if not logs:
        lines.append("  （无日志）")
    else:
        for ts, msg in logs:
            lines.append(f"  {ts}  {msg}")
    lines.append("")

    # ── 给 AI 的说明 ──
    lines += [
        "=" * 55,
        "【给 AI 的说明】",
        "",
        "Hub 是一个节点枢纽，架构分三层：",
        "  1. HubDB（hub.db）— SQLite，存状态/日志/事件",
        "  2. NodeManager — 管理节点进程（subprocess）",
        "  3. Hub 主循环 — 扫描 nodes/，呈现菜单",
        "",
        "节点类型：",
        "  interactive — 交互式，在终端直接运行（如原中枢）",
        "  service     — 后台常驻服务，日志写入节点目录",
        "  task        — 一次性任务，有超时限制",
        "",
        "新增节点方法：",
        "  在 nodes/<名称>/ 下放 node.json 和入口文件",
        "  Hub 下次启动自动识别（热插拔）",
        "",
        "节点入口文件用 @记/@毕 备忘录格式标注意图：",
        "  # @记",
        "  # 需求：这个节点做什么",
        "  # 注意：使用时的注意事项",
        "  # @毕",
        "",
        "如需修改 Hub 核心，编辑 core.py 后重启生效。",
        "=" * 55,
    ]

    return "\n".join(lines)


def copy_to_clipboard(text):
    """尝试复制到剪贴板（Termux 环境）"""
    try:
        proc = subprocess.run(
            ["termux-clipboard-set"],
            input=text.encode("utf-8"),
            timeout=5
        )
        return proc.returncode == 0
    except Exception:
        return False


def main():
    print("\n⏳ 生成 Hub 上下文...")

    nodes          = read_nodes()
    state, logs, events = read_db()
    context        = build_context(nodes, state, logs, events)

    # 写入文件
    OUT_FILE.write_text(context, encoding="utf-8")
    print(f"✅ 已写入: {OUT_FILE}")
    print(f"   字符数: {len(context)}")
    print(f"   行数:   {len(context.splitlines())}")

    # 尝试复制到剪贴板
    copied = copy_to_clipboard(context)
    if copied:
        print("📋 已复制到剪贴板")
    else:
        print("   （未能复制到剪贴板，请手动 cat hub_context.txt）")

    print()

    # 预览前20行
    print("─" * 55)
    print("预览（前20行）：")
    print("─" * 55)
    for line in context.splitlines()[:20]:
        print(line)
    print("...")
    print("─" * 55)

    input("\n回车返回...")


main()
