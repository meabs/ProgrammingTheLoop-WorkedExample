"""Launch cursor-agent inside a bubblewrap sandbox that sees only the run's work folder.

Hidden from the agent (empty tmpfs): /workspace, /tmp, /home, /cursor, /mnt, /srv, /media, /var/tmp.
Visible: the OS read-only, the run's work folder (rw) at SANDBOX_ROOT (/workspace/project inside the sandbox), an in-memory HOME, the cursor-agent install (ro),
and the shared Python venv (ro). Separate PID namespace, so the agent cannot read other processes' environments and
everything it starts dies with it. Network is shared (the agent needs the Cursor API).
The API key is read from .env.local into this process's memory and passed only through the child's environment.
"""
import os
import pathlib
import subprocess
import time
from datetime import datetime

HOME = pathlib.Path.home()
HERE = pathlib.Path(__file__).resolve().parent
ENV_FILE = pathlib.Path(os.environ.get("CURSOR_ENV_FILE", str(HERE / ".env.local")))  # used only if CURSOR_API_KEY is not set
VENV = HERE / ".venv"
SANDBOX_ROOT = "/workspace/project"  # mount point inside the sandbox (what the agent sees), not a host path
AGENT_SHARE = HOME / ".local/share/cursor-agent"
AGENT_BIN = HOME / ".local/bin/cursor-agent"
# cursor-agent -p (2026.10.16) prints its final message as partial deltas but never emits the closing result event while
# a shell job it backgrounded (e.g. a uvicorn server) is still alive. Measured on this box: after the final text, a
# SIGINT makes it emit the result event with token usage. So: once the stream is silent for NUDGE_AFTER seconds and no
# tool call is open, send SIGINT once.
NUDGE_AFTER = 60
IDLE = int(os.environ.get("TRIAL_IDLE", "300"))  # seconds without any new agent output before the run is treated as hung
# Turns off the CLI's server-side web search and web fetch tools (its eval-hardening switch); shell network is set to
# allow so the sandbox's own network rules apply. Without this the agent could search the web for the published example.
EXTRA_ENV = {"CURSOR_FORCED_SHELL_EGRESS": "1", "CURSOR_FORCED_SHELL_EGRESS_NETWORK_DEFAULT": "allow"}
HOSTS_BLOCK = HERE / "grader" / "sandbox-hosts.block"  # github.com etc. -> 0.0.0.0, appended to this machine's /etc/hosts
HOSTS = HERE / ".sandbox-hosts"
# pasta gives the sandbox its own network namespace with outbound internet but no host loopback; private ranges are
# blackholed (the machine these trials ran on exposed an unauthenticated Docker API on its docker0 address), except the DNS resolver.
# The resolver and default gateway are read from this machine at run time, and the resolver is let through.
NET_SETUP = ("for n in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10; do ip route add blackhole $n; done; "
             "dns=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf); gw=$(ip route | awk '/^default/{print $3; exit}'); "
             "[ -n \"$dns\" ] && [ -n \"$gw\" ] && ip route add \"$dns/32\" via \"$gw\" 2>/dev/null; "
             "f=\"$1\"; shift; exec bwrap --args 3 -- \"$@\" 3< \"$f\"")


def _write_hosts():
    HOSTS.write_text(pathlib.Path("/etc/hosts").read_text() + "\n" + HOSTS_BLOCK.read_text())


