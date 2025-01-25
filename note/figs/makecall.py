# makecall.py

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
C = 1
K_C = 25
S_min, S_max = 24, 27.5

# Generate S values
S = np.linspace(S_min, S_max, 400)

# Compute varphi_C(S) = max(S - K_C, 0) - C
varphi = np.maximum(S - K_C, 0) - C

# Find the point where varphi_C = 0
S_plus = K_C + C  # This is the value of S where varphi_C = 0

# Separate by sign of varphi:
#   - green if varphi >= 0
#   - red if varphi < 0
mask_green = (varphi >= 0)
mask_red = (varphi < 0)

green_muted = "#66A266"
red_muted = "#CC6666"

plt.figure(figsize=(6, 4), dpi=300)

# Plot green (varphi >= 0)
plt.plot(S[mask_green], varphi[mask_green],
         color=green_muted, linewidth=line_thickness,
         label=r'$\varphi_C(S)\,\ge\,0$')

# Plot red (varphi < 0)
plt.plot(S[mask_red], varphi[mask_red],
         color=red_muted, linewidth=line_thickness,
         label=r'$\varphi_C(S)\,<\,0$')

# Add a single thin black grid line at varphi_C = 0
plt.axhline(0, color='black', linewidth=0.8, linestyle='-')

# Add marker for S_plus with higher zorder using plt.plot
plt.plot(S_plus, 0, color='black', marker='>', markersize=16, 
         linestyle='None', label=r'$S_{+}$', zorder=5)  # Right-pointing triangle


# Labels with (\$)
plt.xlabel(r'$S$ (\$)')
plt.ylabel(r'$\varphi_C(S)$ (\$)')

# X-axis limits
plt.xlim([S_min, S_max])

# Add legend (optional, if not already present)
# plt.legend()

# Tight layout for nicer spacing
plt.tight_layout()

# Save & Show
plt.savefig('call.pdf', bbox_inches='tight')
# plt.show()