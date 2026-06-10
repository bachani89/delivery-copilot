"""Shared Anthropic client wrapper used by all delivery-copilot agents."""

import json
import os
import re
import time
from typing import Union

import anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"


def _get_client() -> anthropic.Anthropic:
    """Build an Anthropic client from the environment, or raise a clear error."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set.\n"
            "Windows: set ANTHROPIC_API_KEY=sk-...\n"
            "Unix:    export ANTHROPIC_API_KEY=sk-..."
        )
    return anthropic.Anthropic(api_key=api_key)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that models sometimes add despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def call_agent(
    system_prompt: str,
    user_content: str,
    model: str = DEFAULT_MODEL,
    json_mode: bool = False,
) -> Union[str, dict]:
    """Send a single prompt to the specified model and return the response.

    Args:
        system_prompt: The system-level instructions for the agent.
        user_content: The user turn content (the artefact text to analyse).
        model: Anthropic model ID. Defaults to claude-sonnet-4-6.
        json_mode: When True, prefill the assistant turn with '{' and parse
                   the response as JSON, returning a dict.

    Returns:
        Parsed dict if json_mode is True, plain string otherwise.

    Raises:
        EnvironmentError: If ANTHROPIC_API_KEY is missing.
        anthropic.APIError: If both attempts fail due to an API error.
        json.JSONDecodeError: If json_mode is True and output cannot be parsed.
    """
    client = _get_client()

    messages: list[dict] = [{"role": "user", "content": user_content}]
    prefill = ""

    if json_mode:
        system_prompt = (
            system_prompt
            + "\nReturn raw JSON only. Do not include markdown fences or any text outside the JSON object."
        )
        messages.append({"role": "assistant", "content": "{"})
        prefill = "{"

    last_exc: Exception = RuntimeError("call_agent: no attempts made")

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            )
            text = response.content[0].text
            if json_mode:
                raw = _strip_fences(prefill + text)
                return json.loads(raw)
            return text
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(5)

    raise last_exc
