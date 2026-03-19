from __future__ import annotations

import os
from pathlib import Path

import pytest

from aos.compute.react_unit import ReActUnit
from aos.control.plane import AOSRuntime
from aos.model.history import SessionHistoryMessage

pytestmark = pytest.mark.filterwarnings(
    "ignore:coroutine 'Logging.async_success_handler' was never awaited:RuntimeWarning"
)


def _load_openrouter_env() -> bool:
    env_candidates = [
        Path(__file__).resolve().parents[2] / ".env",
    ]
    env_data: dict[str, str] = {}
    for candidate in env_candidates:
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_data[key.strip()] = value.strip().strip('"').strip("'")

    api_key = env_data.get("OPENROUTE_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    base_url = env_data.get("OPENROUTE_BASE_URL") or os.getenv("OPENROUTER_API_BASE")
    if not api_key:
        return False

    os.environ["OPENROUTER_API_KEY"] = api_key
    if base_url:
        if "openroute.ai" in base_url:
            base_url = "https://openrouter.ai/api/v1"
        os.environ["OPENROUTER_API_BASE"] = base_url
    return True


@pytest.mark.asyncio
async def test_real_llm_completion_with_gpt_4o_mini() -> None:
    if not _load_openrouter_env():
        pytest.skip("OpenRouter credentials are unavailable")

    unit = ReActUnit(model="openrouter/openai/gpt-4o-mini")
    result = await unit.complete(
        messages=[{"role": "user", "content": "Reply with exactly AGENTOS_OK and nothing else."}],
        tools=[],
    )

    assert result.text is not None
    assert result.text.strip() == "AGENTOS_OK"


@pytest.mark.asyncio
async def test_real_llm_can_emit_bash_tool_call() -> None:
    if not _load_openrouter_env():
        pytest.skip("OpenRouter credentials are unavailable")

    unit = ReActUnit(model="openrouter/openai/gpt-4o-mini")
    result = await unit.complete(
        messages=[
            {
                "role": "user",
                "content": (
                    "Use the bash tool exactly once to run printf agentos_tool_ok. "
                    "Do not answer in plain text first."
                ),
            }
        ],
    )

    assert result.tool_calls
    assert result.tool_calls[0].function.name == "bash"
    assert "agentos_tool_ok" in result.tool_calls[0].function.arguments["command"]


@pytest.mark.asyncio
async def test_real_runtime_session_loop_executes_bash_and_finishes(tmp_path) -> None:
    if not _load_openrouter_env():
        pytest.skip("OpenRouter credentials are unavailable")

    skill_root = tmp_path / "skills"
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )

    runtime = await AOSRuntime.open(
        database_path=tmp_path / "agentos.db",
        skill_root=skill_root,
        default_model="openrouter/openai/gpt-4o-mini",
    )
    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Real Loop")
    await runtime.call(
        "session.append",
        sessionId=session["sessionId"],
        message=SessionHistoryMessage.user_text(
            seq=4,
            text=(
                "Use the bash tool once to run printf runtime_e2e_ok. "
                "Then answer with exactly RUNTIME_E2E_OK."
            ),
        ).model_dump(mode="json", by_alias=True),
    )

    await runtime.run_session(session["sessionId"])

    history = await runtime.call("session.history.list", sessionId=session["sessionId"])
    parts = [part for item in history["items"] for part in item["parts"]]

    assert any(part["type"] == "tool-bash" for part in parts)
    assert any(part["type"] == "text" and "RUNTIME_E2E_OK" in part["text"] for part in parts)
