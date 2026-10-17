import os
import re
import json
import csv


def parse_text_or_markdown_file(filepath):
    """
    Parses a .txt or .md file that contains lecture transcripts and summaries.
    Supports formats like:
    TRANSCRIPT:
    ...
    SUMMARY:
    ...
    (or LECTURE: ... NOTES: ...)
    """
    samples = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Pattern: TRANSCRIPT: ... SUMMARY: ...
    pattern = re.compile(
        r"(?:TRANSCRIPT|LECTURE|TEXT|INPUT)\s*:\s*(.*?)\s*(?:SUMMARY|NOTES|OUTPUT|TARGET)\s*:\s*(.*?)(?=(?:TRANSCRIPT|LECTURE|TEXT|INPUT)\s*:|$)",
        re.DOTALL | re.IGNORECASE
    )

    matches = pattern.findall(content)
    if matches:
        for trans, summ in matches:
            t = trans.strip()
            s = summ.strip()
            if t and s:
                samples.append({
                    "transcript": t,
                    "target_summary": s,
                    "summary_type": infer_style_from_filename_or_text(filepath, s),
                    "source_file": os.path.basename(filepath)
                })
    else:
        # If no sections, treat the whole content as reference summary text
        cleaned = content.strip()
        if len(cleaned) > 30:
            samples.append({
                "transcript": cleaned,
                "target_summary": cleaned,
                "summary_type": infer_style_from_filename_or_text(filepath, cleaned),
                "source_file": os.path.basename(filepath)
            })

    return samples


def parse_json_file(filepath):
    """
    Parses any JSON file into standard {"transcript", "target_summary", "summary_type"} objects.
    """
    samples = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON from {filepath}: {e}")
            return samples

    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if "samples" in data and isinstance(data["samples"], list):
            items = data["samples"]
        elif "data" in data and isinstance(data["data"], list):
            items = data["data"]
        else:
            items = [data]

    for item in items:
        if not isinstance(item, dict):
            continue

        trans = (
            item.get("transcript") or
            item.get("text") or
            item.get("input") or
            item.get("lecture") or
            item.get("content") or
            ""
        ).strip()

        summ = (
            item.get("target_summary") or
            item.get("summary") or
            item.get("target") or
            item.get("output") or
            item.get("notes") or
            ""
        ).strip()

        style = (
            item.get("summary_type") or
            item.get("style") or
            infer_style_from_filename_or_text(filepath, summ)
        )

        if trans or summ:
            samples.append({
                "transcript": trans or summ,
                "target_summary": summ or trans,
                "summary_type": style,
                "topic": item.get("topic", "Lecture"),
                "source_file": os.path.basename(filepath)
            })

    return samples


def parse_csv_file(filepath):
    """
    Parses CSV files containing transcripts and summaries.
    """
    samples = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_lower = {k.strip().lower(): v for k, v in row.items() if k}
            trans = (
                row_lower.get("transcript") or
                row_lower.get("text") or
                row_lower.get("input") or
                row_lower.get("lecture") or
                ""
            ).strip()

            summ = (
                row_lower.get("target_summary") or
                row_lower.get("summary") or
                row_lower.get("target") or
                row_lower.get("output") or
                ""
            ).strip()

            style = row_lower.get("summary_type") or row_lower.get("style") or "bullet_points"

            if trans and summ:
                samples.append({
                    "transcript": trans,
                    "target_summary": summ,
                    "summary_type": style,
                    "source_file": os.path.basename(filepath)
                })
    return samples


def infer_style_from_filename_or_text(filepath, text):
    """
    Infers the summary style based on the filename or content patterns.
    """
    fname = os.path.basename(filepath).lower()

    if "bullet" in fname or "takeaway" in fname:
        return "bullet_points"
    elif "detail" in fname or "note" in fname:
        return "detailed_notes"
    elif "exec" in fname or "tldr" in fname or "brief" in fname:
        return "executive_summary"
    elif "exam" in fname or "prep" in fname or "qa" in fname or "question" in fname:
        return "exam_prep"
    elif "action" in fname or "task" in fname or "item" in fname:
        return "action_items"

    # Inspect text patterns
    if "###" in text or "1. Core" in text:
        return "detailed_notes"
    elif text.count("•") >= 2 or text.count("\n-") >= 2:
        return "bullet_points"
    elif "[ ]" in text or "Actionable" in text:
        return "action_items"
    elif "Q:" in text or "Flashcard" in text:
        return "exam_prep"

    return "bullet_points"


def load_all_training_files(search_dirs=None):
    """
    Scans directories and loads all training samples from .json, .txt, .md, and .csv files.
    """
    if search_dirs is None:
        search_dirs = [
            "training/data",
            "training/custom_summaries"
        ]

    all_samples = []
    discovered_files = []

    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue

        for root, _, files in os.walk(s_dir):
            for file in files:
                if file.lower().startswith("readme"):
                    continue

                filepath = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()


                file_samples = []
                if ext == ".json":
                    file_samples = parse_json_file(filepath)
                elif ext in [".txt", ".md"]:
                    file_samples = parse_text_or_markdown_file(filepath)
                elif ext == ".csv":
                    file_samples = parse_csv_file(filepath)

                if file_samples:
                    all_samples.extend(file_samples)
                    discovered_files.append((file, len(file_samples)))

    print(f"\nDiscovered {len(discovered_files)} training files:")
    for fname, count in discovered_files:
        print(f"   - {fname}: {count} sample(s)")
    print(f"Total training samples loaded: {len(all_samples)}\n")

    return all_samples

