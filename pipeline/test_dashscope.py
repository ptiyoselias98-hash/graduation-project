# -*- coding: utf-8 -*-
"""Verify DashScope (Aliyun Bailian) OpenAI-compatible endpoint: chat + embedding.
Reads key from env DASHSCOPE_API_KEY. Never prints the full key."""
import os, json, urllib.request, urllib.error
KEY = os.environ.get("DASHSCOPE_API_KEY", "")
BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
mask = (KEY[:6] + "****" + KEY[-2:]) if len(KEY) > 10 else "(missing)"
print("key:", mask, "| len", len(KEY))

def post(path, payload, timeout=40):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "replace") or "{}")
    except Exception as e:
        return -1, {"error": repr(e)}

print("\n=== CHAT qwen-plus ===")
st, resp = post("/chat/completions", {"model": "qwen-plus",
    "messages": [{"role": "user", "content": "用一句话回答：2022 ESC/ERS 指南中肺动脉高压(PH)的 mPAP 诊断阈值是多少？"}],
    "temperature": 0.2})
print("status:", st)
if st == 200:
    print("reply:", resp["choices"][0]["message"]["content"][:200])
    print("usage:", resp.get("usage"))
else:
    print("ERR:", json.dumps(resp, ensure_ascii=False)[:400])

print("\n=== EMBED text-embedding-v4 ===")
st, resp = post("/embeddings", {"model": "text-embedding-v4",
    "input": "mPAP > 20 mmHg at rest defines pulmonary hypertension; PVR > 2 WU indicates pre-capillary PH."})
print("status:", st)
if st == 200:
    emb = resp["data"][0]["embedding"]
    print("embedding dim:", len(emb), "| first3:", [round(x, 4) for x in emb[:3]])
    print("usage:", resp.get("usage"))
else:
    print("ERR:", json.dumps(resp, ensure_ascii=False)[:400])

print("\n=== CHAT qwen-max (optional top-tier) ===")
st, resp = post("/chat/completions", {"model": "qwen-max",
    "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5})
print("qwen-max status:", st, "" if st == 200 else json.dumps(resp, ensure_ascii=False)[:200])
