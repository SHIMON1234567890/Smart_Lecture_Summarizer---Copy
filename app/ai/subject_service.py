"""Predicts a lecture's subject from its transcript.

Uses the TF-IDF + logistic-regression model (subject_classifier/models/tfidf_logreg.joblib),
which scored best on the test split (macro-F1 0.897 vs 0.861 for fine-tuned DistilBERT;
see subject_classifier/README.md). Set SUBJECT_MODEL=distilbert to use the DistilBERT
model instead, after unzipping it into subject_classifier/models/distilbert/.
"""
import json
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = os.path.join(ROOT, "subject_classifier", "models")
DISTILBERT_DIR = os.path.join(MODELS, "distilbert")
TFIDF_PATH = os.path.join(MODELS, "tfidf_logreg.joblib")
MAX_WORDS = 3000  # same as training

_lock = threading.Lock()
_backend = None  # ("distilbert", (tokenizer, model, settings)) | ("tfidf", pipeline) | ("none", None)


def _load():
    global _backend
    with _lock:
        if _backend is not None:
            return _backend
        want_bert = os.environ.get("SUBJECT_MODEL", "tfidf").lower() == "distilbert"
        if want_bert and os.path.exists(os.path.join(DISTILBERT_DIR, "config.json")):
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            settings = {"max_len": 512, "chunks_per_lecture": 4}
            settings_path = os.path.join(DISTILBERT_DIR, "inference.json")
            if os.path.exists(settings_path):
                settings.update(json.load(open(settings_path, encoding="utf-8")))
            tok = AutoTokenizer.from_pretrained(DISTILBERT_DIR)
            model = AutoModelForSequenceClassification.from_pretrained(DISTILBERT_DIR).eval()
            _backend = ("distilbert", (tok, model, settings))
        elif os.path.exists(TFIDF_PATH):
            import joblib
            _backend = ("tfidf", joblib.load(TFIDF_PATH))
        else:
            _backend = ("none", None)
        return _backend


def _distilbert_probs(text, tok, model, settings):
    import torch
    body = settings["max_len"] - 2
    ids = tok(text, add_special_tokens=False, truncation=False)["input_ids"]
    pieces = [ids[s:s + body] for s in range(0, min(len(ids), body * settings["chunks_per_lecture"]), body)]
    pieces = [p for i, p in enumerate(pieces) if i == 0 or len(p) >= 62] or [[]]
    batch = tok.pad({"input_ids": [[tok.cls_token_id] + p + [tok.sep_token_id] for p in pieces]},
                    return_tensors="pt")
    with torch.no_grad():
        probs = torch.softmax(model(**batch).logits, dim=-1).mean(0)
    labels = [model.config.id2label[i] for i in range(len(probs))]
    return dict(zip(labels, probs.tolist()))


def predict_subject(text):
    """Return {"subject", "confidence", "top": [(subject, prob), ...], "model"} or None."""
    words = (text or "").split()
    if len(words) < 30:
        return None
    text = " ".join(words[:MAX_WORDS])

    name, backend = _load()
    if name == "distilbert":
        probs = _distilbert_probs(text, *backend)
    elif name == "tfidf":
        probs = dict(zip(backend.classes_, backend.predict_proba([text])[0].tolist()))
    else:
        return None

    top = sorted(((str(k), float(v)) for k, v in probs.items()), key=lambda kv: kv[1], reverse=True)[:3]
    return {"subject": top[0][0], "confidence": round(top[0][1], 3),
            "top": [(k, round(v, 3)) for k, v in top], "model": name}
