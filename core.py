#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hub 内核 v1.0
一切皆节点。原中枢是第一个节点，一字不改。

设计原则：
- 状态存 SQLite（WAL 模式，并发安全，增量写）
- 节点是独立进程（subprocess，可取消，有状态）
- 节点描述是 node.json（AI 可读，人可写）
- @记/@毕 格式完全保留
"""

import json
import os
import sqlite3
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

VERSION  = "1.0"
BASE_DIR = Path(__file__).parent
DB_FILE  = BASE_DIR / "hub.db"
NODES_DIR = BASE_DIR / "nodes"


# ==================== 数据库层 ====================

class HubDB:
    """
    SQLite 替代 JSON 的状态层。
    WAL 模式：多读一写不阻塞，Termux 上比 flock 更可靠。
    """
    def __init__(self):
        self.path = DB_FILE
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS state (
                    key     TEXT PRIMARY KEY,
                    value   TEXT,
                    updated TEXT
                );
                CREATE TABLE IF NOT EXISTS logs (
                    id  INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts  TEXT,
                    msg TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts       TEXT,
                    name     TEXT,
                    data     TEXT,
                    consumed INTEGER DEFAULT 0
                );
            """)

    # ── 状态读写（增量，不重写整个文件）──
    def get(self, key, default=None):
        with self._conn() as c:
            row = c.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        if row:
            try:   return json.loads(row[0])
            except: return row[0]
        return default

    def set(self, key, value):
        ts = datetime.now().isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO state(key,value,updated) VALUES(?,?,?)",
                (key, json.dumps(value, ensure_ascii=False), ts)
            )

    def delete(self, key):
        with self._conn() as c:
            c.execute("DELETE FROM state WHERE key=?", (key,))

    def keys(self, prefix=""):
        with self._conn() as c:
            rows = c.execute(
                "SELECT key FROM state WHERE key LIKE ?", (prefix + "%",)
            ).fetchall()
        return [r[0] for r in rows]

    # ── 日志（追加写，不重写）──
    def log(self, msg):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as c:
            c.execute("INSERT INTO logs(ts,msg) VALUES(?,?)", (ts, msg))

    def recent_logs(self, n=30):
        with self._conn() as c:
            rows = c.execute(
                "SELECT ts, msg FROM logs ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return list(reversed([(r["ts"], r["msg"]) for r in rows]))

    # ── 事件总线（节点间通信）──
    def emit(self, name, data=None):
        ts = datetime.now().isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO events(ts,name,data) VALUES(?,?,?)",
                (ts, name, json.dumps(data or {}, ensure_ascii=False))
            )

    def pending(self, name=None):
        with self._conn() as c:
            if name:
                rows = c.execute(
                    "SELECT id,ts,name,data FROM events WHERE consumed=0 AND name=? ORDER BY id",
                    (name,)
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id,ts,name,data FROM events WHERE consumed=0 ORDER BY id"
                ).fetchall()
        return [{"id": r["id"], "ts": r["ts"], "name": r["name"],
                 "data": json.loads(r["data"])} for r in rows]

    def consume(self, event_id):
        with self._conn() as c:
            c.execute("UPDATE events SET consumed=1 WHERE id=?", (event_id,))

    # ── 状态摘要（给 AI 看）──
    def summary(self):
        lines = [f"HubDB @ {DB_FILE}", f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
        keys = self.keys()
        lines.append(f"状态条目: {len(keys)} 个")
        with self._conn() as c:
            log_count = c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            ev_count  = c.execute("SELECT COUNT(*) FROM events WHERE consumed=0").fetchone()[0]
        lines.append(f"日志总条: {log_count}")
        lines.append(f"待处理事件: {ev_count}")
        return "\n".join(lines)


# ==================== 节点管理 ====================

class NodeManager:
    """
    节点 = nodes/<name>/node.json + 入口文件。
    交互式节点：subprocess.run()，阻塞，在当前终端交互。
    后台服务：subprocess.Popen()，不阻塞，日志写到节点目录。
    一次性任务：subprocess.run()，带超时。
    """
    def __init__(self, db: HubDB):
        self.db = db
        self.nodes: dict[str, dict] = {}
        self.procs: dict[str, subprocess.Popen] = {}

    def scan(self):
        """扫描 nodes/ 目录，支持热插拔——每次循环都调用。"""
        self.nodes = {}
        if not NODES_DIR.exists():
            return
        for node_dir in sorted(NODES_DIR.iterdir()):
            if not node_dir.is_dir():
                continue
            meta_file = node_dir / "node.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                meta["_path"] = str(node_dir)
                self.nodes[meta["name"]] = meta
            except Exception as e:
                print(f"⚠️  加载节点失败 [{node_dir.name}]: {e}")

    def run(self, name: str):
        node = self.nodes.get(name)
        if not node:
            print(f"❌ 节点不存在: {name}")
            input("回车继续...")
            return

        node_path = Path(node["_path"])
        entry     = node_path / node.get("entry", "main.py")
        ntype     = node.get("type", "interactive")

        if not entry.exists():
            print(f"❌ 入口文件不存在: {entry}")
            input("回车继续...")
            return

        self.db.log(f"启动节点「{name}」({ntype})")

        if ntype == "interactive":
            # 原中枢就是这种——直接在当前终端跑，完全透明
            try:
                subprocess.run(["python", str(entry)], cwd=str(node_path))
            except KeyboardInterrupt:
                pass
            self.db.log(f"节点「{name}」退出")

        elif ntype == "service":
            # 后台服务
            if name in self.procs and self.procs[name].poll() is None:
                print(f"⚠️  「{name}」已在运行 (PID {self.procs[name].pid})")
                input("回车继续...")
                return
            log_out = open(node_path / "stdout.log", "a")
            log_err = open(node_path / "stderr.log", "a")
            proc = subprocess.Popen(
                ["python", str(entry)],
                cwd=str(node_path),
                stdout=log_out,
                stderr=log_err
            )
            self.procs[name] = proc
            print(f"✅ 「{name}」已后台启动 (PID {proc.pid})")
            print(f"   日志: {node_path}/stdout.log")
            self.db.log(f"后台节点「{name}」PID={proc.pid}")
            input("回车继续...")

        elif ntype == "task":
            timeout = node.get("timeout", 300)
            print(f"▶️  运行「{name}」(超时 {timeout}s)...")
            try:
                r = subprocess.run(
                    ["python", str(entry)],
                    cwd=str(node_path),
                    timeout=timeout
                )
                self.db.log(f"任务「{name}」完成，返回码={r.returncode}")
            except subprocess.TimeoutExpired:
                print(f"⚠️  「{name}」超时（{timeout}秒）已取消")
                self.db.log(f"任务「{name}」超时")
            except KeyboardInterrupt:
                print(f"\n⚠️  「{name}」被中断")
                self.db.log(f"任务「{name}」被中断")
            input("回车继续...")

    def stop(self, name: str):
        proc = self.procs.get(name)
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
            print(f"✅ 「{name}」已停止")
            self.db.log(f"停止节点「{name}」")
        else:
            print(f"⚠️  「{name}」未在运行")

    def stop_all(self):
        for name in list(self.procs.keys()):
            if self.procs[name].poll() is None:
                self.stop(name)

    def status_text(self) -> str:
        """纯文本状态摘要，AI 可直接 cat 理解。"""
        lines = [
            f"Hub 节点状态 @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"节点目录: {NODES_DIR}",
            ""
        ]
        if not self.nodes:
            lines.append("  （无节点）")
        for name, node in self.nodes.items():
            ntype = node.get("type", "interactive")
            icon  = {"interactive": "🖥 ", "service": "⚙️ ", "task": "▶️ "}.get(ntype, "  ")
            if name in self.procs:
                running = self.procs[name].poll() is None
                state = f"运行中 PID={self.procs[name].pid}" if running else "已结束"
            else:
                state = "未启动" if ntype != "interactive" else "——"
            desc = node.get("desc", "")
            lines.append(f"  {icon} [{ntype:12s}] {name:20s} {state:20s} {desc}")
        return "\n".join(lines)


# ==================== Hub 主循环 ====================

class Hub:
    def __init__(self):
        self.db = HubDB()
        self.nm = NodeManager(self.db)

    def main(self):
        self.db.log("Hub 启动")
        while True:
            self.nm.scan()   # 支持热插拔，每次循环重新扫描
            os.system("clear")

            nodes = list(self.nm.nodes.values())

            print("=" * 47)
            print(f"🌐  Hub v{VERSION}  —  节点枢纽")
            print("=" * 47)

            if not nodes:
                print("  （nodes/ 目录为空，还没有任何节点）")
                print("  运行 migrate.py 把原中枢迁移进来")
            else:
                for i, node in enumerate(nodes, 1):
                    ntype = node.get("type", "interactive")
                    icon  = {"interactive": "🖥 ", "service": "⚙️ ", "task": "▶️ "}.get(ntype, "  ")
                    # 后台服务显示运行状态
                    name = node["name"]
                    extra = ""
                    if ntype == "service" and name in self.nm.procs:
                        running = self.nm.procs[name].poll() is None
                        extra = " [运行中]" if running else " [已停止]"
                    print(f"  {i}. {icon}{name}{extra}")
                    desc = node.get("desc", "")
                    if desc:
                        print(f"       {desc}")

            print()
            print("  s. 节点状态")
            print("  l. 最近日志")
            print("  d. 数据库摘要")
            print("  0. 退出")
            print("=" * 47)

            choice = input("选择: ").strip()

            if choice == "0":
                self.nm.stop_all()
                self.db.log("Hub 退出")
                print("\n👋 再见。")
                break

            elif choice == "s":
                os.system("clear")
                print(self.nm.status_text())
                input("\n回车继续...")

            elif choice == "l":
                os.system("clear")
                print("─" * 47)
                print("最近操作日志")
                print("─" * 47)
                for ts, msg in self.db.recent_logs(30):
                    print(f"  {ts}  {msg}")
                input("\n回车继续...")

            elif choice == "d":
                os.system("clear")
                print(self.db.summary())
                input("\n回车继续...")

            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(nodes):
                        node = nodes[idx]
                        ntype = node.get("type", "interactive")
                        name  = node["name"]
                        # 后台服务：再次选择 = 停止
                        if ntype == "service" and name in self.nm.procs \
                                and self.nm.procs[name].poll() is None:
                            os.system("clear")
                            print(f"「{name}」正在运行。")
                            if input("停止它？(y/n): ").strip().lower() == "y":
                                self.nm.stop(name)
                            input("回车继续...")
                        else:
                            self.nm.run(name)
                    else:
                        input("⚠️  无效选项，回车继续...")
                except ValueError:
                    input("⚠️  无效输入，回车继续...")


if __name__ == "__main__":
    Hub().main()
