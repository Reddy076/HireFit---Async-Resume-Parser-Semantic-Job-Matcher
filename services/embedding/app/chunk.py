"""Word-window chunking shared by resume sections and job descriptions."""


def chunk_text(text: str, words: int = 120, overlap: int = 20) -> list[str]:
    toks = text.split()
    if not toks:
        return []
    out = []
    i = 0
    while i < len(toks):
        out.append(" ".join(toks[i : i + words]))
        if i + words >= len(toks):
            break
        i += words - overlap
    return out


def chunk_sections(parsed: dict, words: int = 120, overlap: int = 20) -> list[tuple[str, str]]:
    """Flatten {section: text} into [(section, chunk)] pairs, skipping metadata keys."""
    out = []
    for section, body in parsed.items():
        if section.startswith("_") or not (body or "").strip():
            continue
        for chunk in chunk_text(body, words=words, overlap=overlap):
            out.append((section, chunk))
    return out
