# aos-frontend Skill

_前端 UI。人类交互界面，以 Skill 的形式存在。_

---

## 1. 概述

`aos-frontend` 是一个服务型 Plugin Skill。它的 Plugin 面启动一个 Next.js Web 应用，为人类用户提供可视化的交互界面。

前端不是 AOS 的内核功能，而是一个普通的 Skill。删除它，AOS 照常运行——只是没有了 Web UI，用户只能通过 CLI 或 SDK 操作。

## 2. 运行模式

`aos-frontend` 属于**服务型 Plugin**：daemon spawn 子进程后，子进程内部启动 Next.js 服务（默认 :3000 端口），同时通过 stdio JSON-RPC 完成 Hook 注册。

前端应用通过 TypeScript SDK 的 HTTP 模式与 daemon 通信，调用 AOSCP 操作读写数据。

```
Daemon (:8420)
  ├── spawn → aos-frontend plugin (stdio JSON-RPC)
  │              └── 内部启动 Next.js (:3000)
  │                     └── 通过 TS SDK → HTTP → Daemon AOSCP
  └── 接受 CLI / SDK 请求
```

## 3. 功能范围

前端 Skill 可以：

- 展示 Session 列表和消息历史
- 发送用户消息（通过 `session.dispatch`）
- 实时显示 dispatch 进度（通过 SSE dispatch 流）
- 监听 Runtime Event（通过 SSE 事件流）
- 管理 Agent 和 Skill

## 4. SKILL.md 结构

```yaml
---
name: aos-frontend
description: AOS Web UI — 人类交互前端
plugin: ./plugin.ts
---
（skillText 正文：可选，描述前端 Skill 的能力供 AI 知晓）
```

## 5. 目录结构

```
skills/frontend/
├── SKILL.md
├── plugin.ts          # Plugin 入口，注册 Hook + 启动 Next.js
├── package.json
└── app/               # Next.js 应用
    ├── page.tsx
    └── ...
```
