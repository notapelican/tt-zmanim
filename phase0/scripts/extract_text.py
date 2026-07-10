#!/usr/bin/env python3
"""Extract the text layer of every sample PDF into phase0/extracted/<name>.txt."""
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
OUT = ROOT / "phase0" / "extracted"


def clean_name(pdf_name: str) -> str:
    # Undo the %20-style mangling baked into some filenames: "_20" == space, "_26" == "&", "_2C" == ","
    n = pdf_name
    n = re.sub(r"_2[0]", " ", n)
    n = n.replace("_26", "&").replace("_2C", ",")
    n = re.sub(r"\s+", " ", n).strip()
    return n


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failures = []
    for pdf in sorted(SAMPLES.glob("*.pdf")):
        try:
            reader = PdfReader(pdf)
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n=== PAGE BREAK ===\n\n".join(pages)
        except Exception as e:  # keep going; report at end
            failures.append((pdf.name, str(e)))
            continue
        out = OUT / (pdf.stem + ".txt")
        out.write_text(f"SOURCE PDF: {pdf.name}\nREADABLE NAME: {clean_name(pdf.stem)}\n\n{text}\n")
        print(f"{pdf.name}: {len(text)} chars, {len(reader.pages)} page(s)")
    for name, err in failures:
        print(f"FAILED {name}: {err}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
