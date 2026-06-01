# -*- coding: utf-8 -*-
import json
d = json.load(open(r"C:\Users\cheng\graphrag_pulmo\out_debates.json", encoding="utf-8"))
AG = {"PulmonologistAgent", "CardiologistAgent", "RadiologistAgent"}
CL = {"COPD", "COPD-PH"}; CT = {"Continue", "Complete", "Terminate"}
for cid, cd in d.items():
    assert len(cd["kg_retrieval"]) == 5, (cid, "kg_retrieval!=5")
    for r in cd["kg_retrieval"]:
        for k in ("id", "source", "chunk", "score", "supports", "node_id"):
            assert k in r, (cid, "kgr", k)
        assert isinstance(r["score"], (int, float)), (cid, "score not num")
    for rd in cd["rounds"]:
        for k in ("round", "responses", "vote", "synthesis"):
            assert k in rd, (cid, "round", k)
        for rp in rd["responses"]:
            assert rp["agent"] in AG and rp["claim"] in CL and rp["control"] in CT, (cid, rp.get("agent"), rp.get("claim"), rp.get("control"))
            assert isinstance(rp["confidence"], (int, float)) and isinstance(rp["evidence"], list)
    f = cd["final"]
    for k in ("diagnosis", "confidence", "evidence_chain", "fallback_triggered", "trace_id"):
        assert k in f, (cid, "final", k)
    assert f["diagnosis"] in CL
print("CONTRACT OK for", len(d), "cases")
cb = d["B_2026_0044"]
print("\n--- B_2026_0044 kg_retrieval[0] ---")
print(json.dumps(cb["kg_retrieval"][0], ensure_ascii=False))
print("\n--- B round1 responses ---")
for rp in cb["rounds"][0]["responses"]:
    print(f"  {rp['agent']}: {rp['claim']} conf={rp['confidence']} ctrl={rp['control']}")
    print(f"     ev: {(rp['evidence'][0] if rp['evidence'] else '')}")
print("  vote:", cb["rounds"][0]["vote"])
print("  synthesis:", cb["rounds"][0]["synthesis"][:240])
print("\n--- B final ---")
print(json.dumps(cb["final"], ensure_ascii=False)[:650])
# also show a correct PH case retrieval source/page
print("\n--- P_2026_0142 kg_retrieval sources ---")
for r in d["P_2026_0142"]["kg_retrieval"]:
    print(f"  {r['id']} score={r['score']} node={r['node_id']} | {r['source']} | {r['supports']}")
