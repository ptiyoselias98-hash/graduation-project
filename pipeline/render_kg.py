# -*- coding: utf-8 -*-
"""Render a kg.json (nodes with x/y/size/type, edges from/to/rel/w) to a PNG for the README."""
import sys, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
    try:
        font_manager.fontManager.addfont(fp); plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name(); break
    except Exception: pass
plt.rcParams["axes.unicode_minus"] = False

src = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\cheng\graphrag_pulmo\out_kg.json"
dst = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\cheng\graphrag_pulmo\docs_img\kg_graph.png"
kg = json.load(open(src, encoding="utf-8"))
nodes = {n["id"]: n for n in kg["nodes"]}
W, H = 1600, 1000
COL = {"disease": "#ef4444", "indicator": "#3b82f6", "concept": "#a855f7", "source": "#10b981",
       "threshold": "#f59e0b", "finding": "#06b6d4"}

fig, ax = plt.subplots(figsize=(16, 10), dpi=130)
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
ax.set_facecolor("#0b1220"); fig.patch.set_facecolor("#0b1220")

def px(n): return 60 + n["x"] * (W - 120), 70 + n["y"] * (H - 140)
# edges
for e in kg["edges"]:
    a, b = nodes.get(e["from"]), nodes.get(e["to"])
    if not a or not b: continue
    x1, y1 = px(a); x2, y2 = px(b)
    w = e.get("w", 0.5)
    ax.plot([x1, x2], [y1, y2], color="#334155", lw=0.5 + 1.6 * w, alpha=0.45, zorder=1)
# nodes
for n in kg["nodes"]:
    x, y = px(n); c = COL.get(n["type"], "#64748b"); s = n.get("size", 16)
    ax.scatter([x], [y], s=(s * 9), c=c, edgecolors="white", linewidths=0.7, zorder=3, alpha=0.95)
    ax.text(x, y + s + 9, n["label"], ha="center", va="top", fontsize=8.2, color="#e2e8f0", zorder=4)
# legend
import matplotlib.patches as mp
present = sorted({n["type"] for n in kg["nodes"]})
handles = [mp.Patch(color=COL.get(t, "#64748b"), label=t) for t in present]
ax.legend(handles=handles, loc="lower right", fontsize=10, framealpha=0.2, labelcolor="#e2e8f0")
ax.set_title(f"指南知识图谱 (GraphRAG)  ·  {len(kg['nodes'])} 节点 / {len(kg['edges'])} 边",
             fontsize=15, fontweight="bold", color="#f1f5f9", pad=14)
plt.tight_layout()
os.makedirs(os.path.dirname(dst), exist_ok=True)
plt.savefig(dst, bbox_inches="tight", facecolor="#0b1220")
print("wrote", dst, "|", len(kg["nodes"]), "nodes", len(kg["edges"]), "edges")
