import httpx
import openai

from app.providers.base import ProviderError, T


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, http_client: httpx.AsyncClient | None = None,
                 max_retries: int = 2):
        self.api_key = api_key
        self.model = model
        self.client = openai.AsyncOpenAI(api_key=api_key, http_client=http_client,
                                         max_retries=max_retries)

    async def generate_structured(self, system: str, user: str, schema: type[T]) -> T:
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                response_format={"type": "json_schema", "json_schema": {
                    "name": schema.__name__, "schema": schema.model_json_schema(),
                    "strict": False}},
            )
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise ProviderError("auth") from e
        except openai.RateLimitError as e:
            raise ProviderError("rate_limited") from e
        except openai.APIError as e:
            raise ProviderError("upstream") from e
        return schema.model_validate_json(resp.choices[0].message.content or "{}")
