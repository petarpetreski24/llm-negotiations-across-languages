"""Compute and storage estimate for the FINKI-only plan (all models open-weight, on A100 80 GB GPUs).

Volumes follow PLAN.md. Throughput is given as a range because the real numbers depend on how
many negotiations fit in GPU memory at once (KV cache); the pilot measures them.
Run: python planning/compute_model.py
"""

TURNS = 20            # messages per negotiation (10 per side; conservative: no early deals)
PROMPT_TOK = 6000     # average prompt tokens per negotiator call (EN ~5k, RU ~7k)
UNCACHED = 0.2        # share of prompt tokens not served from vLLM's prefix cache
OUT_TOK = 450         # message + private JSON per call, thinking off

RUNS_PER_MODEL = 12 * 2 * 40        # 12 cell variants x 2 persona pairings x 40 repetitions
MODELS = 2                          # Qwen3.8-27B and Gemma 4 31B
MT_MSGS_PER_MODEL = 4 * 2 * 40 * TURNS          # B2, B2-swap, B3, B3-swap
RT_STEPS_PER_MODEL = 2 * 2 * 40 * TURNS * 2     # C1, C2: two translation steps per message
JUDGED = MT_MSGS_PER_MODEL * MODELS             # every translated message in the B cells

# aggregate throughput on ONE A100 for a 27-31B model, tokens/s: (pessimistic, optimistic)
DECODE = (250, 700)      # 250: BF16 weights, few sequences fit; 700: FP8 weights or 2 GPUs
PREFILL = (5000, 10000)


def hours(out_tokens, prefill_tokens, i):
    return (out_tokens / DECODE[i] + prefill_tokens / PREFILL[i]) / 3600


def report():
    out_neg = RUNS_PER_MODEL * TURNS * OUT_TOK
    pre_neg = RUNS_PER_MODEL * TURNS * PROMPT_TOK * UNCACHED
    judge_out, judge_in = JUDGED * 800, JUDGED * 3000
    bt_out, bt_in = JUDGED * 300, JUDGED * 500
    pilot_out, pilot_in = 200 * TURNS * OUT_TOK, 200 * TURNS * PROMPT_TOK * UNCACHED

    print(f"negotiations: {RUNS_PER_MODEL} per model x {MODELS} models = {RUNS_PER_MODEL * MODELS}")
    print(f"translated messages per model: {MT_MSGS_PER_MODEL} (+{RT_STEPS_PER_MODEL} round-trip steps)")
    print(f"messages judged: {JUDGED}\n")
    print(f"{'phase':52s} {'GPU-hours (pessimistic / optimistic)':>36s}")
    rows = [
        ("pilot + translator comparison (~200 runs)", pilot_out, pilot_in),
        ("negotiations, one model (1 GPU, models run in parallel)", out_neg, pre_neg),
        ("error judge, Gemma 4 31B", judge_out, judge_in),
        ("back-translation, TranslateGemma 27B", bt_out, bt_in),
    ]
    for name, o, p in rows:
        print(f"  {name:50s} {hours(o, p, 0):8.1f} / {hours(o, p, 1):5.1f}")
    neg = [hours(out_neg, pre_neg, i) for i in (0, 1)]
    ana = [max(hours(judge_out, judge_in, i), hours(bt_out, bt_in, i)) for i in (0, 1)]
    pil = [hours(pilot_out, pilot_in, i) for i in (0, 1)]
    wall = [pil[i] + neg[i] + ana[i] for i in (0, 1)]
    print(f"\nwall-clock on one 4-GPU node (phases in sequence, jobs in parallel inside a phase): "
          f"{wall[0]:.0f} h pessimistic / {wall[1]:.0f} h optimistic")
    print("  translation (Hy-MT2-7B, NLLB) runs inline on its own GPU and is not the bottleneck\n")

    disk = {
        "Qwen/Qwen3.8-27B (BF16)": 56, "google/gemma-4-31B-it (BF16)": 62, "google/translategemma-27b-it": 55,
        "tencent/Hy-MT2-7B": 16, "facebook/nllb-200-3.3B (fp32 files)": 18, "BAAI/bge-m3": 2.3,
        "Unbabel/wmt22-cometkiwi-da": 2.3, "vLLM container image": 12, "Python env / second container": 8,
        "logs (~150 KB x ~2,100 runs) + cache + analysis": 2,
    }
    for k, v in disk.items():
        print(f"  disk  {k:48s} {v:6.1f} GB")
    print(f"  disk  {'TOTAL':48s} {sum(disk.values()):6.1f} GB  (request 300 GB)")


if __name__ == "__main__":
    report()
