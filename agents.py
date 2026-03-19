"""
Agent implementations for the KMP tasks eval.

Each agent receives:
  - A task prompt
  - The path of a project directory (their working directory)
  - A flag indicating whether they have access to the `kotlin` CLI tool

The `kotlin` CLI tool flag only affects the context/system prompt given to the
agent.  When with_kotlin_tool=True the agent is told about the available
`kotlin` commands so it can use them.  The actual `kotlin` binary must be on
PATH for any tool calls to succeed; if it isn't, the agent is expected to fall
back to direct file editing.
"""

from __future__ import annotations

import asyncio
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# ---------------------------------------------------------------------------
# kotlin CLI tool description (injected when with_kotlin_tool=True)
# ---------------------------------------------------------------------------

KOTLIN_TOOL_DESCRIPTION = """\
You also have access to the `kotlin` CLI tool in this project's terminal.
Available commands:

  kotlin build [<platform>]             Build for android | ios | desktop | web (or all)
  kotlin test [<platform>]              Run tests for a platform (or all)
  kotlin dependency add <lib>           Add a dependency (e.g. kotlin dependency add io.ktor:ktor-client-core:3.1.2)
  kotlin dependency remove <lib>        Remove a dependency by group:artifact
  kotlin dependency list                List installed dependencies
  kotlin platform add <name>            Add a target platform (android | ios | desktop | web)
  kotlin platform remove <name>         Remove a target platform
  kotlin info                           Print project summary (name, version, platforms, dependencies)
  kotlin clean                          Wipe build artifacts and Gradle caches
  kotlin devices [list|start|stop]      Manage connected devices and emulators

Use these commands when they are the most efficient way to complete the task.
You can always fall back to editing build files directly if a command doesn't exist
or doesn't cover your use case.
"""


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class Agent(ABC):
    name: str

    @abstractmethod
    async def run_task(
        self,
        prompt: str,
        project_dir: Path,
        with_kotlin_tool: bool = False,
    ) -> str:
        """Execute a task inside project_dir. Returns the agent's text output."""


# ---------------------------------------------------------------------------
# Junie CLI agent
# ---------------------------------------------------------------------------

class JunieAgent(Agent):
    """
    Wraps the `junie` CLI binary.
    The working directory is set to the project copy so Junie's file tools
    operate on the right files.
    """
    _TIMEOUT = 900  # seconds

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        display_name: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self.name = display_name or (f"Junie ({model})" if model else "Junie")

    async def run_task(
        self,
        prompt: str,
        project_dir: Path,
        with_kotlin_tool: bool = False,
    ) -> str:
        import shutil

        if not shutil.which("junie"):
            raise RuntimeError(
                "junie binary not found in PATH. "
                "Install: curl -fsSL https://junie.jetbrains.com/install.sh | bash"
            )

        full_prompt = _build_prompt(prompt, project_dir, with_kotlin_tool)

        cmd = ["junie", f"--auth={self._api_key}"]
        if self._model:
            cmd.extend(["--model", self._model])
        cmd.append(full_prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_dir),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError(f"Agent timed out after {self._TIMEOUT}s")

        output = _ANSI_RE.sub("", stdout.decode()).strip()
        if not output:
            output = _ANSI_RE.sub("", stderr.decode()).strip()
        if not output:
            raise RuntimeError(
                f"Agent returned no output (exit {proc.returncode}). "
                f"stderr: {stderr.decode()[:300]}"
            )
        return output


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(prompt: str, project_dir: Path, with_kotlin_tool: bool) -> str:
    parts = [
        f"You are working on a Kotlin Multiplatform (Compose Multiplatform) project.",
        f"The project is located at: {project_dir}",
        "",
        "Your task:",
        prompt,
        "",
        "Make all necessary changes to the project files to complete the task.",
        "Do not describe what you would do — make the actual changes.",
    ]
    if with_kotlin_tool:
        parts.append("")
        parts.append(KOTLIN_TOOL_DESCRIPTION)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# (display_name, junie_model_alias | None for Junie's default)
_PROVIDERS: list[tuple[str, str | None]] = [
    ("Junie",         None),
    ("Claude Sonnet", "sonnet"),
    ("Claude Opus",   "opus"),
    ("GPT Codex",     "gpt-codex"),
    ("Gemini Flash",  "gemini-flash"),
]


def agents_from_env(only: list[str] | None = None) -> list[Agent]:
    """
    Return JunieAgent instances for providers matching `only`
    (case-insensitive substring).  Pass None to include all providers.
    Requires JUNIE_API_KEY in the environment.
    """
    api_key = os.getenv("JUNIE_API_KEY")
    if not api_key:
        return []

    def _include(name: str) -> bool:
        if only is None:
            return True
        return any(f.lower() in name.lower() for f in only)

    return [
        JunieAgent(api_key=api_key, model=model, display_name=name)
        for name, model in _PROVIDERS
        if _include(name)
    ]
