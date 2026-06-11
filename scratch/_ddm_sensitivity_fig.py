"""Generate the DDM fusion-exponent sensitivity figure (Ch4 §4.1.2).
Re-fuses the stored per-node traffic (W_i) and centrality (C_i) at varying alpha
(beta = 1 - alpha) and measures how much the demand surface changes vs the
production (alpha=0.6, beta=0.4) surface."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from utils_simplified import reuse_ddm

ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
nodes = ddm.node_list
W = np.array([ddm.traffic_weights.get(n, 1.0) for n in nodes], float)
C = np.array([ddm.centrality_scores.get(n, 1e-4) for n in nodes], float)
C = np.where(C <= 0, 1e-9, C)


def surf(a):
    s = (W ** a) * (C ** (1 - a))
    return s / s.sum()


Pp = surf(0.6)
k = max(1, int(0.10 * len(nodes)))
topp = set(np.argsort(Pp)[-k:])

alphas = np.round(np.arange(0.10, 0.901, 0.025), 3)
rho, jac = [], []
for a in alphas:
    P = surf(a)
    rho.append(spearmanr(Pp, P).correlation)
    top = set(np.argsort(P)[-k:])
    jac.append(len(topp & top) / len(topp | top))
rho, jac = np.array(rho), np.array(jac)

fig, ax = plt.subplots(figsize=(7, 4.3))
ax.axvspan(0.3, 0.7, color="#cfe8cf", alpha=0.6, zorder=0,
           label="robust band (0.3-0.7)")
ax.plot(alphas, rho, "-o", ms=4, color="#1f77b4",
        label="Spearman rho vs production (0.6/0.4)")
ax.plot(alphas, jac, "-s", ms=4, color="#d62728",
        label="top-10% demand-node Jaccard")
ax.axvline(0.6, ls="--", color="k", lw=1)
ax.text(0.61, 0.735, "production\nalpha = 0.6", fontsize=9)
ax.set_xlabel("traffic exponent  alpha   (centrality exponent  beta = 1 - alpha)")
ax.set_ylabel("similarity to production surface")
ax.set_ylim(0.70, 1.01)
ax.set_xlim(0.10, 0.90)
ax.grid(alpha=0.3)
ax.set_title("DDM demand surface is robust to the fusion exponent",
             fontweight="bold", fontsize=11)
ax.legend(loc="lower center", fontsize=8, framealpha=0.9)
plt.tight_layout()

out = "results_and_discussion/images/ddm_alpha_beta_sensitivity.png"
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches="tight")
plt.close()

band = (alphas >= 0.3) & (alphas <= 0.7)
print("saved", out)
print("over alpha in [0.3,0.7]: rho %.4f-%.4f, jaccard %.3f-%.3f" % (
    rho[band].min(), rho[band].max(), jac[band].min(), jac[band].max()))
