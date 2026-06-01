# -*- coding: utf-8 -*-
"""PulmoAgent GraphRAG diagnosis service (server-resident, DashScope).
Pure stdlib (urllib) -> runs on the lab server's system python3.8 with no installs.
Retrieval: text-embedding-v4 cosine over the ESC/ERS guideline chunks.
Debate: qwen-plus 3-specialist MDT (calibrated) -> vote -> synthesis -> final.

Usage:
  python3 pulmo_dx.py --list
  python3 pulmo_dx.py --case ph_xxx                 # one server cohort case
  python3 pulmo_dx.py --ids ph_a,nonph_b            # a few
  python3 pulmo_dx.py --all --out debates_server.json
  python3 pulmo_dx.py --serve --port 8077           # stdlib HTTP service: POST /diagnose
"""
import os, sys, json, math, time, datetime, urllib.request, urllib.error, re, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
SCR_PATH  = "/home/imss/cw/PulmoAgent/v2_260_run/sat_derived_scr_v2_260.json"
OOF_PATH  = "/home/imss/cw/PulmoAgent/v2_260_run/v4_oof_proba.json"
CHUNKS    = os.path.join(HERE, "chunks.jsonl")
KG_NODES  = os.path.join(HERE, "kg_v2.json")
EMB_CACHE = os.path.join(HERE, "chunk_emb.json")
BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
CHAT_MODEL, EMB_MODEL = "qwen-plus", "text-embedding-v4"

def _key():
    k = os.environ.get("DASHSCOPE_API_KEY", "")
    if not k and os.path.exists(os.path.join(HERE, ".env")):
        for ln in open(os.path.join(HERE, ".env"), encoding="utf-8"):
            if ln.startswith("DASHSCOPE_API_KEY"):
                k = ln.split("=", 1)[1].strip().strip('"')
    return k
KEY = _key()

def _post(path, payload, timeout=60, retries=3):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e; time.sleep(1.5 * (a + 1))
    raise RuntimeError("POST %s failed: %r" % (path, last))

def embed(texts):
    out = []
    for i in range(0, len(texts), 10):
        resp = _post("/embeddings", {"model": EMB_MODEL, "input": texts[i:i+10]})
        out += [d["embedding"] for d in sorted(resp["data"], key=lambda d: d["index"])]
    return out

def chat(messages, temperature=0.2, max_tokens=900):
    return _post("/chat/completions", {"model": CHAT_MODEL, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens})["choices"][0]["message"]["content"]

def chat_json(messages, temperature=0.2):
    txt = chat(messages, temperature)
    m = re.search(r"\{.*\}", txt, re.S)
    try: return json.loads(m.group(0) if m else txt)
    except Exception:
        fix = chat(messages + [{"role": "assistant", "content": txt},
            {"role": "user", "content": "只输出合法 JSON，无解释无围栏。"}], 0.0)
        m = re.search(r"\{.*\}", fix, re.S); return json.loads(m.group(0) if m else fix)

def cosine(a, b):
    s = sum(x*y for x, y in zip(a, b)); na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return s/(na*nb) if na and nb else 0.0

# ---- data ----
CH = [json.loads(l) for l in open(CHUNKS, encoding="utf-8") if l.strip()]
KGN = {n["id"] for n in json.load(open(KG_NODES, encoding="utf-8"))["nodes"]}
ENT2NODE = {"mpap":"MPAP","pvr":"PVR","pawp":"PAWP","pa/ao":"PA_AO","rv/lv":"RVLV_CT","trv":"TRV","dlco":"DLCO",
    "cteph":"CTEPH","group 3":"GROUP3","copd":"COPD","emphysema":"EMPHYSEMA","pruning":"PRUNING","bv5":"BV5",
    "ra area":"RAAREA","tapse":"TAPSE","septal":"LVEI","post-capillary":"POSTCAP","pre-capillary":"PRECAP",
    "bnp":"BNP","paco2":"PACO2","v/q":"VQ","wedge":"PAWP"}
