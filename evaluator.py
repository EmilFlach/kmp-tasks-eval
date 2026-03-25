"""
KMP tasks eval — orchestration.

For each (agent, task, run) triple:
  1. Extract the project at task.parent_sha into a fresh temp directory.
  2. Optionally run task.setup() for additional mutations.
  3. Run the agent.
  4. Run the JVM Gradle compilation to validate the code compiles.
  5. Run task.verify(project_dir, sample_repo) to compare files against the
     real expected output from the target commit.
  6. passed = build_passed AND verify.passed

The sample repo is never modified; all work happens in temporary copies.
"""

from __future__ import annotations

import asyncio
import subprocess
import tarfile
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from agents import Agent
from judge import JudgeResult, run_judge
from tasks import Task, VerificationResult

# Default directory that contains all cloned repos as subdirectories.
# e.g. DEFAULT_REPOS_DIR/kotlinconf-app, DEFAULT_REPOS_DIR/jetcaster-kmp-migration
DEFAULT_REPOS_DIR: Path = Path(__file__).parent.parent.parent

BUILD_TIMEOUT = 300   # seconds


# ---------------------------------------------------------------------------
# Repo helpers
# ---------------------------------------------------------------------------

def repo_dir(repos_dir: Path, repo_url: str) -> Path:
    """Derive the local clone path for a repo from its URL."""
    name = repo_url.rstrip("/").split("/")[-1]
    return repos_dir / name


def clone_repos(tasks: list[Task], repos_dir: Path) -> None:
    """Clone all unique repos referenced by the given tasks."""
    seen: set[str] = set()
    for task in tasks:
        if not task.repo_url:  # generation tasks have no repo to clone
            continue
        if task.repo_url in seen:
            continue
        seen.add(task.repo_url)
        dest = repo_dir(repos_dir, task.repo_url)
        if dest.exists():
            print(f"Already exists: {dest}")
        else:
            print(f"Cloning {task.repo_url} → {dest} …")
            subprocess.run(["git", "clone", task.repo_url, str(dest)], check=True)
            print("Clone complete.")


def _extract_at_sha(repo: Path, sha: str, dest: Path) -> None:
    """
    Extract the repo tree at `sha` into `dest` using `git archive`.
    The result is a plain directory — no .git, no history visible to the agent.
    """
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
        archive_path = Path(tmp.name)

    try:
        subprocess.run(
            ["git", "archive", "--format=tar", sha, "-o", str(archive_path)],
            cwd=str(repo),
            check=True,
            capture_output=True,
        )
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path) as tar:
            tar.extractall(dest)
    finally:
        archive_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# JVM build
# ---------------------------------------------------------------------------

