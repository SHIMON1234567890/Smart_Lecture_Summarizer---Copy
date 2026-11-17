"""How good are the app's summaries? Scores them against human-written abstracts.

Data: N random lectures (transcripts up to --max-words words) from the TEST split of TIB (gigant/tib). Each has a
Whisper transcript (the same model the app uses) and the abstract its speaker
wrote, which serves as the reference summary.

Systems compared:
  lead_200      first 200 words of the transcript (simple baseline)
  app           the app's summarizer, exactly as in production
                (BART-large-CNN on ~500-word chunks + grammar polish), bullets removed
  app_first200  the app's summary cut to its first 200 words, to separate content
                from length (references are ~150 words; app summaries are longer)

Metrics: ROUGE-1/2/L F1 (word overlap, with stemming) and BERTScore F1 (meaning
overlap, distilbert-base-uncased), with 95% bootstrap confidence intervals.

Run from the project root (BART is slow on a CPU: roughly 1 minute per lecture):
    .venv\\Scripts\\python summary_eval\\evaluate.py           # 20 lectures, up to 6,000 words
    .venv\\Scripts\\python summary_eval\\evaluate.py --n 5     # quick try
Summaries are cached in summary_eval/results/summaries.jsonl, so a stopped run resumes.
"""
import argparse
import gc
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent
RESULTS = HERE / "results"
CACHE = RESULTS / "summaries.jsonl"
SEED = 42
LEAD_WORDS = 200
SYSTEMS = ["lead_200", "app", "app_first200"]
sys.path.insert(0, str(ROOT))


def pick_lectures(n, max_words):
    """n random test-split lectures with a usable abstract and a transcript of
    300..max_words words (fixed seed)."""
    from datasets import load_dataset
    test = load_dataset("gigant/tib", split="test").select_columns(["doi", "title", "abstract", "transcript"])
    ok = [i for i, (a, t) in enumerate(zip(test["abstract"], test["transcript"]))
          if a and t and len(a.split()) >= 40 and 300 <= len(t.split()) <= max_words]
    chosen = random.Random(SEED).sample(ok, n)
    return [test[i] for i in chosen]


def first_words(text, k):
    return " ".join(text.split()[:k])


def plain(summary):
    """The app's bullet-point summary as plain text."""
    lines = [ln.strip().lstrip("•-").strip() for ln in summary.splitlines()]
    return " ".join(ln for ln in lines if ln and not ln.startswith("#"))


