# -*- coding: utf-8 -*-
"""REAL GraphRAG + multi-agent debate pipeline (DashScope qwen-plus + text-embedding-v4).
Inputs : chunks.jsonl (guideline corpus), out_kg.json (KG), out_cases.json (cases)
Output : out_debates.json  (frontend-contract: kg_retrieval + rounds + final, per case id)
Retrieval is real cosine over real embeddings; debate is real qwen-plus reasoning that
cites guideline pages. Mirrors the LungNoduleAgent DebateOrchestrator (portable to server).
"""
import os, json, math, time, datetime, urllib.request, urllib.error, re
WORK = r"C:\Users\cheng\graphrag_pulmo"
KEY = os.environ.get("DASHSCOPE_API_KEY", "")
BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
CHAT_MODEL = "qwen-plus"
EMB_MODEL = "text-embedding-v4"

# ---------------- API helpers ----------------
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
    raise RuntimeError(f"POST {path} failed: {last!r}")

def embed(texts):
    out = []
    for i in range(0, len(texts), 10):
        batch = texts[i:i+10]
        resp = _post("/embeddings", {"model": EMB_MODEL, "input": batch})
        out.extend([d["embedding"] for d in sorted(resp["data"], key=lambda d: d["index"])])
    return out

def chat(messages, temperature=0.3, max_tokens=900):
    resp = _post("/chat/completions", {"model": CHAT_MODEL, "messages": messages,
                                       "temperature": temperature, "max_tokens": max_tokens})
    return resp["choices"][0]["message"]["content"]

def chat_json(messages, temperature=0.3):
    """Call chat and parse a JSON object from the reply (robust to code fences)."""
    txt = chat(messages, temperature=temperature)
    m = re.search(r"\{.*\}", txt, re.S)
    raw = m.group(0) if m else txt
    try:
        return json.loads(raw)
    except Exception:
        fix = chat(messages + [{"role": "assistant", "content": txt},
                   {"role": "user", "content": "只输出合法 JSON 对象，不要任何解释或代码围栏。"}], temperature=0.0)
        m = re.search(r"\{.*\}", fix, re.S)
        return json.loads(m.group(0) if m else fix)

def cosine(a, b):
    s = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return s/(na*nb) if na and nb else 0.0

# ---------------- load corpus / kg / cases ----------------
chunks = [json.loads(l) for l in open(os.path.join(WORK, "chunks.jsonl"), encoding="utf-8") if l.strip()]
kg = json.load(open(os.path.join(WORK, "out_kg.json"), encoding="utf-8"))
cases_doc = json.load(open(os.path.join(WORK, "out_cases.json"), encoding="utf-8"))
cases = cases_doc["cases"]

# KG node keyword index for chunk->node mapping
NODE_KW = {}
for n in kg["nodes"]:
    kws = {n["id"].lower(), n["label"].lower()}
    NODE_KW[n["id"]] = (kws, n["type"])
ENT2NODE = {
    "mpap": "MPAP", "pvr": "PVR", "pawp": "PAWP", "pa/ao": "PA_AO", "pa-ao": "PA_AO",
    "rv/lv": "RVLV_CT", "trv": "TRV", "dlco": "DLCO", "cteph": "CTEPH", "pah": "PAH",
    "group 3": "GROUP3", "copd": "COPD", "emphysema": "EMPHYSEMA", "pruning": "PRUNING",
    "bv5": "BV5", "ra area": "RAAREA", "tapse": "TAPSE", "septal": "LVEI",
    "post-capillary": "POSTCAP", "pre-capillary": "PRECAP", "exercise ph": "EXPH",
    "bnp": "BNP", "paco2": "PACO2", "v/q": "VQ", "wedge": "PAWP",
}
def chunk_to_node(ch):
    ents = " ".join(ch.get("entities", []) + [ch["text"]]).lower()
    for kw, nid in ENT2NODE.items():
        if kw in ents:
            return nid
    return "PH"

PH_NODES = {"PH", "PAH", "COPD_PH", "GROUP3", "PRECAP", "SEVERE3", "VASCPHEN", "MPAP", "PVR",
            "PA_AO", "RVLV_CT", "TRV", "PRUNING", "BV5", "RAAREA", "TAPSE", "LVEI", "DLCO", "PACO2"}
