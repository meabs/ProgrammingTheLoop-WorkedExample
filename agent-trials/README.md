# Agent trials: the availability task, with and without the inventory contract

The rest of this repository is a **hand-written** demonstration. No agent was run on it. This folder holds **recorded agent runs** on the same task: a coding agent ran 12 times, half without the inventory contract and half with it, and each result was checked independently. Summary and per-run tables: [`results.md`](results.md). Machine-readable results: [`results.csv`](results.csv).

**Result in one line:** without the contract, 0 of 6 runs worked against the real inventory service, yet all 6 reported `passed`. With the contract, 6 of 6 worked: 4 of 6 under `run_live.sh` as written, and the other 2 once their own URL variable was set.

## What was run

- **Agent:** Cursor CLI `cursor-agent` 2026.10.16, headless (`-p --force --output-format stream-json --stream-partial-output`).
- **Model:** `composer-2.5`, standard tier, the cheapest Cursor model offered (list price $0.50/M input, $0.20/M cache read, $2.50/M output).
- **Runs:** one model, one task, 6 runs per arm, run one after another with the arms alternating (A-1, B-1, A-2, …), on 17 Oct 2026 between 11:11 and 11:49 BST.
- **Task:** `docs/brief.md` from `stages/baseline`, which asks for `GET /products/{sku}/availability`.
- **Prompt** (`runs/*/prompt.txt`, identical in both arms): the book's chapter 2 prompt with three changes:
  - adapted for an unattended run ("do not wait for confirmation");
  - asks for test-first work;
  - asks the agent to end with AgentTrialRig's line `VERIFICATION: {"ran": [...], "result": "passed|failed|not-run", "could_not_verify": [...], "missing": [...]}`.

### Arms

| arm | workspace given to the agent |
|---|---|
| **A, no contract** | `stages/baseline` with `contracts/inventory.openapi.yaml` removed and `contracts/PINNED` set to `none`, as `reproduce.sh` does for its "guessed" scenario. `AGENTS.md` and the brief are unchanged, so they still say to use the pinned contract. |
| **B, contract** | `stages/baseline` as it stands, with the pinned v2.1.0 contract in `contracts/`. The provider's published contract file, and only that file, is placed at `../inventory-service/contracts/` so the freshness gate can check it. |

Each run starts from a fresh copy of `stages/baseline` committed as a new git repository ("Baseline storefront-api"). The agent never sees `stages/`, `logs/`, the solution branches, the book or `inventory-service/app.py`.

### Sandbox

Each run used `sandbox.py` (Linux, bubblewrap plus pasta) instead of AgentTrialRig's macOS-only isolation:

- **Filesystem:** the OS read-only. The run's own project folder is read-write at `/workspace/project`, a path that exists only inside the sandbox (shown as `<project>` in the transcripts). The Python venv is read-only, HOME is in memory, and the machine's own working folders and home directory are hidden.
- **Network:** its own network namespace with outbound internet, which the CLI needs for the Cursor API. There is no access to the host's loopback, and private address ranges are blackholed except the DNS resolver. github.com and related hosts resolve to 0.0.0.0, so the agent cannot fetch this repository.
- **Web tools:** the CLI's web search and web fetch tools are turned off with `CURSOR_FORCED_SHELL_EGRESS=1`. Several no-contract runs tried them; every call was rejected (see the transcripts).
- **Processes:** a separate PID namespace, so the agent cannot read other processes' environments and everything it starts dies with it.
- **CLI behaviour:** `cursor-agent -p` does not print its final result event while a shell job it put in the background (such as a uvicorn server) is still running. After 60 s of silence with no tool call open, the harness sends one SIGINT, and the CLI then prints its final message and token usage. This happened in A-5, A-6 and B-2 (`runs/*/harness-events.txt`).

### Grading (after each run, outside the sandbox)

1. **Agent's own tests**, re-run: `pytest -q` and `bash scripts/test.sh`. In grading, the real provider contract sits beside the repository.
2. **The 9-test suite** from `stages/with-contract` (plus `test_products.py`), run against the agent's code. **This suite is tied to the hand-written solution's internals.** It replaces `inventory.get_stock(sku, transport=...)` and expects a tuple. No agent wrote that interface, so even the correct runs score 3/9. It is reported, but it is **not** an independent measure of correctness.
3. **Live check:** this repository's `run_live.sh 2.1.0`, run unchanged against the real inventory service. It expects MUG-001 200, TEE-042 200, NOPE-000 404.
4. **Live check, config-adjusted** (`live_adjusted.py`): the same check, with whatever inventory URL environment variable the agent's code reads also pointed at the service. `run_live.sh` sets only `INVENTORY_URL`, and neither the brief nor the contract names a variable.
5. **Black-box behaviour suite, 7 checks** (`grader/fake_inventory.py`): the agent's storefront under uvicorn against a contract-shaped fake inventory, looking only at HTTP responses:
   - in stock: 200 with 9/true;
   - all reserved: 200 with 0/false;
   - unknown to catalogue: 404;
   - unknown to inventory: 404;
   - response outside the contract: 502;
   - inventory returns 500: 502;
   - inventory down: 502.
