# -*- coding: utf-8 -*-
"""Finalize + deploy the 3 real JSON files into the frontend demo data/ dir.
- make kg_retrieval ids unique & readable (KG#<page>-<i>)
- copy cases/kg/debates into the frontend (originals already backed up to data/_backup_orig)"""
import json, os, re, shutil
WORK = r"C:\Users\cheng\graphrag_pulmo"
DATA = r"E:\桌面文件\5月14日下午毕业设计\！！！前端演示\data"

deb = json.load(open(os.path.join(WORK, "out_debates.json"), encoding="utf-8"))
for cid, cd in deb.items():
    for i, r in enumerate(cd["kg_retrieval"], 1):
        m = re.search(r"p\.(\d+)", r.get("source", ""))
        page = m.group(1) if m else str(i)
        r["id"] = f"KG#{page}-{i}"
json.dump(deb, open(os.path.join(WORK, "out_debates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

pairs = [("out_cases.json", "cases.json"), ("out_kg.json", "kg.json"), ("out_debates.json", "debates.json")]
for src, dst in pairs:
    shutil.copyfile(os.path.join(WORK, src), os.path.join(DATA, dst))
    print("deployed", dst, os.path.getsize(os.path.join(DATA, dst)), "bytes")

# quick cross-file integrity: every case id present in debates, every node_id exists in kg
cases = json.load(open(os.path.join(DATA, "cases.json"), encoding="utf-8"))["cases"]
kg_ids = {n["id"] for n in json.load(open(os.path.join(DATA, "kg.json"), encoding="utf-8"))["nodes"]}
miss_dbg = [c["id"] for c in cases if c["id"] not in deb]
bad_node = sorted({r["node_id"] for cd in deb.values() for r in cd["kg_retrieval"] if r["node_id"] not in kg_ids})
print("cases without debate:", miss_dbg or "none")
print("retrieval node_id not in kg:", bad_node or "none")
print("ids sample:", [r["id"] for r in deb["P_2026_0142"]["kg_retrieval"]])