COPD_NODES = {"COPD", "EMPHYSEMA"}
def supports_tag(nid, score, label_hint):
    w = round(0.3 + 0.4*score, 2)
    if nid in COPD_NODES: return f"COPD +{w}"
    if nid in PH_NODES:   return f"COPD-PH +{w}"
    return "context +0.0"

# ---------------- retrieval ----------------
print("embedding", len(chunks), "chunks ...")
CH_EMB = embed([c["text"] for c in chunks])

def case_query(c):
    s, d, v = c["structural_metrics"], c["density_metrics"], c["vessel_tree_metrics"]
    def g(x): return "NA" if x is None else x
    return (f"Differentiating COPD from COPD-associated pulmonary hypertension (Group 3 PH) on CT. "
            f"PA/AO ratio {g(s['PA_AO_ratio'])} (PH if >0.9); main PA diameter {g(s['PA_d_mm'])} mm; "
            f"RV/LV ratio {g(s['RV_LV_ratio'])} (PH if >=1); RA {g(s['RA_a_mm'])} mm; "
            f"emphysema %LAA-950 {g(d['LAA_950_pct'])}%; small-vessel BV5 {g(v['BV5_mL'])} mL (vascular pruning); "
            f"PA wall calcification {g(v['pa_wall_calcification'])}. mPAP>20 mmHg defines PH; PVR>5 WU defines severe Group 3 PH; "
            f"pulmonary vascular phenotype: low DLCO, hypoxaemia, preserved spirometry.")

def retrieve(c, k=5):
    q = embed([case_query(c)])[0]
    scored = sorted(((cosine(q, e), ch) for e, ch in zip(CH_EMB, chunks)), key=lambda t: t[0], reverse=True)
    out = []
    for i, (sc, ch) in enumerate(scored[:k], 1):
        nid = chunk_to_node(ch)
        out.append({
            "id": f"KG#{ch['metadata']['page']%10000:04d}{i}"[:7],
            "node_id": nid,
            "source": ch["source"],
            "chunk": ch["text"][:240] + ("…" if len(ch["text"]) > 240 else ""),
            "score": round(float(sc), 2),
            "supports": supports_tag(nid, float(sc), c["ground_truth"]),
            "_page": ch["metadata"]["page"],
        })
    return out

# ---------------- agents ----------------
ROLES = {
    "PulmonologistAgent": "呼吸内科医生。关注肺实质/气道：肺气肿(%LAA-950)、COPD背景、DLCO、低氧/低PaCO2、'肺血管表型'。判断密度学证据能否单独解释影像。",
    "CardiologistAgent":  "心血管内科医生。关注右心与血流动力学：RV/LV、RA扩张、TAPSE/sPAP、mPAP>20、PVR>2(>5为严重)、毛细血管前/后 PH 鉴别。",
    "RadiologistAgent":   "影像科医生。关注CT征象：PA/AO>0.9、主肺动脉≥30mm、RV/LV≥1、外周血管修剪(BV5↓)、PA壁钙化、室间隔变平。",
}
LABELS = ["COPD", "COPD-PH"]

def fmt_case(c):
    s, d, v = c["structural_metrics"], c["density_metrics"], c["vessel_tree_metrics"]
    return (f"患者{c['patient']['age']}岁{c['patient']['sex']}，{c['patient']['smoking']}，{c['patient']['presenting']}。"
            f"CT结构: PA/AO={s['PA_AO_ratio']}, 主肺动脉={s['PA_d_mm']}mm, RV/LV={s['RV_LV_ratio']}, "
            f"RV={s['RV_d_mm']}mm, LV={s['LV_d_mm']}mm, RA={s['RA_a_mm']}mm。"
            f"密度: %LAA-950={d['LAA_950_pct']}%, %LAA-856={d['LAA_856_pct']}%。"
            f"血管: BV5={v['BV5_mL']}mL, TAC={v['TAC']}, PA壁钙化={v['pa_wall_calcification']}。"
            f"RF模型P(PH)={c['rf_proba_ph']}。")

def fmt_evidence(retr):
    return "\n".join(f"[{r['id']} | {r['source']} | score={r['score']}] {r['chunk']}" for r in retr)

