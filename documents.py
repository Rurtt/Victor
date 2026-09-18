"""Only explicitly selected, size-limited UTF-8 text is supported in v0.1."""
from pathlib import Path

def read_document(path: Path) -> str:
    if path.suffix.lower() not in {".txt", ".md", ".csv", ".json", ".log"}:
        raise ValueError("Choose a .txt, .md, .csv, .json or .log file. For PDF/Word/web pages, paste the text instead.")
    with path.open("rb") as f:
        raw = f.read(240001)
    if len(raw) > 240000:
        raise ValueError("File is too large. Paste a shorter excerpt instead.")
    if b"\x00" in raw:
        raise ValueError("This file is not plain UTF-8 text.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("File must use UTF-8 encoding. Copy and paste its text instead.") from None
