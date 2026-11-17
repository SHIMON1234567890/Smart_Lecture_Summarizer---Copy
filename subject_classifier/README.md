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
| **TF-IDF + logistic regression** (`baseline.py`) | **0.968** | **0.897** |
| DistilBERT fine-tuned (`train_distilbert.ipynb`, 4 epochs, Kaggle T4, 17 min) | 0.948 | 0.861 |

Per-class F1 on test:

| | CS | Math | Chem | Physics | Info Sci | Ling | Econ | Eng |
|---|---|---|---|---|---|---|---|---|
| TF-IDF + LR | 0.986 | 0.903 | 0.929 | 0.850 | 0.565 | 1.000 | 1.000 | 0.941 |
| DistilBERT | 0.974 | 0.883 | 0.928 | 0.847 | 0.474 | 1.000 | 0.880 | 0.900 |

**The simple model wins, so the app uses it.** DistilBERT finds the rare
subjects more often (macro recall 0.942 vs 0.903) but raises far more false
alarms (macro precision 0.814 vs 0.893). Most of them are Computer Science talks
labelled Information Science (precision 0.33), a side effect of weighting rare
classes in the loss. It also reads only the first ~2,000 words (4 × 512 tokens),
while TF-IDF uses 3,000. Things to try next: no or milder class weights,
more pieces per lecture, or a long-context model.

Information Science is the hardest class for both models; it overlaps heavily
with Computer Science. Baseline confusion matrix: `results/baseline.json`.

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
   `subject_classifier/results/distilbert.json`. To make the app use it, start
   it with the environment variable `SUBJECT_MODEL=distilbert`.

## Limitations

- Only 8 subjects, the ones TIB has enough lectures for. Biology, medicine or
  history lectures are forced into one of them; the app shows "Subject unsure"
  below 50% confidence.
- TIB is mostly conference talks; a classroom lecture reads differently.
- The split is random, so talks from the same conference series can appear in
  both train and test. That may flatter the scores, notably the perfect
  Linguistics and Economics results.
