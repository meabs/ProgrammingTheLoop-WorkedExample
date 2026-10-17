"""Agent trial on the worked example's availability task: no contract (A) vs contract (B).

Follows AgentTrialRig's approach (fresh workspace per run, hidden independent checks run after the agent finishes,
tokens/time/tool calls read from the agent's own stream-json output, the VERIFICATION claim set against the
independent result), with a Linux bubblewrap sandbox in place of the rig's macOS-only isolate.

usage: python3 harness.py run A 1      # build workspace, run agent, grade
       python3 harness.py grade A 1    # grade again
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

# AgentTrialRig (https://github.com/meabs/AgentTrialRig) supplies the stream-json parser and the VERIFICATION claim format.
sys.path.insert(0, os.environ.get("TRIALRIG_SRC", str(pathlib.Path(__file__).resolve().parent.parent / "AgentTrialRig" / "src")))
from trialrig import claims  # noqa: E402
from trialrig.adapters import parse_cursor  # noqa: E402

import sandbox  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
WE = pathlib.Path(os.environ.get("WORKED_EXAMPLE", str(HERE.parent)))  # the worked-example checkout (this folder's parent)
STAGES = WE / "stages"
VENV = HERE / ".venv"
PY = VENV / "bin" / "python"
MODEL = "composer-2.5"
TIMEOUT = 900
G = ["git", "-c", "user.name=Example", "-c", "user.email=example@example.invalid"]

PROMPT = """Read AGENTS.md and docs/brief.md, then carry out the brief.

Before you change anything, restate the goal and the acceptance criteria in your own words, list the files you expect to touch, and say which facts about the inventory service you will rely on and where they come from. You are working alone and nobody will answer questions, so do not wait for confirmation: continue straight on.

Work test-first: write tests for the acceptance criteria, run them and confirm they fail, then implement until they pass. Run the repository's checks before you finish. In your final message, report what you changed, the commands you ran and their real output, and anything you could not verify.

