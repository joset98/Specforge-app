from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

ErrorCode = Literal["auth", "rate_limited", "upstream"]

MESSAGES: dict[ErrorCode, str] = {
    "auth": "The API key was rejected. Check that it is valid and has access.",
    "rate_limited": "The LLM provider rate-limited this key or it has no credit left.",
    "upstream": "The LLM provider failed. Try again in a moment.",
}


class ProviderError(Exception):
    """Provider failure safe to show to users: never carries the key or raw SDK text."""

    def __init__(self, code: ErrorCode, message: str | None = None):
        self.code = code
        self.message = message or MESSAGES[code]
        super().__init__(self.message)


class LLMProvider(Protocol):
    async def generate_structured(self, system: str, user: str, schema: type[T]) -> T:
        """Return an instance of `schema`; raise pydantic.ValidationError on a bad shape."""
        ...
