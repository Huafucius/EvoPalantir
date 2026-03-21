# LLM Provider 抽象层研究

> **非规范文档。** 本文是技术调研与设计草案，不定义 AgentOS 正式行为。接口建议需经 spec 评审流程后方具约束力。

_问题：AgentOS 的 ReAct 循环如何与多个 LLM 提供商解耦？_

_关联文档：[aos-lifecycle.md](../specs/aos-lifecycle.md)_

---

## 1. 问题陈述

AgentOS 当前的 `ReActUnit`（`AgentOS/src/aos/compute/react_unit.py`）直接 import `litellm.acompletion` 作为默认 provider call：

```python
from litellm import acompletion

class ReActUnit:
    def __init__(self, *, model: str, provider_call: ProviderCall | None = None) -> None:
        self.model = model
        self._provider_call = provider_call or acompletion
```

这个设计有一个 `provider_call` 注入口，但存在以下问题：

1. **无流式支持**：当前 `complete()` 方法等待完整响应，不支持 SSE streaming。对于长回答，用户需等待数十秒才能看到第一个 token。
2. **无 provider 配置管理**：model 字符串直接传给 LiteLLM（如 `"anthropic/claude-sonnet-4-20250514"`），但 API key、base URL、超时、重试策略散落在环境变量和硬编码中。
3. **无成本追踪**：`ComputeResult.usage` 字段存在但未被上层消费，无法做预算管理。
4. **无 fallback/路由**：单一 model，单一 provider，任一故障即全局故障。
5. **tool calling 格式耦合**：`_normalize_response` 假设 OpenAI 格式的 `response.choices[0].message.tool_calls`，不同 provider 的原生 tool calling 格式差异被 LiteLLM 屏蔽，但如果未来想绕过 LiteLLM 直连某个 provider，就会破裂。

**核心需求**：在不改变 ReAct 循环语义的前提下，提供一个干净的 provider 抽象层，让用户通过配置切换 LLM 后端。

---

## 2. 生态主要方案对比

### 2.1 LiteLLM — 库级 Provider 代理

**项目地址**：https://github.com/BerriAI/litellm

LiteLLM 是目前最流行的 Python LLM provider 统一库。核心思路是把所有 provider 的 API 翻译成 OpenAI 格式的输入/输出。

**API 表面**：

```python
import litellm

# 同步
response = litellm.completion(
    model="anthropic/claude-sonnet-4-20250514",  # provider/model 格式
    messages=[{"role": "user", "content": "Hello"}],
    tools=[...],           # OpenAI 格式的 tool spec
    tool_choice="auto",
    stream=False,
)

# 异步
response = await litellm.acompletion(...)

# 流式
async for chunk in await litellm.acompletion(..., stream=True):
    print(chunk.choices[0].delta.content)
```

**model 字符串约定**：`provider_prefix/model_name`，例如：

- `openai/gpt-4o` — OpenAI
- `anthropic/claude-sonnet-4-20250514` — Anthropic
- `ollama/llama3` — 本地 Ollama
- `bedrock/anthropic.claude-v2` — AWS Bedrock
- `azure/gpt-4-deployment` — Azure OpenAI

**成本追踪**：

```python
from litellm import completion, completion_cost

response = completion(model="anthropic/claude-sonnet-4-20250514", messages=messages)
cost = completion_cost(completion_response=response)  # 返回 USD float
# 或直接从 hidden params 获取
cost = response._hidden_params["response_cost"]
```

LiteLLM 内置每个 model 的 input/output token 价格表（`model_cost` 字典），自动计算费用。

**异常映射**：

| HTTP 状态码 | LiteLLM 异常                 | 继承自                       |
| ----------- | ---------------------------- | ---------------------------- |
| 400         | `BadRequestError`            | `openai.BadRequestError`     |
| 400         | `ContextWindowExceededError` | `litellm.BadRequestError`    |
| 401         | `AuthenticationError`        | `openai.AuthenticationError` |
| 408         | `Timeout`                    | `openai.APITimeoutError`     |
| 429         | `RateLimitError`             | `openai.RateLimitError`      |
| 500         | `APIError`                   | `openai.APIError`            |
| 503         | `ServiceUnavailableError`    | `openai.APIStatusError`      |

