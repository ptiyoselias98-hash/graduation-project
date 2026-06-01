# -*- coding: utf-8 -*-
"""Merge Claude-auto-extracted entities/relations with the curated backbone into an
auto-built GraphRAG knowledge graph (kg_v2.json). Preserves backbone ids (so debates'
node_id highlighting stays valid). Dedup + normalize + degree-filter + spring layout."""
import json, os, re, html, collections
import networkx as nx
WORK = r"C:\Users\cheng\graphrag_pulmo"
OUT = r"C:\Users\cheng\AppData\Local\Temp\claude\C--Users-cheng\0937ceae-a20c-4823-8e71-73080f136053\tasks\wdv5og7yx.output"

raw = json.load(open(OUT, encoding="utf-8"))
if isinstance(raw, dict) and "result" in raw: raw = raw["result"]
ents = raw["entities"]; rels = raw["relations"]
print("raw:", len(ents), "entities,", len(rels), "relations")

backbone = json.load(open(os.path.join(WORK, "out_kg.json"), encoding="utf-8"))
BB_NODES = {n["id"]: n for n in backbone["nodes"]}

def U(s): return html.unescape(s).strip() if isinstance(s, str) else s
def norm(s):
    s = U(s).lower().replace("：", ":").replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", " ", s).strip(" .,:;")
    return s

# normalized-name -> backbone id (synonym table for the key entities)
ALIAS = {
 "ph": "PH", "pulmonary hypertension": "PH", "pulmonary arterial hypertension": "PAH", "pah": "PAH",
 "mpap": "MPAP", "mean pulmonary arterial pressure": "MPAP", "pap": "MPAP",
 "pvr": "PVR", "pulmonary vascular resistance": "PVR", "pawp": "PAWP", "pulmonary arterial wedge pressure": "PAWP",
 "pa/ao": "PA_AO", "pa/ao ratio": "PA_AO", "pa-ao": "PA_AO", "pa:ao": "PA_AO",
 "rv/lv ratio": "RVLV_CT", "rv/lv": "RVLV_CT", "rv:lv": "RVLV_CT", "rv/lv basal ratio": "RVLV_CT",
 "trv": "TRV", "peak trv": "TRV", "dlco": "DLCO", "paco2": "PACO2", "pao2": "PACO2",
 "cteph": "CTEPH", "group 3 ph": "GROUP3", "group 3": "GROUP3", "group 3 pulmonary hypertension": "GROUP3",
 "copd": "COPD", "copd-ph": "COPD_PH", "emphysema": "EMPHYSEMA", "obstructive lung disease": "COPD",
 "vascular pruning": "PRUNING", "pruning": "PRUNING", "peripheral vascular pruning": "PRUNING",
 "pre-capillary ph": "PRECAP", "precapillary ph": "PRECAP", "post-capillary ph": "POSTCAP", "postcapillary ph": "POSTCAP",
 "exercise ph": "EXPH", "bnp": "BNP", "nt-probnp": "BNP", "bnp/nt-probnp": "BNP",
 "pa diameter": "MPA_CT", "pa enlargement": "MPA_CT", "pulmonary artery diameter": "MPA_CT", "main pa diameter": "MPA_CT",
 "ra area": "RAAREA", "right atrial area": "RAAREA", "tapse": "TAPSE", "tapse/spap ratio": "TAPSE", "tapse/spap": "TAPSE",
 "lvei": "LVEI", "d-shaped lv": "LVEI", "septal flattening": "LVEI", "interventricular septum flattening": "LVEI",
 "rvot at": "RVOT_AT", "rvot notching": "RVOT_AT", "rvot acceleration time": "RVOT_AT",
 "%laa-950": "LAA950", "laa-950": "LAA950", "laa_950": "LAA950", "%laa-856": "LAA856", "laa-856": "LAA856",
 "mld": "MLD", "mean lung density": "MLD", "v/q": "VQ", "v/q scan": "VQ", "ventilation/perfusion scan": "VQ",
 "pa wall calcification": "PA_CALC", "lhd": "PH_LHD", "left heart disease": "PH_LHD", "group 2 ph": "PH_LHD",
 "rap": "RAP", "svo2": "SVO2", "ci": "CI", "cardiac index": "CI", "mpap/co slope": "MPAPCO",
 "rvot wall thickness": "RVOT_W", "bv5": "BV5", "rv/lv ratio (ct)": "RVLV_CT",
 "esc/ers ph 2022": "ESC", "esc/ers 2022 ph guidelines": "ESC", "esc/ers 2022": "ESC",
 "humbert 2022": "HUMBERT", "gold 2024": "GOLD", "pulmonary vascular phenotype": "VASCPHEN",
}

TYPE_MAP = {"disease": "disease", "indicator": "indicator", "concept": "concept", "source": "source",
            "threshold": "indicator", "finding": "concept", "treatment": "concept", "anatomy": "concept"}

