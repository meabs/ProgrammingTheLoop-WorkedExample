"""Collect runs/*/grading.json into results.csv and a per-run table (results-table.md)."""
import csv, json, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
# Hand check of every trial run's command log against its VERIFICATION "ran" list (17 Oct 2026): nothing claimed that was not run.
HAND_CHECK = {f"{a}-{n}": 0 for a in "AB" for n in range(1, 7)}
rows = []
for d in sorted((HERE / "runs").iterdir(), key=lambda p: (p.name.split("-")[0], int(p.name.rsplit("-", 1)[1]) if p.name.rsplit("-", 1)[-1].isdigit() else 0)):
    gf = d / "grading.json"
    if not d.is_dir() or not gf.exists():
        continue
    g = json.loads(gf.read_text())
    c = g.get("claim") or {}
    t = g.get("tokens") or {}
    live_adj = None
    la = d / "grade-live-adjusted.txt"
    if la.exists():
        live_adj = la.read_text().splitlines()[0].endswith("(exit 0)")
    rows.append({
        "run": d.name, "kind": "pilot" if d.name.startswith("pilot") else ("control" if d.name.startswith("ctrl") else "trial"),
        "arm": d.name.split("-")[0] if not d.name.startswith("pilot") else "A",
        "agent_tests_own_rerun": g.get("own_pytest_summary"), "agent_test_sh_rerun_exit": g.get("own_test_sh_exit"),
        "hidden_passed_of_9": g.get("hidden_passed"), "live_pass": g.get("live_pass"),
        "live_pass_config_adjusted": live_adj,
        "blackbox_passed_of_7": g.get("blackbox_passed"), "independent_pass": g.get("independent_pass"),
        "claimed_result": c.get("result"), "claim_vs_independent": g.get("claim_vs_independent"),
        "agent_last_test_exit_in_sandbox": g.get("agent_last_test_exit"), "agent_ran_curl_or_server": g.get("agent_ran_curl_or_server"),
        "claimed_ran_not_in_log": len(g.get("claimed_ran_not_in_log") or []),  # automatic string match; over-flags descriptive claims
        "claimed_ran_not_in_log_hand_check": HAND_CHECK.get(d.name, ""),
        "env_vars_read": " ".join(g.get("env_vars_read") or []),
        "files_changed": " ".join(g.get("files_changed") or []), "diffstat": (g.get("diffstat") or [""])[0].strip(),
        "tokens_total": t.get("total"), "tokens_input": t.get("input"), "tokens_output": t.get("output"), "tokens_cache_read": t.get("cache_read"),
        "shell_commands": g.get("shell_commands"), "seconds": g.get("seconds"), "killed": g.get("killed") or g.get("timed_out"),
        "answer_source": g.get("answer_source"), "leak_hits": len(g.get("leak_hits") or []), "web_tool_calls": len(g.get("web_tool_calls") or []),
    })
with open(HERE / "results.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
cols = ["run", "agent_tests_own_rerun", "agent_test_sh_rerun_exit", "hidden_passed_of_9", "live_pass", "live_pass_config_adjusted", "blackbox_passed_of_7",
        "claimed_result", "claim_vs_independent", "claimed_ran_not_in_log", "tokens_total", "seconds", "files_changed"]
lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
for r in rows:
    lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
(HERE / "results-table.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
