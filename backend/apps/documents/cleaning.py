import math
import re
import unicodedata
from collections import Counter

# Control characters, except tab (09), line feed (0a) and carriage return (0d)
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# "inter-\nnational" -> "international"
HYPHEN_BREAK = re.compile(r"([a-z])-\n([a-z])")
# Lines that start a bullet or a numbered item
BULLET_START = re.compile(r"^([-*\u2022\u25cf]|\d{1,3}[.)])\s+")
# A line that is only a page number: "12", "Page 12", "12 of 40", "12/40"
PAGE_NUMBER_LINE = re.compile(r"^\s*(page\s+)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$", re.IGNORECASE)

MAX_BOILERPLATE_LINE_LENGTH = 100
MIN_PAGES_FOR_REPEAT_DETECTION = 3


def join_wrapped_lines(text):
    """A single line break inside a paragraph becomes a space.

    Blank lines stay as paragraph breaks and bullet items stay on their own line.
    """
    result = []
    for line in text.split("\n"):
        starts_new_line = not result or line == "" or result[-1] == "" or BULLET_START.match(line)
        if starts_new_line:
            result.append(line)
        else:
            result[-1] = result[-1] + " " + line
    return "\n".join(result)


def clean_text(text):
    """Turns raw extracted text into clean text that is good for search."""
    # NFKC turns ligatures (ﬁ -> fi) and odd lookalike characters into plain ones
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    text = CONTROL_CHARS.sub("", text)
    text = text.replace("\u00ad", "")  # invisible soft hyphen
    # Trim every line and collapse repeated spaces
    text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))
    text = HYPHEN_BREAK.sub(r"\1\2", text)
    text = join_wrapped_lines(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_line(line):
    """Digits become '#', so 'Page 1' and 'Page 2' count as the same line."""
    return re.sub(r"\d+", "#", line.strip().lower())


def _edge_indexes(lines):
    """Positions of the first two and last two non-blank lines of a page."""
    non_blank = [i for i, line in enumerate(lines) if line.strip()]
    return set(non_blank[:2] + non_blank[-2:])


def remove_boilerplate(page_texts):
    """Removes page numbers and headers/footers that repeat on many pages.

    Only the first two and last two lines of each page are examined, so real
    content in the middle of a page is never touched.
    """
    pages = [text.split("\n") for text in page_texts]

    counts = Counter()
    for lines in pages:
        seen = {_normalize_line(lines[i]) for i in _edge_indexes(lines)}
        counts.update(n for n in seen if n and len(n) <= MAX_BOILERPLATE_LINE_LENGTH)

    repeated = set()
    if len(pages) >= MIN_PAGES_FOR_REPEAT_DETECTION:
        threshold = max(MIN_PAGES_FOR_REPEAT_DETECTION, math.ceil(len(pages) * 0.5))
        repeated = {line for line, count in counts.items() if count >= threshold}

    cleaned_pages = []
    for lines in pages:
        edges = _edge_indexes(lines)
        kept = []
        for index, line in enumerate(lines):
            if index in edges and PAGE_NUMBER_LINE.match(line):
                continue
            if index in edges and _normalize_line(line) in repeated:
                continue
            kept.append(line)
        cleaned_pages.append("\n".join(kept))
    return cleaned_pages
