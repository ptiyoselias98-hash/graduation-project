# -*- coding: utf-8 -*-
"""Build a REAL kg.json for the frontend, grounded in the 2022 ESC/ERS PH Guidelines
(+ GOLD / ATS-ERS / PVRI). Nodes: disease|indicator|concept|source. Edges carry real
relation + weight + source + guideline page for provenance (frontend uses from/to;
rel/w/src/page are extra but emitted for traceability)."""
import json, os
WORK = r"C:\Users\cheng\graphrag_pulmo"

# (id, label, type, category) ; category drives layout band
N = [
    # sources (top)
    ("ESC","ESC/ERS 2022","source","src"),
    ("GOLD","GOLD 2024","source","src"),
    ("ATS","ATS/ERS PH-CLD","source","src"),
    ("WSPH","PVRI 6th WSPH","source","src"),
    ("HUMBERT","Humbert 2022","source","src"),
    # diseases (center)
    ("PH","肺动脉高压 PH","disease","dz"),
    ("PAH","PAH (Group 1)","disease","dz"),
    ("PH_LHD","PH-左心 (Group 2)","disease","dz"),
    ("GROUP3","肺病相关PH (Group 3)","disease","dz"),
    ("COPD_PH","COPD-PH","disease","dz"),
    ("CTEPH","CTEPH (Group 4)","disease","dz"),
    ("COPD","COPD","disease","dz"),
    ("EMPHYSEMA","肺气肿","disease","dz"),
    # concepts
    ("PRECAP","毛细血管前 PH","concept","concept"),
    ("POSTCAP","毛细血管后 PH","concept","concept"),
    ("SEVERE3","严重 Group3 PH","concept","concept"),
    ("VASCPHEN","肺血管表型","concept","concept"),
    ("PRUNING","血管修剪","concept","concept"),
    ("EXPH","运动性 PH","concept","concept"),
    # hemodynamic indicators (RHC)
    ("MPAP","mPAP","indicator","hemo"),
    ("PAWP","PAWP","indicator","hemo"),
    ("PVR","PVR","indicator","hemo"),
    ("MPAPCO","mPAP/CO 斜率","indicator","hemo"),
    ("CI","心指数 CI","indicator","hemo"),
    ("RAP","RAP","indicator","hemo"),
    ("SVO2","SvO2","indicator","hemo"),
    # echo indicators
    ("TRV","峰值 TRV","indicator","echo"),
    ("RVLV_E","RV/LV (超声)","indicator","echo"),
    ("LVEI","室间隔变平 LVEI","indicator","echo"),
    ("TAPSE","TAPSE/sPAP","indicator","echo"),
    ("RAAREA","RA 面积","indicator","echo"),
    ("RVOT_AT","RVOT 加速时间","indicator","echo"),
    # CT indicators
    ("PA_AO","PA/AO 比值","indicator","ct"),
    ("MPA_CT","PA 直径 (CT)","indicator","ct"),
    ("RVLV_CT","RV/LV (CT)","indicator","ct"),
    ("RVOT_W","RVOT 壁厚","indicator","ct"),
    ("BV5","BV5 / 外周血管","indicator","ct"),
    ("PA_CALC","PA 壁钙化","indicator","ct"),
    # functional / lab
    ("DLCO","DLCO","indicator","func"),
    ("PACO2","PaCO2","indicator","func"),
    ("BNP","BNP/NT-proBNP","indicator","func"),
    ("LAA950","%LAA-950","indicator","func"),
    ("LAA856","%LAA-856","indicator","func"),
    ("MLD","MLD","indicator","func"),
    ("VQ","V/Q 扫描","indicator","func"),
]

