import pstats

# Load the profile data
p = pstats.Stats('profile_output.prof')

# Sort and print the top 20 lines (or more if desired) by cumulative time
p.sort_stats('cumulative').print_stats(100)

with open("profile_summary.txt", "w") as f:
    p = pstats.Stats('profile_output.prof', stream=f)
    p.sort_stats('cumulative').print_stats(100)