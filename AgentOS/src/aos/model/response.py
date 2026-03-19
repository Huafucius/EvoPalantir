from typing import Any

from pydantic import model_validator

from aos.model.common import AOSModel


class AosError(AOSModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class AosResponse(AOSModel):
    ok: bool
    op: str
    revision: int | None = None
    data: dict[str, Any] | None = None
    error: AosError | None = None

    @model_validator(mode="after")
    def validate_error_shape(self) -> "AosResponse":
        if self.ok and self.error is not None:
            raise ValueError("successful responses must not include error")
        if not self.ok and self.error is None:
            raise ValueError("failed responses must include error")
        return self


__all__ = ["AosError", "AosResponse"]