所有异常统一继承自 OpenAI SDK 的异常类型，意味着现有的 `try/except openai.XXXError` 代码无需改动。

**Router（负载均衡 + fallback）**：

```python
from litellm import Router

router = Router(
    model_list=[
        {
            "model_name": "default",  # 逻辑名
            "litellm_params": {
                "model": "anthropic/claude-sonnet-4-20250514",
                "api_key": "sk-ant-...",
            },
        },
        {
            "model_name": "default",  # 同名 = 负载均衡
            "litellm_params": {
                "model": "openai/gpt-4o",
                "api_key": "sk-...",
            },
        },
    ],
    fallbacks=[{"default": ["fallback-cheap"]}],
    num_retries=3,
    retry_policy={
        "RateLimitErrorRetries": 5,
        "TimeoutErrorRetries": 3,
    },
)

response = await router.acompletion(model="default", messages=messages)
```

**优点**：100+ provider 支持，社区活跃（37k+ stars），tool calling / streaming / async 全覆盖，成本追踪内置。
**缺点**：依赖重（拉入多个 provider SDK），model_cost 表需要跟随各 provider 调价更新，Proxy Server 模式对单机部署是 overkill。

---

### 2.2 OpenRouter — 托管 API 网关

**地址**：https://openrouter.ai

OpenRouter 是一个托管的反向代理服务。你向 `api.openrouter.ai` 发请求，它路由到实际 provider。

```python
import openai

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="or-...",
)

response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4-20250514",
    messages=[...],
)
```

**特点**：

- 500+ model，60+ provider
- OpenAI 兼容 API（只改 base_url 和 api_key）
- 自动 fallback，延迟约 25ms overhead
- 按 token 计费，markup 在 0-15% 之间

**对 AgentOS 的意义**：OpenRouter 适合不想自建 provider 层的场景。但它引入外部依赖和网络跳转，不适合本地 Ollama 场景，也无法在离线环境使用。可作为 LiteLLM 之上的一个 provider 选项（LiteLLM 原生支持 `openrouter/model` 前缀），但不能替代 provider 抽象层本身。

---

### 2.3 LangChain BaseChatModel — 重抽象

LangChain 的 LLM 抽象分三层：

```
BaseLanguageModel (abc)
  └── BaseChatModel (abc)
        ├── ChatOpenAI
        ├── ChatAnthropic
        ├── ChatOllama
        └── ...
```

每个 provider 实现 `_generate()` 和 `_agenerate()` 方法。统一通过 `Runnable` 接口调用（`.invoke()`, `.ainvoke()`, `.stream()`, `.astream()`）。

**问题**：LangChain 的抽象层级太深（Runnable -> RunnableSerializable -> BaseLanguageModel -> BaseChatModel -> 具体实现），带来大量间接调用和 debug 困难。对 AgentOS 这样有自己 ReAct 循环的系统，LangChain 的 agent/chain 抽象是冗余的——我们只需要 completion 调用，不需要 LCEL。

---

### 2.4 Vercel AI SDK — TypeScript 世界的 Provider Pattern

AI SDK v6 的 provider 模式（TypeScript）：

```typescript
import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";
import { anthropic } from "@ai-sdk/anthropic";

// provider 是工厂函数，返回 model 实例
const result = await generateText({
    model: openai("gpt-4o"),  // 或 anthropic("claude-sonnet-4-20250514")
    prompt: "Hello",
    tools: { ... },
});
```

**设计要点**：

- `model` 参数接受一个 `LanguageModel` 接口实例，而不是字符串
- 每个 provider 包（`@ai-sdk/openai`, `@ai-sdk/anthropic`）独立发布
- 统一的 streaming protocol（`streamText()` 返回 `ReadableStream`）
- AI Gateway 作为可选的服务端路由层

