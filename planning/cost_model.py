"""Cost model for the $20 plan. All prices USD per 1M tokens (Claude list prices cached 2026-11-03)."""

HAIKU = {"in": 0.10, "out": 0.50}
SONNET = {"in": 2.00, "out": 10.00}
BATCH = 0.5  # Message Batches discount


def cost(tokens_in, tokens_out, price, batch=False):
    f = BATCH if batch else 1.0
    return f * (tokens_in * price["in"] + tokens_out * price["out"]) / 1e6


def plan(scale=1.0, n_main=40, n_rep=30, rep_personas=1):
    turns = 20                      # messages per negotiation (round limit 10 each, conservative: no early deals)
    in_call = 6000 * scale          # avg input tokens per negotiator call (EN ~5k, RU ~7k incl. prompt, RAG, history)
    out_call = 450 * scale          # message + private JSON state + short plan, thinking off

    cells_main, personas_main = 12, 2
    mt_cells = 4                    # B2, B3, each run with both role assignments
    rt_cells = 2                    # C1, C2 round-trip controls

    runs_main = cells_main * personas_main * n_main
    runs_rep = 8 * rep_personas * n_rep  # A1, A2, B1x2, B2x2, B3x2 with Claude Haiku

    msgs_mt_main = mt_cells * personas_main * n_main * turns
    msgs_mt_rep = mt_cells * rep_personas * n_rep * turns
    msgs_rt = rt_cells * personas_main * n_main * turns
    judged = msgs_mt_main + msgs_mt_rep

    items = {
        "Haiku negotiations (replication)": cost(runs_rep * turns * in_call, runs_rep * turns * out_call, HAIKU),
        "Back-translation (Haiku, batch)": cost(judged * 600 * scale, judged * 400 * scale, HAIKU, batch=True),
        "Error judge (Haiku, batch, low effort)": cost(judged * 3000 * scale, judged * 800 * scale, HAIKU, batch=True),
        "Judge check (Sonnet 5.5 on 150 human-labelled msgs, batch)": cost(150 * 3000 * scale, 150 * 1200 * scale, SONNET, batch=True),
        "Pilot (20 Haiku runs + 300 judged msgs)": cost(20 * turns * in_call, 20 * turns * out_call, HAIKU)
                                                  + cost(300 * 3000 * scale, 300 * 800 * scale, HAIKU, batch=True),
    }
    total = sum(items.values())
    return runs_main, runs_rep, msgs_mt_main + msgs_mt_rep, msgs_rt, items, total


for label, scale in [("expected", 1.0), ("pessimistic (+50% tokens)", 1.5), ("very pessimistic (x2 tokens)", 2.0)]:
    runs_main, runs_rep, judged, msgs_rt, items, total = plan(scale)
    print(f"\n== {label} ==")
    print(f"main runs (Qwen on FINKI, free): {runs_main}; Haiku replication runs: {runs_rep}")
    print(f"translated messages judged: {judged}; round-trip control messages (auto metrics only): {msgs_rt}")
    for k, v in items.items():
        print(f"  {k:60s} ${v:6.2f}")
    print(f"  {'TOTAL API':60s} ${total:6.2f}")

# options that would break the budget
print("\n== reference: things that do NOT fit in $20 ==")
_, _, judged, _, _, _ = plan(1.0)
print(f"Sonnet 5.5 as the main judge (batch): ${cost(judged*3000, judged*1200, SONNET, batch=True):.2f}")
runs_full = 24 * 40
print(f"Haiku on the full grid instead of Qwen (960 runs): ${cost(runs_full*20*6000, runs_full*20*450, HAIKU):.2f}")
mt1_chars = (4 * 2 * 40 * 20 / 2 + 2 * 2 * 40 * 20 * 2 / 2) * 700
print(f"Commercial MT1 characters needed: {mt1_chars/1e6:.1f}M (Azure free tier covers 2M/month; paid ~$10/M beyond)")
