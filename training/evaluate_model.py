
import os
import json
import argparse
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


def calculate_ngram_overlaps(hypothesis, reference, n=1):
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()

    if len(hyp_tokens) < n or len(ref_tokens) < n:
        return 0.0, 0.0, 0.0

    hyp_ngrams = [tuple(hyp_tokens[i:i + n]) for i in range(len(hyp_tokens) - n + 1)]
    ref_ngrams = [tuple(ref_tokens[i:i + n]) for i in range(len(ref_tokens) - n + 1)]

    hyp_count = len(hyp_ngrams)
    ref_count = len(ref_ngrams)

    overlap = sum(1 for gram in hyp_ngrams if gram in ref_ngrams)

    precision = overlap / hyp_count if hyp_count > 0 else 0.0
    recall = overlap / ref_count if ref_count > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return precision, recall, f1


def evaluate_summary_sample(model, tokenizer, item, device):
    style = item.get("summary_type", "bullet_points")
    transcript = item.get("transcript", "")
    target = item.get("target_summary", "")

    prompt = f"summarize ({style}): {transcript}"

    inputs = tokenizer(
        prompt,
        max_length=1024,
        truncation=True,
        return_tensors="pt"
    ).to(device)

    with torch.no_grad():
        summary_ids = model.generate(
            inputs["input_ids"],
            max_length=200,
            min_length=30,
            num_beams=4,
            length_penalty=1.0,
            early_stopping=True
        )

    prediction = tokenizer.decode(summary_ids[0], skip_special_tokens=True)

    _, _, r1 = calculate_ngram_overlaps(prediction, target, n=1)
    _, _, r2 = calculate_ngram_overlaps(prediction, target, n=2)

    return {
        "style": style,
        "topic": item.get("topic", "General"),
        "target": target,
        "prediction": prediction,
        "rouge1": r1,
        "rouge2": r2
    }


def evaluate(model_path="training/saved_model", data_path="training/data/dataset.json"):
    print("=" * 65)
    print("=== Evaluating Multi-Style Summarizer Model ===")
    print("=" * 65)

    if not os.path.exists(model_path):
        print(f"[NOTE] Model path '{model_path}' not found! Falling back to 'facebook/bart-large-cnn'...")
        model_path = "facebook/bart-large-cnn"


    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Dataset file '{data_path}' not found.")

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        samples = data.get("samples", [])

    print(f"Evaluating {len(samples)} samples on model: {model_path}")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    total_r1 = 0.0
    total_r2 = 0.0

    print("-" * 65)
    for i, sample in enumerate(samples, 1):
        res = evaluate_summary_sample(model, tokenizer, sample, device)
        total_r1 += res["rouge1"]
        total_r2 += res["rouge2"]

        print(f"\n[{i}/{len(samples)}] Style: {res['style'].upper()} | Topic: {res['topic']}")
        print(f"ROUGE-1 F1: {res['rouge1']:.4f} | ROUGE-2 F1: {res['rouge2']:.4f}")
        print("Generated Output:")
        print(res["prediction"][:200] + ("..." if len(res["prediction"]) > 200 else ""))
        print("-" * 65)

    avg_r1 = total_r1 / len(samples) if samples else 0
    avg_r2 = total_r2 / len(samples) if samples else 0

    print("\n" + "=" * 65)
    print("=== FINAL EVALUATION RESULTS ===")
    print(f"Average ROUGE-1 F1 Score: {avg_r1:.4f}")

    print(f"Average ROUGE-2 F1 Score: {avg_r2:.4f}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate multi-style lecture summarizer")
    parser.add_argument("--model", type=str, default="training/saved_model", help="Path to model directory or HuggingFace ID")
    parser.add_argument("--data", type=str, default="training/data/dataset.json", help="Path to evaluation dataset")

    args = parser.parse_args()
    evaluate(model_path=args.model, data_path=args.data)
