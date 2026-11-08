import anthropic

from app.providers.base import ProviderError, T


class ClaudeProvider:
    # anthropic>=2 uses its own httpx2 fork: http_client must be an httpx2.AsyncClient.
    def __init__(self, api_key: str, model: str, http_client=None,
                 max_retries: int = 2):
        self.api_key = api_key
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=api_key, http_client=http_client,
                                               max_retries=max_retries)

    async def generate_structured(self, system: str, user: str, schema: type[T]) -> T:
        try:
            msg = await self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[{"name": "submit", "description": "Submit the result.",
                        "input_schema": schema.model_json_schema()}],
                tool_choice={"type": "tool", "name": "submit"},
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise ProviderError("auth") from e
        except anthropic.RateLimitError as e:
            raise ProviderError("rate_limited") from e
        except anthropic.APIError as e:
            raise ProviderError("upstream") from e
        if msg.stop_reason == "max_tokens":
            raise ProviderError("upstream", "The answer was too long for the model's output "
                                "limit. Try a shorter or more focused requirement.")
        block = next((b for b in msg.content if b.type == "tool_use"), None)
        return schema.model_validate(block.input if block else {})
