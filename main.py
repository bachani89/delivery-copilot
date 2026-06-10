"""Delivery Copilot CLI: orchestrates specialist agents to produce executive status reports."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anthropic

from agents.base import call_agent
from agents.action_extractor import extract_actions
from agents.risk_analyst import analyse_risks
from agents.summariser import summarise

_SYNTH_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesiser.txt"

_VALID_AGENTS = {"risk_analyst", "summariser", "action_extractor"}

_CLASSIFY_SYSTEM = """You are a routing assistant for a delivery management tool.
Given a filename and the start of a file's content, decide which specialist agents should analyse it.

Available agents:
- risk_analyst: for RAID logs or content containing risks, issues, assumptions, or dependencies
- summariser: for meeting notes, status updates, or narrative prose content
- action_extractor: for task lists, action items, or content with owners or deadlines

Return a JSON object in this exact format: {"agents": ["agent_name1", "agent_name2"]}

A file may route to multiple agents. Always include at least one agent.
Return raw JSON only."""


def _classify(filename: str, content: str) -> list[str]:
    """Route a single file to the appropriate agents via a cheap classification call."""
    user_content = f"Filename: {filename}\n\nContent preview:\n{content[:500]}"
    result: dict = call_agent(_CLASSIFY_SYSTEM, user_content, json_mode=True)
    agents = [a for a in result.get("agents", []) if a in _VALID_AGENTS]
    return agents or ["action_extractor"]


def _run_agents(content: str, agent_names: list[str]) -> dict[str, Any]:
    """Run the named agents against the file content and return their outputs."""
    outputs: dict[str, Any] = {}
    if "risk_analyst" in agent_names:
        outputs["risks"] = analyse_risks(content)
    if "summariser" in agent_names:
        outputs["summary"] = summarise(content)
    if "action_extractor" in agent_names:
        outputs["actions"] = extract_actions(content)
    return outputs


def _synthesise(combined: dict[str, Any]) -> str:
    """Make a final synthesis call combining all agent outputs into a Markdown report."""
    synth_prompt = _SYNTH_PROMPT_PATH.read_text(encoding="utf-8")
    return call_agent(synth_prompt, json.dumps(combined, indent=2), json_mode=False)


def main() -> None:
    """Parse arguments, orchestrate agents, and write the final report."""
    parser = argparse.ArgumentParser(
        description="Analyse project artefacts and produce an executive status report."
    )
    parser.add_argument("inputs", nargs="+", help="One or more input files to analyse")
    parser.add_argument(
        "--output",
        default="output/report.md",
        help="Output path for the report (default: output/report.md)",
    )
    args = parser.parse_args()

    combined: dict[str, Any] = {"risks": [], "summaries": [], "actions": []}

    for filepath in args.inputs:
        path = Path(filepath)
        if not path.exists():
            print(f"[error] file not found: {filepath}", file=sys.stderr)
            sys.exit(1)

        content = path.read_text(encoding="utf-8", errors="replace")
        agent_names = _classify(path.name, content)
        print(f"[orchestrator] routing {path.name} to: {', '.join(agent_names)}")

        outputs = _run_agents(content, agent_names)

        if "risks" in outputs:
            combined["risks"].extend(outputs["risks"])
            print(f"[risk_analyst] found {len(outputs['risks'])} risks in {path.name}")
        if "summary" in outputs:
            combined["summaries"].append({"file": path.name, "summary": outputs["summary"]})
            print(f"[summariser] summarised {path.name}")
        if "actions" in outputs:
            combined["actions"].extend(outputs["actions"])
            print(f"[action_extractor] found {len(outputs['actions'])} actions in {path.name}")

    print("[orchestrator] synthesising final report...")
    report = _synthesise(combined)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"[orchestrator] report written to {out_path}")


if __name__ == "__main__":
    try:
        main()
    except EnvironmentError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIError as exc:
        print(f"[error] Anthropic API error: {exc}", file=sys.stderr)
        sys.exit(1)
