# -*- coding: utf-8 -*-
"""Merge the 260-case Claude debate workflow output into debates.json, validate,
score vs ground truth, reconcile consensus_round, and deploy to the frontend."""
import json, os, re, html, datetime, shutil, collections
WORK = r"C:\Users\cheng\graphrag_pulmo"
DATA = r"E:\桌面文件\5月14日下午毕业设计\！！！前端演示\data"
OUT = r"C:\Users\cheng\AppData\Local\Temp\claude\C--Users-cheng\0937ceae-a20c-4823-8e71-73080f136053\tasks\w1ajll3oh.output"

raw = json.load(open(OUT, encoding="utf-8"))
if isinstance(raw, dict) and "result" in raw: raw = raw["result"]
entries = raw["entries"] if isinstance(raw, dict) else raw
print("entries from workflow:", len(entries))

kg = json.load(open(os.path.join(WORK, "out_kg.json"), encoding="utf-8"))
KG_IDS = {n["id"] for n in kg["nodes"]}
mapping = json.load(open(os.path.join(WORK, "_case_mapping_private.json"), encoding="utf-8"))
cases_doc = json.load(open(os.path.join(WORK, "out_cases_all.json"), encoding="utf-8"))
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def U(s): return html.unescape(s) if isinstance(s, str) else s
def clean_list(xs): return [U(x) for x in xs] if isinstance(xs, list) else xs

CL = {"COPD", "COPD-PH"}; CT = {"Continue", "Complete", "Terminate"}
AGENTS = {"PulmonologistAgent", "CardiologistAgent", "RadiologistAgent"}
debates = {}
problems = []
for e in entries:
    cid = e["id"]
    # kg_retrieval: unescape, unique ids, valid node_id
    kr = []
    for i, r in enumerate(e.get("kg_retrieval", [])[:5], 1):
        m = re.search(r"p\.(\d+)", r.get("source", "")); page = m.group(1) if m else str(i)
        nid = r.get("node_id") if r.get("node_id") in KG_IDS else "PH"
        try: sc = round(float(r.get("score", 0.5)), 2)
        except Exception: sc = 0.5
        kr.append({"id": f"KG#{page}-{i}", "node_id": nid, "source": U(r.get("source", "")),
                   "chunk": U(r.get("chunk", "")), "score": sc, "supports": U(r.get("supports", "context +0.0"))})
    # rounds
    rounds = []
    for rd in e.get("rounds", []):
        resps = []
        for rp in rd.get("responses", []):
            claim = rp.get("claim") if rp.get("claim") in CL else ("COPD-PH" if "PH" in str(rp.get("claim", "")).upper() else "COPD")
            ctrl = rp.get("control") if rp.get("control") in CT else "Continue"
            ag = rp.get("agent") if rp.get("agent") in AGENTS else "PulmonologistAgent"
            try: conf = round(float(rp.get("confidence", 0.7)), 2)
            except Exception: conf = 0.7
            resps.append({"agent": ag, "claim": claim, "confidence": conf,
                          "evidence": clean_list(rp.get("evidence", []))[:4], "cot": U(rp.get("cot", "")), "control": ctrl})
        vote = rd.get("vote", {}) if isinstance(rd.get("vote"), dict) else {}
        rounds.append({"round": rd.get("round", len(rounds)+1), "responses": resps,
                       "vote": vote, "synthesis": U(rd.get("synthesis", ""))})
    f = e.get("final", {})
    diagnosis = f.get("diagnosis") if f.get("diagnosis") in CL else ("COPD-PH" if "PH" in str(f.get("diagnosis","")).upper() else "COPD")
    try: fconf = round(float(f.get("confidence", 0.7)), 2)
    except Exception: fconf = 0.7
    final = {"diagnosis": diagnosis, "confidence": fconf,
             "evidence_chain": clean_list(f.get("evidence_chain", [])),
             "fallback_triggered": bool(f.get("fallback_triggered", False)),
             "trace_id": f"MDT-{stamp}-{cid}"}
    if final["fallback_triggered"]:
        final["fallback_recommendation"] = U(f.get("fallback_recommendation",
            "影像证据不足以独立定论，建议补充超声心动图/右心导管(RHC)确认 mPAP 与 PVR，并人工复核。"))
    if not kr or not rounds: problems.append(cid)
    debates[cid] = {"kg_retrieval": kr, "rounds": rounds, "final": final}

# coverage
all_ids = [c["id"] for c in cases_doc["cases"]]
missing = [i for i in all_ids if i not in debates]
print("missing debates:", len(missing), missing[:10])
print("entries with empty retrieval/rounds:", len(problems), problems[:10])

# score vs ground truth
y_true = []; y_pred = []; fb = 0
for cid, cd in debates.items():
    gtl = mapping.get(cid, {}).get("label")
    if gtl: y_true.append(gtl); y_pred.append(cd["final"]["diagnosis"])
    if cd["final"]["fallback_triggered"]: fb += 1
correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
n = len(y_true)
# per class
tp = sum(1 for t,p in zip(y_true,y_pred) if t=="COPD-PH" and p=="COPD-PH")
ph_tot = sum(1 for t in y_true if t=="COPD-PH")
copd_tp = sum(1 for t,p in zip(y_true,y_pred) if t=="COPD" and p=="COPD")
copd_tot = sum(1 for t in y_true if t=="COPD")
print(f"\n=== AGREEMENT vs GT (label) ===")
print(f"overall: {correct}/{n} = {correct/n:.3f}")
print(f"COPD-PH recall: {tp}/{ph_tot} = {tp/ph_tot:.3f}" if ph_tot else "")
print(f"COPD   recall: {copd_tp}/{copd_tot} = {copd_tp/copd_tot:.3f}" if copd_tot else "")
print(f"fallback triggered: {fb}/{len(debates)} = {fb/len(debates):.3f}")
# fallback among disagreements
dis = [(cid) for cid,cd in debates.items() if mapping.get(cid,{}).get("label") and cd["final"]["diagnosis"]!=mapping[cid]["label"]]
dis_fb = sum(1 for cid in dis if debates[cid]["final"]["fallback_triggered"])
print(f"disagreements: {len(dis)}; of which fallback-flagged: {dis_fb}")

# reconcile consensus_round into cases
for c in cases_doc["cases"]:
    cd = debates.get(c["id"])
    if cd: c["consensus_round"] = len(cd["rounds"]) or 1

json.dump(debates, open(os.path.join(WORK, "out_debates_all.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(cases_doc, open(os.path.join(WORK, "out_cases_all.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# deploy
shutil.copyfile(os.path.join(WORK, "out_cases_all.json"), os.path.join(DATA, "cases.json"))
shutil.copyfile(os.path.join(WORK, "out_debates_all.json"), os.path.join(DATA, "debates.json"))
print("\nDEPLOYED cases.json + debates.json (260 cases) to frontend")
print("metrics_block n_cases:", cases_doc["metrics"]["n_cases"])
