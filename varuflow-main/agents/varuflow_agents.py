#!/usr/bin/env python3
"""
Varuflow Multi-Agent System
===========================
WORKER  (claude-sonnet-4-6) — reads files, searches code, runs shell checks
MONITOR (claude-haiku-4-5)  — reviews worker output, produces clean problem report

Usage:
    python agents/varuflow_agents.py "check for missing auth dependencies in routers"
    python agents/varuflow_agents.py "find all hardcoded URLs in the frontend"
    python agents/varuflow_agents.py "audit plan enforcement across all routers"

Output:
    - Console: live progress from worker + final report from monitor
    - File:    agents/reports/<timestamp>_report.txt
"""

import argparse
import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import anthropic

# ── Models ────────────────────────────────────────────────────────────────────
WORKER_MODEL  = "claude-sonnet-4-6"
MONITOR_MODEL = "claude-haiku-4-5"

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent
REPORTS_DIR  = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ── Worker tools ──────────────────────────────────────────────────────────────
WORKER_TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file in the Varuflow repository. "
            "Use relative paths from the repo root (e.g. 'backend/app/routers/auth.py')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from repo root"
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-based, optional)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read (inclusive, optional)"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "search_code",
        "description": (
            "Search for a pattern in the codebase using grep. "
            "Returns matching lines with file path and line number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex or literal pattern to search for"
                },
                "directory": {
                    "type": "string",
                    "description": "Subdirectory to search in (default: whole repo)"
                },
                "file_glob": {
                    "type": "string",
                    "description": "File glob filter e.g. '*.py' or '*.tsx'"
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default: false)"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory (non-recursive by default).",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Relative path from repo root"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories (default: false)"
                },
                "file_glob": {
                    "type": "string",
                    "description": "Glob filter e.g. '*.py'"
                }
            },
            "required": ["directory"]
        }
    },
    {
        "name": "run_check",
        "description": (
            "Run a safe read-only shell command for code quality checks. "
            "Allowed commands: grep, find, wc, head, tail, cat, python -m py_compile, "
            "npx tsc --noEmit (dry-run). "
            "NEVER runs destructive commands."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run (read-only only)"
                }
            },
            "required": ["command"]
        }
    }
]

# ── Tool execution ─────────────────────────────────────────────────────────────

_ALLOWED_COMMANDS = ("grep", "find", "wc", "head", "tail", "cat",
                     "python", "python3", "npx")

def _tool_read_file(path: str, start_line: int | None, end_line: int | None) -> str:
    full = REPO_ROOT / path
    if not full.exists():
        return f"ERROR: File not found: {path}"
    try:
        lines = full.read_text(errors="replace").splitlines()
        if start_line or end_line:
            s = (start_line or 1) - 1
            e = end_line or len(lines)
            lines = lines[s:e]
        text = "\n".join(f"{(start_line or 1) + i}: {l}" for i, l in enumerate(lines))
        # Cap at 400 lines to keep context sane
        if len(lines) > 400:
            text = "\n".join(f"{(start_line or 1) + i}: {l}" for i, l in enumerate(lines[:400]))
            text += f"\n... (truncated, {len(lines)} total lines)"
        return text
    except Exception as exc:
        return f"ERROR reading {path}: {exc}"


def _tool_search_code(pattern: str, directory: str | None,
                      file_glob: str | None, case_insensitive: bool) -> str:
    search_dir = REPO_ROOT / (directory or "")
    cmd = ["grep", "-rn", "--include", file_glob or "*"]
    if case_insensitive:
        cmd.append("-i")
    cmd += [pattern, str(search_dir)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        output = result.stdout.strip()
        if not output:
            return "No matches found."
        lines = output.splitlines()
        # Shorten absolute paths to relative
        lines = [l.replace(str(REPO_ROOT) + "/", "") for l in lines]
        if len(lines) > 200:
            lines = lines[:200]
            lines.append(f"... (truncated, showing 200 of more results)")
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "ERROR: search timed out (>15s)"
    except Exception as exc:
        return f"ERROR: {exc}"


def _tool_list_files(directory: str, recursive: bool, file_glob: str | None) -> str:
    target = REPO_ROOT / directory
    if not target.exists():
        return f"ERROR: Directory not found: {directory}"
    try:
        if recursive:
            pattern = f"**/{file_glob}" if file_glob else "**/*"
            files = [str(p.relative_to(REPO_ROOT)) for p in target.glob(pattern)
                     if p.is_file()]
        else:
            pattern = file_glob or "*"
            files = [str(p.relative_to(REPO_ROOT)) for p in target.glob(pattern)
                     if p.is_file()]
        files.sort()
        if len(files) > 300:
            files = files[:300]
            files.append("... (truncated)")
        return "\n".join(files) if files else "(no files found)"
    except Exception as exc:
        return f"ERROR: {exc}"


def _tool_run_check(command: str) -> str:
    first = command.strip().split()[0]
    if first not in _ALLOWED_COMMANDS:
        return f"ERROR: Command '{first}' is not in the allowed list: {_ALLOWED_COMMANDS}"
    # Block any rm / write patterns
    for forbidden in ("rm ", "mv ", ">", ">>", "sudo", "curl", "wget", "ssh"):
        if forbidden in command:
            return f"ERROR: Forbidden pattern '{forbidden}' in command."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=str(REPO_ROOT)
        )
        out = (result.stdout + result.stderr).strip()
        if len(out) > 4000:
            out = out[:4000] + "\n... (truncated)"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out (>30s)"
    except Exception as exc:
        return f"ERROR: {exc}"


