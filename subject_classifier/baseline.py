"""Baselines for subject classification: majority class and TF-IDF + logistic regression.

Picks the regularisation strength on the validation split, reports the TEST
split once, and saves the model the app uses until a fine-tuned one exists.

Run from the project root:
    .venv\\Scripts\\python subject_classifier\\baseline.py
"""
import json
import time
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline

from data import CLASSES, load_splits

HERE = Path(__file__).parent
RESULTS = HERE / "results"
MODELS = HERE / "models"
RESULTS.mkdir(exist_ok=True)
MODELS.mkdir(exist_ok=True)


def scores(y_true, y_pred):
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0), 4),
        "per_class_f1": dict(zip(CLASSES, [round(x, 4) for x in f1_score(
            y_true, y_pred, labels=CLASSES, average=None, zero_division=0)])),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist(),
    }


def make_model(c):
    return Pipeline([
        ("tfidf", TfidfVectorizer(sublinear_tf=True, min_df=3, max_df=0.9, ngram_range=(1, 2),
                                  max_features=60000, stop_words="english")),
        ("clf", LogisticRegression(C=c, class_weight="balanced", max_iter=2000)),
    ])


def main():
    train, valid, test = load_splits()
    Xtr, ytr = zip(*train)
    Xva, yva = zip(*valid)
    Xte, yte = zip(*test)
    results = {"classes": CLASSES, "sizes": {"train": len(train), "valid": len(valid), "test": len(test)}}

    # 1) Majority class: always "Computer Science".
    results["majority"] = {"test": scores(yte, ["Computer Science"] * len(yte))}

    # 2) TF-IDF + logistic regression; choose C on validation macro-F1.
    best = None
    for c in (1, 4, 16, 64):
        t = time.time()
        model = make_model(c).fit(Xtr, ytr)
        f1 = f1_score(yva, model.predict(Xva), labels=CLASSES, average="macro")
        print(f"C={c:<3} valid macro-F1 {f1:.3f}  ({time.time() - t:.0f}s)")
        if best is None or f1 > best[0]:
            best = (f1, c, model)

    _, c, model = best
    pred = model.predict(Xte)
    results["tfidf_logreg"] = {"C": c, "valid_macro_f1": round(best[0], 4), "test": scores(yte, pred)}
    print(f"\nChosen C={c}\n")
    print(classification_report(yte, pred, labels=CLASSES, zero_division=0, digits=3))

    joblib.dump(model, MODELS / "tfidf_logreg.joblib", compress=3)
    (RESULTS / "baseline.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    m, b = results["majority"]["test"], results["tfidf_logreg"]["test"]
    print(f"TEST  majority: acc {m['accuracy']:.3f}  macro-F1 {m['macro_f1']:.3f}")
    print(f"TEST  tf-idf  : acc {b['accuracy']:.3f}  macro-F1 {b['macro_f1']:.3f}")


if __name__ == "__main__":
    main()
