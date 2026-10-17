import os
import re

pipeline = None

try:
    from transformers import pipeline
except ImportError:
    pass

_summarizer = None
_model_source = None


SUMMARY_TYPES = {
    "bullet_points": {
        "name": "Bullet Points & Key Takeaways",
        "description": "Concise high-impact bulleted list of essential points and conclusions."
    },
    "detailed_notes": {
        "name": "Comprehensive Study Notes",
        "description": "Multi-section notes with topic headers and in-depth explanations."
    },
    "executive_summary": {
        "name": "Executive Summary / TL;DR",
        "description": "Crisp 2-4 sentence high-level synthesis capturing core findings."
    },
    "exam_prep": {
        "name": "Exam Revision & Q&A",
        "description": "Review questions, key definitions, formulas, and flashcard-style concepts."
    },
    "action_items": {
        "name": "Topics & Actionable Steps",
        "description": "Core topics followed by clear actionable tasks and next steps."
    }
}


def get_summarizer():
    global _summarizer, _model_source
    if pipeline is None:
        raise ImportError("transformers is not installed. Please run: pip install transformers torch")

    if _summarizer is None:

        custom_model_dir = os.path.abspath("training/saved_model")
        if os.path.exists(custom_model_dir) and any(
            os.path.exists(os.path.join(custom_model_dir, f))
            for f in ["config.json", "pytorch_model.bin", "model.safetensors"]
        ):
            print(f"Loading custom fine-tuned model from: {custom_model_dir}")
            _model_source = "custom"
            _summarizer = pipeline("summarization", model=custom_model_dir)
        else:
            print("Loading default base model: facebook/bart-large-cnn")
            _model_source = "bart-large-cnn"
            _summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    return _summarizer


def format_summary_by_style(summary_text, summary_type, original_text=""):
    """
    Format and structure the raw summary according to the selected summary type.
    """
    cleaned = summary_text.strip()

    if summary_type == "bullet_points":
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if len(s.strip()) > 10]
        if not sentences:
            return f"• {cleaned}"
        bullets = [f"• {s}" if not s.startswith("•") and not s.startswith("-") else s for s in sentences]
        return "\n".join(bullets)

    elif summary_type == "detailed_notes":
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if len(s.strip()) > 10]
        if len(sentences) >= 4:
            mid1 = len(sentences) // 3
            mid2 = (len(sentences) * 2) // 3
            part1 = " ".join(sentences[:mid1])
            part2 = " ".join(sentences[mid1:mid2])
            part3 = " ".join(sentences[mid2:])
            return (
                f"### 1. Core Principles\n{part1}\n\n"
                f"### 2. In-Depth Analysis\n{part2}\n\n"
                f"### 3. Key Conclusions & Implications\n{part3}"
            )
        return f"### Comprehensive Lecture Notes\n{cleaned}"

    elif summary_type == "executive_summary":
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if len(s.strip()) > 10]
        concise = " ".join(sentences[:3]) if sentences else cleaned
        return f"**Executive Overview:**\n{concise}"

    elif summary_type == "exam_prep":
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if len(s.strip()) > 10]
        qa_list = []
        for i, s in enumerate(sentences[:5], 1):
            qa_list.append(f"• **Review Point {i}:** {s}")
        qa_section = "\n".join(qa_list) if qa_list else f"• {cleaned}"
        return (
            f"### 🎓 High-Yield Exam Revision Notes\n\n"
            f"**Key Concepts & Flashcards:**\n{qa_section}\n\n"
            f"**💡 Quick Recall Tip:** Review the foundational definitions and their core mechanisms above."
        )

    elif summary_type == "action_items":
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if len(s.strip()) > 10]
        topics = " ".join(sentences[:2]) if len(sentences) >= 2 else cleaned
        items = []
        for i, s in enumerate(sentences[2:6] if len(sentences) >= 3 else sentences, 1):
            items.append(f"{i}. [ ] Review and apply: {s}")
        action_list = "\n".join(items) if items else "1. [ ] Review key concepts from lecture."
        return (
            f"### 📌 Discussion Topics Covered\n{topics}\n\n"
            f"### ✅ Actionable Next Steps & Tasks\n{action_list}"
        )

    return cleaned


try:
    from .grammar_service import correct_grammar_and_polish
except ImportError:
    try:
        from app.ai.grammar_service import correct_grammar_and_polish
    except ImportError:
        def correct_grammar_and_polish(t):
            return t


def summarize_text(text, summary_type="bullet_points"):
    if not text or not text.strip():
        return "No transcript text available to summarize."

    if summary_type not in SUMMARY_TYPES:
        summary_type = "bullet_points"

    # Polish raw speech transcript before summarization to eliminate spoken fillers
    cleaned_transcript = correct_grammar_and_polish(text.strip())

    words = cleaned_transcript.split()
    total_words = len(words)

    # For very short text, format directly
    if total_words < 40:
        formatted = format_summary_by_style(cleaned_transcript, summary_type, text)
        return correct_grammar_and_polish(formatted)

    model = get_summarizer()

    chunk_size = 500
    chunks = [
        " ".join(words[i:i + chunk_size])
        for i in range(0, total_words, chunk_size)
    ]

    summaries = []
    for chunk in chunks:
        chunk_word_count = len(chunk.split())
        max_len = min(150, max(30, int(chunk_word_count * 0.6)))
        min_len = min(30, max(10, int(chunk_word_count * 0.2)))

        input_prompt = f"summarize ({summary_type}): {chunk}" if _model_source == "custom" else chunk

        try:
            result = model(
                input_prompt,
                max_length=max_len,
                min_length=min_len,
                truncation=True,
                do_sample=False
            )
            raw_chunk_summary = result[0]["summary_text"]
            # Apply grammar correction to each chunk summary
            summaries.append(correct_grammar_and_polish(raw_chunk_summary))
        except Exception as e:
            print(f"Error summarizing chunk: {e}")
            summaries.append(chunk)

    raw_combined = " ".join(summaries)
    formatted_summary = format_summary_by_style(raw_combined, summary_type, text)
    
    # Final grammar, capitalization, and punctuation polish pass
    final_summary = correct_grammar_and_polish(formatted_summary)
    return final_summary


