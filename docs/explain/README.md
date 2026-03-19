# AgentOS 业务说明导航

这组文档面向不懂技术的产品经理，目标不是解释代码细节，而是把 AgentOS 这套系统背后的业务逻辑、角色关系、流程走向、能力供给方式、治理方式和产品机会讲清楚。

建议阅读顺序：

1. `docs/explain/01-aos-business-overview.md`
2. `docs/explain/02-session-and-memory-flow.md`
3. `docs/explain/03-skill-plugin-and-hook-ecosystem.md`
4. `docs/explain/04-control-plane-and-operating-model.md`
5. `docs/explain/05-product-opportunity-map.md`

## 这组文档各自回答什么问题

| 文档                                      | 重点问题                   | 适合什么场景                 |
| ----------------------------------------- | -------------------------- | ---------------------------- |
| `01-aos-business-overview.md`             | AgentOS 到底是什么产品     | 新人入门，统一口径           |
| `02-session-and-memory-flow.md`           | 一个任务从开始到结束怎么走 | 梳理用户旅程，做主流程设计   |
| `03-skill-plugin-and-hook-ecosystem.md`   | 能力如何接入系统并持续运行 | 梳理生态，设计平台策略       |
| `04-control-plane-and-operating-model.md` | 系统如何被控制，如何治理   | 设计控制台，权限，运营流程   |
| `05-product-opportunity-map.md`           | 哪些点最值得继续挖掘       | 做 roadmap，商业化，增长规划 |

## 一张图看完全文档结构

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#FFFFFF", "primaryColor": "#EAF4FF", "primaryBorderColor": "#9DB8D1", "primaryTextColor": "#29465B", "secondaryColor": "#F2F8EE", "secondaryBorderColor": "#A8C7A0", "tertiaryColor": "#FFF7EA", "tertiaryBorderColor": "#D9C49A", "lineColor": "#7E9DB9", "clusterBkg": "#F8FBFF", "clusterBorder": "#CAD9E8"}}}%%
flowchart TD
    A[AgentOS 产品全景] --> B[一 产品定位]
    A --> C[二 任务主流程]
    A --> D[三 能力生态]
    A --> E[四 控制与治理]
    A --> F[五 机会地图]

    B --> B1[是什么]
    B --> B2[解决什么问题]
    B --> B3[系统边界]

    C --> C1[任务怎么启动]
    C --> C2[会话怎么推进]
    C --> C3[历史怎么沉淀]

    D --> D1[Skill 怎么提供能力]
    D --> D2[Plugin 怎么持续运行]
    D --> D3[Hook 怎么介入流程]

    E --> E1[AOSCP 怎么控制系统]
    E --> E2[日志怎么审计]
    E --> E3[资源怎么托管]

    F --> F1[商业化]
    F --> F2[平台化]
    F --> F3[企业化]
```

## 阅读提示

- 文中会反复出现五个词：AOS，Agent，Session，Skill，ReActUnit
- 你可以把它们理解成五个业务对象，而不是五段代码
- 所有 Mermaid 图都尽量用浅色科研配色，目的是让业务流向一眼能看明白
- 图里如果出现换行，一律使用 `</br>` 以保证兼容性

## 推荐先抓住的三个总问题

1. 为什么 AgentOS 不是一个普通聊天机器人外壳
2. 为什么它要把任务，会话，能力，控制分开治理
3. 为什么它天然适合走平台化和企业化路线
