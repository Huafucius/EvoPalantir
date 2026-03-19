import json
from pathlib import Path

from click.testing import CliRunner

from aos.cli import cli


def test_version_command_outputs_json() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"name": "AgentOS", "version": "0.1.0"}


def test_call_command_outputs_aos_response_envelope() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        skills_dir = Path("skills/aos")
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
        )
        result = runner.invoke(
            cli,
            ["call", "skill.list", "--db-path", "agentos.db", "--skill-root", "skills"],
        )

    assert result.exit_code == 0
    body = json.loads(result.output)
    assert body["ok"] is True
    assert body["op"] == "skill.list"
    assert {item["name"] for item in body["data"]} == {"aos"}
