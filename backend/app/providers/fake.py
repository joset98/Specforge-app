from app.providers.base import T


class FakeProvider:
    """Replays canned responses (dicts are validated against the schema; exceptions are raised)."""

    def __init__(self, responses: list[dict | Exception]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, str]] = []

    async def generate_structured(self, system: str, user: str, schema: type[T]) -> T:
        self.calls.append((system, user, schema.__name__))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return schema.model_validate(item)
