"""Summariser agent: produces a 150-word executive summary from project artefacts."""

from pathlib import Path

from agents.base import call_agent

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "summariser.txt"


def summarise(content: str) -> str:
    """Generate a concise executive summary from raw artefact text.

    Args:
        content: The full text of a project artefact (meeting notes, task list, etc.).

    Returns:
        Plain prose summary of at most 150 words.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    return call_agent(system_prompt, content, json_mode=False)
