import base64, json, os, re, subprocess, sys, threading, time, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, os.path.expanduser("~/work/cijian-agent"))
from cijian_agent.ai import runner
from cijian_agent.config import load_config
PORT=4412; BASE=f"http://127.0.0.1:{PORT}"
home=Path("/tmp/ocbench/home"); cfg=load_config()
env={k:v for k,v in os.environ.items() if k in runner.SAFE_ENV_KEYS}
env.update(runner.WEBSEARCH_ENV); env["CIJIAN_API_BASE"]=cfg.api_url; env["CIJIAN_CAP_TOKEN"]="bench-fake-token"
runner.isolate_config(env,home)
logp="/tmp/ocbench/serve8.log"; log=open(logp,"w")
srv=subprocess.Popen(["opencode","serve","--port",str(PORT),"--hostname","127.0.0.1"],cwd=str(home),env=env,stdout=log,stderr=subprocess.STDOUT)
pw=None
for _ in range(400):
    time.sleep(0.05)
    m=re.search(r"server password (\S+)", open(logp).read())
    if m: pw=m.group(1); break
auth="Basic "+base64.b64encode(f"opencode:{pw}".encode()).decode()
def req(method,path,body=None,timeout=180):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(BASE+path,data=data,method=method)
    r.add_header("authorization",auth)
    if data: r.add_header("content-type","application/json")
    try:
        with urllib.request.urlopen(r,timeout=timeout) as resp:
            raw=resp.read(); return resp.status,(json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
for _ in range(200):
    try: req("GET","/api/info"); break
    except Exception: time.sleep(0.05)

events=[]; stop=threading.Event(); done=threading.Event()
def listen():
    r=urllib.request.Request(BASE+"/api/event")
    r.add_header("authorization",auth)
    try:
        with urllib.request.urlopen(r,timeout=900) as resp:
            for line in resp:
                if stop.is_set(): return
                s=line.decode("utf-8","replace").strip()
                if not s.startswith("data:"): continue
                try: ev=json.loads(s[5:].strip())
                except Exception: continue
                events.append((time.monotonic(), ev.get("type"), (ev.get("data") or {}).get("sessionID")))
                if ev.get("type") in ("session.execution.succeeded","session.execution.failed","session.execution.interrupted"):
                    done.set()
    except Exception as e:
        if not stop.is_set(): print("sse err",e)
threading.Thread(target=listen,daemon=True).start(); time.sleep(0.4)

def new_session():
    return req("POST","/api/session",{"location":{"directory":str(home)},"agent":"assistant-chat","model":{"providerID":"deepseek","id":"deepseek-flash"},"permissions":[{"action":"*","resource":"*","effect":"allow"}]})[1]["data"]["id"]

def run_prompt(sid,text,files=None,label=""):
    events.clear(); done.clear()
    body={"text":text,"delivery":"queue"}
    if files: body["files"]=files
    t=time.monotonic()
    code, resp = req("POST",f"/api/session/{sid}/prompt",body)
    if code!=200: print(label,"PROMPT ERR",code,str(resp)[:300]); return
    admit=time.monotonic()-t
    done.wait(180)
    marks=[]
    for ts,typ,s in events:
        if s and s!=sid: continue
        if typ in ("session.execution.started","session.step.started","session.step.first-token","session.step.ended","session.execution.succeeded","session.tool.called","session.retry.scheduled"):
            marks.append((typ.replace("session.",""), (ts-t)*1000))
    print(f"\n[{label}] admit={admit*1000:.0f}ms total={(time.monotonic()-t)*1000:.0f}ms")
    for typ,ms in marks: print(f"   +{ms:7.0f}ms {typ}")

# warm up location first
sid=new_session(); run_prompt(sid,"只输出 ok",label="warmup")
for i in range(2):
    sid=new_session(); run_prompt(sid,"只输出 ok",label=f"ok new-session #{i+1}")
sid=new_session()
run_prompt(sid,"只输出 ok",label="ok same-session turn1")
run_prompt(sid,"只输出 ok",label="ok same-session turn2")
sid=new_session(); run_prompt(sid,"今天北京天气怎么样?一句话",label="tool prompt")
sid=new_session(); run_prompt(sid,"图里是什么颜色?一句话",files=[{"uri":"file:///tmp/red8.png"}],label="image file:// uri")
sid=new_session(); run_prompt(sid,"图里是什么颜色?一句话",files=[{"uri":"/tmp/red8.png","source":{"type":"inline"}}],label="image inline")
stop.set(); srv.terminate()
