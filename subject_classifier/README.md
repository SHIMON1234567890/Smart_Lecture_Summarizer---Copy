# Lecture subject classifier

Reads a lecture transcript and predicts its subject. The app uses it to tag
every summary and, with **Folder → Auto: by subject**, to file it in a folder
named after the subject.

## Data

[TIB](https://huggingface.co/datasets/gigant/tib): 9,103 English academic talks
and lectures with Whisper transcripts and a `subject` label. `data.py` keeps the
lectures with exactly one subject from 8 classes, then makes a fixed, stratified
70/15/15 split (seed 42):

| | Computer Science | Mathematics | Chemistry | Physics | Information Science | Linguistics | Economics & Social Sci. | Engineering | total |
|---|---|---|---|---|---|---|---|---|---|
| train | 1,000 (capped) | 258 | 235 | 172 | 104 | 71 | 53 | 41 | 1,934 |
| valid | 1,097 | 55 | 50 | 37 | 22 | 15 | 11 | 9 | 1,296 |
| test  | 1,097 | 55 | 50 | 37 | 22 | 15 | 11 | 9 | 1,296 |

80% of TIB is Computer Science, so training caps it at 1,000 examples, and the
main score is **macro-F1** (every subject counts equally). Validation and test
keep the real mix.

## Results (test split, 1,296 lectures)

| model | accuracy | macro-F1 |
|---|---|---|
| Majority class (always "Computer Science") | 0.847 | 0.115 |
| TF-IDF + logistic regression (`baseline.py`) | 0.968 | 0.897 |
| DistilBERT fine-tuned (`train_distilbert.ipynb`) | *run on Kaggle* | *run on Kaggle* |

Weakest class for the baseline: Information Science (F1 0.57), often confused
with Computer Science. Full per-class scores and confusion matrices are in
`results/`.

## Reproduce

```
.venv\Scripts\python subject_classifier\baseline.py      # ~3 min on a laptop CPU
```

DistilBERT on Kaggle (free GPU):
1. kaggle.com → **Create → New Notebook → File → Import Notebook**, choose `train_distilbert.ipynb`.
2. Right panel: **Accelerator → GPU T4 x2**, **Internet → On**.
3. **Run All** (about 15–25 min).
4. From the **Output** tab download `subject-distilbert.zip` and `results_distilbert.json`.
5. Unzip into `subject_classifier/models/distilbert/` and save the JSON as
   `subject_classifier/results/distilbert.json`. The app switches to it automatically.

## Limitations

- Only 8 subjects, the ones TIB has enough lectures for. Biology, medicine or
  history lectures are forced into one of them; the app shows "Subject unsure"
  below 50% confidence.
- TIB is mostly conference talks; a classroom lecture reads differently.
- The split is random, so talks from the same conference series can appear in
  both train and test. That may flatter the scores, notably the perfect
  Linguistics and Economics results.
