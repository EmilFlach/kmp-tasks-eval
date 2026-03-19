# kmp-tasks-eval

Runs AI agents on real Kotlin Multiplatform coding tasks and checks how closely they reproduce the actual commits from [kotlinconf-app](https://github.com/JetBrains/kotlinconf-app).

Each task gives the agent a snapshot of the project at a specific commit and asks it to make a change. Pass/fail is based on file similarity against the real commit, plus a JVM build check.

## Setup

Requires Python 3.11+ and a venv at `../.venv` relative to this directory.

```bash
# Install dependencies
pip install -r requirements.txt

# Clone the sample project (needed for all real runs)
./run --setup
```

Copy `.env.example` to `.env` and add your Junie API key (get one at [junie.jetbrains.com/cli](https://junie.jetbrains.com/cli)):

```bash
cp .env.example .env
# edit .env and set JUNIE_API_KEY
```

## Running

```bash
./run                                      # first task, default agent (Junie)
./run --all-tasks                          # all tasks
./run --tasks fix-db-migrations update-deps
./run --agent claude                       # any agent whose name contains "claude"
./run --all-agents                         # all configured agents
./run --runs 3                             # 3 runs per task
./run --compare                            # with vs. without the kotlin CLI tool
./run --no-build                           # skip JVM compilation
./run --no-judge                           # skip LLM judge
./run --dry-run                            # mock results, no API calls
./run --list-tasks                         # print all task IDs
```

## Tasks

| ID | Name | Category |
|----|------|----------|
| `update-deps` | Update Kotlin and Compose dependencies | upgrade |
| `partner-column-layout` | Add missing Column layout in PartnerDetailScreen | bugfix |
| `fix-db-migrations` | Fix DB migrations for H2 compatibility | bugfix |
| `fix-theme-propagation` | Fix theme change propagation | bugfix |
| `fix-bottom-insets` | Fix bottom inset paddings on main screens | bugfix |
| `single-backstack` | Use single list instance for backstack | refactor |
| `extract-golden-kodee` | Extract RadialBackdrop composable | refactor |
| `browser-navigation` | Add browser navigation support | feature |
| `feedback-form-redesign` | Implement new feedback form design | feature |
| `golden-kodee-test-data` | Add testing indicator and Golden Kodee fake data | feature |

## How a run works

1. `git archive` extracts the project at `parent_sha` into a temp directory (no `.git`)
2. The agent edits files inside that directory
3. JVM build: `./gradlew :app:shared:compileKotlinJvm --no-daemon --quiet`
4. File similarity is measured against the files changed in `commit_sha`
5. An LLM judge gives qualitative feedback (informational only)

**Pass criteria:** `verify_score >= min_similarity` across all changed files, and the JVM build passes (when enabled).

## Adding a task

Add a `[[tasks]]` entry to `tasks.toml`:

```toml
[[tasks]]
id          = "my-task"
name        = "Human-readable name"
category    = "bugfix"               # upgrade | bugfix | refactor | feature
parent_sha  = "<full SHA>"           # agent starts here
commit_sha  = "<short SHA>"          # agent must reproduce this
run_build   = true
min_similarity = 0.70
skip_patterns  = []                  # path substrings to exclude from verification
prompt      = """
Task description given verbatim to the agent.
"""
```

## Project layout

```
main.py       CLI entry point
agents.py     Agent implementations and factory
evaluator.py  Orchestration: extract → agent → build → verify → judge
tasks.py      Task definitions and similarity verification
judge.py      LLM judge
reporter.py   Console, Markdown, and JSON report generation
tasks.toml    Task catalog
run           Shell wrapper (uses ../.venv/bin/python3)
results/
  data/       Raw JSON exports
  reports/    Markdown reports
```