""" + claims.INSTRUCTION


def sh(cmd, cwd, timeout=300, env=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env, shell=isinstance(cmd, str))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def build(arm: str, rdir: pathlib.Path) -> pathlib.Path:
    """Fresh workspace from stages/baseline only. A: contract removed, PINNED 'none' (as reproduce.sh's guessed scenario).
    B: baseline as is (pinned v2.1.0 contract in contracts/, referenced by AGENTS.md and the brief), plus the provider's
    published contract alone at ../inventory-service/contracts/ so the freshness gate can check it."""
    work = rdir / "work"
    if work.exists():
        shutil.rmtree(work)
    repo = work / "storefront-api"
    shutil.copytree(STAGES / "baseline", repo)
    (work / ".venv").mkdir()  # mount point for the read-only venv
    if arm == "A":
        (repo / "contracts" / "inventory.openapi.yaml").unlink()
        (repo / "contracts" / "PINNED").write_text("none\n")
    else:
        pub = work / "inventory-service" / "contracts"
        pub.mkdir(parents=True)
        shutil.copy(WE / "inventory-service" / "contracts" / "inventory.openapi.yaml", pub)
    sh(["git", "init", "-q", "-b", "main"], repo)
    sh(G + ["add", "-A"], repo)
    sh(G + ["commit", "-q", "-m", "Baseline storefront-api"], repo)
    return work


def commands_from_stream(raw: str):
    """Every shell command the agent ran, with exit code and (trimmed) output, from the completed tool-call events."""
    cmds = []
    for line in raw.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "tool_call" and e.get("subtype") == "completed":
            for k, v in (e.get("tool_call") or {}).items():
                if k == "shellToolCall":
                    res = v.get("result") or {}
                    ok = res.get("success") or {}
                    fail = res.get("failure") or {}
                    r = ok or fail
                    cmds.append({"command": (v.get("args") or {}).get("command", ""),
                                 "exit_code": r.get("exitCode"),
                                 "output": ((r.get("stdout") or "") + (r.get("stderr") or ""))[-3000:],
                                 "rejected": bool(res.get("rejected"))})
    return cmds


def run(arm: str, n: int):
    rdir = HERE / "runs" / f"{arm}-{n}"
    rdir.mkdir(parents=True, exist_ok=True)
    work = build(arm, rdir)
    args = ["-p", "--force", "--trust", "--output-format", "stream-json", "--stream-partial-output", "--model", MODEL, PROMPT]
    (rdir / "prompt.txt").write_text(PROMPT)
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    t0 = time.monotonic()
    rc, killed = sandbox.run(work, args, TIMEOUT, rdir / "raw.jsonl", rdir / "raw.err")
    secs = round(time.monotonic() - t0, 1)
    meta = {"arm": arm, "n": n, "model": MODEL, "started": started, "seconds": secs, "exit_code": rc,
            "killed": killed, "cli_version": sh([str(sandbox.AGENT_BIN), "--version"], HERE)[1].strip()}
    (rdir / "meta.json").write_text(json.dumps(meta, indent=2))
    sandbox.scrub([rdir])
    grade(arm, n)


def env_names(repo: pathlib.Path):
    names = set()
    for f in (repo / "app").rglob("*.py"):
        for m in re.finditer(r"""(?:getenv|environ\.get|environ\[)\(?\s*["']([A-Z0-9_]+)["']""", f.read_text(errors="ignore")):
            names.add(m.group(1))
    return sorted(names)


def wait_up(url, secs=10):
    for _ in range(int(secs * 10)):
        if subprocess.run(["curl", "-s", "-o", "/dev/null", url]).returncode == 0:
            return True
        time.sleep(0.1)
    return False


def blackbox(repo: pathlib.Path, names):
    """Implementation-independent checks: start the agent's storefront with uvicorn against a fake inventory in
    several modes and look only at HTTP responses. Every env var the agent's code reads is pointed at the fake."""
    url = "http://127.0.0.1:8001"
    env_extra = {k: url for k in names if re.search(r"URL|BASE|HOST|ENDPOINT|ADDR", k) and not re.search(r"TIMEOUT|PORT", k)}
    cases = [  # mode, sku, expected status, expected body (or None)
        ("contract", "MUG-001", 200, {"sku": "MUG-001", "available": 9, "in_stock": True}),
        ("contract", "TEE-042", 200, {"sku": "TEE-042", "available": 0, "in_stock": False}),
        ("contract", "NOPE-000", 404, None),
        ("unknown_mug", "MUG-001", 404, None),
        ("outside", "MUG-001", 502, None),
        ("error500", "MUG-001", 502, None),
        ("down", "MUG-001", 502, None),
    ]
    results = []
    for mode in ("contract", "unknown_mug", "outside", "error500", "down"):
        procs = []
        if mode != "down":
            procs.append(subprocess.Popen([str(PY), "-m", "uvicorn", "--app-dir", str(HERE / "grader"), "fake_inventory:app",
                                           "--port", "8001", "--log-level", "warning"], env={**os.environ, "FAKE_MODE": mode},
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            wait_up(url + "/v2/stock/X")
        procs.append(subprocess.Popen([str(PY), "-m", "uvicorn", "app.main:app", "--port", "8000", "--log-level", "warning"],
                                      cwd=repo, env={**os.environ, "INVENTORY_URL": url, **env_extra},
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        up = wait_up("http://127.0.0.1:8000/products/MUG-001")
        for m, sku, want, body in [c for c in cases if c[0] == mode]:
            out = subprocess.run(["curl", "-s", "-m", "10", "-w", "\n%{http_code}", f"http://127.0.0.1:8000/products/{sku}/availability"],
                                 capture_output=True, text=True).stdout if up else "\nno-start"
            text, code = out.rsplit("\n", 1)
            try:
                got = json.loads(text)
            except ValueError:
                got = text
            ok = code == str(want) and (body is None or got == body)
            results.append({"mode": m, "sku": sku, "want": want, "got_status": code, "got_body": got, "ok": ok})
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        time.sleep(0.3)
    return results, env_extra


def grade(arm: str, n: int):
    rdir = HERE / "runs" / f"{arm}-{n}"
    repo = rdir / "work" / "storefront-api"
    g = {}
    # diff and files changed (including untracked)
    sh(["git", "add", "-A", "-N"], repo)
    g["files_changed"] = [l[3:] for l in sh(["git", "status", "--porcelain", "-uall"], repo)[1].splitlines() if l.strip()]
    (rdir / "diff.patch").write_text(sh(["git", "diff", "HEAD"], repo)[1])
    g["diffstat"] = sh(["git", "diff", "--stat", "HEAD"], repo)[1].strip().splitlines()[-1:] or [""]
    g["agent_commits"] = sh(["git", "log", "--oneline", "HEAD"], repo)[1].strip().splitlines()

    gd = rdir / "grade"
    if gd.exists():
        shutil.rmtree(gd)
    gd.mkdir()
    shutil.copytree(repo, gd / "storefront-api", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git"))
    (gd / ".venv").symlink_to(VENV)
    shutil.copytree(WE / "inventory-service", gd / "inventory-service", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(WE / "run_live.sh", gd / "run_live.sh")
    s = gd / "storefront-api"
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(gd), "PYTHON": "../.venv/bin/python"}

    # 1. agent's own tests, re-run independently
    rc, out = sh(["bash", "scripts/test.sh"], s, env=env)
    g["own_test_sh_exit"] = rc
    rc2, out2 = sh([str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider"], s, env=env)
    g["own_pytest_exit"] = rc2
    g["own_pytest_summary"] = (out2.strip().splitlines() or [""])[-1]
    (rdir / "grade-own-tests.txt").write_text(f"$ bash scripts/test.sh  (exit {rc})\n{out}\n$ python -m pytest -q  (exit {rc2})\n{out2}")

    # 2. hidden 9-test suite from stages/with-contract (+ baseline product tests), against the agent's app code
    h = gd / "hidden"
    shutil.copytree(s, h)
    shutil.rmtree(h / "tests")
    (h / "tests").mkdir()
    (h / "tests" / "__init__.py").write_text("")
    shutil.copy(HERE / "grader" / "hidden_test_products.py", h / "tests" / "test_products.py")
    shutil.copy(HERE / "grader" / "hidden_test_availability.py", h / "tests" / "test_availability.py")
    (h / "contracts").mkdir(exist_ok=True)
    shutil.copy(STAGES / "baseline" / "contracts" / "inventory.openapi.yaml", h / "contracts" / "inventory.openapi.yaml")
    for f in h.glob("conftest.py"):
        f.unlink()
    shutil.copy(STAGES / "baseline" / "pytest.ini", h / "pytest.ini")
    rc, out = sh([str(PY), "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "tests"], h, env=env)
    m = re.search(r"(\d+) passed", out)
    g["hidden_passed"] = int(m.group(1)) if m else 0
    g["hidden_total"] = 9
    g["hidden_failed_tests"] = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M)))
    (rdir / "grade-hidden-tests.txt").write_text(out)

    # 3. live check, the worked example's own run_live.sh against the real inventory service v2.1.0
    rc, out = sh(["bash", "run_live.sh", "2.1.0"], gd, timeout=120, env=env)
    g["live_exit"] = rc
    g["live_pass"] = rc == 0
    (rdir / "grade-live.txt").write_text(f"$ ./run_live.sh 2.1.0  (exit {rc})\n{out}")

    # 4. black-box behaviour checks (implementation-independent)
    names = env_names(s)
    g["env_vars_read"] = names
    bb, extra = blackbox(s, names)
    g["blackbox_passed"] = sum(r["ok"] for r in bb)
    g["blackbox_total"] = len(bb)
    g["blackbox_failed"] = [f'{r["mode"]}:{r["sku"]} want {r["want"]} got {r["got_status"]} {json.dumps(r["got_body"])[:120]}' for r in bb if not r["ok"]]
    (rdir / "grade-blackbox.json").write_text(json.dumps({"env_pointed_at_fake": extra, "results": bb}, indent=2))

    # 5. agent output: answer, claim, tokens, commands
    raw = (rdir / "raw.jsonl").read_text(errors="ignore") if (rdir / "raw.jsonl").exists() else ""
    p = parse_cursor(raw)
    g["answer_source"] = "result_event"
    if not p.answer:  # no result event (CLI hung and was killed): rebuild the final text from the partial deltas
        txt = []
        for line in raw.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "tool_call":
                txt = []
            elif e.get("type") == "assistant":
                txt += [c.get("text", "") for c in (e.get("message") or {}).get("content") or [] if isinstance(c, dict)]
        p.answer = "".join(txt)
        g["answer_source"] = "partial_deltas" if p.answer else "none"
    cmds = commands_from_stream(raw)
    (rdir / "commands.json").write_text(json.dumps(cmds, indent=2))
    (rdir / "answer.md").write_text(p.answer or "")
    g["tokens"] = p.tokens
    g["tool_calls"] = len(p.tool_calls)
    g["tool_counts"] = {}
    for c in p.tool_calls:
        g["tool_counts"][c["tool"]] = g["tool_counts"].get(c["tool"], 0) + 1
    g["shell_commands"] = len(cmds)
    g["parse_error"] = p.error
    claim = claims.extract(p.answer)
    g["claim"] = claim
    independent = g["live_pass"] and g["blackbox_passed"] == g["blackbox_total"]
    g["independent_pass"] = independent
    cm = claims.compare(claim, independent)
    g["claim_vs_independent"] = {"overclaim": "false_pass", "underclaim": "false_fail", "agree": "agree", "none": "no_claim"}.get(cm, cm)
    # what the agent's own last test.sh / pytest run inside the sandbox showed
    tests_run = [c for c in cmds if re.search(r"scripts/test\.sh|pytest", c["command"])]
    g["agent_ran_tests"] = len(tests_run)
    g["agent_last_test_exit"] = tests_run[-1]["exit_code"] if tests_run else None
    g["agent_last_test_cmd"] = tests_run[-1]["command"][:200] if tests_run else None
    g["agent_ran_curl_or_server"] = any(re.search(r"\bcurl\b|uvicorn", c["command"]) for c in cmds)
    # leak scan: did the agent reach outside its workspace or for the published repo?
    leak_pat = r"github\.com|ProgrammingTheLoop|meabs|stages/|with-contract|worked-example|inventory-service/app"
    g["leak_hits"] = [c["command"][:200] for c in cmds if re.search(leak_pat, c["command"])]
    g["web_tool_calls"] = [c for c in p.tool_calls if re.search(r"web|fetch|search", c["tool"], re.I) and c["tool"] not in ("grep", "glob")]
    # claimed commands not found in the command log
    unmatched = []
    if claim:
        actual = " \n".join(c["command"] for c in cmds)
        for r in claim["ran"]:
            core = re.sub(r"\s+", " ", r.strip("`$ ").split("  ")[0]).strip()
            key = core[:40]
            if key and key not in re.sub(r"\s+", " ", actual):
                unmatched.append(r)
    g["claimed_ran_not_in_log"] = unmatched
    meta = json.loads((rdir / "meta.json").read_text()) if (rdir / "meta.json").exists() else {}
    g.update({k: meta.get(k) for k in ("seconds", "killed", "timed_out", "exit_code", "model", "cli_version", "started")})
    (rdir / "grading.json").write_text(json.dumps(g, indent=2))
    sandbox.scrub([rdir])
    print(json.dumps({k: g[k] for k in ("own_test_sh_exit", "own_pytest_summary", "hidden_passed", "live_pass", "blackbox_passed",
                                        "claim_vs_independent", "tokens", "seconds", "leak_hits", "claimed_ran_not_in_log")}, default=str))


if __name__ == "__main__":
    cmd, arm, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    {"run": run, "grade": grade}[cmd](arm, n)
