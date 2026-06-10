# Delivery Copilot

An agentic CLI tool that analyses messy project management artefacts (RAID logs, meeting notes, task lists) and produces an executive-ready status report using an orchestrator-worker multi-agent pattern built on the Anthropic API.

## Purpose

Built by a Senior Delivery Manager to demonstrate practical AI architecture skills: agent orchestration, structured outputs, prompt design, and separation of concerns. The tool automates the weekly status reporting workflow that delivery managers do by hand.

## Architecture

Orchestrator-worker pattern. One orchestrator classifies inputs and routes to specialist agents, then synthesises their outputs into a single report.

```
input files --> Orchestrator (classify + route)
                  |--> Risk Analyst agent (extract risks, RAG-rate them)
                  |--> Summariser agent (exec summary)
                  |--> Action Extractor agent (owners, deadlines, blockers)
                Orchestrator (synthesise) --> status_report.md
```

## Tech stack and constraints

- Python 3.11+, Windows environment (use pathlib for all paths, never hardcode separators)
- Anthropic Python SDK directly. Do NOT use LangChain, CrewAI, or any agent framework. The point is to demonstrate understanding of the primitives.
- Model: claude-sonnet-4-6 for worker agents (fast, cheap), claude-opus-4-8 optional for the synthesis step
- API key read from environment variable ANTHROPIC_API_KEY only. Never write it to any file.
- No UI, no database, no async. Keep it simple and readable.

## Project structure

```
delivery-copilot/
  main.py              # CLI entry point (argparse) + orchestrator logic
  agents/
    __init__.py
    base.py            # shared Anthropic client wrapper, retry on rate limit
    risk_analyst.py    # structured JSON output: risk, category, RAG rating, mitigation
    summariser.py      # 150-word exec summary, plain prose
    action_extractor.py # structured JSON: action, owner, deadline, status
  prompts/             # one .txt system prompt per agent, loaded at runtime
  samples/             # 3 sample inputs: raid_log.csv, meeting_notes.txt, task_list.csv
  output/              # generated reports land here (gitignored)
  requirements.txt
  README.md
  .gitignore           # must include output/, .env, __pycache__
```

## Implementation guidance

1. **base.py first.** A thin wrapper: `call_agent(system_prompt, user_content, json_mode=False)`. For json_mode, use assistant prefilling with `{` and instruct the model to return raw JSON only. Strip markdown fences defensively before json.loads. Wrap in try/except with one retry.
2. **Worker agents** are each a single function that loads its system prompt from prompts/, calls base.call_agent, and returns a typed dict or string. Keep each under 40 lines.
3. **Orchestrator** in main.py: reads input file(s), does a cheap classification call to decide which agents apply to each input, runs the relevant agents, then makes a final synthesis call that combines all worker outputs into a Markdown report with sections: Executive Summary, Risk Register (table), Actions and Blockers (table), Recommendations.
4. **CLI usage:** `python main.py samples/raid_log.csv samples/meeting_notes.txt --output output/report.md`
5. Print progress to the terminal as each agent runs (e.g. "[orchestrator] routing meeting_notes.txt to: summariser, action_extractor") so a demo recording looks alive.
6. Handle the no-API-key case with a clear error message and setup instructions.

## Style rules

- Type hints on all functions, docstrings on all modules
- No em dashes anywhere in code comments, prompts, or generated docs
- Each commit should be small and descriptive; build incrementally (base client, then one agent at a time, then orchestrator, then README)

## Definition of done

- `python main.py samples/*.csv samples/meeting_notes.txt` produces a coherent report in under 60 seconds
- A stranger can clone, `pip install -r requirements.txt`, set their API key, and run it from the README alone
- README includes a Mermaid architecture diagram and a Design Decisions section
