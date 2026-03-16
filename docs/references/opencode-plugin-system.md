# OpenCode Plugin System 调研

> 范围：官方文档 `https://opencode.ai/docs/plugins/` + 官方仓库 `anomalyco/opencode` 的 `dev` 分支源码。源码基线提交：`c2ca1494e5f2b21655982d694b6bafd4526f147e`。

## 一句话结论

OpenCode 的 plugin 体系本质上是一个 **基于 Bun + TypeScript 的运行时扩展层**：启动时收集插件来源，动态导入模块，执行插件工厂函数得到一组 hooks；运行期再通过 `Plugin.trigger()` 和全局 `Bus` 事件流，把会话、工具、shell、compaction、LLM 参数等关键节点暴露给插件。

## 1. Plugin 到底是什么

官方定义里，plugin 是一个 JS/TS 模块，导出一个或多个异步函数；每个函数签名大致如下：

```ts
type Plugin = (input: PluginInput) => Promise<Hooks>;
```

插件初始化输入 `PluginInput` 来自 `packages/plugin/src/index.ts`，核心字段有：

- `client`: `createOpencodeClient()` 生成的 SDK client
- `project`: 当前项目信息
- `directory`: 当前工作目录
- `worktree`: 当前 git worktree 路径
- `serverUrl`: 当前 OpenCode server URL
- `$`: Bun shell API

返回值 `Hooks` 是一组可选 hook：

- 生命周期/总线类：`event`、`config`
- 扩展能力类：`tool`、`auth`
- 对话链路类：`chat.message`、`chat.params`、`chat.headers`
- 工具链路类：`tool.execute.before`、`tool.execute.after`、`tool.definition`
- shell 链路类：`shell.env`
- 实验链路类：`experimental.chat.messages.transform`、`experimental.chat.system.transform`、`experimental.session.compacting`、`experimental.text.complete`
- 还有一个类型层声明了 `permission.ask`，但当前源码分支里没找到对应的 `Plugin.trigger("permission.ask", ...)` 调用点

## 2. 插件从哪里来

官方公开的来源有两类：

1. 本地文件：
   - `.opencode/plugins/`
   - `~/.config/opencode/plugins/`
2. npm 包：`opencode.json` 中的 `plugin` 数组

源码里的真实装载还多了两层：

- **内建直载插件**：`packages/opencode/src/plugin/index.ts`
  - `CodexAuthPlugin`
  - `CopilotAuthPlugin`
  - `GitlabAuthPlugin`
- **内建 npm 插件**：当前硬编码了 `opencode-anthropic-auth@0.0.13`

另外有两个实现细节很重要：

- `Config.deduplicatePlugins()` 会按“规范化插件名”去重：npm 包按包名去版本，文件插件按文件名去扩展名；**高优先级来源覆盖低优先级来源**。
- 旧的 `opencode-openai-codex-auth` / `opencode-copilot-auth` 会在加载阶段被硬跳过，因为已被一方内建插件取代。

## 3. 启动与加载顺序

### 3.1 文档层的公开顺序

官方文档给出的用户可感知顺序是：

1. 全局 config `~/.config/opencode/opencode.json`
2. 项目 config `opencode.json`
3. 全局插件目录 `~/.config/opencode/plugins/`
4. 项目插件目录 `.opencode/plugins/`

这描述的是 **配置来源优先级**。

### 3.2 源码里的真实启动路径

更完整的实际路径如下：

```text
CLI bootstrap
-> Instance.provide()
-> InstanceBootstrap()
-> Plugin.init()
   -> Config.get()
      -> 合并多级 config
      -> 扫描 .opencode/plugins 和全局 plugins 目录
      -> 必要时给配置目录自动 bun install
      -> 生成最终 config.plugin 列表
   -> 加载 INTERNAL_PLUGINS
   -> 加载内建 npm 插件 + 用户配置插件
   -> 执行每个插件工厂函数，收集 hooks
   -> 对所有 hooks 执行 hook.config?.(config)
   -> Bus.subscribeAll(...)
-> 其余子系统初始化（LSP / FileWatcher / VCS / Snapshot ...）
```

