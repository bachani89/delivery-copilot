"""Delivery Copilot CLI: orchestrates specialist agents to produce executive status reports."""

import argparse
import html as _html
import json
import re
import string
import sys
from datetime import date
from pathlib import Path
from typing import Any

import anthropic

from agents.base import call_agent
from agents.action_extractor import extract_actions
from agents.risk_analyst import analyse_risks
from agents.summariser import summarise

_SYNTH_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesiser.txt"
_SYNTH_STRUCTURED_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesiser_structured.txt"
_HTML_TEMPLATE_PATH = Path(__file__).parent / "templates" / "report_template.html"

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


def _synthesise_structured(combined: dict[str, Any]) -> dict:
    """Make a synthesis call that returns structured JSON for HTML rendering."""
    synth_prompt = _SYNTH_STRUCTURED_PROMPT_PATH.read_text(encoding="utf-8")
    return call_agent(synth_prompt, json.dumps(combined, indent=2), json_mode=True)


# ---------- HTML rendering helpers ----------

def _rag_css_class(rag: str) -> str:
    return {"red": "red", "amber": "amber", "green": "green"}.get(rag.strip().lower(), "amber")


def _rag_badge(rag: str) -> str:
    cls = _rag_css_class(rag)
    return f'<span class="badge {cls}">{_html.escape(rag.upper())}</span>'


def _status_pill(status: str) -> str:
    cls_map = {"blocked": "blocked", "in progress": "progress", "complete": "complete"}
    cls = cls_map.get(status.strip().lower(), "")
    escaped = _html.escape(status)
    return f'<span class="pill {cls}">{escaped}</span>' if cls else f'<span class="pill">{escaped}</span>'


def _md_bold_to_html(text: str) -> str:
    """Convert **bold** markers to <strong> after HTML-escaping the text."""
    escaped = _html.escape(text)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)


def _risk_rows_html(risks: list[dict]) -> str:
    parts = []
    for r in risks:
        cls = _rag_css_class(r.get("rag_rating", ""))
        parts.append(
            f'        <tr class="r-{cls}">\n'
            f'          <td>{_html.escape(r.get("risk", ""))}</td>\n'
            f'          <td class="cat">{_html.escape(r.get("category", ""))}</td>\n'
            f'          <td>{_rag_badge(r.get("rag_rating", ""))}</td>\n'
            f'          <td>{_html.escape(r.get("mitigation", ""))}</td>\n'
            f'        </tr>'
        )
    return "\n".join(parts)


def _action_rows_html(actions: list[dict]) -> str:
    parts = []
    for a in actions:
        parts.append(
            f'        <tr>\n'
            f'          <td>{_html.escape(a.get("action", ""))}</td>\n'
            f'          <td class="owner">{_html.escape(a.get("owner", ""))}</td>\n'
            f'          <td class="deadline">{_html.escape(a.get("deadline", ""))}</td>\n'
            f'          <td>{_status_pill(a.get("status", "Open"))}</td>\n'
            f'        </tr>'
        )
    return "\n".join(parts)


def _rec_cards_html(recommendations: list[dict]) -> str:
    parts = []
    for rec in recommendations:
        owner = _html.escape(rec.get("owner", ""))
        heading = _html.escape(rec.get("heading", ""))
        body = _html.escape(rec.get("body", ""))
        owner_line = f'\n      <div class="rec-owner">Owner: {owner}</div>' if owner else ""
        parts.append(
            f'    <div class="rec">{owner_line}\n'
            f'      <div class="rec-head">{heading}</div>\n'
            f'      <p>{body}</p>\n'
            f'    </div>'
        )
    return "\n".join(parts)


def _render_html(data: dict) -> str:
    """Populate the HTML report template from structured synthesiser output."""
    tpl = string.Template(_HTML_TEMPLATE_PATH.read_text(encoding="utf-8"))

    risks = data.get("risks", [])
    actions = data.get("actions", [])
    overall_rag = data.get("overall_rag", "Amber")
    reporting_date = data.get("reporting_date") or date.today().strftime("%d %B %Y")

    red_count = sum(1 for r in risks if r.get("rag_rating", "").lower() == "red")
    amber_count = sum(1 for r in risks if r.get("rag_rating", "").lower() == "amber")
    green_count = sum(1 for r in risks if r.get("rag_rating", "").lower() == "green")

    return tpl.substitute(
        project_name=_html.escape(data.get("project_name", "Project")),
        period=_html.escape(data.get("period", "")),
        reporting_date=_html.escape(reporting_date),
        overall_rag=_html.escape(overall_rag.upper()),
        overall_rag_lower=_rag_css_class(overall_rag),
        red_count=red_count,
        amber_count=amber_count,
        green_count=green_count,
        action_count=len(actions),
        executive_summary=_md_bold_to_html(data.get("executive_summary", "")),
        risk_rows=_risk_rows_html(risks),
        action_rows=_action_rows_html(actions),
        recommendation_cards=_rec_cards_html(data.get("recommendations", [])),
    )


# ---------- CLI entry point ----------

def main() -> None:
    """Parse arguments, orchestrate agents, and write the final report."""
    parser = argparse.ArgumentParser(
        description="Analyse project artefacts and produce an executive status report."
    )
    parser.add_argument("inputs", nargs="+", help="One or more input files to analyse")
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: output/report.md or output/report.html)",
    )
    parser.add_argument(
        "--format",
        choices=["md", "html"],
        default="md",
        dest="fmt",
        help="Output format: md (default) or html",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = f"output/report.{'html' if args.fmt == 'html' else 'md'}"

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
    if args.fmt == "html":
        structured = _synthesise_structured(combined)
        report = _render_html(structured)
    else:
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
