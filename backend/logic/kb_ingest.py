import hashlib
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pdfplumber

# If you want OCR fallback later, you can wire in your existing ocr_engine.scan_pdf


@dataclass
class KBChunk:
    id: str
    text: str
    metadata: Dict


def _normalize_ws(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _sha1_id(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update((p or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


def extract_text_by_page(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """
    Returns list of (page_number_1_based, text)
    Uses pdfplumber text extraction (fast if PDF has embedded text).
    """
    out: List[Tuple[int, str]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:  # type: ignore
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = _normalize_ws(text)
            out.append((i, text))
    return out


def chunk_text(
    pages: List[Tuple[int, str]],
    book: str,
    chapter: str,
    max_chars: int = 1800,
    overlap_chars: int = 250,
) -> List[KBChunk]:
    """
    Simple character-based chunking that preserves page citations.
    Each chunk is associated with a page range (usually 1 page unless spillover).
    """
    chunks: List[KBChunk] = []
    buffer = ""
    buffer_pages: List[int] = []

    def flush():
        nonlocal buffer, buffer_pages
        txt = _normalize_ws(buffer)
        if not txt:
            buffer = ""
            buffer_pages = []
            return

        page_min = min(buffer_pages) if buffer_pages else None
        page_max = max(buffer_pages) if buffer_pages else None
        chunk_index = len(chunks)

        cid = _sha1_id(book, chapter, str(page_min), str(page_max), str(chunk_index), txt[:200])

        chunks.append(
            KBChunk(
                id=cid,
                text=txt,
                metadata={
                    "book": book,
                    "chapter": chapter,
                    "page_min": page_min,
                    "page_max": page_max,
                    "chunk_index": chunk_index,
                    "source": "textbook",
                },
            )
        )

        # overlap
        if overlap_chars > 0 and len(txt) > overlap_chars:
            buffer = txt[-overlap_chars:]
            buffer_pages = buffer_pages[-2:] if len(buffer_pages) > 2 else buffer_pages
        else:
            buffer = ""
            buffer_pages = []

    for page_num, page_text in pages:
        if not page_text:
            continue

        # Start new buffer if empty
        if not buffer:
            buffer_pages = [page_num]

        # If adding this page would exceed max, flush first
        if len(buffer) + len(page_text) + 2 > max_chars:
            flush()
            if buffer:
                # if overlap retained, keep tracking this page too
                if page_num not in buffer_pages:
                    buffer_pages.append(page_num)

        # Append page text
        if buffer:
            buffer += "\n\n"
        buffer += page_text
        if page_num not in buffer_pages:
            buffer_pages.append(page_num)

        # Flush if buffer is big enough
        if len(buffer) >= max_chars:
            flush()

    flush()
    return chunks

