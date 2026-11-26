"""Inventaire des codes d'indicateurs des fiches CTI et DEFI (audit, phase 0).

Script d'audit indépendant de l'extracteur du prototype : il repère les codes
d'indicateurs dans la marge gauche des PDF (x0 <= 45 pt), reconstitue un
libellé approximatif et produit :

- docs/audit/data/indicator_codes.csv : une ligne par (document, code) ;
- docs/audit/data/indicator_inventory.json : synthèse (stabilité des codes
  entre campagnes, changements de libellés, recouvrement CTI/DEFI).

Usage (depuis la racine du dépôt) :
    python docs/audit/scripts/inventory_codes.py documents_brut
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

import pdfplumber

CODE_RE = re.compile(r"^([IVX]+(?:[.\-][A-Za-z0-9]+)+)-?$")
MAJOR_RE = re.compile(r"^([IVX]+)\.\s+(.+)$")
FILENAME_RE = re.compile(r"^(?P<school>.+)-(?P<source>cti|defi)-(?P<year>\d{4})\.pdf$", re.I)
LEFT_MARGIN = 45.0
LABEL_X_MIN, LABEL_X_MAX = 46.0, 260.0
OUT_DIR = Path("docs/audit/data")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def normalize_code(code: str) -> str:
    """Retire l'indice de diplôme propre à l'école : II.1-D6-1 -> II.1-D*-1."""
    return re.sub(r"([.\-])D\d+(?=$|[.\-])", r"\1D*", code)


def campaign_from_pdf(path: Path) -> int | None:
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    match = re.search(r"Campagne\s*[:\-]?\s*(20\d{2})", text)
    return int(match.group(1)) if match else None


def scan_pdf(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    major = ""
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            lines = sorted(
                page.extract_text_lines(strip=True), key=lambda line: (line["top"], line["x0"])
            )
            anchors: list[tuple[str, float, str]] = []
            skip: set[int] = set()
            for i, line in enumerate(lines):
                if i in skip:
                    continue
                text = line["text"].strip()
                major_match = MAJOR_RE.match(text)
                if major_match and text.upper() == text and len(text) > 8:
                    major = major_match.group(1)
                if line["x0"] > LEFT_MARGIN or not text:
                    continue
                token = text.split()[0]
                if token.endswith("-"):  # code coupé sur deux lignes
                    for j in range(i + 1, min(i + 4, len(lines))):
                        nxt = lines[j]
                        if nxt["x0"] <= LEFT_MARGIN and nxt["top"] - line["top"] <= 28:
                            token = token + nxt["text"].split()[0]
                            skip.add(j)
                            break
                match = CODE_RE.match(token)
                if not match or not re.search(r"\d", match.group(1)):
                    continue
                anchors.append((match.group(1), (line["top"] + line["bottom"]) / 2, major))
            for k, (code, center, major_code) in enumerate(anchors):
                low = (anchors[k - 1][1] + center) / 2 if k else center - 40
                high = (anchors[k + 1][1] + center) / 2 if k + 1 < len(anchors) else center + 60
                parts = [
                    line["text"].strip()
                    for line in lines
                    if low <= (line["top"] + line["bottom"]) / 2 < high
                    and LABEL_X_MIN <= line["x0"] <= LABEL_X_MAX
                    and not re.fullmatch(r"[\d\s.,%/€-]+", line["text"].strip())
                ]
                label = re.sub(r"\s+", " ", " ".join(parts))[:220]
                rows.append(
                    {"page": page_no, "code": code, "major_section": major_code, "label": label}
                )
    return rows


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def main(argv: list[str]) -> int:
    source_dir = Path(argv[1] if len(argv) > 1 else "documents_brut")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    hashes: dict[str, str] = {}
    for pdf_path in sorted(source_dir.glob("*.pdf")):
        meta = FILENAME_RE.match(pdf_path.name)
        if not meta:
            print(f"Nom de fichier non reconnu : {pdf_path.name}", file=sys.stderr)
            continue
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        if digest in hashes:
            print(f"Doublon de contenu ignoré : {pdf_path.name} (= {hashes[digest]})", file=sys.stderr)
            continue
        hashes[digest] = pdf_path.name
        campaign = campaign_from_pdf(pdf_path) or int(meta["year"])
        if campaign != int(meta["year"]):
            print(f"Campagne du PDF ({campaign}) différente du nom : {pdf_path.name}", file=sys.stderr)
        seen: set[str] = set()
        for row in scan_pdf(pdf_path):
            if row["code"] in seen:  # première occurrence par document
                continue
            seen.add(str(row["code"]))
            records.append(
                {
                    "file": pdf_path.name,
                    "school": meta["school"].upper(),
                    "source": meta["source"].lower(),
                    "campaign": campaign,
                    "filename_year": int(meta["year"]),
                    "code_normalized": normalize_code(str(row["code"])),
                    **row,
                }
            )
        print(f"{pdf_path.name}: {len(seen)} codes", file=sys.stderr)

    with (OUT_DIR / "indicator_codes.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file", "school", "source", "campaign", "filename_year", "page",
                "code", "code_normalized", "major_section", "label",
            ],
        )
        writer.writeheader()
        writer.writerows(records)

    by_doc: dict[str, set[str]] = defaultdict(set)
    by_source_campaign: dict[tuple[str, int], set[str]] = defaultdict(set)
    docs_per_sc: dict[tuple[str, int], set[str]] = defaultdict(set)
    labels: dict[tuple[str, str, int], list[str]] = defaultdict(list)
    for r in records:
        key = (str(r["source"]), int(r["campaign"]))  # type: ignore[arg-type]
        by_doc[str(r["file"])].add(str(r["code"]))
        by_source_campaign[key].add(str(r["code"]))
        docs_per_sc[key].add(str(r["file"]))
        labels[(key[0], str(r["code"]), key[1])].append(str(r["label"]))

    summary: dict[str, object] = {"documents": len(by_doc), "per_source_campaign": {}, "stability": {}}
    for (source, campaign), codes in sorted(by_source_campaign.items()):
        doc_counts = sorted(len(by_doc[f]) for f in docs_per_sc[(source, campaign)])
        summary["per_source_campaign"][f"{source}-{campaign}"] = {  # type: ignore[index]
            "documents": len(doc_counts),
            "distinct_codes_union": len(codes),
            "distinct_normalized_codes_union": len({normalize_code(c) for c in codes}),
            "codes_per_document_min": doc_counts[0],
            "codes_per_document_median": doc_counts[len(doc_counts) // 2],
            "codes_per_document_max": doc_counts[-1],
        }

    for source in ("cti", "defi"):
        campaigns = sorted(c for s, c in by_source_campaign if s == source)
        pairs = {}
        for a, b in combinations(campaigns, 2):
            set_a, set_b = by_source_campaign[(source, a)], by_source_campaign[(source, b)]
            common = set_a & set_b
            relabelled = []
            for code in sorted(common):
                la = max(set(labels[(source, code, a)]), key=labels[(source, code, a)].count)
                lb = max(set(labels[(source, code, b)]), key=labels[(source, code, b)].count)
                ratio = SequenceMatcher(None, fold(la)[:120], fold(lb)[:120]).ratio()
                if ratio < 0.6:
                    relabelled.append({"code": code, f"label_{a}": la[:120], f"label_{b}": lb[:120], "similarity": round(ratio, 2)})
            norm_a = {normalize_code(c) for c in set_a}
            norm_b = {normalize_code(c) for c in set_b}
            pairs[f"{a}-{b}"] = {
                "jaccard": round(jaccard(set_a, set_b), 3),
                "jaccard_normalized": round(jaccard(norm_a, norm_b), 3),
                "normalized_common": len(norm_a & norm_b),
                "common": len(common),
                f"only_{a}": sorted(set_a - set_b),
                f"only_{b}": sorted(set_b - set_a),
                "label_changes_same_code": len(relabelled),
                "label_changes_examples": relabelled[:15],
            }
        summary["stability"][source] = pairs  # type: ignore[index]

    # Recouvrement CTI / DEFI : rapprochement par libellé (les codes sont des espaces distincts).
    def representative(source: str) -> dict[str, str]:
        rep: dict[str, str] = {}
        for (s, code, _campaign), values in labels.items():
            if s == source and code not in rep and values and values[0]:
                rep[code] = values[0]
        return rep

    cti_rep, defi_rep = representative("cti"), representative("defi")
    matches = []
    for dcode, dlabel in sorted(defi_rep.items()):
        best = max(
            ((ccode, SequenceMatcher(None, fold(dlabel)[:100], fold(clabel)[:100]).ratio()) for ccode, clabel in cti_rep.items()),
            key=lambda item: item[1],
            default=("", 0.0),
        )
        if best[1] >= 0.75:
            matches.append({"defi_code": dcode, "cti_code": best[0], "similarity": round(best[1], 2), "defi_label": dlabel[:100], "cti_label": cti_rep[best[0]][:100]})
    summary["cti_defi_overlap"] = {
        "cti_codes_total": len(cti_rep),
        "defi_codes_total": len(defi_rep),
        "same_code_string": len(set(cti_rep) & set(defi_rep)),
        "label_matches_ge_0_75": len(matches),
        "examples": matches[:25],
    }
    (OUT_DIR / "indicator_inventory.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "stability"}, ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
