from aos.model.response import AosError, AosResponse


def test_success_response_dumps_with_aliases() -> None:
    response = AosResponse(
        ok=True,
        op="agent.create",
        revision=2,
        data={"agentId": "agent-1"},
    )

    assert response.model_dump(by_alias=True) == {
        "ok": True,
        "op": "agent.create",
        "revision": 2,
        "data": {"agentId": "agent-1"},
        "error": None,
    }


def test_error_response_requires_error_payload() -> None:
    response = AosResponse(
        ok=False,
        op="agent.create",
        error=AosError(code="conflict", message="agent already exists"),
    )

    assert response.error is not None
    assert response.error.code == "conflict"