def chunk_node(ch):
    t = " ".join(ch.get("entities", []) + [ch["text"]]).lower()
    for k, v in ENT2NODE.items():
        if k in t and v in KGN: return v
    return "PH"
PH_N = {"PH","PAH","COPD_PH","GROUP3","PRECAP","SEVERE3","VASCPHEN","MPAP","PVR","PA_AO","RVLV_CT","TRV","PRUNING","BV5","RAAREA","TAPSE","LVEI","DLCO","PACO2"}
COPD_N = {"COPD","EMPHYSEMA"}
def supports(nid, sc):
    w = round(0.3 + 0.4*sc, 2)
    return ("COPD +%s" % w) if nid in COPD_N else (("COPD-PH +%s" % w) if nid in PH_N else "context +0.0")

def chunk_emb():
    if os.path.exists(EMB_CACHE):
        c = json.load(open(EMB_CACHE, encoding="utf-8"))
        if len(c) == len(CH): return c
    e = embed([c["text"] for c in CH]); json.dump(e, open(EMB_CACHE, "w")); return e
CE = None

def g(rec, k): return rec.get(k)
def query_of(rec, pph):
    return ("Differentiating COPD from COPD-associated pulmonary hypertension (Group 3 PH). "
        "PA/AO %s; main PA %s mm; RV/LV %s; RA %s mm; emphysema LAA-950 %s%%; arterial BV5 %s mL (vascular pruning); "
        "PA wall calcification %s. mPAP>20 defines PH; PVR>5 WU severe Group3 PH; vascular phenotype low DLCO." % (
        g(rec,"pa_ao"), g(rec,"mpa_mm"), g(rec,"rv_lv"), g(rec,"ra_mm"), g(rec,"laa_950_pct"), g(rec,"artery_bv5_ml"), g(rec,"pa_wall_calcification")))
def fmt_case(rec, pph):
    return ("CT结构: PA/AO=%s, 主肺动脉=%smm, RV/LV=%s, RV=%smm, LV=%smm, RA=%smm。密度: %%LAA-950=%s%%, %%LAA-856=%s%%, MLD=%sHU。"
        "血管: 动脉BV5=%smL, 静脉BV5=%smL, TAC=%s, PA壁钙化=%s。RF模型P(PH)=%s。" % (
        g(rec,"pa_ao"), g(rec,"mpa_mm"), g(rec,"rv_lv"), g(rec,"rv_mm_4ch"), g(rec,"lv_mm_4ch"), g(rec,"ra_mm"),
        g(rec,"laa_950_pct"), g(rec,"laa_856_pct"), g(rec,"mld_HU"), g(rec,"artery_bv5_ml"), g(rec,"vein_bv5_ml"), g(rec,"tac"),
        g(rec,"pa_wall_calcification"), pph))

def retrieve(rec, pph, k=5):
    q = embed([query_of(rec, pph)])[0]
    scored = sorted(((cosine(q, e), ch) for e, ch in zip(CE, CH)), key=lambda t: t[0], reverse=True)
    out = []
    for i, (sc, ch) in enumerate(scored[:k], 1):
        nid = chunk_node(ch); pg = ch["metadata"]["page"]
        out.append({"id": "KG#%s-%s" % (pg, i), "node_id": nid, "source": ch["source"],
            "chunk": ch["text"][:240], "score": round(float(sc), 2), "supports": supports(nid, float(sc))})
    return out

ROLES = {"PulmonologistAgent":"呼吸内科：肺实质/气道/肺气肿(%LAA-950)/DLCO/血管表型",
         "CardiologistAgent":"心血管内科：右心与血流动力学/RV-LV/RA/TAPSE/mPAP/PVR",
         "RadiologistAgent":"影像科：CT征象 PA/AO、RV/LV、血管修剪(BV5)、PA壁钙化、室间隔变平"}
