# makestrangle.py

import numpy as np
import matplotlib.pyplot as plt

# --- LaTeX + serif font setup (must happen before plotting) ---
plt.rcParams['text.usetex'] = True
plt.rcParams['font.family'] = 'serif'

# Increase font size for publication
plt.rcParams['font.size'] = 14      # Base font size for all text
plt.rcParams['axes.labelsize'] = 16 # Axis labels

# Increase line thickness
line_thickness = 4

# Parameters
P = 1        # Premium for Put option
C = 1        # Premium for Call option
K_P = 24     # Strike price for Put option
K_C = 26     # Strike price for Call option
S_min, S_max = 20, 30  # Range of underlying asset prices

# Generate S values
S = np.linspace(S_min, S_max, 400)

# Compute varphi_P(S) = max(K_P - S, 0) - P
varphi_P = np.maximum(K_P - S, 0) - P

# Compute varphi_C(S) = max(S - K_C, 0) - C
varphi_C = np.maximum(S - K_C, 0) - C

# Compute total varphi = varphi_P + varphi_C
varphi = varphi_P + varphi_C

# Find the breakeven points where varphi = 0
# For a strangle with K_P != K_C, the breakeven points are:
# S_breakeven_low = K_P - P - C
# S_breakeven_high = K_C + P + C
S_breakeven_low = K_P - P - C  # 24 - 1 - 1 = 22
S_breakeven_high = K_C + P + C # 26 + 1 + 1 = 28

# Separate by sign of varphi:
#   - Green if varphi >= 0
#   - Red if varphi < 0

# Define separate masks for lower and upper green regions
mask_green_low = (varphi >= 0) & (S <= S_breakeven_low)
mask_green_high = (varphi >= 0) & (S >= S_breakeven_high)
mask_red = (varphi < 0)

green_muted = "#66A266"
red_muted = "#CC6666"

plt.figure(figsize=(6, 4), dpi=300)

# Plot green regions where varphi >= 0 (lower)
plt.plot(S[mask_green_low], varphi[mask_green_low],
         color=green_muted, linewidth=line_thickness)

# Plot red regions where varphi < 0
plt.plot(S[mask_red], varphi[mask_red],
         color=red_muted, linewidth=line_thickness)

# Plot green regions where varphi >= 0 (upper)
plt.plot(S[mask_green_high], varphi[mask_green_high],
         color=green_muted, linewidth=line_thickness)

# Add a single thin black horizontal line at varphi = 0
plt.axhline(0, color='black', linewidth=0.8, linestyle='-')

# Add left-pointing triangle marker at S_breakeven_low
plt.plot(S_breakeven_low, 0, color='black', marker='<', markersize=16, 
         linestyle='None', zorder=5)

# Add right-pointing triangle marker at S_breakeven_high
plt.plot(S_breakeven_high, 0, color='black', marker='>', markersize=16, 
         linestyle='None', zorder=5)

# Labels with (USD)
plt.xlabel(r'$S$ (USD)')
plt.ylabel(r'$\varphi(S)$ (USD)')

# X-axis limits
plt.xlim([S_min, S_max])

# Optional: Remove the legend since markers have no labels
# plt.legend()

# Tight layout for nicer spacing
plt.tight_layout()

# Save & Show
plt.savefig('strangle.pdf', bbox_inches='tight')
# plt.show()