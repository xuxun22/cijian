#!/usr/bin/env python3
"""给打卡后台补「口算」「跳绳」两个项目（一次性，可重复执行）。

用法：
  CHECKIN_TOKEN=<登录后的 JWT> python3 scripts/seed-checkin-projects.py
  CHECKIN_API_BASE=https://api.whereami.cn CHECKIN_TOKEN=... python3 scripts/seed-checkin-projects.py

- 按 name 幂等：已存在的项目跳过，不会覆盖后台改过的配置。
- 新建项目的 sort = 现有最大 sort + 1/+2，排在已有项目之后。
- 口算/跳绳都是 media_type=any、全周应打；字段和分类提示见下方 PROJECTS。
"""

import json
import os
import urllib.error
import urllib.request

API_BASE = os.environ.get("CHECKIN_API_BASE", "https://api.whereami.cn").rstrip("/")
TOKEN = os.environ.get("CHECKIN_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("错误：需要 CHECKIN_TOKEN（网页登录后拿到的 JWT）")

PROJECTS = [
    {
        "name": "口算",
        "media_type": "any",
        "days_of_week": [1, 2, 3, 4, 5, 6, 7],
        "classifier_hint": "人声/说话/口算/报答案",
        "fields_schema": [
            {"key": "problem_count", "label": "题数", "type": "number", "required": False},
            {"key": "wrong_count", "label": "错题", "type": "number", "required": False},
        ],
    },
    {
        "name": "跳绳",
        "media_type": "any",
        "days_of_week": [1, 2, 3, 4, 5, 6, 7],
        "classifier_hint": "无人声/跳绳/绳打地",
        "fields_schema": [
            {"key": "count", "label": "个数", "type": "number", "required": False},
            {"key": "sets", "label": "组数", "type": "number", "required": False},
        ],
    },
]


def request(method, path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"请求失败 {method} {path} → {e.code}\n{detail}")


def main():
    projects = request("GET", "/api/checkin/projects")["projects"]
    existing = {p["name"] for p in projects}
    next_sort = max([int(p.get("sort") or 0) for p in projects], default=0) + 1

    for spec in PROJECTS:
        if spec["name"] in existing:
            print(f"跳过（已存在）：{spec['name']}")
            continue
        body = dict(spec, sort=next_sort)
        created = request("POST", "/api/checkin/projects", body)["project"]
        print(f"已创建：{created['name']}  id={created['id']}  sort={created['sort']}")
        next_sort += 1

    print("完成。打开打卡页确认「口算」「跳绳」两张卡（全周应打）。")


if __name__ == "__main__":
    main()
