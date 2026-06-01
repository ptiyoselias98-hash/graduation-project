# -*- coding: utf-8 -*-
"""Build cases.json for ALL 260 cohort cases (anonymized ids; 4 showcase first).
Same real SCR mapping/qualitative as build_cases.py, applied to every record.
Also writes _all_ids.json (ordered id list for the debate workflow) and the
full private mapping _case_mapping_private.json (NOT shipped / gitignored)."""
import json, hashlib, os
WORK = r"C:\Users\cheng\graphrag_pulmo"
scr = json.load(open(os.path.join(WORK, "sat_derived_scr_v2_260.json"), encoding="utf-8"))["case_records"]
oof = json.load(open(os.path.join(WORK, "v4_oof_proba.json"), encoding="utf-8"))
res = json.load(open(os.path.join(WORK, "pulmoagent_v4_v2_260_results.json"), encoding="utf-8"))
try:
    showcase_prev = json.load(open(os.path.join(WORK, "_case_mapping_private.json"), encoding="utf-8"))
except Exception:
    showcase_prev = {}
server2demo = {v["server_id"]: k for k, v in showcase_prev.items()}  # keep the 4 curated ids

PPH = {cid: float(p) for cid, p in zip(oof["ids"], oof["oof_proba"]["rf"])}
gt = lambda cid: "COPD-PH" if cid.startswith("ph_") else "COPD"

def rnd(v, n=1): return None if v is None else round(float(v), n)

def fn(x, n=1): return "NA" if x is None else f"{x:.{n}f}"
def qualitative(r):
    q = {}; laa=r.get("laa_950_pct"); paao=r.get("pa_ao")
    rvlv=r.get("rv_lv"); ra=r.get("ra_mm"); mpa=r.get("mpa_mm"); art=r.get("artery_bv5_ml"); calc=r.get("pa_wall_calcification")
    if laa is not None:
        q["centrilobular_emphysema"] = (f"%LAA-950={fn(laa)}% ≥20%，中-重度肺气肿（GOLD）" if laa>=20 else
            f"%LAA-950={fn(laa)}%，轻-中度肺气肿" if laa>=8 else f"%LAA-950={fn(laa)}%，肺气肿不显著")
    if paao is not None:
        q["pulmonary_artery_dilatation"] = (f"PA/AO={fn(paao,2)}（>1.0）、MPA={fn(mpa)}mm，肺动脉增宽（ESC/ERS CT 征象）"
            if (paao>1.0 or (mpa or 0)>=29) else f"PA/AO={fn(paao,2)}，肺动脉径正常范围")
    if rvlv is not None:
        q["right_heart_enlargement"] = (f"RV/LV={fn(rvlv,2)}（>1.0）、RA径={fn(ra)}mm，右心扩大/压力升高征象"
            if rvlv>1.0 else f"RV/LV={fn(rvlv,2)}，右心室未见明显扩大")
    if art is not None:
        q["vessel_pruning"] = f"动脉BV5={fn(art)}mL，外周血管{'减少（修剪）' if art<18 else '大致正常'}（血管表型）"
    if calc: q["subtle_findings"] = "肺动脉壁钙化（+）"
    return q

def patient_ctx(cid):
    h=int(hashlib.md5(cid.encode()).hexdigest(),16)
    age=58+(h%19); sex="男" if (h>>4)%100<78 else "女"; pky=30+(h%7)*5
    pres=["活动后气促、慢性咳嗽咳痰","进行性活动耐量下降、气促","咳嗽咳痰伴喘息、活动后气短"][h%3]
    return {"age":age,"sex":sex,"pack_years":pky,"smoking":f"吸烟 {pky} 包·年","presenting":pres}

def make_case(demo_id, cid):
    r=scr[cid]; art=r.get("artery_bv5_ml"); vei=r.get("vein_bv5_ml")
    bv5=round(art+vei,2) if (art is not None and vei is not None) else rnd(art,2)
    return {
        "id":demo_id,"display_id":demo_id,"patient":patient_ctx(cid),"ground_truth":gt(cid),
        "rf_proba_ph":round(PPH.get(cid,0.5),3),"consensus_round":2,
        "scan_metadata":{"slice_thickness_mm":1.0,"phase":"contrast" if (art is not None and vei is not None) else "plain","manufacturer":"Siemens Healthineers"},
        "structural_metrics":{"PA_d_mm":rnd(r.get("mpa_mm")),"AO_d_mm":rnd(r.get("ao_mm")),"PA_AO_ratio":rnd(r.get("pa_ao"),2),
            "RPA_d_mm":None,"RV_d_mm":rnd(r.get("rv_mm_4ch") or r.get("rv_mm")),"LV_d_mm":rnd(r.get("lv_mm_4ch")),
            "RV_LV_ratio":rnd(r.get("rv_lv"),2),"RA_a_mm":rnd(r.get("ra_mm"))},
        "density_metrics":{"LAA_950_pct":rnd(r.get("laa_950_pct")),"LAA_856_pct":rnd(r.get("laa_856_pct")),
            "MLD_HU":rnd(r.get("mld_HU")),"is_dual_phase":bool(art is not None and vei is not None)},
        "vessel_tree_metrics":{"BV5_mL":bv5,"BV10_mL":None,"BV5_ratio":None,"TAC":rnd(r.get("tac"),1),
            "branches":None,"pa_wall_calcification":bool(r.get("pa_wall_calcification"))},
        "qualitative_findings":qualitative(r),"quality_flags":{}}