async def _run_jvm_build(project_dir: Path, build_task: str) -> tuple[bool, str]:
    """
    Run the JVM Kotlin compilation in project_dir.
    Returns (passed, output).
    """
    proc = await asyncio.create_subprocess_exec(
        "./gradlew", build_task, "--no-daemon", "--quiet",
        cwd=str(project_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=BUILD_TIMEOUT)
        output = stdout.decode(errors="replace")
        return proc.returncode == 0, output
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return False, f"Build timed out after {BUILD_TIMEOUT}s"
    except Exception as exc:
        return False, f"Build error: {exc}"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TaskRunResult:
    agent: str
    task_id: str
    task_name: str
    task_category: str
    parent_sha: str
    commit_sha: str
    with_kotlin_tool: bool
    run_number: int
    # File-similarity verification
    verify_passed: bool
    verify_score: float
    verification_details: list[str]
    # JVM build
    build_passed: bool | None    # None when build was skipped
    build_output: str
    # Overall
    passed: bool                 # verify_passed AND (build_passed or skipped)
    agent_output: str
    error: str = ""
    # LLM judge
    judge_verdict: str = "skipped"   # "yes" | "partial" | "no" | "skipped" | "error"
    judge_reasoning: str = ""
    judge_output: str = ""           # full raw text returned by the judge

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

async def run_task_once(
    agent: Agent,
    task: Task,
    repos_dir: Path,
    run_number: int,
    with_kotlin_tool: bool = False,
    skip_build: bool = False,
    skip_judge: bool = False,
    on_result: "Callable[[TaskRunResult], None] | None" = None,
) -> TaskRunResult:
    is_generation = task.task_type == "generation"

    if is_generation:
        # Generation tasks start from an empty directory; no git repo needed.
        sample_repo = repos_dir  # dummy — not used by the generation verifier
    else:
        sample_repo = repo_dir(repos_dir, task.repo_url)

    with tempfile.TemporaryDirectory(prefix="kmp_eval_") as tmpdir:
        project_copy = Path(tmpdir) / "project"

        # 1. Extract project at parent commit (skipped for generation tasks)
        if is_generation:
            project_copy.mkdir(parents=True, exist_ok=True)
        else:
            _extract_at_sha(sample_repo, task.parent_sha, project_copy)

        # 2. Optional extra setup
        if task.setup:
            task.setup(project_copy)

        # 3. Run agent
        agent_output = ""
        error = ""
        try:
            agent_output = await agent.run_task(
                prompt=task.prompt,
                project_dir=project_copy,
                with_kotlin_tool=with_kotlin_tool,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        # 4. JVM build
        build_passed: bool | None = None
        build_output = ""
        if not error and task.run_build and not skip_build:
            build_passed, build_output = await _run_jvm_build(project_copy, task.build_task)

        # 5. File-similarity verification
        if error:
            verification = VerificationResult(
                passed=False, score=0.0,
                checks=[(False, f"Agent error: {error}")]
            )
        else:
            verification = task.verify(project_copy, sample_repo)

        # 6. LLM judge
        judge: JudgeResult
        if error or skip_judge:
            judge = JudgeResult(
                verdict="skipped",
                reasoning="Skipped due to agent error" if error else "Judge disabled",
            )
        else:
            judge = await run_judge(
                task_prompt=task.prompt,
                commit_sha=task.commit_sha,
                parent_sha=task.parent_sha,
                project_dir=project_copy,
                sample_repo=sample_repo,
                build_passed=build_passed,
                verify_score=verification.score,
                verification_details=verification.details,
                generation_url=task.generation_url,
            )

        # 7. Overall pass (judge is informational — does not affect passed)
        build_ok = (build_passed is True) or (build_passed is None)
        overall = verification.passed and build_ok

    result = TaskRunResult(
        agent=agent.name,
        task_id=task.id,
        task_name=task.name,
        task_category=task.category,
        parent_sha=task.parent_sha,
        commit_sha=task.commit_sha,
        with_kotlin_tool=with_kotlin_tool,
        run_number=run_number,
        verify_passed=verification.passed,
        verify_score=verification.score,
        verification_details=verification.details,
        build_passed=build_passed,
        build_output=build_output[:4000],   # cap stored output
        passed=overall,
        agent_output=agent_output,
        error=error,
        judge_verdict=judge.verdict,
        judge_reasoning=judge.reasoning,
        judge_output=judge.output[:4000],
    )

    if on_result:
        on_result(result)

    return result


# ---------------------------------------------------------------------------
# Multiple runs
# ---------------------------------------------------------------------------

async def run_task_n_times(
    agent: Agent,
    task: Task,
    repos_dir: Path,
    n: int,
    with_kotlin_tool: bool = False,
    skip_build: bool = False,
    skip_judge: bool = False,
    on_result: "Callable[[TaskRunResult], None] | None" = None,
) -> list[TaskRunResult]:
    results = []
    for i in range(1, n + 1):
        r = await run_task_once(
            agent, task, repos_dir, i, with_kotlin_tool, skip_build, skip_judge, on_result
        )
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# Full eval run
# ---------------------------------------------------------------------------

async def run_all(
    agents: list[Agent],
    tasks: list[Task],
    repos_dir: Path,
    n: int = 1,
    with_kotlin_tool: bool = False,
    skip_build: bool = False,
    skip_judge: bool = False,
    on_result: "Callable[[TaskRunResult], None] | None" = None,
) -> dict[str, list[TaskRunResult]]:
    """Run every task for every agent in parallel across agents, sequential within."""

    async def _run_agent(agent: Agent) -> list[TaskRunResult]:
        results: list[TaskRunResult] = []
        for task in tasks:
            task_results = await run_task_n_times(
                agent, task, repos_dir, n, with_kotlin_tool, skip_build, skip_judge, on_result
            )
            results.extend(task_results)
        return results

    agent_results = await asyncio.gather(*(_run_agent(a) for a in agents))
    return {agent.name: results for agent, results in zip(agents, agent_results)}
