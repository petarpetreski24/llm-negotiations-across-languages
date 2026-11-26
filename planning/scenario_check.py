"""Quick calibration of the draft 'Ostra River' scenario: outcome space, Pareto frontier, Nash point, ZOPA size."""
import itertools

ISSUES = {
    "filling":      ["3 yrs", "5 yrs", "7 yrs", "10 yrs", "15 yrs"],
    "release":      ["25 bcm", "30 bcm", "35 bcm", "40 bcm", "45 bcm"],
    "compensation": ["$0", "$100M", "$250M", "$500M", "$1000M"],
    "electricity":  ["0%", "10%", "20%", "30%", "40%"],
    "monitoring":   ["none", "annual reports", "real-time portal", "joint tech commission", "commission+observers"],
    "communique":   ["recognizes rights", "acknowledges use", "takes note", "equitable utilization", "no reference"],
}
# points per option (each party's issue maxima sum to 100)
A = {  # Aldoria, upstream
    "filling": [25, 19, 13, 7, 0], "release": [20, 15, 10, 5, 0], "compensation": [25, 20, 14, 7, 0],
    "electricity": [5, 4, 3, 1, 0], "monitoring": [3, 5, 7, 10, 0], "communique": [0, 4, 8, 15, 12],
}
V = {  # Veskaria, downstream
    "filling": [0, 4, 8, 12, 15], "release": [0, 8, 15, 23, 30], "compensation": [0, 1, 2, 4, 5],
    "electricity": [0, 6, 12, 19, 25], "monitoring": [0, 3, 6, 10, 8], "communique": [15, 11, 7, 0, 3],
}
assert sum(max(v) for v in A.values()) == 100 and sum(max(v) for v in V.values()) == 100

names = list(ISSUES)
deals = []
for combo in itertools.product(range(5), repeat=len(names)):
    ua = sum(A[n][i] for n, i in zip(names, combo))
    uv = sum(V[n][i] for n, i in zip(names, combo))
    deals.append((combo, ua, uv))
print(f"deals: {len(deals)}")

# Pareto frontier
pareto = [d for d in deals if not any((o[1] >= d[1] and o[2] >= d[2]) and (o[1] > d[1] or o[2] > d[2]) for o in deals)]
pts = sorted({(d[1], d[2]) for d in pareto})
print(f"pareto-optimal deals: {len(pareto)}  distinct utility points: {len(pts)}")
print("frontier (A, V):", pts)

compromise = (2, 2, 2, 2, 2, 2)
ua = sum(A[n][i] for n, i in zip(names, compromise)); uv = sum(V[n][i] for n, i in zip(names, compromise))
print(f"split-everything deal: A={ua} V={uv} joint={ua+uv}")
best_joint = max(deals, key=lambda d: d[1] + d[2])
print(f"max joint utility: {best_joint[1]+best_joint[2]} at A={best_joint[1]} V={best_joint[2]}")

for ba, bv in [(40, 40), (45, 45), (50, 45), (50, 50)]:
    zopa = [d for d in deals if d[1] >= ba and d[2] >= bv]
    nash = max(zopa, key=lambda d: (d[1] - ba) * (d[2] - bv))
    print(f"BATNA A={ba} V={bv}: ZOPA {len(zopa)/len(deals):.1%} of deals; "
          f"split deal acceptable to both: {ua >= ba and uv >= bv}; "
          f"Nash point A={nash[1]} V={nash[2]} -> " + ", ".join(ISSUES[n][i] for n, i in zip(names, nash[0])))

# how many deals lose on the compatible issue (monitoring != joint commission) yet are otherwise identical: lose-lose check
mon = names.index("monitoring")
print("monitoring option is the same favourite for both parties:",
      max(range(5), key=lambda i: A['monitoring'][i]) == max(range(5), key=lambda i: V['monitoring'][i]))
