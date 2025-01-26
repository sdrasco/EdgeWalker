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
P = 1
K_P = 25
S_min, S_max = 22.5, 26

# Generate S values
S = np.linspace(S_min, S_max, 400)

# Compute varphi_P(S) = max(K_P - S, 0) - P
varphi = np.maximum(K_P - S, 0) - P

# Find the point where varphi_P = 0
S_minus = K_P - P  # This is the value of S where varphi_P = 0

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
         label=r'$\varphi_P(S)\,\ge\,0$')

# Plot red (varphi < 0)
plt.plot(S[mask_red], varphi[mask_red],
         color=red_muted, linewidth=line_thickness,
         label=r'$\varphi_P(S)\,<\,0$')

# Add a single thin black grid line at varphi_P = 0
plt.axhline(0, color='black', linewidth=1, linestyle='-', zorder=1)

# Add marker for K_P with higher zorder using plt.plot
plt.plot(K_P, 0, color='black', marker='3', markersize=16, 
         linestyle='None', label=r'$S_{-}$', zorder=0)  

# Add marker for S_minus with higher zorder using plt.plot
plt.plot(S_minus, 0, color='black', marker='<', markersize=16, 
         linestyle='None', label=r'$S_{-}$', zorder=5)  

# # Adjust the label position to be just above the marker
# plt.text(S_minus + 0.3, 0.5, r'$S_{-}$', fontsize=18, ha='left', 
#          va='bottom', zorder=6)  # Positioned above the marker

# Labels with (\$)
plt.xlabel(r'$S$ (\$)')
plt.ylabel(r'$\varphi_P(S)$ (\$)')

# X-axis limits
plt.xlim([S_min, S_max])

# Add legend (optional, if not already present)
# plt.legend()

# Tight layout for nicer spacing
plt.tight_layout()

# Save & Show
plt.savefig('put.pdf', bbox_inches='tight')
# plt.show()