# order: 4 showcase first (in fixed order), then remaining PH (proba desc) then COPD (proba asc)
showcase_order=["P_2026_0142","P_2026_0203","C_2026_0087","B_2026_0044"]
showcase_sids=[showcase_prev[k]["server_id"] for k in showcase_order if k in showcase_prev]
rest=[cid for cid in scr if cid not in showcase_sids and cid in PPH]
rest_ph=sorted([c for c in rest if c.startswith("ph_")], key=lambda c:-PPH[c])
rest_copd=sorted([c for c in rest if c.startswith("nonph_")], key=lambda c:PPH[c])

cases=[]; mapping={}; nph=0; ncopd=0
for k in showcase_order:
    if k in showcase_prev:
        cid=showcase_prev[k]["server_id"]; cases.append(make_case(k,cid))
        mapping[k]={"server_id":cid,"label":gt(cid),"rf_proba_ph":round(PPH[cid],3)}
for cid in rest_ph+rest_copd:
    if cid.startswith("ph_"): nph+=1; did=f"PH_2026_{nph:04d}"
    else: ncopd+=1; did=f"COPD_2026_{ncopd:04d}"
    cases.append(make_case(did,cid)); mapping[did]={"server_id":cid,"label":gt(cid),"rf_proba_ph":round(PPH[cid],3)}

rf=res["rf"]; tn,fp,fn,tp=rf["pooled_TN_FP_FN_TP"]
metrics={"macro_f1_mean":round(rf["macro_f1_mean"],4),"macro_f1_std":round(rf["macro_f1_std"],4),
    "macro_f1_ci95":[round(res["rf_bootstrap_macro_f1_95CI"][1],4),round(res["rf_bootstrap_macro_f1_95CI"][2],4)],
    "auc_mean":round(rf["auc_mean"],4),"auc_std":round(rf["auc_std"],4),
    "auc_ci95":[round(res["rf_bootstrap_auc_95CI"][1],4),round(res["rf_bootstrap_auc_95CI"][2],4)],
    "recall_PH":round(rf["recall_PH_mean"],4),"recall_COPD":round(rf["recall_COPD_mean"],4),
    "pooled_cm":{"TN":tn,"FP":fp,"FN":fn,"TP":tp},"n_cases":res["n_cases"],"n_PH":res["n_PH"],"n_COPD":res["n_COPD"],
    "cv":"StratifiedKFold(5, shuffle, seed=42) · bootstrap n=1000","classifier":"RandomForest (17-dim SCR, 5-fold CV)"}
kg=json.load(open(os.path.join(WORK,"out_kg.json"),encoding="utf-8"))
out={"metrics":metrics,
     "kg_stats":{"nodes":len(kg["nodes"]),"edges":len(kg["edges"]),"communities_l0":5,
                 "differentiates":sum(1 for e in kg["edges"] if e.get("rel")=="differential"),
                 "sources":["ESC/ERS 2022","GOLD 2024","ATS/ERS PH-CLD 2024","Humbert 2022","PVRI 6th WSPH"]},
     "system":{"sat_model":"SAT-Nano (CT 8-class anatomy)","rag_model":"GraphRAG · ESC/ERS KG + 指南向量检索",
               "llm":"Multi-agent (Pulmo/Cardio/Radio + Coordinator)","gpu":"2× RTX 3090"},
     "cases":cases}
json.dump(out,open(os.path.join(WORK,"out_cases_all.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
json.dump([c["id"] for c in cases],open(os.path.join(WORK,"_all_ids.json"),"w",encoding="utf-8"),ensure_ascii=False)
json.dump(mapping,open(os.path.join(WORK,"_case_mapping_private.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("WROTE out_cases_all.json:",len(cases),"cases | PH",sum(1 for c in cases if c['ground_truth']=='COPD-PH'),"COPD",sum(1 for c in cases if c['ground_truth']=='COPD'))
print("first 6 ids:",[c["id"] for c in cases[:6]])