def make_summaries(lectures):
    done = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["doi"]] = row

    todo = [lec for lec in lectures if lec["doi"] not in done]
    if todo:
        from app.ai.summarizer_service import summarize_text
        with CACHE.open("a", encoding="utf-8") as f:
            for k, lec in enumerate(todo, 1):
                t = time.time()
                app = plain(summarize_text(lec["transcript"], summary_type="bullet_points"))
                row = {
                    "doi": lec["doi"], "title": lec["title"], "reference": lec["abstract"],
                    "transcript_words": len(lec["transcript"].split()),
                    "lead_200": first_words(lec["transcript"], LEAD_WORDS),
                    "app": app, "app_first200": first_words(app, LEAD_WORDS),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                done[lec["doi"]] = row
                print(f"[{k}/{len(todo)}] {time.time() - t:5.0f}s  {row['transcript_words']:>6} words -> "
                      f"{len(app.split())} word summary  | {lec['title'][:60]}", flush=True)
        del summarize_text
        sys.modules.pop("app.ai.summarizer_service", None)
        gc.collect()  # free BART before loading the BERTScore model
    return [done[lec["doi"]] for lec in lectures]


def bootstrap_ci(values, reps=2000):
    values = np.asarray(values)
    rng = np.random.default_rng(SEED)
    means = values[rng.integers(0, len(values), (reps, len(values)))].mean(1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--max-words", type=int, default=6000,
                    help="skip longer transcripts: BART needs ~1 min per 1,500 words on a laptop CPU")
    args = ap.parse_args()
    n = args.n
    RESULTS.mkdir(parents=True, exist_ok=True)

    print(f"Picking {n} test lectures ...", flush=True)
    rows = make_summaries(pick_lectures(n, args.max_words))
    refs = [r["reference"] for r in rows]

    from rouge_score import rouge_scorer
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeLsum"], use_stemmer=True)
    from bert_score import score as bertscore

    per = {}  # system -> metric -> [per-lecture value]
    for system in SYSTEMS:
        cands = [r[system] for r in rows]
        m = {"rouge1": [], "rouge2": [], "rougeL": []}
        for c, ref in zip(cands, refs):
            s = scorer.score(ref, c)
            m["rouge1"].append(s["rouge1"].fmeasure)
            m["rouge2"].append(s["rouge2"].fmeasure)
            m["rougeL"].append(s["rougeLsum"].fmeasure)
        _, _, f1 = bertscore(cands, refs, model_type="distilbert-base-uncased", verbose=False)
        m["bertscore"] = f1.tolist()
        m["words"] = [len(c.split()) for c in cands]
        per[system] = m

    metrics = ["rouge1", "rouge2", "rougeL", "bertscore"]
    report = {"n": len(rows), "seed": SEED, "max_transcript_words": args.max_words, "reference_words_mean": float(np.mean([len(x.split()) for x in refs])),
              "transcript_words_mean": float(np.mean([r["transcript_words"] for r in rows])), "systems": {}}
    for system in SYSTEMS:
        report["systems"][system] = {
            "words_mean": float(np.mean(per[system]["words"])),
            **{k: {"mean": float(np.mean(per[system][k])), "ci95": bootstrap_ci(per[system][k])} for k in metrics},
        }
    # Paired comparison: does the app beat the lead baseline on the same lectures?
    report["app_minus_lead"] = {}
    for system in ("app", "app_first200"):
        report["app_minus_lead"][system] = {}
        for k in metrics:
            diff = np.array(per[system][k]) - np.array(per["lead_200"][k])
            report["app_minus_lead"][system][k] = {"mean": float(diff.mean()), "ci95": bootstrap_ci(diff),
                                                   "app_wins": int((diff > 0).sum())}
    (RESULTS / "summary_eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Readable table
    names = {"lead_200": "Lead-200 (first 200 words)", "app": "App summarizer (full)",
             "app_first200": "App summarizer, first 200 words"}
    lines = [f"Lectures: {report['n']} (TIB test split, seed {SEED}, transcripts up to {args.max_words:,} words); "
             f"transcripts {report['transcript_words_mean']:.0f} "
             f"words on average, reference abstracts {report['reference_words_mean']:.0f} words.", "",
             "| system | words | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore |", "|---|---|---|---|---|---|"]
    for system in SYSTEMS:
        s = report["systems"][system]
        cells = [f"{s[k]['mean']:.3f} ({s[k]['ci95'][0]:.3f}–{s[k]['ci95'][1]:.3f})" for k in metrics]
        lines.append(f"| {names[system]} | {s['words_mean']:.0f} | " + " | ".join(cells) + " |")
    lines += ["", "Difference vs Lead-200 on the same lectures (mean, 95% CI, lectures won):", ""]
    for system in ("app", "app_first200"):
        d = report["app_minus_lead"][system]
        lines.append(f"- {names[system]}: " + "; ".join(
            f"{k} {d[k]['mean']:+.3f} ({d[k]['ci95'][0]:+.3f} to {d[k]['ci95'][1]:+.3f}), wins {d[k]['app_wins']}/{report['n']}"
            for k in metrics))
    table = "\n".join(lines)
    (RESULTS / "summary_eval.md").write_text(table + "\n", encoding="utf-8")
    print("\n" + table)


if __name__ == "__main__":
    main()
