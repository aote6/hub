#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @记
# 需求：统一管理所有节点（增删改查）
# 注意：合并了 node_builder、node_deleter、node_editor、node_viewer
# @毕

import os
import json
import shutil
from pathlib import Path

HUB_DIR = Path(__file__).parent.parent.parent
NODES_DIR = HUB_DIR / "nodes"

NODE_TYPES = {
    "1": {"name": "interactive", "desc": "交互式节点，直接运行，适合菜单工具"},
    "2": {"name": "service", "desc": "后台服务节点，常驻运行，适合 Web/监控"},
    "3": {"name": "task", "desc": "一次性任务节点，带超时，适合备份/生成"}
}

def list_nodes():
    """列出所有节点（返回列表）"""
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
            nodes.append({
                "dir": node_dir,
                "name": meta.get("name", node_dir.name),
                "type": meta.get("type", "unknown"),
                "desc": meta.get("desc", ""),
                "entry": meta.get("entry", "main.py")
            })
        except:
            nodes.append({
                "dir": node_dir,
                "name": node_dir.name,
                "type": "error",
                "desc": "配置文件损坏"
            })
    return nodes

def show_menu(nodes):
    """显示节点列表供选择"""
    print("\n" + "-" * 40)
    for i, node in enumerate(nodes, 1):
        icon = {"interactive": "🖥", "service": "⚙️", "task": "▶️"}.get(node["type"], "❓")
        print(f"  {i}. {icon} {node['name']} — {node['desc'][:40]}")
    print("-" * 40)

