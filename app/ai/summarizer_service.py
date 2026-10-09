from transformers import pipeline

_summarizer = None


def get_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = pipeline(
            "summarization",
            model="facebook/bart-large-cnn"
        )
    return _summarizer


def summarize_text(text):
    if not text or not text.strip():
        return "No transcript text available to summarize."

    words = text.strip().split()
    total_words = len(words)

    # If the text is very short, BART's min_length requirement might fail
    if total_words < 40:
        return text.strip()

    model = get_summarizer()

    # BART has a max input limit of 1024 tokens (~700-800 words).
    # For lecture transcripts that exceed this, chunk into ~500-word segments.
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

        try:
            result = model(
                chunk,
                max_length=max_len,
                min_length=min_len,
                truncation=True,
                do_sample=False
            )
            summaries.append(result[0]["summary_text"])
        except Exception as e:
            # Fallback for unexpected errors on a chunk
            print(f"Error summarizing chunk: {e}")
            summaries.append(chunk)

    return " ".join(summaries)
