# kmp-tasks-eval

Evaluation harness that runs AI agents on Kotlin Multiplatform coding tasks and measures how accurately they reproduce real commits from KMP sample repos (kotlinconf-app, jetcaster-kmp-migration, and others).

## Project layout

```
main.py          CLI entry point and argument parsing
agents.py        Agent implementations (JunieAgent) and factory
evaluator.py     Orchestration: extract → agent → build → verify → judge
tasks.py         Task definitions and file-similarity verification
judge.py         LLM judge (informational, does not affect pass/fail)
reporter.py      Console, Markdown, and JSON report generation
tasks.toml       Task catalog (one [[tasks]] entry per git commit)
run              Shell wrapper — uses ../.venv/bin/python3
results/
  data/          Raw JSON exports
  reports/       Markdown reports
```

## Running the eval

```bash
# Setup (clone all repos referenced by the selected tasks)
./run --setup                          # clones repos for the default task only
./run --all-tasks --setup              # clones all repos (kotlinconf-app + jetcaster-kmp-migration)

# Run default agent on first task
./run

# Common flags
./run --all-tasks --all-agents
./run --tasks update-deps fix-db-migrations --agent junie
./run --runs 3
./run --compare              # run with and without kotlin CLI tool
./run --no-build             # skip JVM compilation step
./run --no-judge             # skip LLM judge step
./run --dry-run              # mock results, no API calls
./run --list-tasks
```

## Configuration

Copy `.env.example` to `.env` and set:
- `JUNIE_API_KEY` — required for all agents (Junie routes all models)

## How a task run works

1. `git archive` extracts the project at `parent_sha` into a temp dir (no `.git`)
2. Optional `task.setup()` mutates the project
3. Agent edits files inside the temp dir
4. JVM Gradle build: `./gradlew <task.build_task> --no-daemon --quiet` (configurable per task)
5. File-similarity verification compares agent output against `commit_sha` files
6. LLM judge provides qualitative feedback (verdict: yes/partial/no)
7. `passed = verify_passed AND (build_passed or build skipped)`

## Pass criteria

- `verify_score` ≥ `min_similarity` (per-task threshold, default 0.70) across changed files
- JVM build succeeds (when `run_build = true`)
- Judge verdict is informational only

## Adding tasks

Add a `[[tasks]]` entry to `tasks.toml`:

```toml
[[tasks]]
id          = "my-task"
name        = "Human-readable name"
category    = "feature"          # upgrade | bugfix | refactor | feature
repo_url    = "https://github.com/owner/repo"  # omit to default to kotlinconf-app
parent_sha  = "<full SHA>"       # agent starts here
commit_sha  = "<short SHA>"      # agent must reproduce this
run_build   = true
build_task  = ":module:compileKotlinJvm"  # omit to default to :app:shared:compileKotlinJvm
min_similarity = 0.70
skip_patterns  = []              # path substrings to exclude from verification
prompt      = """
Task description given verbatim to the agent.
"""
```

Repos are cloned into `--repos-dir` (default: `../` relative to this directory) as
subdirectories named after the repo. Run `./run --tasks <id> --setup` to clone
only the repos needed for specific tasks.

## Key implementation notes

- Agents run in parallel across agents, sequential across tasks within an agent
- Build timeout: 300 seconds; agent timeout: 900 seconds
- Reports saved to `results/` with timestamp slug: `YYYY-MM-DD_HHhMM_<agent>_<tasks>.{md,json}`
- The `run` script expects a venv at `../.venv` relative to this directory
