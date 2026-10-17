"""
Fine-Tuning Script for Multi-Style Lecture Summarization
Supports 5 summary types:
1. bullet_points    (Key Takeaways & Bullet Points)
2. detailed_notes   (Comprehensive Study Notes)
3. executive_summary (Executive Summary / TL;DR)
4. exam_prep        (Exam Revision & Q&A)
5. action_items     (Topics & Actionable Steps)
"""

import os
import json
import argparse
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    DataCollatorForSeq2Seq
)
from datasets import Dataset

try:
    from training.data_loader import load_all_training_files
except ImportError:
    from data_loader import load_all_training_files


def load_all_training_data(data_dirs=None):
    if data_dirs is None:
        data_dirs = ["training/data", "training/custom_summaries"]
    return load_all_training_files(data_dirs)



def prepare_dataset(samples, tokenizer, max_input_length=1024, max_target_length=256):
    formatted_inputs = []
    formatted_targets = []

    for item in samples:
        style = item.get("summary_type", "bullet_points")
        transcript = item.get("transcript", "")
        target = item.get("target_summary", "")

        # Prefix style instruction for conditioned seq2seq generation
        prompt = f"summarize ({style}): {transcript}"
        formatted_inputs.append(prompt)
        formatted_targets.append(target)

    hf_dataset = Dataset.from_dict({
        "input_text": formatted_inputs,
        "target_text": formatted_targets
    })

    def preprocess_function(examples):
        model_inputs = tokenizer(
            examples["input_text"],
            max_length=max_input_length,
            truncation=True,
            padding="max_length"
        )
        labels = tokenizer(
            examples["target_text"],
            max_length=max_target_length,
            truncation=True,
            padding="max_length"
        )
        # Replace padding token id's of the labels with -100 so cross-entropy ignores them
        labels["input_ids"] = [
            [(label if label != tokenizer.pad_token_id else -100) for label in label_seq]
            for label_seq in labels["input_ids"]
        ]
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    tokenized_dataset = hf_dataset.map(preprocess_function, batched=True)
    return tokenized_dataset


def train_model(
    model_name="facebook/bart-large-cnn",
    data_dir="training/data",
    output_dir="training/saved_model",
    epochs=3,
    batch_size=1,
    learning_rate=5e-5,
    gradient_accumulation_steps=4
):
    print("=" * 60)
    print("=== Starting Multi-Style Summarizer Training ===")
    print(f"Base model: {model_name}")

    print(f"Output directory: {output_dir}")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Load Data
    samples = load_all_training_data(data_dir)
    if not samples:
        raise ValueError(f"No samples found in {data_dir} to train on!")

    # 2. Load Tokenizer & Model
    print(f"Loading tokenizer and model for: {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    # 3. Tokenize Dataset
    print("Tokenizing dataset with style prompts...")
    tokenized_dataset = prepare_dataset(samples, tokenizer)

    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_fp16 = torch.cuda.is_available()

    print(f"Training on device: {device.upper()} (FP16: {use_fp16})")

    # 4. Training Arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        weight_decay=0.01,
        save_total_limit=1,
        predict_with_generate=True,
        logging_steps=1,
        fp16=use_fp16,
        remove_unused_columns=False,
        report_to="none"
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator
    )

    # 5. Execute Training
    print("Beginning training...")
    trainer.train()

    # 6. Save Model & Tokenizer
    print(f"Saving fine-tuned model and tokenizer to: {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("[SUCCESS] Training complete! The model is saved and ready for inference.")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train multi-style lecture summarizer")
    parser.add_argument("--model", type=str, default="facebook/bart-large-cnn", help="Base pretrained model name")
    parser.add_argument("--data_dir", type=str, default="training/data", help="Directory containing dataset files")
    parser.add_argument("--output_dir", type=str, default="training/saved_model", help="Directory to save fine-tuned model")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=1, help="Per-device batch size")
    parser.add_argument("--lr", type=float, default=5e-5, help="Learning rate")

    args = parser.parse_args()

    train_model(
        model_name=args.model,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr
    )