# edges: (from, to, rel, w, src, page)
E = [
    # definitions (DEFINES)
    ("MPAP","PH","defines",0.98,"ESC/ERS 2022","p.3637 (mPAP>20mmHg)"),
    ("PAWP","PRECAP","defines",0.9,"ESC/ERS 2022","p.3637 (PAWP≤15)"),
    ("PAWP","POSTCAP","defines",0.9,"ESC/ERS 2022","p.3637 (PAWP>15)"),
    ("PVR","PRECAP","defines",0.9,"ESC/ERS 2022","p.3637 (PVR>2 WU)"),
    ("PVR","SEVERE3","defines",0.92,"ESC/ERS 2022","p.3690-91 (PVR>5 WU)"),
    ("MPAPCO","EXPH","defines",0.8,"ESC/ERS 2022","p.3637 (>3 mmHg/L/min)"),
    ("PRECAP","PAH","defines",0.85,"ESC/ERS 2022","p.3637"),
    ("PRECAP","GROUP3","defines",0.8,"ESC/ERS 2022","p.3691"),
    ("PRECAP","CTEPH","defines",0.8,"ESC/ERS 2022","p.3637/3694"),
    ("POSTCAP","PH_LHD","defines",0.85,"ESC/ERS 2022","p.3685"),
    # disease taxonomy (subtype)
    ("COPD_PH","GROUP3","subtype",0.95,"ESC/ERS 2022","p.3638 (3.1)"),
    ("GROUP3","PH","subtype",0.9,"ESC/ERS 2022","p.3638"),
    ("PAH","PH","subtype",0.9,"ESC/ERS 2022","p.3638 (Group1)"),
    ("PH_LHD","PH","subtype",0.9,"ESC/ERS 2022","p.3638 (Group2)"),
    ("CTEPH","PH","subtype",0.9,"ESC/ERS 2022","p.3638 (Group4)"),
    ("EMPHYSEMA","COPD","subtype",0.9,"GOLD 2024","emphysema phenotype"),
    ("COPD","COPD_PH","progresses_to",0.7,"ESC/ERS 2022","p.3690 (1-5% severe)"),
    ("SEVERE3","COPD_PH","describes",0.8,"ATS/ERS PH-CLD 2024","severe PH-CLD"),
    ("VASCPHEN","SEVERE3","describes",0.8,"ESC/ERS 2022","p.3691 vascular phenotype"),
    # emphysema density markers (GOLD)
    ("LAA950","EMPHYSEMA","supports",0.9,"GOLD 2024","%LAA-950≥20% 中重度"),
    ("LAA856","EMPHYSEMA","supports",0.55,"GOLD 2024","气体陷闭"),
    ("MLD","EMPHYSEMA","supports",0.6,"GOLD 2024","低衰减"),
    ("LAA950","COPD","supports",0.6,"GOLD 2024",""),
    # CT signs of PH (supports COPD-PH / Group3)
    ("PA_AO","COPD_PH","supports",0.85,"ESC/ERS 2022","p.3644 (PA/AO>0.9)"),
    ("PA_AO","PH","supports",0.6,"ESC/ERS 2022","p.3644"),
    ("MPA_CT","PH","supports",0.7,"ESC/ERS 2022","p.3644 (≥30mm)"),
    ("RVLV_CT","COPD_PH","supports",0.78,"ESC/ERS 2022","p.3644 (RV/LV≥1)"),
    ("RVOT_W","PH","supports",0.55,"ESC/ERS 2022","p.3644 (≥6mm)"),
    ("BV5","PRUNING","supports",0.75,"Rahaghi 2021 / PVRI 6th WSPH","BV5↓"),
    ("PRUNING","COPD_PH","supports",0.6,"ESC/ERS 2022","p.3651/3691 vascular pruning"),
    ("PRUNING","VASCPHEN","supports",0.6,"ESC/ERS 2022","p.3691"),
    ("PA_CALC","PH","supports",0.4,"ESC/ERS 2022","p.3643"),
    # echo signs
    ("TRV","PH","supports",0.85,"ESC/ERS 2022","p.3645 (>2.8 m/s)"),
    ("RVLV_E","PH","supports",0.7,"ESC/ERS 2022","p.3645 (>1.0, cat A)"),
    ("LVEI","PH","supports",0.65,"ESC/ERS 2022","p.3645 (D-shape)"),
    ("TAPSE","PH","supports",0.6,"ESC/ERS 2022","p.3645 (TAPSE/sPAP)"),
    ("RAAREA","PH","supports",0.55,"ESC/ERS 2022","p.3645 (RA>18cm²)"),
    ("RVOT_AT","PRECAP","supports",0.6,"ESC/ERS 2022","p.3644 (<105ms notch)"),
    ("RVLV_E","SEVERE3","supports",0.6,"ESC/ERS 2022","p.3692 composite score"),
    ("RAAREA","SEVERE3","supports",0.55,"ESC/ERS 2022","p.3692"),
    # hemodynamic risk
    ("RAP","PAH","indicates",0.5,"ESC/ERS 2022","p.3657 risk"),
    ("CI","PAH","indicates",0.55,"ESC/ERS 2022","p.3657 risk"),
    ("SVO2","PAH","indicates",0.5,"ESC/ERS 2022","p.3657 risk"),
    # functional / lab
    ("DLCO","VASCPHEN","supports",0.7,"ESC/ERS 2022","p.3691 (DLCO↓<45%)"),
    ("DLCO","GROUP3","supports",0.6,"ESC/ERS 2022","p.3651"),
    ("PACO2","VASCPHEN","supports",0.55,"ESC/ERS 2022","p.3691 (低PaCO2)"),
    ("BNP","PH","supports",0.55,"ESC/ERS 2022","p.3648/3657"),
    ("BNP","COPD_PH","supports",0.5,"ATS/ERS PH-CLD 2024",""),
    ("VQ","CTEPH","differential",0.85,"ESC/ERS 2022","p.3651 (失配灌注)"),
    # differential edges
    ("GROUP3","PAH","differential",0.6,"ESC/ERS 2022","p.3691 (低DLCO/低氧)"),
    ("CTEPH","PAH","differential",0.6,"ESC/ERS 2022","p.3694 (机化血栓)"),
    ("PH_LHD","PAH","differential",0.55,"ESC/ERS 2022","p.3685 (PAWP)"),
    # source citations
    ("ESC","PH","cites",0.4,"ESC/ERS 2022",""),
    ("GOLD","COPD","cites",0.4,"GOLD 2024",""),
    ("ATS","COPD_PH","cites",0.4,"ATS/ERS PH-CLD 2024",""),
    ("WSPH","PVR","cites",0.4,"PVRI 6th WSPH",""),
    ("HUMBERT","PH","cites",0.4,"Humbert 2022",""),
]