# canonical id resolution
new_slug_seen = {}
def slug(name):
    s = re.sub(r"[^a-z0-9]+", "_", U(name).lower()).strip("_")[:24] or "node"
    return "X_" + s

nodes = {}  # id -> {id,label,type}
for nid, n in BB_NODES.items():  # seed with backbone (authoritative ids/labels/types)
    nodes[nid] = {"id": nid, "label": n["label"], "type": n["type"]}

def resolve(name):
    nm = norm(name)
    if nm in ALIAS: return ALIAS[nm]
    # match backbone label/id directly
    for nid, n in BB_NODES.items():
        if norm(n["label"]) == nm or nid.lower() == nm: return nid
    if nm in new_slug_seen: return new_slug_seen[nm]
    sid = slug(name);
    # avoid collision with backbone
    while sid in nodes and sid not in new_slug_seen.values(): sid += "_"
    new_slug_seen[nm] = sid
    return sid

for e in ents:
    nid = resolve(e["name"])
    if nid in BB_NODES: continue  # keep backbone definition
    if nid not in nodes:
        nodes[nid] = {"id": nid, "label": U(e["name"])[:18], "type": TYPE_MAP.get(e.get("type", "concept"), "concept")}

# edges
WMAP = {"defines": 0.9, "subtype_of": 0.9, "splits_severity": 0.85, "supports": 0.7,
        "differentiates": 0.6, "measured_by": 0.6, "associated_with": 0.5, "cites": 0.4}
edge_map = {}
for r in rels:
    a = resolve(r["source"]); b = resolve(r["target"])
    if a == b or a not in nodes or b not in nodes: continue
    rel = U(r.get("relation", "associated_with"))
    key = (a, b, rel)
    if key in edge_map: continue
    edge_map[key] = {"from": a, "to": b, "rel": rel, "w": WMAP.get(rel, 0.55),
                     "page": r.get("page"), "src": "ESC/ERS 2022 PH Guidelines"}
# add backbone edges (preserve)
for e in backbone["edges"]:
    key = (e["from"], e["to"], e.get("rel", "supports"))
    if key not in edge_map:
        edge_map[key] = {"from": e["from"], "to": e["to"], "rel": e.get("rel", "supports"),
                         "w": e.get("w", 0.6), "page": None, "src": e.get("src", "")}
edges = list(edge_map.values())

# degree filter: keep backbone + auto nodes that are in the MAIN connected component with degree>=2
deg = collections.Counter()
for e in edges: deg[e["from"]] += 1; deg[e["to"]] += 1
Gf = nx.Graph(); Gf.add_nodes_from(nodes)
for e in edges: Gf.add_edge(e["from"], e["to"])
ccs = sorted(nx.connected_components(Gf), key=len, reverse=True)
main = ccs[0] if ccs else set()
keep = set(BB_NODES) | {nid for nid in nodes if deg[nid] >= 2 and nid in main}
nodes = {nid: n for nid, n in nodes.items() if nid in keep}
edges = [e for e in edges if e["from"] in nodes and e["to"] in nodes]
deg = collections.Counter()
for e in edges: deg[e["from"]] += 1; deg[e["to"]] += 1

# layout: kamada-kawai (even spread) if connected, else spring fallback
G = nx.Graph()
G.add_nodes_from(nodes.keys())
for e in edges: G.add_edge(e["from"], e["to"], weight=e["w"])
try:
    pos = nx.kamada_kawai_layout(G) if nx.is_connected(G) else nx.spring_layout(G, k=0.7, iterations=300, seed=42)
except Exception:
    pos = nx.spring_layout(G, k=0.7, iterations=300, seed=42)
xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
def nx_(v, lo, hi): return 0.05 + 0.90 * ((v - lo) / (hi - lo) if hi > lo else 0.5)

out_nodes = []
for nid, n in nodes.items():
    p = pos[nid]
    size = 12 + min(18, 2 * deg[nid])
    if n["type"] == "disease": size = max(size, 20)
    out_nodes.append({"id": nid, "label": n["label"], "type": n["type"],
                      "x": round(nx_(p[0], x0, x1), 3), "y": round(nx_(p[1], y0, y1), 3), "size": int(size)})

kg_v2 = {"nodes": out_nodes, "edges": edges}
json.dump(kg_v2, open(os.path.join(WORK, "kg_v2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("kg_v2:", len(out_nodes), "nodes,", len(edges), "edges")
print("type counts:", dict(collections.Counter(n["type"] for n in out_nodes)))
print("backbone preserved:", all(b in nodes for b in BB_NODES), "| top-degree:", [f'{k}:{v}' for k,v in deg.most_common(8)])
# verify debates node_ids still resolve
deb = json.load(open(os.path.join(WORK, "out_debates_all.json"), encoding="utf-8"))
ref = {r["node_id"] for cd in deb.values() for r in cd["kg_retrieval"]}
print("debates node_ids missing from kg_v2:", sorted(ref - set(nodes)) or "none")