def api_key() -> str:
    if os.environ.get("CURSOR_API_KEY"):
        return os.environ["CURSOR_API_KEY"]
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("CURSOR_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("set CURSOR_API_KEY or CURSOR_ENV_FILE")


def bwrap_cmd(work: pathlib.Path, agent_args: list[str]) -> list[str]:
    _write_hosts()
    cmd = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
    for d in ("/tmp", "/workspace", "/home", "/cursor", "/mnt", "/srv", "/media", "/var/tmp"):
        if os.path.isdir(d):
            cmd += ["--tmpfs", d]
    cmd += ["--ro-bind", str(AGENT_SHARE), str(AGENT_SHARE),
            "--bind", str(work), SANDBOX_ROOT,
            "--ro-bind", str(VENV), SANDBOX_ROOT + "/.venv",
            "--ro-bind", str(HOSTS), "/etc/hosts",
            "--chdir", SANDBOX_ROOT + "/storefront-api", "--unshare-pid", "--unshare-user", "--uid", "1000", "--gid", "1000",
            "--die-with-parent"]
    return cmd


def _descendants(pid):
    kids = {}
    for d in pathlib.Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                ppid = int((d / "stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                continue
            kids.setdefault(ppid, []).append(int(d.name))
    out, todo = [], [pid]
    while todo:
        for c in kids.get(todo.pop(), []):
            out.append(c)
            todo.append(c)
    return out


def kill_agent_background_jobs(pid):
    """cursor-agent -p does not print its final message while a shell job it backgrounded (e.g. a uvicorn server)
    is still running. Kill the trees under the CLI's shell wrappers so it can finish; the CLI itself is left alone."""
    killed = []
    for c in _descendants(pid):
        try:
            cmd = pathlib.Path(f"/proc/{c}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore")
        except OSError:
            continue
        if cmd.startswith("/usr/bin/bash -O extglob -c"):
            for g in [c, *_descendants(c)]:
                try:
                    os.kill(g, 9)
                    killed.append(g)
                except OSError:
                    pass
    return killed


def _turn_finished(stdout_path):
    """True if every started tool call has completed and the last event is model output (text or thinking)."""
    import json
    open_calls, last = set(), None
    for line in pathlib.Path(stdout_path).read_text(errors="ignore").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        last = e.get("type")
        if last == "tool_call":
            (open_calls.add if e.get("subtype") == "started" else open_calls.discard)(e.get("call_id"))
    return not open_calls and last in ("assistant", "thinking")


def _sigint_cli(pid):
    hit = []
    for c in _descendants(pid):
        try:
            cmd = pathlib.Path(f"/proc/{c}/cmdline").read_bytes()
        except OSError:
            continue
        if b"cursor-agent" in cmd and b"index.js" in cmd:
            try:
                os.kill(c, 2)
                hit.append(c)
            except OSError:
                pass
    return hit


def run(work, agent_args, timeout, stdout_path, stderr_path):
    """HOME is an in-memory tmpfs inside the sandbox, so cursor-agent's own auth/config files vanish with it.
    bwrap's options go through --args from a file, so host paths do not show up in the agent's `ps`.
    Returns (exit code or None, None or the reason it was killed: total-timeout, idle-timeout, exited-after-result)."""
    env = {"PATH": f"{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin", "HOME": str(HOME), "LANG": "C.UTF-8",
           "TERM": "dumb", "CURSOR_API_KEY": api_key(), **EXTRA_ENV}
    with open(stdout_path, "w") as out, open(stderr_path, "w") as err:
        argfile = pathlib.Path(stdout_path).with_name("bwrap.args")
        argfile.write_bytes(b"\0".join(a.encode() for a in bwrap_cmd(pathlib.Path(work), agent_args)[1:]) + b"\0")
        p = subprocess.Popen(["pasta", "--config-net", "--no-map-gw", "-T", "none", "-U", "none", "-t", "none", "-u", "none", "-q",
                              "--", "sh", "-c", NET_SETUP, "sh", str(argfile), str(AGENT_BIN.resolve()), *agent_args],
                             env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL, start_new_session=True)
        t0 = time.monotonic()
        last_size, last_change, result_seen_at, nudged = -1, t0, None, []
        while True:
            try:
                return p.wait(timeout=5), None
            except subprocess.TimeoutExpired:
                pass
            now = time.monotonic()
            size = os.path.getsize(stdout_path)
            if size != last_size:
                last_size, last_change = size, now
            if result_seen_at is None and b'"type":"result"' in pathlib.Path(stdout_path).read_bytes()[-200000:]:
                result_seen_at = now
            if now - last_change > NUDGE_AFTER and not nudged and _turn_finished(stdout_path):
                nudged = _sigint_cli(p.pid)
                if nudged:
                    last_change = now
                    with open(pathlib.Path(stdout_path).with_name("harness-events.txt"), "a") as f:
                        f.write(f"{datetime.now().astimezone().isoformat(timespec='seconds')} no output for {NUDGE_AFTER}s with no "
                                f"tool call open: sent SIGINT to the CLI so it prints its result event\n")
            why = ("total-timeout" if now - t0 > timeout else
                   "idle-timeout" if now - last_change > IDLE else
                   "exited-after-result" if result_seen_at and now - result_seen_at > 20 else None)
            if why:
                os.killpg(p.pid, 9)
                p.wait()
                return None, why


def scrub(paths):
    """Replace any occurrence of the key in saved files (in case the agent printed its environment)."""
    try:
        key = api_key().encode()
    except (OSError, SystemExit):
        return 0  # no key configured (e.g. regrading only): nothing to scrub
    hits = 0
    for root in paths:
        for f in pathlib.Path(root).rglob("*"):
            if f.is_file() and not f.is_symlink():
                try:
                    b = f.read_bytes()
                except OSError:
                    continue
                if key in b:
                    f.write_bytes(b.replace(key, b"[REDACTED_CURSOR_API_KEY]"))
                    hits += 1
    return hits