对应关键文件：

- `packages/opencode/src/project/bootstrap.ts`
- `packages/opencode/src/plugin/index.ts`
- `packages/opencode/src/config/config.ts`

### 3.3 本地依赖是怎么装上的

`packages/opencode/src/config/config.ts` 里，OpenCode 会对配置目录做一轮依赖自举：

- 检查是否需要安装依赖 `needsInstall(dir)`
- 必要时写入/更新 `package.json`
- 自动注入 `@opencode-ai/plugin`
- 必要时生成 `.gitignore`
- 执行 `bun install`

这意味着：**本地 plugin / 本地 custom tool 可以直接依赖 npm 包，但依赖安装是由 OpenCode 启动过程代劳的。**

## 4. 插件初始化的真实语义

`packages/opencode/src/plugin/index.ts` 的核心逻辑可以概括为：

1. 构造 `PluginInput`
2. 依次执行内部插件工厂函数
3. 处理配置中的每个插件 specifier
   - `file://...` 直接 `import()`
   - npm 包先 `BunProc.install(pkg, version)` 再 `import()`
4. 对每个模块的所有导出做遍历，凡是函数都当 plugin 工厂执行
5. 用 `seen` 集合避免同一个函数因为 `named export + default export` 被重复初始化
6. 把所有返回的 hooks 收集到统一数组

这里有两个关键点：

- **一个模块可以导出多个 plugin 函数**，并不要求只有一个默认导出。
- **hook 顺序就是加载顺序**；后面所有 trigger 都是顺序串行执行，不做并发。

## 5. Hook 模型

### 5.1 核心执行模型

`Plugin.trigger()` 的实现很简单：

```ts
for (const hook of hooks) {
  const fn = hook[name];
  if (!fn) continue;
  await fn(input, output);
}
return output;
```

因此 hook 有三个非常重要的性质：

1. **串行**：前一个 hook 执行完，后一个才执行
2. **可变输出**：`output` 是同一个对象，前一个 hook 的修改会流给后一个 hook
3. **最后态生效**：最终返回的是被多轮修改后的 `output`

### 5.2 关键 hook 与触发点

| Hook                                   | 主要作用                               | 触发点                                  |
| -------------------------------------- | -------------------------------------- | --------------------------------------- |
| `config`                               | 启动后改写最终配置                     | `Plugin.init()`                         |
| `event`                                | 订阅总线上的所有事件                   | `Plugin.init()` 内 `Bus.subscribeAll()` |
| `chat.message`                         | 用户消息入会话前做改写                 | `session/prompt.ts:createUserMessage()` |
| `chat.params`                          | 改写温度、topP、topK、provider options | `session/llm.ts`                        |
| `chat.headers`                         | 改写对模型请求的 headers               | `session/llm.ts`                        |
| `tool.definition`                      | 改写发给模型的 tool 描述和 schema      | `tool/registry.ts`                      |
| `tool.execute.before`                  | 工具执行前改写参数                     | `session/prompt.ts`                     |
| `tool.execute.after`                   | 工具执行后改写输出/metadata/title      | `session/prompt.ts`                     |
| `shell.env`                            | 给 bash shell 注入环境变量             | `tool/bash.ts`                          |
| `experimental.chat.system.transform`   | 改写 system prompt                     | `session/llm.ts`、`agent/agent.ts`      |
| `experimental.chat.messages.transform` | 改写送给模型的消息数组                 | `session/prompt.ts`                     |
| `experimental.session.compacting`      | 改写 compaction prompt 或补充上下文    | `session/compaction.ts`                 |
| `experimental.text.complete`           | 文本 part 收尾时二次改写文本           | `session/processor.ts`                  |