def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "read_file":
        return _tool_read_file(
            tool_input["path"],
            tool_input.get("start_line"),
            tool_input.get("end_line"),
        )
    if tool_name == "search_code":
        return _tool_search_code(
            tool_input["pattern"],
            tool_input.get("directory"),
            tool_input.get("file_glob"),
            tool_input.get("case_insensitive", False),
        )
    if tool_name == "list_files":
        return _tool_list_files(
            tool_input["directory"],
            tool_input.get("recursive", False),
            tool_input.get("file_glob"),
        )
    if tool_name == "run_check":
        return _tool_run_check(tool_input["command"])
    return f"ERROR: Unknown tool '{tool_name}'"


# ── Worker agent ───────────────────────────────────────────────────────────────

WORKER_SYSTEM = {
    "type": "text",
    "text": textwrap.dedent(f"""\
        You are a senior software engineer auditing the Varuflow codebase.
        Varuflow is a B2B SaaS for Nordic wholesalers.
        Stack: Next.js 16 (App Router) + FastAPI (Python 3.11) + PostgreSQL + Supabase Auth.
        Repo root: {REPO_ROOT}

        Your job: investigate the task given by the user, use your tools to read
        files and search code, and produce a detailed technical findings report.

        Rules:
        - Be thorough — check multiple files, not just one
        - Quote exact file paths and line numbers for every issue you find
        - If something looks fine, say so (don't invent problems)
        - Organise your findings as a numbered list
        - At the end write a section called FINDINGS SUMMARY with bullet points

        Available tools: read_file, search_code, list_files, run_check
    """),
    "cache_control": {"type": "ephemeral"},
}


def run_worker(client: anthropic.Anthropic, task: str) -> str:
    """Run the worker agent in an agentic loop, return its full findings text."""
    print(f"\n{'='*60}")
    print(f"  WORKER ({WORKER_MODEL})")
    print(f"  Task: {task}")
    print(f"{'='*60}")

    messages = [{"role": "user", "content": task}]
    findings_parts: list[str] = []

    for iteration in range(20):  # safety cap
        response = client.messages.create(
            model=WORKER_MODEL,
            max_tokens=8192,
            system=[WORKER_SYSTEM],
            tools=WORKER_TOOLS,
            messages=messages,
        )

        # Collect any text blocks
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n[worker] {block.text[:300]}{'...' if len(block.text) > 300 else ''}")
                findings_parts.append(block.text)

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            # Append assistant message
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool calls and collect results
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                print(f"\n[worker tool] {block.name}({json.dumps(block.input)[:120]})")
                result_text = execute_tool(block.name, block.input)
                print(f"  → {result_text[:200]}{'...' if len(result_text) > 200 else ''}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason
            break

    return "\n\n".join(findings_parts)


# ── Monitor/client agent ───────────────────────────────────────────────────────

MONITOR_SYSTEM = {
    "type": "text",
    "text": textwrap.dedent("""\
        You are a technical lead reviewing a code audit report for the Varuflow project.
        Your role: take the raw findings from the worker agent and produce a clean,
        actionable problem report for the developer.

        Format your report exactly like this:

        # VARUFLOW CODE AUDIT REPORT
        ## Task
        <one-line task description>

        ## Critical Issues  (must fix before deploy)
        <numbered list — file:line — description>

        ## Important Issues  (fix soon)
        <numbered list — file:line — description>

        ## Minor / Informational
        <numbered list — description>

        ## Clean (no issues found)
        <list areas that passed>

        ## Recommended Actions
        <prioritised action list>

        Rules:
        - Be concise and direct
        - If the worker found no issues in an area, say so explicitly under "Clean"
        - Do NOT invent issues not present in the worker's findings
        - Do NOT repeat the same issue twice
    """),
    "cache_control": {"type": "ephemeral"},
}


def run_monitor(client: anthropic.Anthropic, task: str, worker_findings: str) -> str:
    """Pass worker findings to the monitor, get back a clean report."""
    print(f"\n{'='*60}")
    print(f"  MONITOR ({MONITOR_MODEL}) — reviewing findings …")
    print(f"{'='*60}")

    prompt = (
        f"Task the worker was given:\n{task}\n\n"
        f"Worker's raw findings:\n{worker_findings}"
    )

    response = client.messages.create(
        model=MONITOR_MODEL,
        max_tokens=4096,
        system=[MONITOR_SYSTEM],
        messages=[{"role": "user", "content": prompt}],
    )

    report = ""
    for block in response.content:
        if block.type == "text":
            report += block.text

    return report


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Varuflow multi-agent code auditor"
    )
    parser.add_argument(
        "task",
        nargs="?",
        default="Check for missing auth dependencies, hardcoded secrets, and missing org_id filters in all backend routers",
        help="Task description for the worker agent",
    )
    parser.add_argument(
        "--output",
        help="Custom output file path (default: agents/reports/<timestamp>_report.txt)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # 1. Worker investigates
    worker_findings = run_worker(client, args.task)

    if not worker_findings.strip():
        worker_findings = "(Worker produced no text output — task may have been answered via tool results only)"

    # 2. Monitor reviews and produces clean report
    report = run_monitor(client, args.task, worker_findings)

    # 3. Print report to console
    print(f"\n{'='*60}")
    print("  FINAL REPORT")
    print(f"{'='*60}\n")
    print(report)

    # 4. Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(args.output) if args.output else REPORTS_DIR / f"{timestamp}_report.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"Generated: {datetime.now().isoformat()}\n"
        f"Task: {args.task}\n"
        f"Worker model: {WORKER_MODEL}\n"
        f"Monitor model: {MONITOR_MODEL}\n"
        f"{'='*60}\n\n"
        + report,
        encoding="utf-8",
    )
    print(f"\nReport saved → {output_path}")


if __name__ == "__main__":
    main()