CALIB = ("【重要校准】本队列均为晚期 COPD 患者，PA/AO 与主肺动脉径普遍偏高，"
         "PA/AO>0.9 或 MPA≥30mm 单独并不能区分是否合并 PH（COPD 本身即可致肺动脉增宽）。"
         "真正有判别力的证据按优先级为：① RF 结构模型 P(PH)（在本队列 5 折校准：<0.3 强烈倾向 COPD，>0.7 倾向 COPD-PH，0.4–0.6 为真不确定）；"
         "② 右心受累——RV/LV≥1.0、RA 明显扩张、室间隔变平；③ 肺血管表型——BV5↓(外周修剪)、低 DLCO、低 PaCO2。"
         "请以这三者为主，PA/AO 与 MPA 仅作辅助，切勿仅凭 PA/AO>0.9 即判 COPD-PH。"
         "若 P(PH) 落在 0.4–0.6 且右心无明确受累(RV/LV<1)，应判 COPD 并将 confidence 控制在 0.6 以下（提示需人工复核）。")
def agent_turn(role, c, retr, others=None):
    sys = (f"你是{role}（{ROLES[role]}）参加一次多学科(MDT)影像诊断辩论。任务：在 COPD 与 COPD-PH 之间二选一判断。\n{CALIB}\n"
           f"必须基于给定的患者结构化指标 + 指南检索证据，每条证据尽量引用来源页码(如 ESC/ERS p.3644)。"
           f"只输出 JSON: {{\"claim\":\"COPD\"|\"COPD-PH\", \"confidence\":0-1 浮点, "
           f"\"evidence\":[\"...含数值与页码...\", ...3条], \"cot\":\"2-4句中文推理\", \"control\":\"Continue\"|\"Complete\"}}。"
           f"control=Complete 表示你认为证据已足够定论。")
    usr = f"【患者】{fmt_case(c)}\n\n【指南检索证据 Top-5】\n{fmt_evidence(retr)}"
    if others:
        usr += "\n\n【其他专家上一轮观点】\n" + "\n".join(f"- {o['agent']}({o['claim']},conf={o['confidence']}): {o['cot']}" for o in others)
        usr += "\n请交叉检验并可修正你的判断。"
    j = chat_json([{"role": "system", "content": sys}, {"role": "user", "content": usr}], temperature=0.2)
    claim = j.get("claim", "COPD-PH")
    if claim not in LABELS: claim = "COPD-PH" if "PH" in str(claim).upper() else "COPD"
    ev = j.get("evidence", [])
    if isinstance(ev, str): ev = [ev]
    ctrl = j.get("control", "Continue")
    if ctrl not in ("Continue", "Complete", "Terminate"): ctrl = "Continue"
    return {"agent": role, "claim": claim, "confidence": round(float(j.get("confidence", 0.7)), 2),
            "evidence": [str(e) for e in ev][:4], "cot": str(j.get("cot", "")).strip(), "control": ctrl}

def tally(resps):
    t = {}
    for r in resps: t[r["claim"]] = t.get(r["claim"], 0) + 1
    return t

def winner(t, n):
    need = math.ceil(n/2)
    best = max(t.items(), key=lambda kv: kv[1]) if t else (None, 0)
    return (best[0] if best[1] >= need else None), best

def synth(c, rnd_no, resps, t):
    win, best = winner(t, len(resps))
    sys = "你是 CoordinatorAgent，多学科辩论的协调员。用2-4句中文总结本轮：票数、共识与否(≥⌈n/2⌉)、主要分歧点、下一步决定。不引用JSON。"
    usr = (f"第{rnd_no}轮，票数{t}。各专家:\n" +
           "\n".join(f"- {r['agent']}: {r['claim']} (conf={r['confidence']}) {r['cot']}" for r in resps))
    txt = chat([{"role": "system", "content": sys}, {"role": "user", "content": usr}], temperature=0.3, max_tokens=320)
    return txt.strip(), win