### 5.3 `tool` 和 `auth` 不是普通 trigger hook

- `tool`：插件返回的自定义工具会被 `ToolRegistry.state()` 收集，并与内建工具一起注册给模型。
- `auth`：插件可以注册自定义认证 provider；这是另一条扩展面，不走 `Plugin.trigger()`。

## 6. Event / Bus 是怎么接上的

### 6.1 底层机制

OpenCode 内部事件不是 Node `EventEmitter`，而是自己的 typed bus：

- 事件类型用 `BusEvent.define(type, zodSchema)` 定义
- 发布走 `Bus.publish(eventDef, properties)`
- 订阅走 `Bus.subscribe()` / `Bus.subscribeAll()`

关键文件：

- `packages/opencode/src/bus/bus-event.ts`
- `packages/opencode/src/bus/index.ts`

### 6.2 Plugin 的 `event` hook 如何收到事件

`Plugin.init()` 最后会注册：

```ts
Bus.subscribeAll(async (input) => {
  for (const hook of hooks) {
    hook['event']?.({ event: input });
  }
});
```

也就是说：

- `event` hook 收到的是统一结构：`{ event: { type, properties } }`
- 它拿到的是 **Bus 的原始事件流**，不是单独包装过的“插件事件 API”
- 事件名字来自各模块分散定义的 `BusEvent.define(...)`

### 6.3 一个很关键的技术细节：event hook 目前是 fire-and-forget

虽然 `Bus.subscribeAll()` 的回调是 `async`，但内部调用 `hook["event"]?.(...)` **没有 `await`**。这意味着：

- `event` hook 默认不会阻塞主流程
- 插件事件处理中的异常/耗时，不会像普通 `Plugin.trigger()` hook 那样串行参与控制流
- 这和 `tool.execute.before/after`、`chat.params` 这类 hook 的行为不同

### 6.4 官方文档公开的事件族

官方 plugins 文档列出的公共事件族包括：

- command: `command.executed`
- file: `file.edited`, `file.watcher.updated`
- installation: `installation.updated`
- lsp: `lsp.client.diagnostics`, `lsp.updated`
- message: `message.part.removed`, `message.part.updated`, `message.removed`, `message.updated`
- permission: `permission.asked`, `permission.replied`
- server: `server.connected`
- session: `session.created`, `session.compacted`, `session.deleted`, `session.diff`, `session.error`, `session.idle`, `session.status`, `session.updated`
- todo: `todo.updated`
- shell: `shell.env`
- tool: `tool.execute.before`, `tool.execute.after`
- tui: `tui.prompt.append`, `tui.command.execute`, `tui.toast.show`

源码补充说明：

- `session.idle` 在 `packages/opencode/src/session/status.ts` 中已经标注为 **deprecated**，但仍会在状态切回 idle 时发布。
- 实例销毁时，`Bus` 还会向 wildcard 订阅者发送 `server.instance.disposed`；这个事件并不在插件文档的公开列表里，但 `event` hook 实际上能收到它。

## 7. 生命周期视角

把 plugin 放到完整生命周期里，可以分成 6 段：

| 阶段     | 发生什么                                                  | 关键文件                              |
| -------- | --------------------------------------------------------- | ------------------------------------- |
| 发现     | 合并 config，扫描 `plugins/`，整理 `plugin` 列表          | `config/config.ts`                    |
| 依赖准备 | 对本地配置目录自动 `bun install`                          | `config/config.ts`                    |
| 初始化   | `import()` 插件并执行插件工厂函数                         | `plugin/index.ts`                     |
| 激活     | 执行 `config` hook，注册 `event` 总线订阅                 | `plugin/index.ts`                     |
| 运行     | 各类 `Plugin.trigger()` 和 `event` 持续生效               | `session/*`, `tool/*`, `agent/*`      |
| 结束     | `Instance.dispose()` 触发实例级清理；无专门 shutdown hook | `project/instance.ts`, `bus/index.ts` |

