"""
LLM judge for the KMP tasks eval — powered by the Junie CLI.

After each task run, the judge compares the agent's implementation against the
expected output from the original commit and rates whether the agent's code
would work just as well functionally.

Uses the same Junie CLI and JUNIE_API_KEY that the coding agents use.
No additional keys or packages required.

Output strategy
---------------
Rather than parsing Junie's free-form stdout (which uses a ### Summary / ### Changes
format), we tell Junie to write its verdict to a dedicated temp file at a known path.
This makes parsing reliable regardless of how Junie formats its console output.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Model used for judging — sonnet gives better code reasoning than the default
_JUDGE_MODEL = "sonnet"

# Per-file display limits to keep the prompt manageable
_MAX_FILES      = 5    # only show up to this many files
_MAX_LINES      = 60   # cap each expected/actual block at this many lines
_JUDGE_TIMEOUT  = 120  # seconds

_VERDICT_FILENAME = "kmp_eval_judge_verdict.txt"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class JudgeResult:
    verdict: str    # "yes" | "partial" | "no" | "skipped" | "error"
    reasoning: str
    output: str = ""    # full raw text returned by Junie


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git_diff_status(repo: Path, parent_sha: str, commit_sha: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "diff", "--name-status", parent_sha, commit_sha],
        cwd=str(repo), capture_output=True, text=True, check=True,
    )
    entries: list[tuple[str, str]] = []
    for line in result.stdout.strip().splitlines():
        if "\t" in line:
            parts = line.split("\t")
            entries.append((parts[0], parts[-1]))
    return entries


def _git_show(repo: Path, sha: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=str(repo), capture_output=True, text=True,
    )
    return result.stdout if result.returncode == 0 else ""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    half = max_lines // 2
    omitted = len(lines) - max_lines
    return "\n".join(lines[:half]) + f"\n[... {omitted} lines omitted ...]\n" + "\n".join(lines[-half:])


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return ""


# ---------------------------------------------------------------------------
# Core judge function
# ---------------------------------------------------------------------------

async def run_judge(
    task_prompt: str,
    commit_sha: str,
    parent_sha: str,
    project_dir: Path,
    sample_repo: Path,
    build_passed: bool | None = None,
    verify_score: float | None = None,
    verification_details: list[str] | None = None,
) -> JudgeResult:
    """
    Ask the Junie CLI to compare the agent's implementation against the expected
    commit output and return a verdict on functional equivalence.

    Junie is instructed to write its verdict to a temp file; we read that file
    after Junie exits rather than parsing its free-form stdout.
    """
    api_key = os.getenv("JUNIE_API_KEY")
    if not api_key:
        return JudgeResult(verdict="skipped", reasoning="JUNIE_API_KEY not set", output="")

    # Get the list of files changed in the expected commit
    try:
        changed = _git_diff_status(sample_repo, parent_sha, commit_sha)
    except subprocess.CalledProcessError as exc:
        return JudgeResult(verdict="error", reasoning=f"git diff failed: {exc}", output="")

    # Build file comparison sections
    file_sections: list[str] = []
    for status, path in changed[:_MAX_FILES]:
        if status.startswith("D"):
            agent_has = (project_dir / path).exists()
            file_sections.append(
                f"FILE: {path}\n"
                f"Expected: DELETED\n"
                f"Agent: {'incorrectly kept' if agent_has else 'correctly deleted'}"
            )
        else:
            expected = _git_show(sample_repo, commit_sha, path)
            if not expected:
                continue    # binary or unavailable
            actual = _read(project_dir / path)
            if not actual:
                actual = "(file not created by agent)"
            tag = "[NEW] " if status.startswith("A") else ""
            file_sections.append(
                f"{tag}FILE: {path}\n\n"
                f"=== EXPECTED (original commit) ===\n"
                f"{_truncate(expected, _MAX_LINES)}\n\n"
                f"=== AGENT IMPLEMENTATION ===\n"
                f"{_truncate(actual, _MAX_LINES)}"
            )

    if not file_sections:
        return JudgeResult(verdict="skipped", reasoning="No text files to compare", output="")

    skipped_note = (
        f"\n\n({len(changed) - _MAX_FILES} additional files not shown)"
        if len(changed) > _MAX_FILES else ""
    )

    # Use a temp dir as Junie's working directory so it has a clean place to
    # write the verdict file without touching the sample repo or project copy.
    with tempfile.TemporaryDirectory(prefix="kmp_judge_") as workdir:
        verdict_file = Path(workdir) / _VERDICT_FILENAME

        build_note = {
            True:  "Build: PASSED",
            False: "Build: FAILED (does not compile)",
            None:  "Build: not run",
        }[build_passed]

        sim_note = (
            f"Similarity score: {verify_score:.0%} "
            "(line-level match against expected files — low score does not necessarily mean wrong)"
            if verify_score is not None else ""
        )

        checks_note = ""
        if verification_details:
            checks_note = "Per-file similarity:\n" + "\n".join(
                f"  {d}" for d in verification_details
            )

        context_parts = [p for p in [build_note, sim_note, checks_note] if p]
        context_block = "\n".join(context_parts)

        prompt = (
            "You are an expert Kotlin Multiplatform code reviewer. "
            "Your only job is to compare an AI agent's implementation against the "
            "expected commit code and judge whether the agent's version would work "
            "the same way functionally. "
            "Focus only on functional correctness — ignore style, formatting, and "
            "cosmetic differences.\n\n"
            f"TASK:\n{task_prompt}\n\n"
            f"{context_block}\n\n"
            "---\n\n"
            + "\n\n---\n\n".join(file_sections)
            + skipped_note
            + "\n\n---\n\n"
            "Does the agent's implementation correctly complete the task and would it "
            "function the same way as the expected commit?\n\n"
            f"Write your verdict to the file: {verdict_file}\n"
            "The file must contain exactly two lines and nothing else:\n"
            "VERDICT: yes|partial|no\n"
            "REASONING: <one sentence explaining your verdict>\n\n"
            "Do not modify any other files."
        )

        cmd = ["junie", f"--auth={api_key}", "--model", _JUDGE_MODEL, prompt]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_JUDGE_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return JudgeResult(verdict="error", reasoning=f"Judge timed out after {_JUDGE_TIMEOUT}s", output="")

        junie_output = _ANSI_RE.sub("", stdout.decode()).strip()
        if not junie_output:
            junie_output = _ANSI_RE.sub("", stderr.decode()).strip()

        # Read the verdict from the file Junie was asked to write
        verdict_text = _read(verdict_file).strip()

    if not verdict_text:
        return JudgeResult(
            verdict="error",
            reasoning="Judge did not write a verdict file",
            output=junie_output,
        )

    # Parse "VERDICT: yes/partial/no" and "REASONING: ..."
    verdict = "error"
    reasoning = verdict_text[:200]
    for line in verdict_text.splitlines():
        upper = line.upper()
        if upper.startswith("VERDICT:"):
            v = line.split(":", 1)[1].strip().lower()
            if v in ("yes", "partial", "no"):
                verdict = v
        elif upper.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return JudgeResult(verdict=verdict, reasoning=reasoning, output=junie_output)
