# -*- coding: utf-8 -*-
"""Clean results figure for README: multi-agent agreement vs ground truth + fallback."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
# pick a CJK-capable font if available
for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyhbd.ttc"]:
    try:
        font_manager.fontManager.addfont(fp); plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name(); break
    except Exception: pass
plt.rcParams["axes.unicode_minus"] = False

labels = ["总体一致率\n(234/260)", "COPD-PH 召回\n(146/160)", "COPD 召回\n(88/100)", "Fallback 兜底率\n(39/260)"]
vals = [90.0, 91.2, 88.0, 15.0]
colors = ["#2563eb", "#3b82f6", "#60a5fa", "#f59e0b"]

fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=160)
bars = ax.barh(range(len(labels)), vals, color=colors, height=0.62)
ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=11)
ax.invert_yaxis()
ax.set_xlim(0, 100); ax.set_xlabel("百分比 (%)", fontsize=11)
for i, v in enumerate(vals):
    ax.text(v + 1.5, i, f"{v:.1f}%", va="center", fontsize=12, fontweight="bold", color="#1e293b")
ax.set_title("基于指南的 GraphRAG 多智能体诊断 · 全 260 例 vs 金标准",
             fontsize=13, fontweight="bold", pad=12)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", alpha=0.25)
fig.text(0.99, 0.01, "结构判别器 RF: macro-F1 0.933 · AUC 0.976 (5-fold CV, n=260)",
         ha="right", fontsize=8.5, color="#64748b")
plt.tight_layout()
plt.savefig(r"C:\Users\cheng\graphrag_pulmo\docs_img\results.png", bbox_inches="tight")
print("wrote docs_img/results.png")
