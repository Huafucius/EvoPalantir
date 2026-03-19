import asyncio
import json
import os
from pathlib import Path

import click

from aos import __version__
from aos.control.plane import AOSRuntime


@click.group()
def cli() -> None:
    pass


@cli.command("version")
def version_command() -> None:
    click.echo(json.dumps({"name": "AgentOS", "version": __version__}))


@cli.command("call")
@click.argument("op")
@click.option("--payload", default="{}", help="JSON payload for the operation")
@click.option("--db-path", default=".agentos.db", help="SQLite database path")
@click.option("--skill-root", default="skills", help="Skill root directory")
@click.option("--model", default="gpt-4o-mini", help="Default LLM model")
def call_command(op: str, payload: str, db_path: str, skill_root: str, model: str) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        click.echo(
            json.dumps(
                {
                    "ok": False,
                    "op": op,
                    "error": {"code": error.__class__.__name__, "message": str(error)},
                }
            )
        )
        return
    agent_id = os.getenv("AOS_AGENT_ID")
    session_id = os.getenv("AOS_SESSION_ID")

    if agent_id and "agentId" not in data and op in {"agent.get", "agent.update", "agent.archive"}:
        data["agentId"] = os.getenv("AOS_AGENT_ID")
    if (
        session_id
        and "sessionId" not in data
        and op
        in {
            "session.get",
            "session.append",
            "session.interrupt",
            "session.compact",
            "session.archive",
            "session.history.list",
            "session.history.get",
            "session.context.get",
            "session.context.fold",
            "session.context.unfold",
            "session.context.compact",
            "session.context.rebuild",
            "skill.load",
        }
    ):
        data["sessionId"] = os.getenv("AOS_SESSION_ID")
    if (
        "ownerType" not in data
        and "ownerId" not in data
        and op
        in {
            "skill.default.list",
            "skill.default.set",
            "skill.default.unset",
            "skill.catalog.refresh",
            "skill.catalog.preview",
            "plugin.list",
        }
    ):
        if session_id:
            data["ownerType"] = "session"
            data["ownerId"] = session_id
        elif agent_id:
            data["ownerType"] = "agent"
            data["ownerId"] = agent_id

    async def _run() -> None:
        runtime = await AOSRuntime.open(
            database_path=Path(db_path),
            skill_root=Path(skill_root),
            default_model=model,
        )
        try:
            result = await runtime.call(op, **data)
            envelope = {"ok": True, "op": op, "data": result}
        except Exception as error:  # noqa: BLE001
            envelope = {
                "ok": False,
                "op": op,
                "error": {"code": error.__class__.__name__, "message": str(error)},
            }
        click.echo(json.dumps(envelope))

    asyncio.run(_run())


def main() -> None:
    cli()
