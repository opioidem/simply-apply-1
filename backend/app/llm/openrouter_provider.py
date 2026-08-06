"""OpenRouter adapter — OpenAI-compatible endpoint.

OpenRouter is an OpenAI-compatible API that provides access to multiple model providers.
Uses the same OpenAI SDK but with OpenRouter's base URL and API key.

This is the most flexible provider — works with Anthropic, OpenAI, Google, Mistral,
Cohere, and many other models through one unified interface.

`chat.completions.parse()` is the structured-output path: the schema is enforced at
decode time and the SDK hands back a validated Pydantic instance — same as OpenAI.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.llm.base import LLMError, LLMProvider

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "openai/gpt-4o"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    name = "openrouter"
    requires_key = True

    def __init__(
        self, api_key: str, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL
    ) -> None:
        if not api_key:
            raise LLMError(
                "No OpenRouter API key configured. Add one in Settings, or switch provider."
            )
        self.model = model or DEFAULT_MODEL
        self.base_url = base_url or DEFAULT_BASE_URL
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise LLMError("The `openai` package is not installed.") from exc
        self._client = AsyncOpenAI(api_key=api_key, base_url=self.base_url)

        # The structured-output helper moved from `beta.chat.completions.parse` to
        # `chat.completions.parse` partway through the 1.x line. Contributors will have
        # whatever version their lockfile resolved, so bind to whichever exists rather
        # than pinning users to one SDK generation.
        chat = self._client.chat.completions
        self._parse = (
            chat.parse
            if hasattr(chat, "parse")
            else self._client.beta.chat.completions.parse
        )

    async def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 16000,
    ) -> T:
        try:
            completion = await self._parse(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=schema,
            )
        except Exception as exc:
            raise LLMError(f"OpenRouter request failed: {exc}") from exc

        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise LLMError(f"The model declined this request: {message.refusal}")
        if message.parsed is None:
            raise LLMError("Model returned no structured output.")
        return message.parsed

    async def health(self) -> tuple[bool, str]:
        """Test that the OpenRouter key is valid and can make structured requests.

        We send a tiny request with a dummy schema rather than checking models,
        which is more reliable: OpenRouter will 401 on an invalid key, 404 on a bad
        model, and return success if the key works for at least one model.
        """
        class _Ping(BaseModel):
            ok: bool

        try:
            await self.complete_structured(
                system="Reply with ok=true.",
                user="ping",
                schema=_Ping,
                max_tokens=64,
            )
        except LLMError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"
        return True, f"Reachable — {self.model}"