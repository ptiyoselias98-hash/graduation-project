# -*- coding: utf-8 -*-
"""Assemble canonical chunks.jsonl (vector-retrieval corpus) from the chunk-extraction
workflow output. HTML-unescape, dedupe, ensure unique chunk_id, write one JSON/line."""
import json, os, html, collections
WORK = r"C:\Users\cheng\graphrag_pulmo"
SRC = r"C:\Users\cheng\AppData\Local\Temp\claude\C--Users-cheng\0937ceae-a20c-4823-8e71-73080f136053\tasks\w33jkf6vc.output"

raw = json.load(open(SRC, encoding="utf-8"))
if isinstance(raw, dict) and "result" in raw and isinstance(raw["result"], dict):
    raw = raw["result"]
chunks_in = raw["chunks"] if isinstance(raw, dict) and "chunks" in raw else raw
print("loaded", len(chunks_in), "chunks")

def clean(s):
    return html.unescape(s).replace(" ", " ").strip() if isinstance(s, str) else s

seen_ids = set()
seen_text = set()
out = []
for c in chunks_in:
    text = clean(c.get("text", ""))
    if not text or len(text) < 40:
        continue
    key = text[:80].lower()
    if key in seen_text:
        continue
    seen_text.add(key)
    cid = c.get("chunk_id") or f"esc_ers_ph_2022::c{len(out)}"
    if cid in seen_ids:
        cid = f"{cid}__{len(out)}"
    seen_ids.add(cid)
    page = c.get("page")
    out.append({
        "chunk_id": cid,
        "text": text,
        "source": clean(c.get("source") or f"ESC/ERS 2022 PH Guidelines, p.{page}"),
        "entities": [clean(e) for e in (c.get("entities") or []) if e],
        "metadata": {"doc": "ESC/ERS PH 2022", "page": page, "section": clean(c.get("section") or "")},
    })

path = os.path.join(WORK, "chunks.jsonl")
with open(path, "w", encoding="utf-8") as fh:
    for c in out:
        fh.write(json.dumps(c, ensure_ascii=False) + "\n")

print("WROTE chunks.jsonl with", len(out), "unique chunks")
pages = sorted({c["metadata"]["page"] for c in out if c["metadata"]["page"]})
print("pages covered:", pages)
print("by section:", dict(collections.Counter(c["metadata"]["section"] for c in out)))
print("sample:", json.dumps(out[0], ensure_ascii=False)[:300])
