from transformers import pipeline

summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn"
)

# BART reads at most 1024 tokens; ~600 words per chunk stays safely under that.
CHUNK_WORDS = 600


def _chunks(words, size):
    for start in range(0, len(words), size):
        yield " ".join(words[start:start + size])


def _summarize_once(text, max_length=150, min_length=50):
    word_count = len(text.split())
    # Never ask for a summary longer than the input itself.
    max_length = min(max_length, max(20, int(word_count * 0.8)))
    min_length = min(min_length, max_length - 5)

    summary = summarizer(
        text,
        max_length=max_length,
        min_length=min_length,
        do_sample=False,
        truncation=True,
    )

    return summary[0]["summary_text"].strip()


def summarize_text(text):
    words = text.split()

    if len(words) < 40:
        # Too short to summarise meaningfully.
        return text.strip()

    if len(words) <= CHUNK_WORDS:
        return _summarize_once(text)

    # Long lecture: summarise each part, then condense the parts.
    partials = [_summarize_once(chunk, max_length=120, min_length=30)
                for chunk in _chunks(words, CHUNK_WORDS)]
    combined = " ".join(partials)

    if len(combined.split()) <= CHUNK_WORDS:
        return _summarize_once(combined, max_length=220, min_length=80)

    return combined