CALIB = ("【重要校准】本队列均为晚期COPD，PA/AO与主肺动脉径普遍偏高，PA/AO>0.9或MPA≥30mm单独不能区分是否合并PH。"
    "判别力优先级：①RF P(PH)(本队列校准:<0.3强烈COPD,>0.7倾向COPD-PH,0.4-0.6真不确定)；②右心受累RV/LV≥1.0、RA扩张；③血管表型BV5↓、低DLCO。"
    "PA/AO与MPA仅作辅助。若P(PH)在0.4-0.6且RV/LV<1.0应判COPD、confidence<0.6并触发fallback。")
def agent(role, rec, pph, retr, others=None):
    sysp = ("你是%s（%s）参加MDT影像辩论，在COPD与COPD-PH间二选一。\n%s\n每条证据尽量引用页码。"
        "只输出JSON:{\"claim\":\"COPD\"|\"COPD-PH\",\"confidence\":0-1,\"evidence\":[3条含数值与页码],\"cot\":\"2-4句中文\",\"control\":\"Continue\"|\"Complete\"}。"
        % (role, ROLES[role], CALIB))
    ev = "\n".join("[%s|%s|score=%s] %s" % (r["id"], r["source"], r["score"], r["chunk"]) for r in retr)
    usr = "【患者】%s\n\n【指南检索Top-5】\n%s" % (fmt_case(rec, pph), ev)
    if others:
        usr += "\n\n【其他专家上轮】\n" + "\n".join("- %s(%s,%s):%s" % (o["agent"], o["claim"], o["confidence"], o["cot"]) for o in others)
    j = chat_json([{"role":"system","content":sysp},{"role":"user","content":usr}])
    cl = j.get("claim"); cl = cl if cl in ("COPD","COPD-PH") else ("COPD-PH" if "PH" in str(cl).upper() else "COPD")
    ct = j.get("control"); ct = ct if ct in ("Continue","Complete","Terminate") else "Continue"
    e = j.get("evidence", []); e = [e] if isinstance(e, str) else e
    return {"agent":role,"claim":cl,"confidence":round(float(j.get("confidence",0.7)),2),
            "evidence":[str(x) for x in e][:4],"cot":str(j.get("cot","")).strip(),"control":ct}

def synth(no, resps, vote):
    sysp = "你是CoordinatorAgent。2-4句中文总结本轮:票数、是否共识(≥⌈n/2⌉)、分歧、下一步。不输出JSON。"
    usr = "第%s轮 票数%s。\n" % (no, vote) + "\n".join("- %s:%s(%s) %s" % (r["agent"],r["claim"],r["confidence"],r["cot"]) for r in resps)
    return chat([{"role":"system","content":sysp},{"role":"user","content":usr}], 0.3, 320).strip()

def evidence_chain(rec, pph, retr):
    pg = {r["node_id"]: re.search(r"p\.(\d+)", r["source"]).group(1) if re.search(r"p\.(\d+)", r["source"]) else "3644" for r in retr}
    ch = ["rf_proba_ph=%s → RF校准概率%s (本队列校准)" % (pph, ">0.7倾向COPD-PH" if pph>0.7 else ("<0.3倾向COPD" if pph<0.3 else "0.4-0.6不确定"))]
    if g(rec,"rv_lv") and g(rec,"rv_lv")>=1.0: ch.append("RV/LV=%s → RV/LV≥1支持PH (p.%s)" % (g(rec,"rv_lv"), pg.get("RVLV_CT","3644")))
    if g(rec,"pa_ao") and g(rec,"pa_ao")>0.9: ch.append("PA/AO=%s → CT PA/AO>0.9辅助支持PH (p.3644)" % g(rec,"pa_ao"))
    if g(rec,"laa_950_pct") is not None: ch.append("%%LAA-950=%s%% → 肺气肿确立COPD基础(Group3) (p.3638)" % g(rec,"laa_950_pct"))
    if g(rec,"pa_wall_calcification"): ch.append("PA壁钙化(+) → 慢性压力负荷")
    return ch

