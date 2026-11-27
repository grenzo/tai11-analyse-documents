"""Sonde du garde-fou SQL du prototype (audit, phase 0).

Soumet des requêtes hostiles ou limites à `query_engine.validate_sql` (le
contrôle final du prototype avant exécution), puis exécute celles qui passent
sur la base en `PRAGMA query_only = ON`, avec un coupe-circuit de 5 s que le
prototype n'a pas (il appelle `fetchall()` sans délai ni plafond).

Usage (depuis la racine du dépôt, après extraction et embedding.py) :
    python docs/audit/scripts/probe_sql_guard.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import query_engine  # noqa: E402  (module du prototype)

DB = "cti_defi_sections.sqlite"
PHYSICAL = ["cti_i_19"]
CASES = [
    ("légitime", "SELECT school_key, year FROM cti_i_19 WHERE school_key = 'MARSEILLE'"),
    ("légitime + REPLACE()", "SELECT REPLACE(school_key, '_', ' ') AS ecole FROM cti_i_19"),
    ("écriture DROP", "DROP TABLE cti_i_19"),
    ("écriture cachée dans WITH", "WITH x AS (SELECT 1) DELETE FROM cti_i_19"),
    ("deux instructions", "SELECT 1 FROM cti_i_19; DELETE FROM cti_i_19"),
    ("lecture catalogue", "SELECT name, sql FROM sqlite_master"),
    ("table hors sélection", "SELECT * FROM documents"),
    (
        "CTE récursive infinie",
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT max(x) FROM c",
    ),
    ("produit cartésien", "SELECT count(*) FROM cti_i_19 a, cti_i_19 b, cti_i_19 c, cti_i_19 d, cti_i_19 e, cti_i_19 f"),
    ("allocation mémoire", "SELECT length(zeroblob(500000000))"),
]


def run_with_timeout(connection: sqlite3.Connection, sql: str, seconds: float = 5.0) -> str:
    deadline = time.monotonic() + seconds
    connection.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    start = time.monotonic()
    try:
        rows = connection.execute(sql).fetchall()
        return f"exécutée en {time.monotonic() - start:.2f} s, {len(rows)} ligne(s)"
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc):
            return f"INTERROMPUE par la sonde après {seconds:.0f} s (le prototype aurait attendu indéfiniment)"
        return f"erreur SQLite : {exc}"
    except sqlite3.Error as exc:
        return f"erreur SQLite : {exc}"
    finally:
        connection.set_progress_handler(None, 0)


def main() -> int:
    schemas = query_engine.load_schema_blocks(Path("semantic_schema.txt"))
    connection = sqlite3.connect(DB)
    connection.execute("PRAGMA query_only = ON")
    results = []
    for label, sql in CASES:
        try:
            valid, error = query_engine.validate_sql(connection, sql, PHYSICAL, schemas)
        except Exception as exc:  # le validateur lui-même peut lever
            valid, error = False, f"exception {type(exc).__name__}: {exc}"
        outcome = run_with_timeout(connection, sql) if valid else "-"
        results.append({"cas": label, "sql": sql, "accepte": valid, "motif_refus": error, "execution": outcome})
        print(f"[{'ACCEPTÉE' if valid else 'refusée '}] {label:28s} | {error or outcome}")
    out = Path("docs/audit/data/probe_sql_guard.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