# ---- layout: per-category bands; spread x evenly, gentle y zig to reduce label overlap ----
BANDS = {  # category: (y_base, y_zig)
    "src":     (0.05, 0.0),
    "dz":      (0.30, 0.06),
    "concept": (0.50, 0.05),
    "ct":      (0.66, 0.05),
    "echo":    (0.80, 0.05),
    "hemo":    (0.90, 0.04),
    "func":    (0.72, 0.06),
}
# put func on the right margin column instead of a band to declutter
from collections import defaultdict, Counter
cats = defaultdict(list)
for nid,lab,typ,cat in N: cats[cat].append(nid)

deg = Counter()
ids_set = {n[0] for n in N}
clean_edges = []
for fr,to,rel,w,src,pg in E:
    if fr in ids_set and to in ids_set:
        deg[fr]+=1; deg[to]+=1
        clean_edges.append({"from":fr,"to":to,"rel":rel,"w":w,"src":src,"page":pg})

pos = {}
for cat, members in cats.items():
    if cat == "func":  # right column
        n=len(members)
        for i,nid in enumerate(members):
            pos[nid]=(0.90, 0.20 + i*(0.66/max(1,n-1)) if n>1 else 0.45)
        continue
    if cat == "echo":  # left column lower
        n=len(members)
        for i,nid in enumerate(members):
            pos[nid]=(0.10, 0.34 + i*(0.58/max(1,n-1)) if n>1 else 0.6)
        continue
    yb,zig = BANDS[cat]
    n=len(members)
    for i,nid in enumerate(members):
        x = 0.20 + i*(0.62/max(1,n-1)) if n>1 else 0.5
        y = yb + (zig if i%2 else -zig)
        pos[nid]=(round(x,3), round(min(0.96,max(0.04,y)),3))

TYPE_BASE={"disease":22,"indicator":14,"concept":15,"source":13}
nodes=[]
for nid,lab,typ,cat in N:
    x,y = pos[nid]
    size = TYPE_BASE[typ] + min(12, 2*deg[nid])
    if typ=="disease": size=max(size,22)
    nodes.append({"id":nid,"label":lab,"type":typ,"x":x,"y":y,"size":int(size)})

kg={"nodes":nodes,"edges":clean_edges}
json.dump(kg, open(os.path.join(WORK,"out_kg.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"WROTE out_kg.json  nodes={len(nodes)} edges={len(clean_edges)}")
print("type counts:", dict(Counter(t for _,_,t,_ in N)))
print("top-degree:", [f'{k}:{v}' for k,v in deg.most_common(8)])
