"""Live check again, with every inventory URL env var the agent's code reads pointed at the real inventory service.
Separates 'wrong contract' from 'different config variable name' (run_live.sh only sets INVENTORY_URL)."""
import json, pathlib, re, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
for name in sys.argv[1:]:
    d = HERE / "runs" / name
    g = json.loads((d / "grading.json").read_text())
    extra = {k: "http://127.0.0.1:8001" for k in g.get("env_vars_read") or [] if re.search(r"URL|BASE|HOST|ENDPOINT|ADDR", k) and not re.search(r"TIMEOUT|PORT", k)}
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(d / "grade"), **extra}
    p = subprocess.run(["bash", "run_live.sh", "2.1.0"], cwd=d / "grade", env=env, capture_output=True, text=True, timeout=120)
    (d / "grade-live-adjusted.txt").write_text(f"$ {' '.join(f'{k}={v}' for k, v in extra.items())} ./run_live.sh 2.1.0  (exit {p.returncode})\n{p.stdout}{p.stderr}")
    print(name, extra, "exit", p.returncode)
