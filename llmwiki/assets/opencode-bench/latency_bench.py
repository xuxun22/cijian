import subprocess, sys, time, os
sys.path.insert(0, os.path.expanduser("~/work/cijian-agent"))
from pathlib import Path
from cijian_agent.ai import runner
from cijian_agent.config import load_config

cfg = load_config()
work = runner.prepare_home(Path(cfg.ai_workdir), "assistant-chat", Path("~/work/cijian-agent/cijian_agent/ai/prompts").expanduser())
runner.install_mcp(work, cfg.api_url, "bench-fake-token")

model = sys.argv[1]
msg = sys.argv[2] if len(sys.argv) > 2 else "只输出 ok"
env = {k: v for k, v in os.environ.items() if k in runner.SAFE_ENV_KEYS}
env.update(runner.WEBSEARCH_ENV)
env["CIJIAN_API_BASE"] = cfg.api_url
env["CIJIAN_CAP_TOKEN"] = "bench-fake-token"
runner.isolate_config(env, work)

t0 = time.monotonic()
p = subprocess.run(
    ["opencode", "run", "--standalone", "--agent", "assistant-chat", "--model", model,
     "--format", "json", "--auto", msg],
    cwd=str(work), env=env, capture_output=True, text=True, timeout=180)
wall = time.monotonic() - t0
events = []
for line in p.stdout.splitlines():
    try:
        e = __import__("json").loads(line)
        if e.get("type") in ("step_start", "step_finish", "tool_execute", "error"):
            events.append((e["type"], e.get("timestamp")))
    except Exception:
        pass
print(f"model={model} wall={wall:.2f}s exit={p.returncode}")
if events:
    t0e = events[0][1]
    for t, ts in events:
        print(f"  {t}: +{(ts - t0e)/1000:.2f}s (emit)")
    print(f"  spawn->first-event: {(events[0][1]/1000) - (time.time()-wall):.2f}s")
if p.returncode != 0:
    print("STDERR:", p.stderr[-300:])
