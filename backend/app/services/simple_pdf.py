"""A tiny, dependency-free PDF writer - plain text lines on A4 pages.

Used only to give customers a real file for documents the platform itself
produces (e.g. the "insurance premium quote" Bidii Credit asks for), so
they are never asked to upload something they don't have. Not a general
PDF library: one built-in font (Helvetica), text only.
"""

PAGE_W, PAGE_H = 595, 842  # A4 in points
MARGIN = 56
LEADING = 16


def _escape(text: str) -> str:
    safe = text.encode("latin-1", "replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(line: str, max_chars: int) -> list[str]:
    if len(line) <= max_chars:
        return [line]
    words, current, out = line.split(" "), "", []
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    return out


def render_text_pdf(title: str, lines: list[str]) -> bytes:
    """Returns a valid PDF whose text layer contains `title` then `lines`
    (blank strings become blank lines)."""
    max_chars = 88
    flat: list[tuple[str, int]] = [(title, 16)]
    flat.append(("", 12))
    for line in lines:
        for part in _wrap(line, max_chars):
            flat.append((part, 11))

    per_page = (PAGE_H - 2 * MARGIN) // LEADING
    pages = [flat[i : i + per_page] for i in range(0, len(flat), per_page)] or [[("", 11)]]

    objects: list[bytes] = []  # index 0 -> object 1

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    catalog_id = add(b"")  # placeholder, filled once page ids are known
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: list[int] = []
    for page in pages:
        ops = ["BT"]
        y = PAGE_H - MARGIN
        for text, size in page:
            ops.append(f"/F1 {size} Tf 1 0 0 1 {MARGIN} {y} Tm ({_escape(text)}) Tj")
            y -= LEADING
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        content_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(
            add(
                (
                    f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
                ).encode()
            )
        )

    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)