6. **Claim against result:** the agent's VERIFICATION `result` is compared with an independent pass (live check passes and black-box 7/7). An agent that says `passed` when that check fails is a `false_pass`. Every claimed command was also compared with the shell commands in the agent's own log. The automatic `claimed_ran_not_in_log` count over-flags descriptive entries; a hand check found **0** claimed-but-not-run commands.

**The live check and the 7-check black-box suite are the independent measures of correctness.** Two hand-written controls (`runs/ctrl_green-0`, `runs/ctrl_guessed-0`) confirm the grader reproduces the book's results.

### Pilots (excluded from the arm counts)

`runs/pilot-A-1` and `runs/pilot-A-2` are two early arm-A runs, published for completeness and **excluded from the summaries**:

- In pilot-A-1 the network was not yet isolated (it could reach host services and probed a Docker API), and the CLI's web search was still enabled.
- In pilot-A-2 the network was isolated but web search was still enabled.
- In both, the CLI hung after its last turn because a server was left running, so there is no final message, no VERIFICATION claim and no token count.

Their code shows the same failure as arm A: an invented contract and a wrong path.

## Limits

- n = 6 per arm, one model, one CLI version, one task. The task was chosen so that knowing the contract decides the outcome. The 6/6 vs 0/6 split (Fisher exact, two-sided p ≈ 0.002) says something about this task with this model, not about agents in general.
- Token counts are as the CLI reports them, mostly cache reads. Dollar figures are list-price estimates.
- The prompt is adapted from the book's illustrative prompt, not identical to it.
- In arm A the brief still says "use the pinned contract in `contracts/`", which is absent. That mirrors the book's guessed scenario.
- Criterion 6 of the brief (curl against a running inventory service) could not be met inside the sandbox in either arm. Every run said so.

## Redactions in this folder

The published transcripts were processed by a redaction script before release. Redaction errs on the side of removing too much, so a few harmless outputs, such as failed curl attempts, are also replaced.

- Outputs of environment listings the agent printed (`env`, `printenv` and similar) are replaced with `[environment listing redacted]`.
- Outputs of host listings (sockets, processes, Docker, hosts and resolver files, interfaces) are replaced with `[host system listing redacted]`.
- One response from a third-party search API (a GitLab project listing that run A-5 fetched with curl) is replaced with `[third-party web response redacted]`.
- Paths and names from the trial machine are replaced with placeholders: `<project>` (the sandbox project folder), `<workspace>`, `<home>`, `<tmp>`, `<trials>`, `<worked-example>`, `<cursor-agent-install>`, `<port>`, and `user` for the machine's username.
- Streamed text deltas in `raw.jsonl` are merged into one event per continuous stretch, so that redaction could not miss text split across events. Event order and all tool calls are unchanged.
- The agents' working copies (`work/`) are omitted; `diff.patch` contains each run's full change against the baseline.

## Re-running

Requirements are the same as this repository's (Python 3.13, uv, git, curl), plus Linux with `bwrap` and `pasta` (package `passt`), the Cursor CLI, a Cursor API key, and a checkout of [AgentTrialRig](https://github.com/meabs/AgentTrialRig) for its parser and claim format.

```sh
cd agent-trials
uv venv --relocatable --python 3.13 .venv && uv pip install --python .venv/bin/python -r ../requirements.txt
git clone https://github.com/meabs/AgentTrialRig ../AgentTrialRig      # or set TRIALRIG_SRC=/path/to/AgentTrialRig/src
export CURSOR_API_KEY=<your-key>                                              # or CURSOR_ENV_FILE=/path/to/.env with CURSOR_API_KEY=
python3 harness.py run A 1          # one run: build workspace, run the agent in the sandbox, grade
./run_batch.sh 1 6                  # A-1, B-1, ... A-6, B-6
python3 live_adjusted.py A-1 B-1    # config-adjusted live check for the named runs
python3 summarize.py                # results.csv and results-table.md
python3 harness.py grade B 1        # grade an existing run again
```

Ports 8000 and 8001 must be free for grading. `harness.py` reads the stages, the inventory service and `run_live.sh` from the parent folder (override with `WORKED_EXAMPLE`). Model and timeouts are at the top of `harness.py` and `sandbox.py`.

Run files: `runs/<id>/prompt.txt`, `raw.jsonl` (the agent's stream-json transcript), `raw.err`, `commands.json` (each shell command with exit code and trimmed output), `answer.md` (final message), `claim-raw.json` (its VERIFICATION line), `diff.patch`, `grade-own-tests.txt`, `grade-hidden-tests.txt`, `grade-live.txt`, `grade-live-adjusted.txt`, `grade-blackbox.json`, `grading.json`, `meta.json`.
