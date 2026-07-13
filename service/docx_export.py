"""Optional .docx export — a "give me a Word copy" path.

Thin wrapper over ``engine.render_docx.render_docx`` (python-docx). Returns the
document as bytes for streaming over HTTP; nothing touches disk.
"""
from __future__ import annotations

import io


def render_docx_bytes(doc_data: dict) -> bytes:
    from engine.render_docx import render_docx

    document = render_docx(doc_data)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
