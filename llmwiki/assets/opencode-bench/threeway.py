import base64, json, os, re, subprocess, sys, threading, time, urllib.request
from pathlib import Path
sys.path.insert(0, os.path.expanduser("~/work/cijian-agent"))
from cijian_agent.ai import runner
from cijian_agent.config import load_config
PORT=4417; BASE=f"http://127.0.0.1:{PORT}"
home=Path("/tmp/ocbench/home"); cfg=load_config()
runner.install_mcp(home,cfg.api_url,"bench-fake-token")
env={k:v for k,v in os.environ.items() if k in runner.SAFE_ENV_KEYS}
env.update(runner.WEBSEARCH_ENV); env["CIJIAN_API_BASE"]=cfg.api_url; env["CIJIAN_CAP_TOKEN"]="bench-fake-token"
runner.isolate_config(env,home)
logp="/tmp/ocbench/serve13.log"; log=open(logp,"w")
srv=subprocess.Popen(["opencode","serve","--port",str(PORT),"--hostname","127.0.0.1"],cwd=str(home),env=env,stdout=log,stderr=subprocess.STDOUT)
pw=None
for _ in range(400):
    time.sleep(0.05)
    m=re.search(r"server password (\S+)", open(logp).read())
    if m: pw=m.group(1); break
auth="Basic "+base64.b64encode(f"opencode:{pw}".encode()).decode()
def req(method,path,body=None,timeout=180):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(BASE+path,data=data,method=method); r.add_header("authorization",auth)
    if data: r.add_header("content-type","application/json")
    with urllib.request.urlopen(r,timeout=timeout) as resp:
        raw=resp.read(); return json.loads(raw) if raw else None
for _ in range(200):
    try: req("GET","/api/info"); break
    except Exception: time.sleep(0.05)
done=threading.Event(); cur={}
def listen():
    r=urllib.request.Request(BASE+"/api/event"); r.add_header("authorization",auth)
    with urllib.request.urlopen(r,timeout=1800) as resp:
        for line in resp:
            s=line.decode("utf-8","replace").strip()
            if not s.startswith("data:"): continue
            try: ev=json.loads(s[5:].strip())
            except Exception: continue
            if ev.get("type") in ("session.execution.succeeded","session.execution.failed","session.execution.interrupted"):
                if (ev.get("data") or {}).get("sessionID")==cur.get("sid"): done.set()
threading.Thread(target=listen,daemon=True).start(); time.sleep(0.4)
def api_run(text="只输出 ok", files=None):
    sid=req("POST","/api/session",{"location":{"directory":str(home)},"agent":"assistant-chat","model":{"providerID":"deepseek","id":"deepseek-flash"},"permissions":[{"action":"*","resource":"*","effect":"allow"}]})["data"]["id"]
    cur["sid"]=sid; done.clear()
    body={"text":text,"delivery":"queue"}
    if files: body["files"]=files
    t=time.monotonic(); req("POST",f"/api/session/{sid}/prompt",body); done.wait(180); w=time.monotonic()-t
    req("DELETE",f"/api/session/{sid}")
    return w*1000
def cli_run(server, text="只输出 ok", img=None):
    cmd=["opencode","run","--agent","assistant-chat","--model","deepseek/deepseek-flash","--format","json","--auto"]
    cmd += (["--server",server] if server else ["--standalone"])
    if img: cmd+=["--file",img]
    cmd.append(text)
    e=dict(env)
    if server: e["OPENCODE_PASSWORD"]=pw
    t=time.monotonic()
    subprocess.run(cmd,cwd=str(home),env=e,capture_output=True,text=True,timeout=180)
    return (time.monotonic()-t)*1000
def runner_run(text="只输出 ok", img=None):
    t=time.monotonic()
    runner.run(home,"assistant-chat",text,model="deepseek/deepseek-flash",opencode_bin="opencode",
        capability=(cfg.api_url,"bench-fake-token"),images=[Path(img)] if img else None,timeout=120)
    return (time.monotonic()-t)*1000
api_run(); runner_run(); cli_run(BASE)  # warmup
res={"api":[], "cli_server":[], "runner":[]}
for i in range(4):
    res["runner"].append(runner_run())
    res["api"].append(api_run())
    res["cli_server"].append(cli_run(BASE))
for k,v in res.items(): print(f"{k:12s}", [f"{x:.0f}" for x in v], f"avg={sum(v)/len(v):.0f}ms")
print("--- image ---")
res={"api":[], "cli_server":[], "runner":[]}
for i in range(3):
    res["runner"].append(runner_run("图里是什么颜色?一句话","/tmp/red8.png"))
    res["api"].append(api_run("图里是什么颜色?一句话",[{"uri":"file:///tmp/red8.png"}]))
    res["cli_server"].append(cli_run(BASE,"图里是什么颜色?一句话","/tmp/red8.png"))
for k,v in res.items(): print(f"{k:12s}", [f"{x:.0f}" for x in v], f"avg={sum(v)/len(v):.0f}ms")
rss=subprocess.run(["ps","-o","rss=","-p",str(srv.pid)],capture_output=True,text=True).stdout.strip()
print(f"server RSS {int(rss)/1024:.0f} MB")
srv.terminate()
