# Request: FINKI GPU resources for the MIPRO 2027 study

Draft prepared 26 Nov 2026. Part A goes to the OSC lab (form or ticket), ideally sent by or with the supervisor. Part B is a short message for the supervisor and co-authors. Fill in the bracketed fields before sending.

---

## Part A: request to the Open Science Cloud lab

**Subject:** GPU access request: multilingual LLM negotiation study (MIPRO 2027, paper deadline 21 December 2026)

**Applicants:** [names, FCSE] · **Supervisor:** [name] · **Contact:** [email]

### 1. The research idea

LLM agents increasingly negotiate on behalf of people and organisations, often across language boundaries. Most evaluations, however, run both sides in English, and recent multilingual studies keep both sides in the same language. Real cross-border negotiations often go through translation, with each party working in its own language.

We study whether routing an LLM negotiation through machine translation changes its outcome. Two retrieval-grounded LLM agents with personas negotiate a fictional six-issue water treaty. We compare four kinds of pairing:
- English–English and Russian–Russian negotiations;
- mixed English–Russian pairs connected by two different machine-translation systems;
- pairs where both agents negotiate in English although one is instructed in Russian;
- controls that pass every message through a translation round trip.

Each side has a private score table, so every outcome can be scored exactly: agreement rate, rounds, utility, concession patterns, and misunderstood offers. Every translated message is back-translated and checked for semantic, pragmatic and cultural errors. The question is whether translation acts as a neutral channel or as an extra, unmodelled participant.

### 2. Why FINKI resources

We want the whole study to run on open-weight models hosted at FCSE, with no external AI services:
- no message text leaves the faculty;
- there is no API cost;
- model versions are pinned, so anyone can reproduce the results.

### 3. Models we plan to run

The line-up is proposed and may change after a short pilot; all candidates are open-weight models of similar size.

| Role | Model | Licence | GPU memory (BF16) |
|---|---|---|---|
| Negotiator 1 | Qwen/Qwen3.8-27B | Apache 2.0 | ~56 GB |
| Negotiator 2 and error judge | google/gemma-4-31B-it | Apache 2.0 | ~62 GB |
| Translation system 1 | facebook/nllb-200-3.3B | CC-BY-NC 4.0 (research) | ~7 GB |
| Translation system 2 | tencent/Hy-MT2-7B | Apache 2.0 | ~16 GB |
| Back-translation | google/translategemma-27b-it | Gemma terms (gated) | ~55 GB |
| Retrieval and quality scores | BAAI/bge-m3, Unbabel/wmt22-cometkiwi-da | MIT, CC-BY-NC-SA | ~2 GB each |

All language models are served with vLLM, an open-source server with an OpenAI-compatible API, from an Apptainer image built from a public vLLM or NGC Docker image. Model weights come from Hugging Face.

### 4. Resources requested

| Item | Request |
|---|---|
| GPUs | 4× A100 80 GB on one node (minimum 2), for about 5 days between **3 and 12 December 2026**; a short test slot (a few hours) around 30 Nov – 2 Dec |
| Expected use | About 10–27 hours of one 4-GPU node: a pilot, ~1,900 negotiations, ~13,000 translation checks; the rest is buffer for reruns |
| Storage | About 300 GB in the project folder (model weights ~210 GB, containers ~20 GB, logs and results ~2 GB) |
| Job length | Jobs of up to 24–48 hours |

### 5. Questions

1. Can this work run under an existing allocation of our group or supervisor? If a new application is needed, can it be reviewed before 1 December?
2. What are the SLURM limits (maximum job time, GPUs per user)? Is a reservation possible for 3–12 December?
3. Can a job run a long-lived inference server (vLLM) and connect to it from the same job or the front node?
4. Can we build Apptainer images on the cluster from Docker Hub or NGC, or must we build them elsewhere and upload?
5. Do the GPU nodes have outbound internet access, at least to download weights from Hugging Face? If not, can we download on the front node to shared storage?
6. Is there a storage quota we should plan around?

### 6. Acknowledgement

We will include the OSC lab's required acknowledgement sentence in the paper and in any released code and data.

---

## Part B: message to the supervisor and co-authors

> Hi all, for our MIPRO 2027 paper (deadline 21 Dec) we'll compare negotiations held in the same language with ones held through machine translation (English–Russian), using open models on FINKI GPUs only (proposed: Qwen3.8-27B and Gemma 4 31B as negotiators, NLLB-200 and Hy-MT2-7B as translators, Gemma 4 as the error judge).
>
> Could you help with two things?
> 1. Do we already have a FINKI GPU allocation (OSC lab or another server) this could run under, or should we apply? The draft request is attached.
> 2. Does anyone know a fluent Russian speaker who could give about 10 hours to check Russian prompts and label 150 translated messages (credit in the paper)?
>
> Thanks!
