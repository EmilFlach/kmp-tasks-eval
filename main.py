#!/usr/bin/env python3
"""
KMP Tasks Evaluator

Run a suite of real KMP coding tasks against one or more AI agents and report
how well each agent completes them.  Between tasks the sample project is
automatically restored to its original state (each run operates on a fresh copy).

Usage:
    python main.py                                    # all tasks, all agents, 1 run
    python main.py --tasks add-ktor rename-composable # only these tasks
    python main.py --agent claude                     # only Claude Sonnet
    python main.py --runs 3                           # 3 runs per task per agent
    python main.py --with-kotlin-tool                 # give agents the kotlin CLI descriptions
    python main.py --compare                          # run each task with AND without kotlin tool
    python main.py --list-tasks                       # print available task IDs and exit
    python main.py --dry-run                          # mock results (no real API calls)

Task IDs (use with --tasks):
    add-ktor              add-counter          rename-composable
    remove-hotreload      add-settings-screen  change-app-name
    add-unit-tests        upgrade-kotlin       add-viewmodel
    add-dark-mode         add-search           fix-broken-gradient

Agent filters (use with --agent, case-insensitive substring):
    claude  codex  gemini  junie
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).parent / ".env"

from agents import Agent, agents_from_env
from evaluator import DEFAULT_REPOS_DIR, TaskRunResult, clone_repos, run_all, repo_dir
from reporter import generate_report
from tasks import TASKS, TASKS_BY_ID, Task


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

def make_progress_callback() -> "Callable[[TaskRunResult], None]":
    start = datetime.now()

    _JUDGE_ICON = {"yes": "🟢", "partial": "🟡", "no": "🔴", "skipped": "", "error": "🟠"}

    def on_result(r: TaskRunResult) -> None:
        elapsed = int((datetime.now() - start).total_seconds())
        status = "🟢" if r.passed else "🔴"
        build = {True: " build 🟢", False: " build 🔴", None: ""}[r.build_passed]
        judge = f" judge {_JUDGE_ICON.get(r.judge_verdict, '')}" if r.judge_verdict not in ("skipped", "") else ""
        tool = " [+kotlin]" if r.with_kotlin_tool else ""
        print(
            f"  [{elapsed:>4}s]  {r.agent:<22}  {r.task_id:<25}  "
            f"{status}  sim={r.verify_score:.2f}{build}{judge}{tool}"
        )

    return on_result


# ---------------------------------------------------------------------------
# Dry-run mock data
# ---------------------------------------------------------------------------

def _mock_results(
    agents: list[Agent],
    tasks: list[Task],
    n: int,
    with_kotlin_tool: bool,
) -> dict[str, list[TaskRunResult]]:
    import random

    results: dict[str, list[TaskRunResult]] = {}
    for agent in agents:
        agent_results: list[TaskRunResult] = []
        for task in tasks:
            for i in range(1, n + 1):
                passed = random.random() > 0.4
                score = random.uniform(0.5, 1.0) if passed else random.uniform(0.0, 0.5)
                build_ok = random.random() > 0.3
                agent_results.append(
                    TaskRunResult(
                        agent=agent.name,
                        task_id=task.id,
                        task_name=task.name,
                        task_category=task.category,
                        parent_sha=task.parent_sha,
                        commit_sha=task.commit_sha,
                        with_kotlin_tool=with_kotlin_tool,
                        run_number=i,
                        verify_passed=passed,
                        verify_score=score,
                        verification_details=["[mock] file.kt: 82% match", "[mock] build.gradle.kts: 55% match"],
                        build_passed=build_ok if task.run_build else None,
                        build_output="[mock build output]",
                        passed=passed and build_ok,
                        agent_output="[DRY RUN] No real agent was called.",
                        judge_verdict=random.choice(["yes", "partial", "no"]),
                        judge_reasoning="[mock] Code looks functionally equivalent.",
                        judge_output="[DRY RUN] No real judge was called.",
                    )
                )
        results[agent.name] = agent_results
    return results


# ---------------------------------------------------------------------------
# Stub agent for dry-run when no .env exists
# ---------------------------------------------------------------------------

class _StubAgent(Agent):
    def __init__(self, name: str) -> None:
        self.name = name

    async def run_task(self, prompt: str, project_dir: Path, with_kotlin_tool: bool = False) -> str:
        return "[DRY RUN]"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate AI agents on Kotlin Multiplatform coding tasks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--runs", type=int, default=1,
        help="Number of runs per task per agent (default: 1)",
    )
    parser.add_argument(
        "--agent", nargs="+", metavar="NAME",
        default=["junie"],
        help="Agent(s) to evaluate. Substring match, e.g. claude, codex, gemini (default: junie)",
    )
    parser.add_argument(
        "--all-agents", action="store_true",
        help="Run all available agents (overrides --agent)",
    )
    parser.add_argument(
        "--tasks", nargs="+", metavar="TASK_ID",
        default=[TASKS[0].id],
        help=f"Task ID(s) to run (default: {TASKS[0].id}). See --list-tasks for all IDs",
    )
    parser.add_argument(
        "--all-tasks", action="store_true",
        help="Run all tasks (overrides --tasks)",
    )
    parser.add_argument(
        "--with-kotlin-tool", action="store_true",
        help="Give agents the kotlin CLI tool descriptions in their context",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help=(
            "Run each task twice: once without and once with the kotlin CLI tool. "
            "Results are reported side-by-side to measure the tool's impact."
        ),
    )
    parser.add_argument(
        "--repos-dir", type=Path, default=DEFAULT_REPOS_DIR,
        help=f"Directory containing cloned repos (default: {DEFAULT_REPOS_DIR}). "
             "Each repo is expected as a subdirectory named after the repo.",
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Clone all repos needed by the selected tasks into --repos-dir and exit",
    )
    parser.add_argument(
        "--no-build", action="store_true",
        help="Skip the JVM build step. "
             "Useful for quick iteration; build is required for a result to count as passed.",
    )
    parser.add_argument(
        "--no-judge", action="store_true",
        help="Skip the LLM judge step (uses Junie/sonnet via JUNIE_API_KEY). "
             "The judge is informational and does not affect pass/fail.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip real API calls; use random mock results (for testing the pipeline)",
    )
    parser.add_argument(
        "--list-tasks", action="store_true",
        help="Print all available task IDs and exit",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def async_main() -> int:
    load_dotenv(_ENV_FILE)
    args = parse_args()

    if args.setup:
        # Resolve which tasks are selected so we only clone what's needed
        setup_tasks = TASKS if args.all_tasks else [
            TASKS_BY_ID[tid] for tid in args.tasks if tid in TASKS_BY_ID
        ]
        if not setup_tasks:
            setup_tasks = TASKS
        clone_repos(setup_tasks, args.repos_dir)
        return 0

    if args.list_tasks:
        print(f"\n{'ID':<28} {'Category':<12} Name")
        print("-" * 70)
        for t in TASKS:
            print(f"{t.id:<28} {t.category:<12} {t.name}")
        return 0

    # Resolve tasks
    if args.all_tasks:
        selected_tasks = TASKS
    else:
        unknown = [tid for tid in args.tasks if tid not in TASKS_BY_ID]
        if unknown:
            print(f"ERROR: Unknown task IDs: {unknown}", file=sys.stderr)
            print(f"Run --list-tasks to see available IDs.", file=sys.stderr)
            return 1
        selected_tasks = [TASKS_BY_ID[tid] for tid in args.tasks]

    # Validate that each required repo is present
    if not args.dry_run:
        missing = []
        seen: set[str] = set()
        for task in selected_tasks:
            if task.repo_url not in seen:
                seen.add(task.repo_url)
                repo_path = repo_dir(args.repos_dir, task.repo_url)
                if not repo_path.exists():
                    missing.append(f"  {repo_path}  (from {task.repo_url})")
        if missing:
            print(
                "ERROR: missing repo(s):\n" + "\n".join(missing) + "\n"
                "Run:  ./run --setup   to clone them automatically.",
                file=sys.stderr,
            )
            return 1

    # Resolve agents
    agent_filter = None if args.all_agents else args.agent
    if args.dry_run:
        agents: list[Agent] = [
            _StubAgent("Claude Sonnet [mock]"),
            _StubAgent("GPT Codex [mock]"),
        ]
    else:
        agents = agents_from_env(only=agent_filter)
        if not agents:
            print(
                "ERROR: No agents available.\n"
                "Set JUNIE_API_KEY in .env (copy .env.example for reference).",
                file=sys.stderr,
            )
            return 1

    # Print run summary
    task_ids_preview = ", ".join(t.id for t in selected_tasks[:5])
    if len(selected_tasks) > 5:
        task_ids_preview += f", … (+{len(selected_tasks) - 5} more)"
    print(f"\nAgents       : {', '.join(a.name for a in agents)}")
    print(f"Tasks        : {len(selected_tasks)} ({task_ids_preview})")
    print(f"Runs each    : {args.runs}")
    mode = "compare (with & without kotlin tool)" if args.compare else (
        "with kotlin tool" if args.with_kotlin_tool else "without kotlin tool"
    )
    print(f"Kotlin tool  : {mode}")
    print(f"JVM build    : {'SKIPPED (--no-build)' if args.no_build else 'enabled (per-task build task)'}")
    print(f"LLM judge    : {'SKIPPED (--no-judge)' if args.no_judge else 'junie (sonnet)'}")
    print(f"Repos dir    : {args.repos_dir}")
    if args.dry_run:
        print("Mode         : DRY RUN")
    print("-" * 72)

    callback = make_progress_callback()
    skip_build = args.no_build
    skip_judge = args.no_judge

    if args.compare:
        print("\n[Phase 1/2] Without kotlin tool\n")
        results_without = (
            _mock_results(agents, selected_tasks, args.runs, with_kotlin_tool=False)
            if args.dry_run
            else await run_all(
                agents, selected_tasks, args.repos_dir,
                n=args.runs, with_kotlin_tool=False, skip_build=skip_build,
                skip_judge=skip_judge, on_result=callback,
            )
        )
        print("\n[Phase 2/2] With kotlin tool\n")
        results_with = (
            _mock_results(agents, selected_tasks, args.runs, with_kotlin_tool=True)
            if args.dry_run
            else await run_all(
                agents, selected_tasks, args.repos_dir,
                n=args.runs, with_kotlin_tool=True, skip_build=skip_build,
                skip_judge=skip_judge, on_result=callback,
            )
        )
        all_results: dict[str, list[TaskRunResult]] = {}
        for agent in agents:
            all_results[f"{agent.name} (no tool)"] = results_without[agent.name]
            all_results[f"{agent.name} (+kotlin)"] = results_with[agent.name]

    elif args.dry_run:
        all_results = _mock_results(agents, selected_tasks, args.runs, args.with_kotlin_tool)

    else:
        all_results = await run_all(
            agents, selected_tasks, args.repos_dir,
            n=args.runs, with_kotlin_tool=args.with_kotlin_tool,
            skip_build=skip_build, skip_judge=skip_judge, on_result=callback,
        )

    # Agent part: "junie" or "junie+sonnet" for multiple
    agent_slug = "+".join(
        a.name.lower().replace(" ", "-") for a in agents
    )

    # Task part: task id for a single task, "all" for all, else count
    if len(selected_tasks) == 1:
        task_slug = selected_tasks[0].id
    elif len(selected_tasks) == len(TASKS):
        task_slug = "all-tasks"
    else:
        task_slug = f"{len(selected_tasks)}-tasks"

    slug = f"{agent_slug}_{task_slug}"
    if args.compare:
        slug += "_compare"
    elif args.with_kotlin_tool:
        slug += "_kotlin"

    generate_report(all_results, slug=slug)
    return 0


def main() -> None:
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
