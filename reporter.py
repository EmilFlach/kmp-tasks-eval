"""
Report generation for the KMP tasks eval.

Outputs:
  - Console summary (task pass/fail table per agent)
  - Markdown report with full per-run details
  - Raw JSON export
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from evaluator import TaskRunResult

RESULTS_DIR   = Path(__file__).parent / "results"
REPORTS_DIR   = RESULTS_DIR / "reports"
DATA_DIR      = RESULTS_DIR / "data"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _pass_rate(results: list[TaskRunResult]) -> float:
    return sum(1 for r in results if r.passed) / len(results) if results else 0.0


def _avg_score(results: list[TaskRunResult]) -> float:
    return sum(r.verify_score for r in results) / len(results) if results else 0.0


def _by_task(results: list[TaskRunResult]) -> dict[str, list[TaskRunResult]]:
    grouped: dict[str, list[TaskRunResult]] = defaultdict(list)
    for r in results:
        grouped[r.task_id].append(r)
    return grouped


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------

_JUDGE_ICON = {
    "yes":     "🟢",
    "partial": "🟡",
    "no":      "🔴",
    "skipped": "⬜",
    "error":   "🟠",
}


def _judge_summary(results: list[TaskRunResult]) -> str:
    """Return one icon per run, e.g. '🟢🟡🔴' for three runs."""
    icons = [_JUDGE_ICON[r.judge_verdict] for r in results if r.judge_verdict != "skipped"]
    return "".join(icons)


def print_console_report(all_results: dict[str, list[TaskRunResult]]) -> None:
    width = 88
    print("\n" + "=" * width)
    print("KMP TASKS EVAL — RESULTS")
    print("=" * width)

    for agent_name, results in all_results.items():
        print(f"\n  {agent_name}")
        print("  " + "-" * (width - 2))

        by_task = _by_task(results)
        for task_id, task_results in by_task.items():
            pr = _pass_rate(task_results)
            avg = _avg_score(task_results)
            status = "🟢" if pr >= 0.5 else "🔴"
            name = task_results[0].task_name
            cat = task_results[0].task_category
            tool = " [+kotlin]" if task_results[0].with_kotlin_tool else ""
            builds = [r.build_passed for r in task_results if r.build_passed is not None]
            build_str = ""
            if builds:
                build_icons = "".join("🟢" if b else "🔴" for b in builds)
                build_str = f"  build {build_icons}"
            judge_str = _judge_summary(task_results)
            judge_col = f"  judge {judge_str}" if judge_str else ""
            print(
                f"  {status} {name:<40} {cat:<12} "
                f"{pr * 100:>3.0f}%  "
                f"sim {avg:.2f}{build_str}{judge_col}{tool}"
            )

        total_pr = _pass_rate(results)
        total_avg = _avg_score(results)
        print(
            f"\n  TOTAL  {len(by_task)} tasks  "
            f"{total_pr * 100:.0f}% pass rate  "
            f"{total_avg:.2f} avg score"
        )

    print("\n" + "=" * width)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_markdown_report(
    all_results: dict[str, list[TaskRunResult]],
    output_path: Path,
) -> None:
    lines: list[str] = [
        "# KMP Tasks Eval Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    # Summary table across agents
    lines += [
        "## Summary",
        "",
        "| Agent | Tasks | Pass Rate | Avg Similarity | Build Pass | Judge ✅/⚠️/❌ | Kotlin Tool |",
        "|-------|-------|-----------|----------------|------------|----------------|-------------|",
    ]
    for agent_name, results in all_results.items():
        n_tasks = len(_by_task(results))
        pr = _pass_rate(results)
        avg = _avg_score(results)
        builds = [r.build_passed for r in results if r.build_passed is not None]
        build_str = f"{sum(1 for b in builds if b) / len(builds) * 100:.0f}%" if builds else "n/a"
        judge_str = _judge_summary(results) or "n/a"
        tool = "yes" if results and results[0].with_kotlin_tool else "no"
        lines.append(
            f"| {agent_name} | {n_tasks} | {pr * 100:.0f}% | {avg:.2f} | {build_str} | {judge_str} | {tool} |"
        )

    # Per-agent detail
    for agent_name, results in all_results.items():
        lines += ["", "---", "", f"## {agent_name}", ""]

        by_task = _by_task(results)
        lines += [
            "| Task | Category | Pass Rate | Avg Similarity | Build Pass | Judge |",
            "|------|----------|-----------|----------------|------------|-------|",
        ]
        for task_id, task_results in by_task.items():
            pr = _pass_rate(task_results)
            avg = _avg_score(task_results)
            name = task_results[0].task_name
            cat = task_results[0].task_category
            builds = [r.build_passed for r in task_results if r.build_passed is not None]
            build_str = f"{sum(1 for b in builds if b) / len(builds) * 100:.0f}%" if builds else "n/a"
            judge_str = _judge_summary(task_results) or "⬜"
            lines.append(f"| {name} | {cat} | {pr * 100:.0f}% | {avg:.2f} | {build_str} | {judge_str} |")

        # Per-run details
        lines.append("")
        lines.append("### Run Details")
        for r in results:
            icon = "✅" if r.passed else "❌"
            tool_tag = " `+kotlin`" if r.with_kotlin_tool else ""
            build_icon = {True: "🟢", False: "🔴", None: "⬜"}[r.build_passed]
            judge_icon = _JUDGE_ICON.get(r.judge_verdict, "❓")
            status_line = (
                f"sim `{r.verify_score:.0%}` · "
                f"build {build_icon} · "
                f"judge {judge_icon} {r.judge_verdict}"
            )
            lines += [
                "",
                f"#### {icon} {r.task_name} — run {r.run_number}{tool_tag}",
                "",
                status_line,
            ]
            if r.judge_reasoning and r.judge_verdict not in ("skipped", "error"):
                lines.append(f"> {r.judge_reasoning}")
            lines += ["", "**File checks:**"]
            for detail in r.verification_details:
                lines.append(f"- {detail}")

            if r.error:
                lines += ["", f"**Error:** `{r.error}`"]

            if r.build_output and r.build_passed is False:
                out = r.build_output[-2000:]   # tail is most useful for build errors
                lines += [
                    "",
                    "<details><summary>Build output (failed)</summary>",
                    "",
                    "```",
                    out,
                    "```",
                    "",
                    "</details>",
                ]

            if r.agent_output:
                out = r.agent_output[:2000]
                suffix = "…" if len(r.agent_output) > 2000 else ""
                lines += [
                    "",
                    "<details><summary>Agent output</summary>",
                    "",
                    "```",
                    out + suffix,
                    "```",
                    "",
                    "</details>",
                ]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown report → {output_path}")


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def write_json_export(
    all_results: dict[str, list[TaskRunResult]],
    output_path: Path,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "generated": datetime.now().isoformat(),
        "results": {
            agent: [r.to_dict() for r in results]
            for agent, results in all_results.items()
        },
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"JSON export     → {output_path}")


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def generate_report(
    all_results: dict[str, list[TaskRunResult]],
    slug: str = "",
) -> None:
    print_console_report(all_results)

    ts = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    name = f"{ts}_{slug}" if slug else ts

    write_markdown_report(all_results, REPORTS_DIR / f"{name}.md")
    write_json_export(all_results, DATA_DIR / f"{name}.json")