def evidence_chain(c, retr):
    s, d, v = c["structural_metrics"], c["density_metrics"], c["vessel_tree_metrics"]
    pg = {r["node_id"]: r["_page"] for r in retr}
    ch = []
    if s["PA_AO_ratio"] and s["PA_AO_ratio"] > 0.9:
        ch.append(f"structural_metrics.PA_AO_ratio={s['PA_AO_ratio']} → ESC/ERS 2022 PA/AO>0.9 为 PH 的 CT 征象 (p.{pg.get('PA_AO',3644)})")
    if s["RV_LV_ratio"] and s["RV_LV_ratio"] >= 1.0:
        ch.append(f"structural_metrics.RV_LV_ratio={s['RV_LV_ratio']} → RV/LV≥1 支持右心受累/PH (p.{pg.get('RVLV_CT',3644)})")
    if s["PA_d_mm"] and s["PA_d_mm"] >= 30:
        ch.append(f"structural_metrics.PA_d_mm={s['PA_d_mm']}mm → 主肺动脉≥30mm 支持 PH (p.3644)")
    if d["LAA_950_pct"] is not None:
        sev = "中-重度" if d["LAA_950_pct"] >= 20 else ("轻-中度" if d["LAA_950_pct"] >= 8 else "不显著")
        ch.append(f"density_metrics.LAA_950_pct={d['LAA_950_pct']}% → 肺气肿{sev} (GOLD)")
    if v["pa_wall_calcification"]:
        ch.append("vessel_tree_metrics.pa_wall_calcification=true → 肺动脉壁钙化，慢性压力负荷")
    ch.append(f"RF 分类器 P(PH)={c['rf_proba_ph']} → 17 维 SCR 结构特征定量支持")
    return ch

def run_case(c):
    retr = retrieve(c)
    rounds = []
    others = None
    final_label = None
    for rnd_no in (1, 2):
        resps = [agent_turn(role, c, retr, others) for role in ROLES]
        t = tally(resps)
        synthesis, win = synth(c, rnd_no, resps, t)
        rounds.append({"round": rnd_no, "responses": resps, "vote": t, "synthesis": synthesis})
        anyone_complete = any(r["control"] in ("Complete", "Terminate") for r in resps)
        if win is not None and (anyone_complete or rnd_no == 1 and t.get(win, 0) == len(resps)):
            final_label = win; break
        if win is not None and rnd_no == 2:
            final_label = win; break
        others = resps  # cross-talk into next round
    if final_label is None:
        t = rounds[-1]["vote"]; final_label = max(t.items(), key=lambda kv: kv[1])[0]
    # confidence = mean confidence of agents who voted the final label (last round)
    last = rounds[-1]["responses"]
    confs = [r["confidence"] for r in last if r["claim"] == final_label] or [r["confidence"] for r in last]
    conf = round(sum(confs)/len(confs), 2)
    # fallback if borderline RF proba or weak consensus
    win_count = rounds[-1]["vote"].get(final_label, 0)
    fallback = (0.4 <= c["rf_proba_ph"] <= 0.6) or (win_count < math.ceil(len(last)/2)) or conf < 0.6
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    final = {
        "diagnosis": final_label,
        "confidence": conf,
        "evidence_chain": evidence_chain(c, retr),
        "fallback_triggered": bool(fallback),
        "trace_id": f"MDT-{now}-{c['id']}",
    }
    if fallback:
        final["fallback_recommendation"] = "影像证据不足以独立定论，建议补充超声心动图/右心导管(RHC)确认 mPAP 与 PVR，并人工复核。"
    # strip private _page from retrieval before shipping
    for r in retr: r.pop("_page", None)
    return {"kg_retrieval": retr, "rounds": rounds, "final": final, "consensus_round": len(rounds)}

debates = {}
consensus_rounds = {}
for c in cases:
    print(f"--- {c['id']} (GT={c['ground_truth']}, P(PH)={c['rf_proba_ph']}) ---")
    rc = run_case(c)
    consensus_rounds[c["id"]] = rc.pop("consensus_round")
    debates[c["id"]] = rc
    fin = rc["final"]
    print(f"    -> {fin['diagnosis']} conf={fin['confidence']} fallback={fin['fallback_triggered']} rounds={len(rc['rounds'])}")

json.dump(debates, open(os.path.join(WORK, "out_debates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# reconcile consensus_round back into cases.json
for c in cases:
    c["consensus_round"] = consensus_rounds.get(c["id"], c.get("consensus_round", 2))
json.dump(cases_doc, open(os.path.join(WORK, "out_cases.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nWROTE out_debates.json for", len(debates), "cases; reconciled consensus_round into out_cases.json")