需要特别注意：

- **没有显式 `onUnload` / `dispose` hook**。
- 插件如果要感知“快结束了”，目前更现实的方式是监听 wildcard 事件中的 `server.instance.disposed`。

## 8. Plugin 与 Tool Registry 的关系

OpenCode 有两类“加工具”的方式：

1. 在 plugin 里返回 `tool: { ... }`
2. 在配置目录放 `tool/*.ts` 或 `tools/*.ts`

两者最终都汇总进 `packages/opencode/src/tool/registry.ts`：

- 本地 `tool(s)` 文件先被扫描、导入、转成内部 `Tool.Info`
- 然后再收集 plugin 返回的 `tool`
- 最后统一进入 `ToolRegistry.tools()`，并在这里再次允许 plugin 用 `tool.definition` 去改写发给模型的 tool schema / description

官方文档还明确说明：**如果插件工具名与内建工具重名，插件工具优先。**

## 9. 重要源码坐标

| 主题                          | 文件                                          |
| ----------------------------- | --------------------------------------------- |
| Plugin 类型定义               | `packages/plugin/src/index.ts`                |
| Tool helper                   | `packages/plugin/src/tool.ts`                 |
| Plugin 装载器                 | `packages/opencode/src/plugin/index.ts`       |
| 启动入口                      | `packages/opencode/src/project/bootstrap.ts`  |
| Config 聚合与本地 plugin 扫描 | `packages/opencode/src/config/config.ts`      |
| Bus 实现                      | `packages/opencode/src/bus/index.ts`          |
| Tool 注册中心                 | `packages/opencode/src/tool/registry.ts`      |
| Bash 对 `shell.env` 的触发    | `packages/opencode/src/tool/bash.ts`          |
| 对话消息入口                  | `packages/opencode/src/session/prompt.ts`     |
| LLM 参数/headers/system hook  | `packages/opencode/src/session/llm.ts`        |
| 文本完成 hook                 | `packages/opencode/src/session/processor.ts`  |
| Compaction hook               | `packages/opencode/src/session/compaction.ts` |
| session 状态事件              | `packages/opencode/src/session/status.ts`     |

## 10. 文档与源码之间，最值得记住的差异

1. **文档说的是公共 load order，源码还有内建插件层。**
   - 实际上 internal plugins 和内建 npm plugin 会先进入系统。

2. **`event` hook 与普通 hooks 的执行语义不同。**
   - 普通 hooks 是串行 `await`；`event` hook 当前不是。

3. **`permission.ask` 目前更像“类型层预留位”。**
   - SDK 类型里有它，但当前基线源码里没找到真正的触发点。

4. **事件系统不是“插件专用事件中心”，而是直接复用内核 Bus。**
   - 所以公共文档列出的事件只是稳定子集，不一定穷尽源码里所有 wildcard 可见事件。

5. **没有正式 shutdown hook。**
   - 只有 instance dispose 相关事件可旁路观察。

## 参考资料

### 官方文档

- Plugins: `https://opencode.ai/docs/plugins/`
- Config: `https://opencode.ai/docs/config/`
- SDK: `https://opencode.ai/docs/sdk/`

### 官方源码

- Repo: `https://github.com/anomalyco/opencode`
- Plugin loader: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/plugin/index.ts`
- Plugin types: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/plugin/src/index.ts`
- Bootstrap: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/project/bootstrap.ts`
- Config loading: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/config/config.ts`
- Bus: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/bus/index.ts`
- Tool registry: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/tool/registry.ts`
- Session prompt: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/session/prompt.ts`
- LLM stream: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/session/llm.ts`
- Session processor: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/session/processor.ts`
- Session compaction: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/session/compaction.ts`
- Session status: `https://github.com/anomalyco/opencode/blob/c2ca1494e5f2b21655982d694b6bafd4526f147e/packages/opencode/src/session/status.ts`
