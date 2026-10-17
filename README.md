# Programming the Loop: worked example

**Add an API endpoint with a cross-repository dependency.** This is the worked example that accompanies the ebook *Programming the Loop: What Actually Works with Coding Agents* by Garry Meaburn (draft v3.2 and later).

It is a **hand-written, reproducible engineering demonstration** of the failure modes found in the author's agent experiments: guessed facts, stale knowledge and unverifiable claims. **It is not a recorded agent session, and no coding agent was run on it.** The code changes in `stages/` were written by hand to show what a reasonable agent change looks like with and without the provider's contract. The prompts in the book are illustrative. The "guessed" variant deliberately uses names an agent without the contract might plausibly pick (`/stock/{sku}`, `quantity`); it is not an agent transcript either.

## What's here

- `stages/`: the source of truth, as plain directories.
  - `baseline/` is the storefront repository before the change.
  - `with-contract/` holds the files of the change written from the pinned contract.
  - `guessed/` holds the same change written without the contract.
- `inventory-service/`: the provider, owned by "another team". In the story the agent cannot read it; it exists so the live check has something real to call. `INVENTORY_API_VERSION=3.0.0` simulates the provider's breaking release, and `contracts/` holds its published v2.1.0 and v3.0.0 OpenAPI contracts.
- `storefront-api/`: the consumer repository in its final state, a snapshot of the last run. `reproduce.sh` deletes it and rebuilds it, including its own git history, from `stages/`. It contains:
  - a short `AGENTS.md`;
  - a task brief in `docs/brief.md`;
  - the pinned provider contract in `contracts/`;
  - one check command, `scripts/test.sh`;
  - the freshness gate, `scripts/check_contract.py`.
- `reproduce.sh`: builds a fresh git repository for `storefront-api/`. In it, the script:
  - commits the baseline;
  - creates the `feature/availability` and `scenario/guessed` branches;
  - runs every stage and writes `logs/00`–`07`;
  - checks each result against what the book reports (19 checks, written to `logs/08-checks.txt`) and exits 1 on any mismatch.
  
  The diff summary in `logs/04-diffstat.txt` comes from that freshly built history, so nothing depends on the history of this repository.
- `run_live.sh [version]`: starts both services with uvicorn, waits until they answer, and calls the new endpoint with curl. It exits 0 only if every response has the status the 2.1.0 contract and the brief promise (MUG-001 200, TEE-042 200, NOPE-000 404), 1 if any differs, and 2 if the services can't be started (for example, port 8000 or 8001 is already in use).
- `logs/`: genuine output of `reproduce.sh` from the run the book quotes.
- `requirements.txt`: the exact package versions used (Python 3.13.5).

## Run it

You need git, curl, [uv](https://docs.astral.sh/uv/), Python 3.13 (uv can fetch it), and free ports 8000 and 8001.

```sh
git clone https://github.com/meabs/ProgrammingTheLoop-WorkedExample
cd ProgrammingTheLoop-WorkedExample
git clone --branch v0.3.0 https://github.com/meabs/AgentFrictionLoop
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python -r requirements.txt
FBL_SRC="$PWD/AgentFrictionLoop" ./reproduce.sh
```

It should end with `all checks passed`. Timings and commit hashes in `logs/` differ from run to run, and the checks ignore them.

**Dependency: AgentFrictionLoop v0.3.0.** Stage 7 installs [AgentFrictionLoop](https://github.com/meabs/AgentFrictionLoop) into the rebuilt `storefront-api/` and files a friction note with it. `FBL_SRC` points at a checkout of tag `v0.3.0` and defaults to `./AgentFrictionLoop`. Without it, stage 7 is skipped and `reproduce.sh` reports the missing friction record as a mismatch. The installed copy (`.fbl-home/`, `storefront-api/.fbl/`) and the checkout itself are generated locally and gitignored.

## Limit of the freshness gate

`scripts/check_contract.py` compares declared versions: the pinned version against the published `info.version`. Version agreement cannot establish behavioural compatibility, and the gate cannot detect a provider that changed its behaviour without bumping its version. Contract tests against the real provider and the live check are what exercise behaviour. If the gate can't check (nothing pinned, contract unreachable, no `info.version`), it prints `UNVERIFIED` and exits 1, unless `ALLOW_UNVERIFIED` is set.

## Licence

MIT; see `LICENSE`.
