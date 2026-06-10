"""Risk analyst agent: extracts and RAG-rates risks from project artefacts."""

from pathlib import Path
from typing import TypedDict

from agents.base import call_agent

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "risk_analyst.txt"


class Risk(TypedDict):
    """A single risk entry returned by the risk analyst agent."""

    risk: str
    category: str
    rag_rating: str
    mitigation: str


def analyse_risks(content: str) -> list[Risk]:
    """Extract and RAG-rate risks from raw artefact text.

    Args:
        content: The full text of a project artefact (RAID log, meeting notes, etc.).

    Returns:
        List of Risk dicts ordered by severity (Red first, then Amber, then Green).
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    result: dict = call_agent(system_prompt, content, json_mode=True)
    risks: list[Risk] = result.get("risks", [])

    for r in risks:
        r["rag_rating"] = r.get("rag_rating", "Amber").strip().title()
        if r["rag_rating"] not in {"Red", "Amber", "Green"}:
            r["rag_rating"] = "Amber"

    order = {"Red": 0, "Amber": 1, "Green": 2}
    risks.sort(key=lambda r: order.get(r["rag_rating"], 1))
    return risks
