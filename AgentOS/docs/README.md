# AgentOS Documentation

当前版本：**v0.9**

---

## 文档结构

### 核心规范

| 文档                                 | 职责                                                                                         | 读者                  |
| ------------------------------------ | -------------------------------------------------------------------------------------------- | --------------------- |
| [`charter.md`](./charter.md)         | 系统世界观、设计原则、对象模型、执行流程。定义「是什么」和「为什么」。                       | 任何参与者            |
| [`impl-manual.md`](./impl-manual.md) | 精确规格：持久化结构字段、AOSCP 操作表、扩展点完整清单、物化规则、恢复协议。定义「怎么做」。 | 实现者、plugin 开发者 |

### 架构决策记录

| 文档                                                                           | 内容                                                                                               |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| [`decisions/0001-v09-arch-redesign.md`](./decisions/0001-v09-arch-redesign.md) | v0.9 六项架构决策：三种扩展机制、异步 dispatch、CQRS、Session lease、五层架构、Capability Manifest |

### 实现计划

| 文档                                                                                         | 内容                         |
| -------------------------------------------------------------------------------------------- | ---------------------------- |
| [`plans/2026-03-19-v09-arch-redesign/plan.md`](./plans/2026-03-19-v09-arch-redesign/plan.md) | 本次文档重写的计划与验收标准 |

### 参考资料

| 文档                                                                             | 内容                  |
| -------------------------------------------------------------------------------- | --------------------- |
| [`references/agent-skills-docs.md`](./references/agent-skills-docs.md)           | 开源 skill 标准参考   |
| [`references/opencode-plugin-system.md`](./references/opencode-plugin-system.md) | OpenCode 插件体系参考 |

---

## 关键数字

| 类别            | 数量 |
| --------------- | ---- |
| 本体对象        | 5    |
| AOSCP 命令      | 20   |
| AOSCP 查询      | 16   |
| AOSCP 操作合计  | 36   |
| Admission Hooks | 13   |
| Transform Hooks | 6    |
| Runtime Events  | 22   |
| 扩展点合计      | 41   |

---

## 快速导航

**我想了解 AOS 是什么** → `charter.md` 第一、二章

**我想了解 Session 如何工作** → `charter.md` 第四章

**我想写一个 Skill plugin** → `charter.md` 第六章 + `impl-manual.md` 第六章（扩展点清单）+ `impl-manual.md` 第五章（AosSDK 能调用什么）

**我想调用 AOSCP** → `impl-manual.md` 第五章（完整操作表）

**我想理解 fold / unfold** → `charter.md` §4.6 + `impl-manual.md` §3.3（占位符格式）+ §4.3（物化规则）

**我想理解架构为什么这么设计** → `decisions/0001-v09-arch-redesign.md`

**我想实现一个新的存储后端** → `impl-manual.md` §5.4（ContentStore 接口）+ §1.2（追加写原则）

---

## 版本历史

| 版本  | 日期       | 变化摘要                                                                                    |
| ----- | ---------- | ------------------------------------------------------------------------------------------- |
| v0.9  | 2026-03-19 | 五层架构、三种扩展机制（AH/TH/RE）、异步 dispatch、Session lease、Capability Manifest、CQRS |
| v0.81 | 2026-03-17 | 初始完整宪章；35 AOSCP 操作；39 hook 点；fold/unfold 占位符；大内容 ContentStore            |
