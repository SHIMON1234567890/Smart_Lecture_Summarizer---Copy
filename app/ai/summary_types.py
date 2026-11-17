"""The summary styles users can pick. Pages import this without loading any model."""

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
