"""Action extractor agent: pulls actions, owners, deadlines, and statuses from project artefacts."""

from pathlib import Path
from typing import TypedDict

from agents.base import call_agent

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "action_extractor.txt"


class Action(TypedDict):
    """A single action item returned by the action extractor agent."""

    action: str
    owner: str
    deadline: str
    status: str


def extract_actions(content: str) -> list[Action]:
    """Extract action items and blockers from raw artefact text.

    Args:
        content: The full text of a project artefact (task list, meeting notes, etc.).

    Returns:
        List of Action dicts with action, owner, deadline, and status fields.
        Blocked items are sorted to the top.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    result: dict = call_agent(system_prompt, content, json_mode=True)
    actions: list[Action] = result.get("actions", [])

    order = {"Blocked": 0, "In Progress": 1, "Open": 2, "Complete": 3}
    actions.sort(key=lambda a: order.get(a.get("status", "Open"), 2))
    return actions
