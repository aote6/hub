# hub · 节点枢纽

一个跑在手机上的个人工具枢纽。节点热插拔，无需重启，你的工具随你扩展。

A personal node hub that runs on your phone. Hot-plug nodes without restarting — your tools grow as you do.

---

## 这是什么 · What is this

Hub 是一个以节点为单位组织工具的枢纽系统。每个工具是一个独立节点，放进去就能用，拿出来不留痕迹。Hub 本身只负责识别节点、调度进程、记录状态——它不关心节点里装的是什么。

你的工具不再是散落在文件夹里的脚本，而是一个有入口、有意图说明、可随时启停的节点集合。

Hub is a node-based tool hub. Each tool is a self-contained node — plug it in and it works, pull it out and nothing breaks. Hub itself only handles node discovery, process scheduling, and state logging. It doesn't care what's inside a node.

Your tools are no longer scattered scripts. They're a collection of nodes, each with an entry point, a stated intent, and a clear lifecycle.

---

## 架构 · Architecture

三层结构，从底到顶：

Three layers, bottom to top:

```

hub.db              ← HubDB · SQLite   状态 / 日志 / 事件
core.py             ← NodeManager      调度节点进程，管理生命周期
Hub 主循环          ← 扫描 nodes/，呈现菜单，响应操作

```

**节点目录即节点本身**：`nodes/<名称>/` 下放一个 `node.json` 和入口文件，Hub 下次启动自动识别，无需注册，无需配置。

**`@记 / @毕` 是节点的意图说明**：入口文件顶部写清楚这个节点做什么、注意什么。Hub 读它，AI 也读它。

**Node directory = node**: drop a `node.json` and an entry file into `nodes/<name>/` and Hub picks it up on next launch — no registration, no config.

**`@记 / @毕` is the node's intent declaration**: write what this node does and what to watch out for at the top of the entry file. Hub reads it. So does any AI you hand context to.

---

## 节点类型 · Node Types

| 类型 | 行为 |
|------|------|
| `interactive` | 在终端直接交互运行 |
| `service` | 后台常驻，日志写入节点目录 |
| `task` | 一次性任务，有超时限制，完成即退出 |

| Type | Behavior |
|------|----------|
| `interactive` | Runs interactively in the terminal |
| `service` | Runs in the background, logs to node directory |
| `task` | One-shot task with timeout, exits on completion |

---

## 与 AI 协作 · Working with AI

Hub 内置「生成上下文」节点，把当前系统状态、所有节点信息、架构说明打包成一个 `.txt` 文件。

把这份文件发给 AI，说明你要什么——它按 Hub 的节点规范直接输出可以放进去的代码。建好目录，把文件放进去，重启 Hub，新节点就在菜单里了。

你不需要向 AI 解释 Hub 怎么运作，上下文文件已经说清楚了。

Hub includes a "Generate Context" node that packages the current system state, all node metadata, and architecture notes into a single `.txt` file.

Send that file to any AI and describe what you want — it writes node code that follows Hub's conventions, ready to drop in. Create the directory, place the files, restart Hub, and the new node appears in the menu.

You don't need to explain how Hub works to the AI. The context file already does that.

---

## 快速开始 · Quick Start

环境要求：Python 3，无额外依赖。推荐在 Android + Termux 上使用，也可以在任何桌面环境运行。

Requirements: Python 3, no extra dependencies. Designed for Android + Termux, but runs anywhere.

```bash
# 1. 启动 Hub
python3 core.py

# 2. 运行「生成上下文」，把导出的 txt 发给 AI，开始构建你的节点
#    Run "Generate Context", send the exported txt to any AI, start building nodes

# 3. 新增节点：在 nodes/<名称>/ 下放 node.json + 入口文件，重启即生效
#    Add a node: place node.json + entry file in nodes/<name>/, restart to activate
```

---

备份 · Backup

Hub 内置「备份推送」节点，把整个 Hub 目录提交并推送到你配置的 Git 仓库。首次运行按提示配置远端地址，后续一键完成。支持 GitHub / Gitee 或任何 Git 远端。

数据在你自己的仓库里，与任何平台无关。

Hub includes a "Backup Push" node that commits and pushes the entire Hub directory to your configured Git remote. Configure the remote on first run; one tap after that. Works with GitHub, Gitee, or any Git remote.

Your data lives in your own repository, independent of any platform.

---

设计哲学 · Design Philosophy

节点即边界 — 每个工具自成一体，互不耦合，坏一个不影响其他。

热插拔，不重构 — 增删工具就是增删目录，Hub 核心轻易不动。

意图显式声明 — @记 / @毕 不是注释，是给人和 AI 看的规范接口。

状态可查，历史可溯 — 所有操作写入 HubDB，你随时知道发生了什么。

数据在你这里 — 没有服务器，没有账号，没有订阅。换设备就是复制一个目录。

---

Nodes as boundaries — each tool is self-contained; one broken node doesn't affect the rest.

Hot-plug, don't refactor — adding or removing tools means adding or removing directories. The Hub core rarely needs touching.

Intent declared explicitly — @记 / @毕 is not a comment; it's a structured interface for humans and AI alike.

State is observable, history is traceable — every operation is written to HubDB; you always know what happened.

Your data stays with you — no server, no account, no subscription. Moving devices means copying one directory.

---

关于这个项目 · About this Project

这个项目由人类构思，工程推进与实现由人与 AI 反复协作完成。它本身就是它所描述的工作方式的产物：一个人带着判断和目标，和 AI 一起把想法变成可以运行的东西。

This project was conceived by a human. The engineering was built through iterative collaboration between a human and AI. It is itself a product of the workflow it describes: one person with a clear judgment and goal, working with AI to turn an idea into something that runs.

---

致下一个 AI · To the Next AI

如果你是收到用户发来的上下文后读到这里的 AI：先读上下文文件，输出当前节点状态简报，然后等待指令。

If you're an AI reading this after receiving context from a user: read the context file first, output a brief node status summary, then wait for instructions.

---

License

MIT — 用它，改它，分发它。数据永远是你的。

MIT — Use it, modify it, distribute it. Your data is always yours.
