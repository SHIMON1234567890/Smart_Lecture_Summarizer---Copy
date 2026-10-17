import urllib.request
import urllib.parse
import json
import time

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "hi": "Hindi (हिन्दी)",
    "zh": "Chinese (中文)",
    "ja": "Japanese (日本語)",
    "ar": "Arabic (العربية)",
    "ru": "Russian (Русский)",
    "pt": "Portuguese (Português)",
    "it": "Italian (Italiano)",
    "nl": "Dutch (Nederlands)",
    "ko": "Korean (한국어)",
    "tr": "Turkish (Türkçe)"
}


def translate_chunk(chunk, target_lang="es", source_lang="auto"):
    """
    Translates a single text chunk using the free Google Translate API endpoint.
    """
    if not chunk or not chunk.strip():
        return chunk

    encoded_text = urllib.parse.quote(chunk)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={encoded_text}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data and isinstance(data, list) and data[0]:
                translated_parts = [part[0] for part in data[0] if part and part[0]]
                return "".join(translated_parts)
    except Exception as e:
        print(f"Translation chunk error: {e}")
        return chunk

    return chunk


def translate_text(text, target_lang="es", source_lang="auto"):
    """
    Translates full text into the specified language, preserving markdown and line breaks.
    """
    if not text or not text.strip():
        return text

    if target_lang == "en" and source_lang == "en":
        return text

    lines = text.split("\n")
    translated_lines = []

    # Process line by line to maintain markdown structures (headers, bullets, checkboxes)
    for line in lines:
        stripped = line.strip()
        if not stripped:
            translated_lines.append("")
            continue

        # Preserve markdown header markers
        prefix = ""
        content_to_translate = line
        if stripped.startswith("### "):
            prefix = "### "
            content_to_translate = stripped[4:]
        elif stripped.startswith("## "):
            prefix = "## "
            content_to_translate = stripped[3:]
        elif stripped.startswith("# "):
            prefix = "# "
            content_to_translate = stripped[2:]
        elif stripped.startswith("• "):
            prefix = "• "
            content_to_translate = stripped[2:]
        elif stripped.startswith("- "):
            prefix = "- "
            content_to_translate = stripped[2:]
        elif stripped.startswith("1. [ ] ") or stripped.startswith("2. [ ] ") or stripped.startswith("3. [ ] "):
            prefix = stripped[:7]
            content_to_translate = stripped[7:]

        translated_content = translate_chunk(content_to_translate, target_lang=target_lang, source_lang=source_lang)
        translated_lines.append(prefix + translated_content)

    return "\n".join(translated_lines)
