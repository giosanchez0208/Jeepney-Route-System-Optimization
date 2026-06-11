"""Final-defense figures from final_runs_2:
 (1) convergence_reproducibility.png  -- fast/stable convergence (7 seeds) + cross-run Jaccard matrix
 (2) optimized_network_heatmap.png    -- clean corridor service-intensity map (vs a 38-loop hairball)
"""
import os, sys, glob, json, csv, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection
from collections import Counter

ROOT = "final_runs_2/final results_"
TAGS8 = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"]
IMG = "results_and_discussion/images"
os.makedirs(IMG, exist_ok=True)


def run_dir(tag):
    return glob.glob(os.path.join(ROOT, tag, "opt_*"))[0]


def final_routes_json(rd):
    snaps = sorted(glob.glob(os.path.join(rd, "snapshots", "network_state_gen_*.json")),
                   key=lambda q: int(q.split("_")[-1].split(".")[0]))
    return json.load(open(snaps[-1]))["layers"]["routes"]


def edge_set(rd):
    s = set()
    for r in final_routes_json(rd):
        for a, b in zip(r[:-1], r[1:]):
            s.add(frozenset(((round(a["lon"], 6), round(a["lat"], 6)),
                             (round(b["lon"], 6), round(b["lat"], 6)))))
    return s


# ---------- Figure 1: convergence + reproducibility ----------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
for t in TAGS8:
    h = list(csv.DictReader(open(os.path.join(run_dir(t), "history.csv"))))
    g = [int(r["Generation"]) for r in h]
    b = [float(r["Global_Best_Cost"]) for r in h]
    ax1.plot(g, b, "-", lw=1.6, alpha=0.8, label=t)
ax1.axvline(20, ls="--", color="gray", lw=1)
ax1.text(20.4, ax1.get_ylim()[1], "all seeds plateau\nby gen ~20\n(within 30-gen budget)", va="top", fontsize=9, color="dimgray")
ax1.set_xlabel("generation")
ax1.set_ylabel("global-best Total User Cost")
ax1.set_title("(a) Stable convergence within budget (7 seeds)", fontweight="bold", fontsize=11)
ax1.legend(fontsize=7, ncol=2)
ax1.grid(alpha=0.3)

S = {t: edge_set(run_dir(t)) for t in TAGS8}
n = len(TAGS8)
M = np.eye(n)
for i, a in enumerate(TAGS8):
    for j, b in enumerate(TAGS8):
        if i < j:
            jac = len(S[a] & S[b]) / len(S[a] | S[b])
            M[i, j] = M[j, i] = jac
im = ax2.imshow(M, vmin=0.5, vmax=1.0, cmap="YlGn")
ax2.set_xticks(range(n)); ax2.set_xticklabels(TAGS8, fontsize=8)
ax2.set_yticks(range(n)); ax2.set_yticklabels(TAGS8, fontsize=8)
for i in range(n):
    for j in range(n):
        ax2.text(j, i, "%.2f" % M[i, j], ha="center", va="center", fontsize=7,
                 color="black" if M[i, j] < 0.85 else "white")
mean_off = float(np.mean([M[i, j] for i, j in itertools.combinations(range(n), 2)]))
ax2.set_title("(b) Cross-run reproducibility (mean Jaccard %.2f)" % mean_off, fontweight="bold", fontsize=11)
plt.colorbar(im, ax=ax2, fraction=0.046, pad=0.02)
plt.tight_layout()
plt.savefig(os.path.join(IMG, "convergence_reproducibility.png"), dpi=150, bbox_inches="tight")
plt.close()
print("saved convergence_reproducibility.png  (mean Jaccard %.3f)" % mean_off)

# ---------- Figure 2: clean corridor service-intensity map ----------
from utils_simplified import reuse_citygraph
cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
base = cg.draw(size=1100, only_drivable=False)
(tl_lon, tl_lat), (br_lon, br_lat) = cg.get_bounds()
extent = [tl_lon, br_lon, br_lat, tl_lat]

cnt = Counter()
for r in final_routes_json(run_dir("p1")):
    for a, b in zip(r[:-1], r[1:]):
        cnt[frozenset(((round(a["lon"], 6), round(a["lat"], 6)),
                       (round(b["lon"], 6), round(b["lat"], 6))))] += 1
segs, w = [], []
for key, c in cnt.items():
    (x1, y1), (x2, y2) = tuple(key)
    segs.append([(x1, y1), (x2, y2)]); w.append(c)
w = np.array(w, float)

fig, ax = plt.subplots(figsize=(9, 9))
ax.imshow(base, extent=extent, alpha=0.22, zorder=0)
lc = LineCollection(segs, array=w, cmap="inferno",
                    norm=mcolors.Normalize(vmin=1, vmax=max(w.max(), 2)),
                    linewidths=0.4 + 2.6 * (w / w.max()), alpha=0.85, capstyle="round", zorder=2)
ax.add_collection(lc)
ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
ax.set_aspect("equal"); ax.axis("off")
cb = plt.colorbar(lc, ax=ax, fraction=0.04, pad=0.02)
cb.set_label("number of routes sharing the corridor (service intensity)")
ax.set_title("Optimized Iligan network: corridor service intensity\n(trunk corridors bright/thick, feeders dim/thin)",
             fontweight="bold", fontsize=12)
plt.tight_layout()
plt.savefig(os.path.join(IMG, "optimized_network_heatmap.png"), dpi=150, bbox_inches="tight")
plt.close()
print("saved optimized_network_heatmap.png  (%d unique corridors, max overlap %d routes)" % (len(segs), int(w.max())))