**启发**：provider 不是字符串映射，而是类型安全的对象。这比 LiteLLM 的 `"provider/model"` 字符串约定更严格，但对 Python 生态的意义有限（Python 类型系统较弱）。

---

### 2.5 AI 编程工具的实现

**aider**：直接使用 LiteLLM 作为 provider 层。model 字符串用 `provider/model` 格式传入，支持 `--model sonnet` 快捷别名。通过环境变量注入 API key。不做额外抽象。

**opencode**（Go 实现）：自建两层 provider 抽象：

- 外层 `Provider` 接口：agent 系统消费
- 内层 `ProviderClient` 接口：每个 provider 实现
- `baseProvider` 桥接两层，处理消息格式转换
- 每个 provider 独立实现消息 -> 原生 API 格式的转换
- 重试采用指数退避：`2000ms * 2^(attempts-1)` + 20% jitter，最多 8 次

**Claude Code**（本工具）：底层直连 Anthropic API，通过配置支持 Bedrock/Vertex 等替代端点。

**总结**：小项目用 LiteLLM 直连，大项目倾向自建薄接口 + 按需对接 provider。

---

### 2.6 LightLLM — 推理框架（非 provider 抽象）

需要澄清：GitHub 上的 [LightLLM](https://github.com/ModelTC/lightllm) 是一个 **LLM 推理/serving 框架**（类似 vLLM），用于在 GPU 上部署和推理开源模型，与 provider 抽象无关。它的特点是三进程异步协作（tokenization、inference、detokenization）和 FlashAttention 集成。

如果 AgentOS 未来需要自托管开源模型，LightLLM/vLLM 是后端引擎选项，但它们会暴露 OpenAI 兼容的 HTTP API，因此对 provider 抽象层来说，它们和 Ollama 一样只是另一个 `openai_compatible` 类型的端点。

---

## 3. 关键技术维度对比

| 维度               | LiteLLM（库）           | OpenRouter（托管）        | 自建抽象层         |
| ------------------ | ----------------------- | ------------------------- | ------------------ |
| **Provider 覆盖**  | 100+                    | 500+ model / 60+ provider | 按需实现           |
| **部署形态**       | pip install，进程内调用 | SaaS，HTTP API            | 内核代码           |
| **Streaming**      | 原生支持 sync/async     | 原生支持                  | 需自行实现         |
| **Tool Calling**   | 统一 OpenAI 格式        | 统一 OpenAI 格式          | 需按 provider 适配 |
| **成本追踪**       | 内置 model_cost 表      | 平台提供 dashboard        | 需自建价格表       |
| **异常映射**       | 统一到 OpenAI 异常      | HTTP 标准错误             | 需逐 provider 映射 |
| **Fallback/LB**    | Router 类               | 自动 fallback             | 需自建             |
| **离线/本地**      | 支持 Ollama/vLLM        | 不支持                    | 完全可控           |
| **依赖量**         | 较重（各 SDK 拉入）     | 零（HTTP 调用）           | 最小               |
| **vendor lock-in** | LiteLLM 项目            | OpenRouter 服务           | 无                 |

---

## 4. Streaming 支持细节

streaming 是 AgentOS 必须支持的能力。当前 dispatch 流程通过 SSE (`GET /aoscp/dispatch/{dispatchId}/stream`) 返回事件。

**LiteLLM 的 streaming 模型**：

```python
# 异步流式
response = await litellm.acompletion(
    model="anthropic/claude-sonnet-4-20250514",
    messages=messages,
    stream=True,
)

async for chunk in response:
    delta = chunk.choices[0].delta
    if delta.content:
        yield delta.content  # 文本 token
    if delta.tool_calls:
        yield delta.tool_calls  # tool call 增量
```

每个 chunk 的结构：

- `chunk.choices[0].delta.content` — 文本增量（或 None）
- `chunk.choices[0].delta.tool_calls` — tool call 增量（function name 和 arguments 分段到达）
- `chunk.choices[0].finish_reason` — 最后一个 chunk 为 `"stop"` 或 `"tool_calls"`

**Tool call 在 streaming 中的拼接**：tool_calls 的 arguments 是 JSON 字符串的碎片，需要在客户端累积拼接后 `json.loads()`。这是所有 provider 的通病，LiteLLM 不做自动拼接。

---

## 5. Tool/Function Calling 兼容性

各 provider 的 tool calling 格式差异是 provider 抽象中最棘手的部分：

| Provider          | Tool 定义格式                                  | Tool Call 返回格式                                | 并行 Tool Call |
| ----------------- | ---------------------------------------------- | ------------------------------------------------- | -------------- |
| OpenAI            | `tools: [{type: "function", function: {...}}]` | `message.tool_calls[].function.{name, arguments}` | 支持           |
| Anthropic（原生） | `tools: [{name, description, input_schema}]`   | `content[].{type: "tool_use", id, name, input}`   | 支持           |
| Ollama            | OpenAI 兼容格式                                | OpenAI 兼容格式                                   | 部分模型支持   |
| Gemini            | `tools: [{functionDeclarations: [...]}]`       | `parts[].functionCall.{name, args}`               | 支持           |

LiteLLM 的价值在于把这些差异全部翻译为 OpenAI 格式。AgentOS 的 `BASH_TOOL_SPEC` 用的就是 OpenAI 格式，通过 LiteLLM 传给任何 provider 都能正确工作。

**注意**：不同模型对 tool calling 的支持质量不同。小模型可能忽略 tool spec 直接输出文本。provider 抽象层不能解决这个问题——这是模型能力问题，应在 ReAct 循环中做容错。

---

## 6. 设计草案（非规范）

> 以下为调研者的探索性建议，不构成正式 spec。正式采纳需经 spec 评审流程。

### 6.1 结论：保持 LiteLLM，在其上建薄接口

不要自建完整 provider 抽象层，也不要直接暴露 LiteLLM API 给内核。推荐在 LiteLLM 之上建一个薄接口层：

**理由**：

- AgentOS 是 Python 项目，LiteLLM 是 Python 生态中最成熟的 provider 抽象，重写无意义
- LiteLLM 已在 `react_unit.py` 中使用，迁移成本为零
- 自建的价值在于：隔离 LiteLLM 的 API 变化、统一 streaming/非 streaming 路径、集成 AgentOS 的 Hook 系统

### 6.2 推荐接口设计

```python
# AgentOS/src/aos/compute/provider.py

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ProviderConfig:
    """单个 provider 端点配置。"""
    model: str                          # "anthropic/claude-sonnet-4-20250514"
    api_key: str | None = None          # 覆盖环境变量
    api_base: str | None = None         # 自定义端点（Ollama、Azure 等）
    timeout: float = 120.0              # 秒
    max_retries: int = 3
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None       # 由 LiteLLM 计算


@dataclass
class CompletionChunk:
    """streaming 模式下的单个增量。"""
    text: str | None = None
    tool_call_index: int | None = None
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_arguments: str | None = None  # JSON 片段
    finish_reason: str | None = None


@dataclass
class CompletionResult:
    """非 streaming 模式的完整结果。"""
    text: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_response: Any = None            # 调试用，保留原始 provider 响应


class LLMProvider(abc.ABC):
    """AgentOS LLM provider 抽象。"""

    @abc.abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = "auto",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """非流式调用。"""
        ...

    @abc.abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = "auto",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[CompletionChunk]:
        """流式调用，逐 chunk yield。"""
        ...
```

### 6.3 LiteLLM 实现

```python
# AgentOS/src/aos/compute/provider_litellm.py

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import litellm
from litellm import acompletion, completion_cost

from .provider import (
    CompletionChunk,
    CompletionResult,
    LLMProvider,
    ProviderConfig,
    TokenUsage,
)


class LiteLLMProvider(LLMProvider):
    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    async def complete(self, messages, *, tools=None, tool_choice="auto",
                       temperature=None, max_tokens=None) -> CompletionResult:
        response = await acompletion(
            model=self._config.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice if tools else None,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._config.api_key,
            api_base=self._config.api_base,
            timeout=self._config.timeout,
            num_retries=self._config.max_retries,
        )
        return self._to_result(response)

    async def stream(self, messages, *, tools=None, tool_choice="auto",
                     temperature=None, max_tokens=None) -> AsyncIterator[CompletionChunk]:
        response = await acompletion(
            model=self._config.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice if tools else None,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._config.api_key,
            api_base=self._config.api_base,
            timeout=self._config.timeout,
            num_retries=self._config.max_retries,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            tc = (delta.tool_calls or [None])[0]
            yield CompletionChunk(
                text=delta.content,
                tool_call_index=tc.index if tc else None,
                tool_call_id=getattr(tc, "id", None) if tc else None,
                tool_call_name=tc.function.name if tc and tc.function.name else None,
                tool_call_arguments=tc.function.arguments if tc and tc.function.arguments else None,
                finish_reason=chunk.choices[0].finish_reason,
            )

    @staticmethod
    def _to_result(response: Any) -> CompletionResult:
        choice = response.choices[0]
        msg = choice.message
        tool_calls = []
        for tc in getattr(msg, "tool_calls", None) or []:
            args = tc.function.arguments
            if isinstance(args, str):
                args = json.loads(args)
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": args,
            })
        usage_data = getattr(response, "usage", None)
        cost = None
        try:
            cost = float(completion_cost(completion_response=response))
        except Exception:
            pass
        return CompletionResult(
            text=getattr(msg, "content", None),
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=TokenUsage(
                prompt_tokens=getattr(usage_data, "prompt_tokens", 0),
                completion_tokens=getattr(usage_data, "completion_tokens", 0),
                total_tokens=getattr(usage_data, "total_tokens", 0),
                cost_usd=cost,
            ),
            raw_response=response,
        )
```

### 6.4 与 ReActUnit 集成

改造后的 ReActUnit 只依赖 `LLMProvider` 接口，不直接依赖 litellm：

```python
class ReActUnit:
    def __init__(self, *, provider: LLMProvider) -> None:
        self._provider = provider

    async def complete(self, *, messages, tools=None) -> ComputeResult:
        result = await self._provider.complete(messages, tools=tools or [BASH_TOOL_SPEC])
        return ComputeResult(
            text=result.text,
            tool_calls=[...],  # 从 result.tool_calls 转换
            finish_reason=result.finish_reason,
            usage=asdict(result.usage),
        )

    async def stream(self, *, messages, tools=None):
        """新增：streaming 路径，yield CompletionChunk。"""
        async for chunk in self._provider.stream(messages, tools=tools or [BASH_TOOL_SPEC]):
            yield chunk
```

### 6.5 配置管理

provider 配置应纳入 AOSCB（系统控制块）或环境变量：

```python
# 环境变量方案（简单场景）
AOS_LLM_MODEL=anthropic/claude-sonnet-4-20250514
AOS_LLM_API_KEY=sk-ant-...
AOS_LLM_API_BASE=                      # 留空则用默认
AOS_LLM_TIMEOUT=120
AOS_LLM_MAX_RETRIES=3

# AOSCB 方案（高级场景，支持 Router）
{
    "llm": {
        "providers": [
            {
                "name": "primary",
                "model": "anthropic/claude-sonnet-4-20250514",
                "api_key_env": "ANTHROPIC_API_KEY"
            },
            {
                "name": "fallback",
                "model": "openai/gpt-4o",
                "api_key_env": "OPENAI_API_KEY"
            }
        ],
        "fallbacks": [{"primary": ["fallback"]}],
        "compaction_model": "anthropic/claude-haiku-4-20250514"
    }
}
```

注意 `compaction_model`：compaction 流程（aos-lifecycle.md 第 5 节）用于生成摘要，可以用更便宜的模型，不需要和主 ReAct 循环用同一个 model。

### 6.6 Hook 集成点

provider 抽象层需要与 Hook 系统的以下节点对齐（参见 aos-lifecycle.md 4.2 节）：

| Hook                       | 时机                 | provider 层的职责                      |
| -------------------------- | -------------------- | -------------------------------------- |
| `compute.params.transform` | LLM 调用前           | 允许 plugin 修改 messages/tools/params |
| `compute.before`           | LLM 调用前 Admission | 拦截不合规请求                         |
| `compute.after`            | LLM 调用后           | 传递 usage/cost 给上层用于追踪         |

provider 层本身不触发 hook——hook 由 ReActUnit 的循环逻辑触发。provider 层的职责是：接受 transform 后的参数，返回标准化的结果（含 usage）。

### 6.7 实施路线

| 阶段 | 工作内容                                                       | 交付物                               |
| ---- | -------------------------------------------------------------- | ------------------------------------ |
| P0   | 定义 `LLMProvider` 接口 + `LiteLLMProvider` 实现               | `provider.py`, `provider_litellm.py` |
| P0   | 改造 `ReActUnit` 依赖 `LLMProvider` 而非 `litellm.acompletion` | 改动 `react_unit.py`                 |
| P1   | 添加 streaming 路径，ReActUnit.stream() → SSE 推送             | `react_unit.py`, transport 层        |
| P1   | provider 配置从环境变量读取，注入 AOSRuntime 初始化            | `runtime.py`                         |
| P2   | 成本追踪：每次 compute.after 写入 usage + cost 到 RunLog       | store 层                             |
| P2   | Router 支持：多 provider fallback，AOSCB 配置                  | `provider_router.py`                 |
| P3   | compaction 独立 model 配置                                     | compaction 逻辑                      |

---

## 7. 补充：为什么不直连 provider SDK

一种替代方案是绕过 LiteLLM，直接 import `anthropic`、`openai` 等 SDK，每个写一个适配器。opencode 就是这么做的。

**不推荐的理由**：

1. **维护成本**：每个 provider 的 SDK 版本升级、API breaking change 都需要单独处理。LiteLLM 社区帮你做了这件事。
2. **tool calling 格式**：Anthropic 和 OpenAI 的 tool calling 格式完全不同（见第 5 节），自行适配需要大量 if/else 和测试。
3. **streaming 协议**：各 SDK 的 streaming chunk 结构不同，统一消费需要额外的 adapter 代码。
4. **AgentOS 定位**：AgentOS 是 agent 框架，不是 LLM client 库。provider 兼容性应该委托给专业工具。

唯一例外：如果某个 provider 有 LiteLLM 不支持的特殊功能（如 Anthropic 的 prompt caching `cache_control`），可通过 `ProviderConfig.extra` 传递 provider 特有参数，或在 `LiteLLMProvider` 中做特殊处理。LiteLLM 的 `extra_body` / `extra_headers` 参数可以透传这些。

---

## 参考资料

- [LiteLLM 文档](https://docs.litellm.ai/) — 完整 API 参考
- [LiteLLM GitHub](https://github.com/BerriAI/litellm) — 源码与 model_cost 表
- [OpenRouter 文档](https://openrouter.ai/docs/guides/routing/provider-selection) — provider routing 机制
- [Vercel AI SDK](https://ai-sdk.dev/docs/introduction) — TypeScript provider pattern 参考
- [OpenCode Provider 架构](https://deepwiki.com/opencode-ai/opencode/3.2-llm-providers) — Go 语言两层 provider 设计
- [aider LLM 连接](https://aider.chat/docs/llms.html) — 多 provider 配置实践
- [LightLLM](https://github.com/ModelTC/lightllm) — LLM 推理 serving 框架（非 provider 抽象）
- [LangChain BaseChatModel](https://python.langchain.com/api_reference/core/language_models/langchain_core.language_models.chat_models.BaseChatModel.html) — 重量级抽象参考
