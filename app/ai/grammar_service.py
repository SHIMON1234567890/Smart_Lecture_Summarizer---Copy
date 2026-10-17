import re


def remove_spoken_fillers(text):
    """
    Removes conversational speech disfluencies and fillers from transcribed text.
    """
    fillers = [
        r"\b(?:um|uh|er|ah|erm)\b",
        r"\b(?:you know|sort of|kind of|like I mean|like you know)\b",
        r"\b(?:so basically|basically speaking|as I said earlier)\b"
    ]
    cleaned = text
    for pattern in fillers:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove stutter repetitions (e.g. "the the" -> "the", "we we" -> "we")
    cleaned = re.sub(r"\b(\w+)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(\w+)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)

    # Normalize multiple whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def fix_punctuation_and_spacing(text):
    """
    Corrects common punctuation, comma spacing, and period spacing anomalies.
    """
    # Remove whitespace before punctuation mark
    text = re.sub(r"\s+([,.:;?!])", r"\1", text)

    # Add space after punctuation if directly followed by an alphabet letter
    text = re.sub(r"([,.:;?!])(?=[A-Za-z])", r"\1 ", text)

    # Fix multiple repeated punctuation marks (e.g., "..", ",,", "??")
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r",{2,}", ",", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"!{2,}", "!", text)

    # Clean double spaces
    text = re.sub(r" +", " ", text)
    return text.strip()


def fix_capitalization(text):
    """
    Ensures sentence beginnings, bullet points, and standalone 'I' are correctly capitalized.
    """
    if not text:
        return text

    # Capitalize standalone lowercase 'i' (e.g., 'i think', 'as i was')
    text = re.sub(r"\b(i)\b", "I", text)
    text = re.sub(r"\b(i'm)\b", "I'm", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(i've)\b", "I've", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(i'll)\b", "I'll", text, flags=re.IGNORECASE)

    # Capitalize first character of text
    if len(text) > 0 and text[0].islower():
        text = text[0].upper() + text[1:]

    # Capitalize first letter after terminal punctuation (. ! ?)
    text = re.sub(r"(?<=[.!?]\s)([a-z])", lambda m: m.group(1).upper(), text)

    # Capitalize after newlines and bullet characters (•, -, *)
    text = re.sub(
        r"(^|\n)([•\-\*]\s*)([a-z])",
        lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
        text
    )

    # Capitalize lines beginning with letters after line breaks
    text = re.sub(
        r"(\n\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text
    )

    return text


def ensure_terminal_punctuation(text):
    """
    Ensures bullet points and paragraphs end with proper terminal punctuation.
    """
    lines = text.split("\n")
    processed_lines = []

    for line in lines:
        stripped = line.strip()
        # Don't add period to markdown headers, empty lines, or checklist items
        if not stripped or stripped.startswith("#") or stripped.endswith(":") or stripped.endswith("]"):
            processed_lines.append(line)
            continue

        if stripped.startswith("•") or stripped.startswith("-"):
            if not stripped[-1] in ".!?:":
                line = line + "."

        processed_lines.append(line)

    return "\n".join(processed_lines)


def correct_grammar_and_polish(text):
    """
    Comprehensive grammar and formatting pipeline for generated summaries and transcripts.
    """
    if not text or not text.strip():
        return text

    # 1. Clean speech fillers & stutters
    cleaned = remove_spoken_fillers(text)

    # 2. Fix punctuation and spacing
    cleaned = fix_punctuation_and_spacing(cleaned)

    # 3. Fix capitalization
    cleaned = fix_capitalization(cleaned)

    # 4. Ensure complete sentence termination
    cleaned = ensure_terminal_punctuation(cleaned)

    return cleaned.strip()

