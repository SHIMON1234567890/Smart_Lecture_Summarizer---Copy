"""Builds the subject-classification dataset from TIB (gigant/tib).

Every TIB record has a `subject` field, sometimes several subjects separated by
newlines. We keep lectures with exactly ONE subject from the classes below
(each has at least ~50 single-subject lectures), pool TIB's own splits, and make
a fixed, stratified 70 / 15 / 15 train / validation / test split.

80% of TIB is Computer Science, so the TRAINING split caps Computer Science at
CS_TRAIN_CAP examples; validation and test keep the natural mix.

This file is self-contained so the Kaggle notebook can copy it unchanged.
"""
import random
from collections import Counter

CLASSES = [
    "Computer Science",
    "Mathematics",
    "Chemistry",
    "Physics",
    "Information Science",
    "Linguistics",
    "Economics and Social Sciences",
    "Engineering",
]
MAX_WORDS = 3000       # enough text for any model here; keeps memory low
CS_TRAIN_CAP = 1000
SEED = 42


def load_examples():
    """[(text, label)] for single-subject lectures in CLASSES, read row by row."""
    from datasets import load_dataset

    ds = load_dataset("gigant/tib")
    examples = []
    for split in ds:
        for row in ds[split].select_columns(["transcript", "subject"]):
            subject = (row["subject"] or "").strip()
            text = (row["transcript"] or "").split()
            if subject in CLASSES and len(text) >= 100:
                examples.append((" ".join(text[:MAX_WORDS]), subject))
    return examples


def split_examples(examples):
    """Stratified 70/15/15 split with a fixed seed, then cap CS in train only."""
    rng = random.Random(SEED)
    by_label = {}
    for ex in examples:
        by_label.setdefault(ex[1], []).append(ex)

    train, valid, test = [], [], []
    for label in CLASSES:
        items = by_label.get(label, [])
        rng.shuffle(items)
        n_test = round(len(items) * 0.15)
        n_valid = round(len(items) * 0.15)
        test += items[:n_test]
        valid += items[n_test:n_test + n_valid]
        train += items[n_test + n_valid:]

    cs = [ex for ex in train if ex[1] == "Computer Science"]
    rest = [ex for ex in train if ex[1] != "Computer Science"]
    rng.shuffle(cs)
    train = rest + cs[:CS_TRAIN_CAP]

    for part in (train, valid, test):
        rng.shuffle(part)
    return train, valid, test


def load_splits():
    return split_examples(load_examples())


if __name__ == "__main__":
    train, valid, test = load_splits()
    for name, part in (("train", train), ("valid", valid), ("test", test)):
        counts = Counter(label for _, label in part)
        print(f"{name}: {len(part)}  " + ", ".join(f"{k}: {counts[k]}" for k in CLASSES))
