"""Affiche la zone d'un PDF autour d'un code d'indicateur (audit, phase 0).

Sert à relever à la main les réponses attendues des questions de référence,
directement dans les PDF et indépendamment de la base du prototype.

Usage :
    python -X utf8 docs/audit/scripts/show_indicator.py FICHIER.pdf CODE [CODE...]
    python -X utf8 docs/audit/scripts/show_indicator.py --all-cti-2026 I.18.a
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pdfplumber

CODE_RE = re.compile(r"^([IVX]+(?:[.\-][A-Za-z0-9]+)+)-?$")


def anchors(page: pdfplumber.page.Page) -> list[tuple[str, float]]:
    found = []
    lines = sorted(page.extract_text_lines(strip=True), key=lambda line: line["top"])
    for i, line in enumerate(lines):
        if line["x0"] > 45 or not line["text"].strip():
            continue
        token = line["text"].split()[0]
        if token.endswith("-") and i + 1 < len(lines):
            token += lines[i + 1]["text"].split()[0]
        match = CODE_RE.match(token)
        if match:
            found.append((match.group(1), (line["top"] + line["bottom"]) / 2))
    return found


def show(path: Path, code: str) -> None:
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            marks = anchors(page)
            for k, (found, center) in enumerate(marks):
                if found != code:
                    continue
                top = (marks[k - 1][1] + center) / 2 if k else max(0, center - 60)
                bottom = (marks[k + 1][1] + center) / 2 if k + 1 < len(marks) else min(page.height, center + 160)
                region = page.crop((0, top, page.width, bottom))
                print(f"===== {path.name} | {code} | page {page_no}")
                print(region.extract_text(layout=True).rstrip())
                return
    print(f"===== {path.name} | {code} | INTROUVABLE")


def main(argv: list[str]) -> int:
    if argv[1] == "--all-cti-2026":
        files = sorted(Path("documents_brut").glob("*-cti-2026.pdf"))
        for f in files:
            show(f, argv[2])
        return 0
    path = Path(argv[1])
    if not path.exists():
        path = Path("documents_brut") / argv[1]
    for code in argv[2:]:
        show(path, code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
