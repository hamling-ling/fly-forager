"""Draw the satiety hysteresis loop (s -> s_eff) for the README.

s_eff follows s on the way up, latches at 1 when s reaches 1, and
stays at 1 on the way down until s falls to FULL_RELEASE, where it
drops back onto the diagonal. FULL_RELEASE is read from the app
config so the figure follows tuning; re-run after changing it:

    python3 docs/images/satiety_hysteresis.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "src/flyforager_q/python")
)
from config import FULL_RELEASE

for name in ("Noto Sans CJK JP", "Noto Serif CJK JP"):
    if any(name in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break

FR = FULL_RELEASE
fig, ax = plt.subplots(figsize=(3.2, 2.7), dpi=200)

# The diagonal the unlocked state follows.
ax.plot([0, 1], [0, 1], color="0.75", lw=1.0, zorder=1)
# Latched segment: s falls from 1 to FR while s_eff stays 1.
ax.plot([FR, 1], [1, 1], color="tab:blue", lw=2.0, zorder=3)
# The release drop back onto the diagonal.
ax.plot([FR, FR], [FR, 1], color="tab:blue", lw=2.0, zorder=3)
# Direction arrows: up the diagonal, left along the latch, down the drop.
ax.annotate("", xy=(0.32, 0.32), xytext=(0.22, 0.22),
            arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.6))
ax.annotate("", xy=(0.78, 1.0), xytext=(0.9, 1.0),
            arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.6))
ax.annotate("", xy=(FR, 0.78), xytext=(FR, 0.9),
            arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.6))

ax.annotate("ラッチ中\n（$s$ が下がっても 1）", xy=(0.8, 1.0),
            xytext=(0.36, 1.06), fontsize=7.5, ha="center")
ax.annotate("解除", xy=(FR, 0.8), xytext=(FR + 0.05, 0.82), fontsize=7.5)
ax.annotate("$s_{\\mathrm{eff}} = s$", xy=(0.14, 0.3), fontsize=8, rotation=38)

ax.set_xlim(-0.03, 1.03)
ax.set_ylim(-0.03, 1.18)
ax.set_xticks([0, FR, 1])
ax.set_xticklabels(["0", "FULL_RELEASE", "1"], fontsize=7.5)
ax.set_yticks([0, 1])
ax.set_yticklabels(["0", "1"], fontsize=7.5)
ax.set_xlabel("$s$（満腹度）", fontsize=9)
ax.set_ylabel("$s_{\\mathrm{eff}}$（実効満腹度）", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()

out = Path(__file__).with_name("satiety-hysteresis.png")
fig.savefig(out)
print(f"wrote {out} (FULL_RELEASE={FR})")
