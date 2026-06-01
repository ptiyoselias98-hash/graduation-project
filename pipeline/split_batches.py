# -*- coding: utf-8 -*-
"""Split the 260 cases into small batch files (GT stripped -> blind diagnosis) for the
Claude debate workflow. Also export the KG node list. chunks.jsonl already on disk."""
import json, os
WORK = r"C:\Users\cheng\graphrag_pulmo"
BATCHDIR = os.path.join(WORK, "batches")
os.makedirs(BATCHDIR, exist_ok=True)
for f in os.listdir(BATCHDIR):
    os.remove(os.path.join(BATCHDIR, f))

cases = json.load(open(os.path.join(WORK, "out_cases_all.json"), encoding="utf-8"))["cases"]
# strip ground_truth so the agents diagnose blind (rf_proba_ph kept as a model prior)
blind = []
for c in cases:
    c2 = {k: v for k, v in c.items() if k != "ground_truth"}
    blind.append(c2)

BS = 5
nb = 0
for i in range(0, len(blind), BS):
    batch = blind[i:i+BS]
    json.dump({"batch": nb, "cases": batch},
              open(os.path.join(BATCHDIR, f"batch_{nb:03d}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    nb += 1

kg = json.load(open(os.path.join(WORK, "out_kg.json"), encoding="utf-8"))
nodes = [{"id": n["id"], "label": n["label"], "type": n["type"]} for n in kg["nodes"]]
json.dump(nodes, open(os.path.join(WORK, "out_kg_nodes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("NBATCHES", nb, "| cases", len(blind), "| nodes", len(nodes))
