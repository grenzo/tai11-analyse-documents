# ADR 0001 — Refonte ciblée plutôt que reprise du prototype

- Statut : **proposé (26/11/2026), en attente de validation** ; rien n'est déplacé dans `legacy/` avant cette validation
- Décideurs : équipe TAI 11
- Lié à : [audit du prototype](../audit.md), [ADR 0002](0002-fournisseurs-llm-gratuits.md)

## Contexte

Le sujet demande de « reprendre un prototype existant » ([`Lex0os/RAG_Polytech`](https://github.com/Lex0os/RAG_Polytech), commit `ccc6a9a` du 23/11/2026) et d'en faire une solution clé en main, mesurée et déployée. L'audit (phase 0) a établi les faits suivants, tous reproductibles avec les commandes de [`docs/audit.md`](../audit.md).

| Mesure | Valeur |
|---|---|
| Taille du code | 12 552 lignes Python, dont `query_engine.py` 5 582, extraction 5 940 (`cti_extractor.py` 3 203, `defi_extractor.py` 1 454, `extracteur_sections_cti_defi.py` 1 283) ; 0 test |
| Base produite | **681 tables physiques**, 18 467 colonnes (dont 2 804 colonnes métier aux noms générés), 15 440 lignes ; 89 % des tables CTI (523 sur 586) sont des sections « par indice de diplôme » (`II.1-D10-…`) dont l'indice ne désigne pas le même diplôme d'une école à l'autre |
| Description du schéma pour le LLM | `semantic_schema.txt` : 26 277 lignes, 931 Ko |
| Moteur | BM25 + embeddings + routage par LLM vers 278 « familles » ; **16 validateurs ad hoc** ; environ **820 lignes de prompts** (5 prompts) ; règles propres à des questions précises (convention « label DDRS », synthèse pondérée des salaires…) |
| Coût par question | 3 à 6 appels LLM de 5 000 à 7 500 tokens chacun, soit **6 à 8 questions par jour** au maximum sur le quota gratuit de Groq |
| Qualité d'extraction (cellules) | **100 valeurs exactes sur 101** contrôlées à la main sur 3 fiches (CTI Marseille 2026, DEFI Marseille 2025, ENSIM CTI et DEFI 2025) |
| Exécution | `requirements.txt` insoluble (4 paquets en double) ; `app.py` plante au démarrage (`LlamaProvider.__init__() got an unexpected keyword argument 'timeout'`) ; 2 étapes d'installation non documentées |
| Sécurité | Garde-fou par expressions régulières : il accepte `sqlite_master`, les tables hors sélection, une CTE récursive infinie et les produits cartésiens, mais refuse `REPLACE()` ; ni délai maximal ni plafond de lignes |
| Données | 4 fichiers mal nommés (« 2025 » au lieu de 2026), 1 doublon exact ; Dijon 2026 chargé deux fois, d'où un **double comptage** dans toute somme sur le réseau |

## Options étudiées

### A. Reprise incrémentale (« rustine »)

Corriger les dépendances et le bug de démarrage, ajouter des tests autour de `query_engine.py`, migrer SQLite vers PostgreSQL en gardant une table par section, puis ajouter l'interface et le benchmark.

- Pour : effort initial le plus faible ; continuité avec l'auteur.
- Contre :
  - **Le défaut est structurel.** Le LLM doit retrouver la bonne table parmi 681 (278 familles), et chaque nouveau type de question demande une règle de prompt ou un validateur de plus : la dette observée (16 validateurs, 820 lignes de prompts) ne peut que croître.
  - Le coût en tokens (6 à 8 questions par jour en gratuit) rend le benchmark de stratégies **irréalisable** dans le budget.
  - Le pipeline monolithique (fonction `ask` de 317 lignes) ne permet pas d'activer ou de désactiver des étapes, alors que c'est la condition d'un benchmark propre (S0 à S6, ablation).
  - Les comparaisons entre écoles et entre années restent fragiles : indice D par école, double comptage, campagnes mal attribuées.

### B. Refonte totale, extraction comprise

Repartir de zéro, par exemple avec Docling partout.

- Pour : architecture homogène.
- Contre : on jette la partie **la plus saine** du prototype. Les extracteurs encodent une connaissance fine des formulaires (ancres en marge, codes coupés sur deux lignes, tableaux de salaires, tableaux vides structurés, chaires DEFI) et atteignent 99 % d'exactitude au niveau des cellules sur l'échantillon. Le risque de régression est élevé, sans gain démontré.

### C. Refonte ciblée (**retenue**)

On garde la couche d'extraction, on remplace le stockage, le moteur et l'interface.

## Décision

Option **C**. Le prototype part dans `legacy/` (après validation de cet ADR). Il y sert de mesure « avant » et d'**oracle** pour l'extraction.

### Ce qui est réutilisé

| Élément du prototype | Lignes (env.) | Devenir |
|---|---|---|
| `cti_extractor.py` : lecture des PDF jusqu'au `Record` long (`extract_pdf`, ancres, en-têtes, salaires, tableaux vides, valeurs scalaires ; l. 1–2 046) | 2 050 | Porté dans `ingestion/extractors/cti.py`, découpé, typé, testé ; enregistré comme plugin |
| `defi_extractor.py` : lecture jusqu'au `Record` (l. 1–1 334, dont chaires et sections XI) | 1 330 | Porté dans `ingestion/extractors/defi.py` |
| `extracteur_sections_cti_defi.py` : sha256, détection du type et de la campagne **depuis le texte du PDF**, nom d'école | 300 | Porté dans `ingestion/documents.py` |
| Corrections déterministes tracées (`extraction_issues`) | — | Conservées dans `raw.extraction_issues` |
| Principe `PRAGMA query_only` | — | Transposé en rôle PostgreSQL `nl2sql_reader` en lecture seule (défense en profondeur) |
| Fournisseur local via API compatible OpenAI (llama.cpp) | 70 | Une implémentation de l'abstraction `llm/` (avec Ollama) |
| Idées du moteur : profil de disponibilité des données, liste des écoles Polytech, canonicalisation des valeurs de dimension, règle de synthèse pondérée des salaires | — | Deviennent respectivement des avertissements de couverture, `dim_ecole.reseau_polytech`, une étape de *value linking*, et une colonne documentée d'une vue `analytics` accompagnée d'un exemple few-shot |

Au total, environ **3 700 lignes réutilisées**, soit 62 % du code d'extraction et 30 % du prototype.

### Ce qui est abandonné

| Élément | Lignes (env.) | Raison |
|---|---|---|
| Construction de la base « une table par section » (`build_section_database_from_records`, `build_unified_section_database`, catalogues de colonnes générées) | 2 200 | Remplacée par le modèle en étoile `core` (`fait_valeur` + dimensions) et les vues `analytics` |
| `query_engine.py` (routage, 16 validateurs, 5 prompts, auto-correction, rédaction de la réponse à partir des lignes) | 5 582 | Remplacé par le pipeline configurable `nl2sql/` (validation sqlglot, exécution en bac à sable, stratégies S0–S6) ; la rédaction de la réponse à partir des lignes est abandonnée (RGPD, voir ADR 0002) |
| `generate_semantic_schema.py`, `embedding.py`, `tables_search.py` | 560 | Remplacés par les `COMMENT ON` des vues `analytics` et le *schema linking* sur un schéma de quelques vues |
| `app.py` (Streamlit), sélection du fournisseur en commentant du code | 245 | Remplacé par FastAPI + React ; fournisseur choisi par configuration |
| `requirements.txt` (`pip freeze` avec doublons) | — | Remplacé par `uv` + `pyproject.toml` + `uv.lock` |

### Points clés du nouveau modèle

Le détail sera fixé par le MCD de la phase 3 :

- **Indicateur stable** = code du formulaire **sans l'indice de diplôme** (`II.1-D6-7-1` → `II.1-D*-7-1`). L'indice devient une clé de `dim_formation`, qui porte l'intitulé réel du diplôme, par exemple « spécialité informatique ».
- **Campagne** = celle écrite dans le PDF, jamais celle du nom de fichier. Unicité (école, source, campagne) garantie par contrainte : un second document pour le même triplet est signalé, pas ajouté.
- **Catalogue rapproché entre campagnes** : environ 584 codes CTI bruts par campagne se ramènent à **124 indicateurs normalisés**, stables entre 2025 et 2026 (Jaccard 0,98) ; les codes DEFI de la section II ont été **renumérotés** entre 2024 et 2025 (Jaccard 0,86), d'où une table de correspondance explicite. Le catalogue comptera donc environ 200 indicateurs.
- **CTI et DEFI** : aucune correspondance par code (29 chaînes identiques mais de sens différent, par exemple `I.1` = nom légal en CTI, effectifs en DEFI) ; rapprochement sémantique manuel des indicateurs communs (effectifs, part de femmes, handicap, international, insertion).

## Conséquences

- **Effort estimé** : environ 80 jours-personne d'ingénierie pour tout le périmètre, et environ 66 sans les exigences C et quelques « S ». La capacité humaine supposée est d'environ 55 à 60 jours-personne (4 personnes × ~2 jours par semaine jusqu'au gel du 24/01/2027), avec l'implémentation assistée par Claude Code. Le détail est dans [PLAN.md](../../PLAN.md). C'est tendu mais faisable ; les éléments « bonus » (génération assistée de tableaux de bord, export PDF, repli LLM d'extraction) sont la variable d'ajustement.
- **Garde-fou contre la régression d'extraction** : test de non-régression *oracle*. Pour les 43 documents, les cellules du nouveau pipeline doivent coïncider avec les `Record` du prototype à au moins 99,5 % ; chaque écart est expliqué (correction volontaire ou régression).
- **Comparabilité « avant / après »** : les 20 questions de référence ([`docs/audit/baseline_questions.json`](../audit/baseline_questions.json)) sont rejouées sur le nouveau système avec le **même modèle** (Groq `openai/gpt-oss-20b`).
- **Collaboration** : l'auteur du prototype reste une ressource précieuse pour les cas limites de l'extraction (question posée en fin de phase 1).
- Si la validation de cet ADR est refusée, l'option A reste possible. Le PLAN serait alors revu : benchmark réduit à 2 stratégies, tableaux de bord simplifiés.
