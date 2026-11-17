# How good are the summaries?

`evaluate.py` scores the app's summarizer against summaries written by people.

## Setup

- **Lectures:** 20 random lectures from the TEST split of [TIB](https://huggingface.co/datasets/gigant/tib)
  (seed 42), with transcripts of 300–6,000 words (3,782 on average). The limit keeps the run
  to about an hour on a laptop CPU, since BART needs roughly a minute per 1,500 words.
- **Reference:** the abstract each speaker wrote for their talk (163 words on average).
- **Systems:**
  - *Lead-200:* the first 200 words of the transcript, the simplest possible summary.
  - *App:* the app's summarizer exactly as in production (BART-large-CNN on ~500-word
    chunks plus grammar polish).
  - *App, first 200 words:* the app's summary cut to 200 words, to separate content from length.
- **Metrics:**
  - *ROUGE-1 / ROUGE-2 / ROUGE-L:* overlap of words, word pairs and the longest common word sequence.
  - *BERTScore:* similarity of meaning, using `distilbert-base-uncased`.
  - Each mean comes with a 95% bootstrap confidence interval. The paired differences show
    whether the app beats Lead-200 on the same lectures.

## Results

| system | words | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore |
|---|---|---|---|---|---|
| Lead-200 | 200 | 0.288 | 0.044 | 0.136 | 0.746 |
| App (full) | 368 | 0.265 | 0.043 | 0.125 | **0.761** |
| App, first 200 words | 187 | **0.304** | **0.047** | **0.145** | **0.764** |

Difference from Lead-200 on the same lectures (95% CI):

| | ROUGE-1 | ROUGE-L | BERTScore |
|---|---|---|---|
| App (full) | −0.023 (−0.047 to 0.000) | −0.011 (−0.019 to −0.002) | **+0.016 (+0.008 to +0.023)**, better on 15/20 |
| App, first 200 words | +0.016 (−0.013 to +0.044) | +0.010 (−0.003 to +0.023) | **+0.018 (+0.010 to +0.027)**, better on 16/20 |

## What it means

- **Meaning:** the app's summaries are closer in meaning to what the speakers wrote than the
  baseline is. The confidence interval stays above zero, so this is unlikely to be luck.
- **Word overlap:** the app does not beat the baseline. Speakers' abstracts are written
  before the talk, in their own words, so they share few exact words with any summary of the
  transcript, and Lead-200 is known to be hard to beat on ROUGE.
- **Length:** full summaries are more than twice as long as the abstracts, and length costs
  them ROUGE precision. Cut to 200 words they score better on every metric. The clear next
  step is to condense long summaries a second time.

## Limits

- Only 20 lectures, so the intervals are wide.
- No transcripts over 6,000 words. Longer lectures produce even longer summaries
  (a 14,000-word talk gave 1,321 words in a trial run).
- Abstracts are only a rough stand-in for a "perfect" summary of the talk.

## Reproduce

```
.venv\Scripts\python summary_eval\evaluate.py            # ~1 hour
.venv\Scripts\python summary_eval\evaluate.py --n 5      # quick try
```

Summaries are cached in `results/summaries.jsonl`, so a stopped run resumes where it left off.
