# aos Skill

_内建指令集。告诉 ReActUnit 如何使用 AOSCP 操作系统。_

---

## 1. 概述

`aos` 是纯 skillText Skill，没有 Plugin 面。它的 SKILL.md 正文是一份写给 ReActUnit 看的系统使用说明书，内容包括：

- 可用的 AOSCP 操作及其用法（`aos call <op> --payload '{}'`）
- Fold / Unfold 操作的使用方式
- ContentStore 的读取和搜索方式
- Session 管理操作
- Skill 加载与管理操作

## 2. 特殊地位

`aos` Skill 在 bootstrap 默认注入流程中被**强制追加**。即使 defaultSkills 中没有配置它，它也会被注入。这保证了 ReActUnit 始终知道怎么和 AOS 交互。

参见 [aos-lifecycle.md](../specs/aos-lifecycle.md) §3.3 Bootstrap 默认 load 解析规则第 5 条。

## 3. 与其他 Skill 的关系

所有 Skill 平等，不区分内建和外部。`aos` 虽然是强制注入的，但它只是 skillRoot 下的一个普通目录，格式和任何其他 Skill 完全一样。

## 4. SKILL.md 结构

```yaml
---
name: aos
description: AOS 系统使用指南，告诉 AI 如何通过 AOSCP 操作系统
---
（skillText 正文：AOSCP 操作指南、fold/unfold 说明、content 读取方式等）
```