def diagnose(rec, pph, cid="case"):
    retr = retrieve(rec, pph); rounds = []; others = None; final = None
    for no in (1, 2):
        resps = [agent(r, rec, pph, retr, others) for r in ROLES]
        vote = {}; [vote.__setitem__(x["claim"], vote.get(x["claim"],0)+1) for x in resps]
        s = synth(no, resps, vote)
        rounds.append({"round":no,"responses":resps,"vote":vote,"synthesis":s})
        win = max(vote.items(), key=lambda kv: kv[1]); winner = win[0] if win[1] >= math.ceil(len(resps)/2) else None
        if winner and (any(x["control"] in ("Complete","Terminate") for x in resps) or win[1]==len(resps) or no==2):
            final = winner; break
        others = resps
    if final is None: final = max(rounds[-1]["vote"].items(), key=lambda kv: kv[1])[0]
    last = rounds[-1]["responses"]; confs = [r["confidence"] for r in last if r["claim"]==final] or [r["confidence"] for r in last]
    conf = round(sum(confs)/len(confs), 2)
    fb = (0.4 <= pph <= 0.6) or rounds[-1]["vote"].get(final,0) < math.ceil(len(last)/2) or conf < 0.6
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fin = {"diagnosis":final,"confidence":conf,"evidence_chain":evidence_chain(rec,pph,retr),
           "fallback_triggered":bool(fb),"trace_id":"MDT-%s-%s" % (now, cid)}
    if fb: fin["fallback_recommendation"] = "影像证据不足以独立定论，建议超声心动图/右心导管(RHC)确认mPAP与PVR并人工复核。"
    return {"kg_retrieval":retr,"rounds":rounds,"final":fin}

def main():
    global CE
    ap = argparse.ArgumentParser()
    ap.add_argument("--case"); ap.add_argument("--ids"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="debates_server.json"); ap.add_argument("--list", action="store_true")
    ap.add_argument("--serve", action="store_true"); ap.add_argument("--port", type=int, default=8077)
    a = ap.parse_args()
    if not KEY: sys.exit("no DASHSCOPE_API_KEY (env or .env)")
    scr = json.load(open(SCR_PATH))["case_records"]
    oof = json.load(open(OOF_PATH)); PPH = {cid: float(p) for cid, p in zip(oof["ids"], oof["oof_proba"]["rf"])}
    if a.list:
        ids = list(scr.keys()); print("%d cases. sample:" % len(ids)); [print("  ", i) for i in ids[:10]]; return
    if a.serve:
        from http.server import BaseHTTPRequestHandler, HTTPServer
        CE = chunk_emb()
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or "{}")
                rec = body.get("scr", {}); pph = float(body.get("rf_proba_ph", 0.5))
                res = diagnose(rec, pph, body.get("id", "api"))
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            def log_message(self, *a): pass
        print("serving on :%d  (POST /diagnose {scr:{...}, rf_proba_ph})" % a.port)
        HTTPServer(("0.0.0.0", a.port), H).serve_forever(); return
    CE = chunk_emb()
    ids = [a.case] if a.case else (a.ids.split(",") if a.ids else (list(scr.keys()) if a.all else []))
    if not ids: sys.exit("specify --case / --ids / --all / --list / --serve")
    out = {}
    for cid in ids:
        if cid not in scr: print("skip (not found):", cid); continue
        pph = PPH.get(cid, 0.5)
        print("--- %s  P(PH)=%.3f ---" % (cid, pph))
        res = diagnose(scr[cid], pph, cid); out[cid] = res
        print("   -> %s conf=%s fallback=%s rounds=%d" % (res["final"]["diagnosis"], res["final"]["confidence"], res["final"]["fallback_triggered"], len(res["rounds"])))
    if a.all or len(ids) > 1:
        json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2); print("wrote", a.out)
    elif out:
        print(json.dumps(list(out.values())[0], ensure_ascii=False, indent=2)[:1500])

if __name__ == "__main__":
    main()
