import pstats

with open('profile_report.txt', 'w') as f:
    stats = pstats.Stats('profile_output.prof', stream=f)
    stats.sort_stats('cumtime')
    stats.print_stats(30)