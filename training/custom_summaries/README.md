# 📁 Custom Summaries Drop-in Folder

You can paste your summary files directly into this folder! The training and summarization pipeline will automatically ingest them.

### Supported File Formats:

#### 1. Plain Text or Markdown (`.txt`, `.md`)
You can format your text file like this:
```text
TRANSCRIPT:
(Paste the original lecture transcript or text here)

SUMMARY:
(Paste the high-quality summary in your preferred style here)
```

Or simply paste your summary notes directly into a `.txt` file, naming the file according to its style (e.g. `biology_notes.txt`, `physics_bullets.txt`).

#### 2. JSON Files (`.json`)
```json
[
  {
    "transcript": "In today's lecture...",
    "target_summary": "• Key takeaway 1\n• Key takeaway 2",
    "summary_type": "bullet_points"
  }
]
```

#### 3. CSV Files (`.csv`)
Columns: `transcript`, `target_summary`, `summary_type`

---

### How to Train:
After pasting your files here or in `training/data/`, simply run:
```bash
python training/train_summarizer.py
```
The model will automatically detect all pasted files and fine-tune according to your summaries!