def create_node():
    """新建节点"""
    print("\n" + "=" * 50)
    print("📝 新建节点")
    print("=" * 50)
    
    # 英文名
    print("\n📌 英文目录名（小写字母/数字/下划线，如 my_tool）：")
    name_en = input("> ").strip()
    if not name_en:
        print("❌ 不能为空")
        return
    if not name_en.replace("_", "").isalnum():
        print("❌ 只能包含字母、数字、下划线")
        return
    
    node_dir = NODES_DIR / name_en
    if node_dir.exists():
        print(f"❌ 节点已存在：{name_en}")
        return
    
    # 中文名
    print("\n📌 菜单显示名（如「我的工具」）：")
    name_cn = input("> ").strip()
    if not name_cn:
        name_cn = name_en
    
    # 类型
    print("\n📌 节点类型：")
    for key, info in NODE_TYPES.items():
        print(f"  {key}. {info['name']:12s} — {info['desc']}")
    type_choice = input("\n选择 (1/2/3): ").strip()
    if type_choice not in NODE_TYPES:
        print("❌ 无效选择")
        return
    node_type = NODE_TYPES[type_choice]["name"]
    
    # 描述
    print("\n📌 描述：")
    desc = input("> ").strip()
    if not desc:
        desc = f"{name_cn} 节点"
    
    # 确认
    print("\n" + "-" * 40)
    print(f"  目录：{name_en}")
    print(f"  显示：{name_cn}")
    print(f"  类型：{node_type}")
    print(f"  描述：{desc}")
    print("-" * 40)
    if input("确认创建？(y/n): ").strip().lower() != "y":
        print("已取消")
        return
    
    # 生成文件
    node_dir.mkdir(parents=True)
    
    # node.json
    node_json = {
        "name": name_cn,
        "type": node_type,
        "entry": "main.py",
        "desc": desc,
        "timeout": 60 if node_type == "task" else 30,
        "added": "2026-04-06"
    }
    (node_dir / "node.json").write_text(
        json.dumps(node_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # main.py 模板
    main_template = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @记
# 需求：{name_cn}
# @毕

def main():
    print("\\n▶️  {name_cn} 已启动")
    print("📝 在这里写你的逻辑...")
    input("\\n回车返回...")

if __name__ == "__main__":
    main()
'''
    (node_dir / "main.py").write_text(main_template, encoding="utf-8")
    
    print(f"\n✅ 节点已创建：{node_dir}")
    print("💡 重启 Hub 后生效")

def delete_node():
    """删除节点"""
    nodes = list_nodes()
    if not nodes:
        print("\n❌ 没有可删除的节点")
        return
    
    print("\n" + "=" * 50)
    print("🗑️  删除节点")
    print("=" * 50)
    show_menu(nodes)
    
    try:
        idx = int(input("\n选择要删除的节点编号: ")) - 1
        if idx < 0 or idx >= len(nodes):
            print("❌ 无效编号")
            return
        node = nodes[idx]
        print(f"\n⚠️  即将删除：{node['name']} ({node['dir']})")
        if input("确认删除？(y/n): ").strip().lower() != "y":
            print("已取消")
            return
        shutil.rmtree(node["dir"])
        print(f"✅ 已删除：{node['name']}")
    except ValueError:
        print("❌ 无效输入")

def edit_node():
    """修改节点配置（node.json）"""
    nodes = list_nodes()
    if not nodes:
        print("\n❌ 没有可修改的节点")
        return
    
    print("\n" + "=" * 50)
    print("✏️  修改节点")
    print("=" * 50)
    show_menu(nodes)
    
    try:
        idx = int(input("\n选择要修改的节点编号: ")) - 1
        if idx < 0 or idx >= len(nodes):
            print("❌ 无效编号")
            return
        node = nodes[idx]
        meta_file = node["dir"] / "node.json"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        
        print(f"\n当前配置：")
        print(f"  显示名：{meta.get('name')}")
        print(f"  类型：{meta.get('type')}")
        print(f"  描述：{meta.get('desc')}")
        
        print("\n修改（直接回车保留原值）：")
        new_name = input(f"  新显示名 [{meta.get('name')}]: ").strip()
        if new_name:
            meta["name"] = new_name
        new_desc = input(f"  新描述 [{meta.get('desc')}]: ").strip()
        if new_desc:
            meta["desc"] = new_desc
        
        meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✅ 已修改：{node['name']}")
    except ValueError:
        print("❌ 无效输入")

def view_node():
    """查看节点详情（代码+配置）"""
    nodes = list_nodes()
    if not nodes:
        print("\n❌ 没有节点")
        return
    
    print("\n" + "=" * 50)
    print("🔍 查看节点")
    print("=" * 50)
    show_menu(nodes)
    
    try:
        idx = int(input("\n选择要查看的节点编号: ")) - 1
        if idx < 0 or idx >= len(nodes):
            print("❌ 无效编号")
            return
        node = nodes[idx]
        
        # 读配置
        meta_file = node["dir"] / "node.json"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        
        print("\n" + "=" * 50)
        print(f"📦 {meta.get('name')}")
        print("=" * 50)
        print(f"  目录：{node['dir']}")
        print(f"  类型：{meta.get('type')}")
        print(f"  描述：{meta.get('desc')}")
        print(f"  入口：{meta.get('entry')}")
        if meta.get('timeout'):
            print(f"  超时：{meta.get('timeout')}秒")
        print(f"  添加时间：{meta.get('added', '未知')}")
        
        # 读代码（前30行）
        entry_file = node["dir"] / meta.get("entry", "main.py")
        if entry_file.exists():
            lines = entry_file.read_text(encoding="utf-8").splitlines()
            print(f"\n📄 代码预览（前30行，共{len(lines)}行）：")
            print("-" * 40)
            for i, line in enumerate(lines[:30], 1):
                print(f"{i:3d}: {line}")
            if len(lines) > 30:
                print("...")
        else:
            print(f"\n⚠️  入口文件不存在：{entry_file}")
        
        input("\n回车返回...")
    except ValueError:
        print("❌ 无效输入")

def main():
    while True:
        print("\n" + "=" * 50)
        print("📦 节点管理")
        print("=" * 50)
        print("  1. 新建节点")
        print("  2. 删除节点")
        print("  3. 修改节点")
        print("  4. 查看节点")
        print("  0. 返回上级菜单")
        print("=" * 50)
        
        choice = input("选择: ").strip()
        
        if choice == "1":
            create_node()
        elif choice == "2":
            delete_node()
        elif choice == "3":
            edit_node()
        elif choice == "4":
            view_node()
        elif choice == "0":
            break
        else:
            print("❌ 无效选择")

if __name__ == "__main__":
    main()
