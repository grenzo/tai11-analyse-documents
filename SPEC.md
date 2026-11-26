# SPEC — TAI 11 « Analyse de documents complexes assistée par IA »

> Statut : **proposition v0.1 (26/11/2026), en attente de validation**. Ce document est la définition de « fini » : toute fonctionnalité absente d'ici est ajoutée ici (avec accord si elle change le périmètre) ou n'est pas faite.
> Entrées : [énoncé officiel](docs/prompt-maitre.md), [audit](docs/audit.md), [ADR 0001](docs/adr/0001-refonte-ou-reprise.md), [ADR 0002](docs/adr/0002-fournisseurs-llm-gratuits.md), [modèle de menace](docs/threat-model.md).

## 1. Objet

Un collègue du réseau Polytech, non informaticien, pose en français une question sur les fiches CTI et DEFI des écoles. Il obtient un résultat juste et compréhensible, sait à quel point il peut s'y fier, retrouve la page du PDF d'où vient chaque chiffre, et compose des tableaux de bord. Le système est déployé sur le serveur du département, reproductible et maintenable après le départ de l'équipe.

Les trois livrables techniques qui en découlent :

1. une **chaîne d'ingestion** PDF → base PostgreSQL normalisée, avec provenance (document, page) ;
2. un **moteur Text-to-SQL** sûr, configurable par stratégie et **mesuré** (banc d'évaluation, IC 95 %) ;
3. une **application web** (questions, confiance, sources, tableaux de bord, administration) déployée clé en main.

## 2. Utilisateurs et personas

| Persona | Rôle applicatif | Besoin principal | Exemple de question |
|---|---|---|---|
| **Claire, enseignante-chercheuse** (Polytech Marseille) | lecteur | Comparer rapidement son école aux autres pour un conseil de département | « Combien d'enseignants-chercheurs permanents à Marseille, Nice et Montpellier en 2026 ? » |
| **Marc, responsable de formation** (directeur des études) | éditeur | Préparer l'audit CTI : insertion, salaires, réussite, accréditations, et suivre leur évolution | « Le taux de réussite en fin de 5e année a-t-il baissé entre 2025 et 2026 ? » |
| **Sofia, ingénieure système du département** | admin | Installer, sauvegarder, mettre à jour ; gérer les comptes ; surveiller coûts et erreurs | — |
| *Secondaire : direction, cellule qualité* | lecteur | Tableaux de bord partagés pour les instances | « Fais-moi un tableau de bord sur l'insertion professionnelle » |

## 3. Cas d'usage

- **UC1 — Importer des fiches** (éditeur) : déposer un ou plusieurs PDF, suivre leur statut (en attente, en cours, extrait, en erreur, doublon), consulter les anomalies.
- **UC2 — Poser une question** (lecteur) : réponse avec interprétation, résultat, graphique, confiance, hypothèses, SQL, sources, avertissements.
- **UC3 — Clarifier ou s'abstenir** : question ambiguë → choix proposés ; question hors périmètre ou sans donnée → refus motivé.
- **UC4 — Vérifier une valeur** : ouvrir le PDF source à la bonne page depuis la réponse.
- **UC5 — Composer un tableau de bord** : épingler des réponses, réorganiser, renommer, filtrer, rafraîchir, partager, exporter.
- **UC6 — Générer un tableau de bord assisté** : « Fais-moi un tableau de bord sur X » → 4 à 6 widgets proposés.
- **UC7 — Améliorer le système** : 👍/👎 avec correction ; l'admin promeut une réponse validée en exemple few-shot.
- **UC8 — Administrer** : comptes et rôles, journal, métriques (succès, abstention, coûts, latences), retours à traiter.
- **UC9 — Mesurer** (équipe) : lancer le banc d'évaluation et régénérer le rapport.

## 4. Hypothèses et défauts retenus

Ces points ne sont ni dans le dépôt ni déductibles. Un défaut est retenu pour avancer, et la question est posée à la fin de la phase 1.

| # | Sujet | Défaut retenu | Impact si faux |
|---|---|---|---|
| D1 | Types de documents | CTI et DEFI uniquement ; architecture à plugins pour en ajouter | Faible : nouveau plugin |
| D2 | Écoles couvertes | Toutes les écoles des PDF importés ; le filtre « réseau Polytech » est une option (`dim_ecole.reseau_polytech`) | Faible |
| D3 | Serveur | Linux x86-64 avec Docker et Docker Compose, 4 vCPU, 16 Go de RAM, **sans GPU**, nom DNS et HTTPS possibles, accès Internet sortant | Fort pour le mode local et le déploiement |
| D4 | Authentification | Comptes locaux (argon2id) avec rôles admin / éditeur / lecteur ; CAS AMU branchable plus tard | Moyen |
| D5 | Budget | 0 € ; offres gratuites et modèles locaux (ADR 0002) | Moyen |
| D6 | Langue | Interface, documentation et rapport en français | — |
| D7 | Volume | Moins de 200 documents et 50 utilisateurs ; 20 utilisateurs simultanés au maximum | Faible |
| D8 | Équipe | 2 binômes, environ 2 jours par semaine et par personne jusqu'au 24/01/2027 | Fort sur le périmètre (voir PLAN) |

## 5. Exigences fonctionnelles

Priorités MoSCoW : **M** = indispensable au rendu, **S** = attendu, **C** = si le temps le permet. Chaque critère d'acceptation est vérifiable par un test automatisé (T), une mesure (M) ou une démonstration scriptée (D).

### 5.1 Ingestion et données

| ID | Exigence | Prio | Critère d'acceptation |
|---|---|---|---|
| F1 | Importer des PDF par l'interface (glisser-déposer, multi-fichiers) et par la CLI (`make ingest`) | M | (T) un import de 3 PDF crée 3 documents au statut « extrait » ; (D) parcours Playwright « importer un PDF » |
| F2 | Ingestion idempotente : même sha256 ⇒ aucun doublon ; reprise sur erreur sans retraiter les documents déjà extraits | M | (T) réimporter le même fichier ne change ni `raw.documents` ni `core.fait_valeur` ; un échec au document 5 sur 10 n'empêche pas les 9 autres |
| F3 | Identification du type (plugin), de l'école et de la **campagne lue dans le PDF** ; signalement si le nom de fichier contredit le contenu | M | (T) les 4 fichiers mal nommés du corpus sont rattachés à la campagne 2026 avec un avertissement ; le doublon exact de Clermont est marqué « doublon » |
| F4 | Unicité (école, source, campagne) : un second document pour le même triplet est mis en attente de décision, pas ajouté | M | (T) les deux fiches Dijon 2026 ne produisent pas de double comptage dans `core.fait_valeur` |
| F5 | Statut par document visible dans l'interface : nombre de valeurs extraites, anomalies (`raw.extraction_issues`), durée | M | (D) page Documents ; (T) API `GET /documents` |
| F6 | Provenance : chaque valeur de `core.fait_valeur` référence son document et sa page | M | (T) 100 % des lignes ont `document_id` et `page` non nuls ; (D) lien « voir la source » ouvrant le PDF à la page |
| F7 | Un extracteur par type de document, enregistré comme plugin (CTI, DEFI) | M | (T) un plugin factice enregistré est découvert et appelé |
| F8 | Catalogue des indicateurs : code normalisé (sans indice de diplôme), libellé, section, thème, unité, type, définition ; correspondances entre campagnes (renumérotation DEFI 2024 → 2025) et entre CTI et DEFI pour les indicateurs communs | M | (T) `II.1-D6-7-1` et `II.1-D2-7-1` partagent l'indicateur `II.1-D*-7-1` ; (T) la table de correspondance DEFI couvre les codes renumérotés |
| F9 | Marquage des indicateurs à caractère personnel (ex. nom du directeur) : jamais envoyés à une API externe | M | (T) aucune valeur de ces colonnes dans les prompts (sonde canari) |
| F10 | Qualité d'extraction mesurée sur 10 à 20 PDF annotés à la main (JSON de référence) : précision, rappel, F1 par champ | M | (M) rapport dans `docs/` et dans le rapport ; non-régression *oracle* ≥ 99,5 % de cellules identiques au prototype, écarts expliqués |
| F11 | Comparaison Docling / extracteur déterministe sur les fiches annotées, et meilleur extracteur retenu par type de section | S | (M) tableau F1 par type de section |
| F12 | Repli LLM à sortie structurée (schéma Pydantic) uniquement pour les sections où l'extraction déterministe échoue, avec marquage de la méthode | C | (T) les valeurs issues du repli portent `methode = 'llm'` et une confiance |

### 5.2 Moteur Text-to-SQL

| ID | Exigence | Prio | Critère d'acceptation |
|---|---|---|---|
| F13 | Pipeline en étapes activables par configuration : intention, *schema linking*, contexte enrichi, few-shot dynamique, génération (N candidats, décomposition), validation, exécution, auto-correction (≤ 2), vote, restitution | M | (T) chaque étape est désactivable par configuration et testée isolément avec un LLM simulé |
| F14 | Stratégies S0 à S6 décrites chacune par un fichier de configuration versionné et haché | M | (T) `nl2sql ask … --strategy s3` charge `strategies/s3.yaml` ; le hachage figure dans `meta` |
| F15 | CLI de débogage : `nl2sql ask "…" --strategy s3 --model …` | M | (D) commande documentée dans le README |
| F16 | Validation statique sqlglot (postgres) : une instruction, racine SELECT/WITH, tables du schéma `analytics` uniquement, fonctions interdites, `WITH RECURSIVE` interdit, `LIMIT` 1 000 ajouté si absent | M | (T) tests de propriétés (hypothesis) et corpus adversarial : 0 requête interdite acceptée |
| F17 | Exécution en bac à sable : rôle `nl2sql_reader` (SELECT sur `analytics` seulement), `default_transaction_read_only = on`, `statement_timeout = 5s`, transaction annulée | M | (T) intégration : le rôle ne peut ni écrire ni lire `app`/`pg_catalog` sensibles, même avec un validateur contourné |
| F18 | Garde-fou d'intention : abstention motivée (hors périmètre, sans donnée) ou clarification avec 2 à 4 choix (ambiguë) | M | (M) précision et rappel d'abstention mesurés sur C6 et C7 |
| F19 | Contrat de réponse figé (Pydantic + OpenAPI), voir §8.1 | M | (T) le schéma OpenAPI généré est comparé à un instantané versionné |
| F20 | Confiance : score combinant des signaux mesurables (accord entre candidats, auto-corrections, couverture du *schema linking*, résultat vide, colonnes ambiguës), **calibré** sur le jeu de dev (diagramme de fiabilité, ECE) ; seuils des niveaux fixés à partir des mesures | M | (M) ECE et diagramme publiés ; (T) en dessous du seuil bas, l'API renvoie `level = "faible"` et un avertissement explicite |
| F21 | Fournisseurs LLM interchangeables par configuration (Groq, Mistral, Google, OpenAI, Anthropic, local llama.cpp/Ollama) ; identifiant exact du modèle enregistré à chaque appel | M | (T) changer de fournisseur ne demande qu'une clé dans `.env` et une ligne de configuration |
| F22 | Cache disque des réponses LLM, limiteur de débit par fournisseur, comptage du coût, plafond journalier (0 $ par défaut) | M | (T) un second appel identique ne touche pas le réseau ; au-delà du plafond, refus explicite et journalisé |

### 5.3 Informer l'usager (page Question et réponse)

| ID | Exigence | Prio | Critère d'acceptation |
|---|---|---|---|
| F23 | « Ce que j'ai compris » : reformulation en français | M | (D) visible pour chaque réponse |
| F24 | Résultat en tableau paginé et graphique suggéré (barres, lignes, secteurs, indicateur chiffré) modifiable par l'utilisateur | M | (T) la suggestion dépend de la forme du résultat (1 valeur → indicateur ; catégorie × nombre → barres ; année × nombre → lignes) |
| F25 | Badge de confiance (élevée / moyenne / faible) avec les raisons au survol et au clavier | M | (D) « 5 requêtes candidates sur 5 donnent le même résultat » |
| F26 | Hypothèses retenues listées | M | (D) ex. « dernière campagne disponible : 2026 » |
| F27 | SQL repliable avec coloration syntaxique | M | (D) |
| F28 | Sources : liens vers les PDF et les pages d'origine des valeurs affichées | M | (T) chaque réponse non vide a au moins une source ; (D) le PDF s'ouvre à la bonne page |
| F29 | Avertissements explicites : résultat tronqué, vide, données manquantes pour certaines écoles ou campagnes, campagnes différentes mélangées | M | (T) une question portant sur 3 écoles dont une sans donnée produit l'avertissement correspondant |
| F30 | Abstention honnête et clarification affichées comme telles, sans chiffre | M | (D) captures des états abstention et clarification |
| F31 | Retour 👍/👎 avec correction facultative ; promotion par un admin en exemple few-shot | S | (T) un exemple promu est récupéré par le few-shot dynamique pour une question proche |
| F32 | États soignés : chargement, vide, erreur réseau ou LLM, quota atteint | M | (D) captures Playwright de chaque état jointes à la PR |

### 5.4 Tableaux de bord

| ID | Exigence | Prio | Critère d'acceptation |
|---|---|---|---|
| F33 | Épingler une réponse comme widget (graphique, tableau, indicateur chiffré) dans un tableau de bord nouveau ou existant | M | (D) parcours Playwright « épingler » |
| F34 | Grille réorganisable et redimensionnable, titres modifiables, disposition persistée | M | (T) la disposition est rechargée à l'identique |
| F35 | Rafraîchissement à la demande : la requête SQL validée est stockée, pas le résultat | M | (T) après ré-ingestion, le widget rafraîchi reflète les nouvelles valeurs |
| F36 | Filtres globaux (campagne, source, école, réseau Polytech) propagés aux widgets compatibles | S | (T) un filtre école réécrit les widgets dont la requête expose `ecole` |
| F37 | Partage en lecture à d'autres comptes | S | (T) un lecteur non destinataire reçoit 403 |
| F38 | Export PNG du tableau de bord et CSV des données d'un widget | S | (D) fichiers générés |
| F39 | Export PDF du tableau de bord | C | (D) |
| F40 | Génération assistée : « Fais-moi un tableau de bord sur X » → 4 à 6 widgets proposés, acceptés ou retirés un par un | C | (D) démonstration sur « insertion professionnelle » |

### 5.5 Administration et observabilité

| ID | Exigence | Prio | Critère d'acceptation |
|---|---|---|---|
| F41 | Gestion des comptes et des rôles (admin, éditeur, lecteur) | M | (T) matrice de droits testée par rôle |
| F42 | Journal structuré de chaque question : utilisateur pseudonymisé, stratégie, modèle, SQL, durée, coût, statut, retour | M | (T) une question crée une entrée complète ; l'identifiant n'est pas réversible sans le secret |
| F43 | Page d'administration : taux de succès, taux d'abstention, coûts, latences p50/p95, retours négatifs à traiter | M | (D) page utilisée comme démonstration à la soutenance |
| F44 | Curation des exemples few-shot (valider, modifier, retirer) | S | (T) |

### 5.6 Banc d'évaluation

| ID | Exigence | Prio | Critère d'acceptation |
|---|---|---|---|
| F45 | Jeu d'au moins 150 questions (cible 200), catégories C1–C9, SQL de référence validé par deux personnes, découpage dev 60 % / test 40 % figé et haché | M | (M) voir [protocole](docs/benchmark/protocol.md) |
| F46 | `make bench` (dev) et `make bench-test` (test, métriques agrégées seulement) régénèrent les résultats bruts (JSONL), le rapport et les figures | M | (D) régénération complète depuis un clone propre |
| F47 | Rapport : exactitude d'exécution avec IC 95 % (bootstrap), McNemar entre les deux meilleures configurations, Pareto coût/fiabilité et latence/fiabilité, ablation, taxonomie d'erreurs, ECE | M | (M) `docs/benchmark/report.md` + figures dans `rapport/figures/` |
| F48 | Mesure « avant / après » sur les 20 questions de référence, avec le même modèle | M | (M) tableau comparatif dans le rapport |

### 5.7 Déploiement

| ID | Exigence | Prio | Critère d'acceptation |
|---|---|---|---|
| F49 | Installation en une commande sur une machine vierge (Docker Compose de production, Caddy avec HTTPS) | M | (D) sortie complète de l'installation sur une VM vierge jointe à la PR |
| F50 | Sauvegardes `pg_dump` planifiées et restauration testée | M | (T) script de restauration rejoué en CI ou en recette |
| F51 | Healthchecks et redémarrage automatique des services | M | (T) un service tué redémarre |
| F52 | Guide utilisateur et guide administrateur en français | M | (D) relus par un collègue lors de la recette |
| F53 | `make zip` produit `TAI_11_code_NOM1_NOM2.zip` sans secret, sans `node_modules`, sans données personnelles | M | (T) contrôle automatique du contenu de l'archive |

## 6. Exigences non fonctionnelles (chiffrées)

| ID | Catégorie | Exigence | Vérification |
|---|---|---|---|
| NF1 | Performance | Latence de bout en bout **p95 < 8 s** pour une question simple (C1/C2) avec la stratégie de production et un modèle API ; **p95 < 20 s** pour C3/C4 | Banc (latences) + test de charge |
| NF2 | Performance | Mode local sur le serveur cible : latence mesurée et publiée (aucun seuil imposé sans GPU) | Banc |
| NF3 | Charge | 20 utilisateurs simultanés : NF1 respectée, 0 erreur 5xx | Locust ou k6 en phase 7 |
| NF4 | Économie | Prompt de génération ≤ **2 500 tokens par appel** en moyenne avec la stratégie de production (ADR 0002) | Banc (tokens) |
| NF5 | Économie | Coût d'exploitation par défaut **0 €** ; plafond journalier par fournisseur configurable | Test unitaire + configuration |
| NF6 | Sécurité | **Zéro écriture possible** via le moteur : 0 violation sur le corpus adversarial (≥ 40 cas) et sur les tests de propriétés | CI, job `adversarial` |
| NF7 | Sécurité | Toute requête interrompue en ≤ 5 s côté base ; ≤ 1 000 lignes renvoyées | Tests d'intégration |
| NF8 | Sécurité | Mots de passe en argon2id ; limitation à 30 questions/heure/utilisateur (configurable) ; 10 tentatives de connexion par 15 min | Tests d'API |
| NF9 | RGPD | Les lignes de résultat ne quittent jamais le serveur ; journaux pseudonymisés ; conservation 12 mois ; mode 100 % local disponible | Sonde canari + revue |
| NF10 | Fiabilité | La stratégie de production fait **mieux que le prototype** sur les 20 questions de référence (même modèle) et sur le jeu de test, avec IC 95 % publiés ; objectif indicatif ≥ 75 % d'exactitude d'exécution sur C1–C5 | Banc |
| NF11 | Calibration | ECE ≤ 0,10 sur le jeu de test | Banc |
| NF12 | Disponibilité | ≥ 99 % aux heures ouvrées pendant la recette ; redémarrage automatique | Supervision des healthchecks |
| NF13 | Ingestion | ≤ 30 s par PDF sur le serveur cible ; F1 ≥ 0,98 sur les champs annotés | Mesure phase 3 |
| NF14 | Qualité du code | ruff (lint + format) ; mypy strict sur `nl2sql/`, `llm/`, `ingestion/` ; TypeScript strict + eslint ; couverture ≥ 80 % sur `nl2sql/` et `ingestion/` | CI |
| NF15 | Accessibilité | Navigation au clavier complète, contrastes WCAG AA, libellés ARIA sur les graphiques | Audit axe + vérification manuelle |
| NF16 | Reproductibilité | `make bench` régénère tout le rapport ; identifiants exacts des modèles, température, graines et hachage des prompts enregistrés | Revue |
| NF17 | Maintenabilité | Chaque choix structurant a son ADR ; README, guide admin et guide utilisateur à jour ; installation reproductible | Revue |

## 7. Hors périmètre (explicite)

- Autres types de documents que CTI et DEFI (l'architecture les permet, mais ils ne sont pas implémentés), PDF scannés et OCR.
- Questions sur le texte libre des fiches par recherche sémantique (RAG documentaire) : on répond par des requêtes SQL sur les données structurées.
- Modification manuelle des valeurs extraites dans l'interface (les corrections passent par l'extracteur et la ré-ingestion).
- Entraînement ou affinage de modèles.
- Modèles payants, sauf budget obtenu et accord explicite (estimation de coût préalable).
- Authentification autre que comptes locaux et CAS AMU ; application mobile ; interface en anglais.
- Prévisions ou analyses statistiques avancées au-delà de l'agrégation SQL.

## 8. Contrats d'interface entre les binômes

### 8.1 Contrat de réponse de l'API (à figer en Pydantic + OpenAPI en phase 2)

```json
{
  "question": "string",
  "interpretation": "string",
  "sql": "string | null",
  "assumptions": ["string"],
  "confidence": { "score": 0.0, "level": "élevée | moyenne | faible", "signals": { "candidate_agreement": "5/5", "self_corrections": 0, "linking_coverage": 1.0, "empty_result": false } },
  "result": { "columns": [{ "name": "string", "type": "string", "unit": "string | null" }], "rows": [[]], "row_count": 0, "truncated": false },
  "chart_suggestion": { "type": "bar | line | pie | kpi | table", "x": "string | null", "y": "string | null", "series": "string | null" },
  "sources": [{ "document_id": 0, "title": "string", "page": 0 }],
  "warnings": [{ "code": "string", "message": "string" }],
  "clarification": { "question": "string", "options": ["string"] },
  "meta": { "strategy": "s6", "strategy_hash": "string", "model": "string", "latency_ms": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0 }
}
```

Écarts volontaires par rapport au contrat du cadrage : `columns` porte le type et l'unité (utile au graphique et au formatage), `warnings` porte un code (utile aux tests et à la traduction), et `meta.strategy_hash` est ajouté (reproductibilité). `clarification` est absent ou `null` hors clarification.

### 8.2 Schéma `analytics` (première ébauche, figée à la fin du MCD en phase 3)

Seule surface visible par le LLM. Chaque vue et chaque colonne porte un `COMMENT ON` (sens, unité, exemples).

| Vue | Grain | Colonnes principales (ébauche) |
|---|---|---|
| `analytics.ecoles` | école | `ecole`, `nom_officiel`, `ville`, `reseau_polytech` |
| `analytics.documents` | document | `document_id`, `ecole`, `source` (CTI/DEFI), `campagne`, `titre`, `nb_pages` |
| `analytics.effectifs` | école × campagne × source × formation × voie × sexe | `effectif`, `dont_apprentis`, `dont_etrangers`, `dont_boursiers`, `part_femmes_pct` |
| `analytics.personnels` | école × campagne | `enseignants_chercheurs`, `enseignants_sans_recherche`, `intervenants_ext_moins_64h`, `intervenants_ext_64h_et_plus` |
| `analytics.formations` | école × campagne × formation × voie | `intitule`, `duree_accreditation`, `type_accreditation`, `derniere_rentree_accreditee`, `exigence_anglais`, `frais_annuels_eur` |
| `analytics.reussite` | école × campagne × année d'étude | `taux_reussite_pct`, `taux_redoublement_pct`, `taux_abandon_pct`, `duree_moyenne_obtention_ans` |
| `analytics.insertion_salaires` | école × campagne × formation × voie × sexe × prime | `diplomes_en_emploi`, `nb_reponses`, `salaire_brut_median_eur`, `cadres`, `cdi` |
| `analytics.international` | école × campagne × formation | `mobilite_sortante`, `mobilite_entrante`, `doubles_diplomes` |
| `analytics.ouverture_sociale` | école × campagne | `apprenants_handicap`, `sportifs_haut_niveau`, `boursiers` |
| `analytics.recherche_innovation` | école × campagne | `doctorants_cotutelle`, `creations_entreprise`, `brevets`, `heures_projet` |
| `analytics.indicateurs` | valeur élémentaire | vue générique sur `core.fait_valeur` pour les indicateurs rares : `indicateur_code`, `indicateur_libelle`, `ecole`, `campagne`, `source`, `formation`, `voie`, `population`, `valeur_num`, `valeur_texte`, `unite`, `document_id`, `page` |
| `analytics.catalogue_indicateurs` | indicateur | `code`, `libelle`, `theme`, `unite`, `type`, `definition`, `codes_equivalents` |

Toutes les vues thématiques exposent `document_id` et `page` (provenance) et la colonne booléenne `est_derniere_campagne`.

## 9. Glossaire

- **CTI** : Commission des titres d'ingénieur ; ses fiches de données certifiées sont publiées chaque année (« campagne »).
- **DEFI** : Données des écoles françaises d'ingénieurs (CDEFI-CGE-CTI).
- **Campagne** : année de collecte inscrite sur la fiche (« Campagne 2026 »). Les mesures portent souvent sur l'année universitaire précédente.
- **FISE / FISA / FISEA / FC** : formation initiale sous statut d'étudiant, sous statut d'apprenti, mixte, formation continue (« voie »).
- **Indicateur** : rubrique codée du formulaire (ex. `I.18.a`). Le **code normalisé** retire l'indice de diplôme (`II.1-D6-7-1` → `II.1-D*-7-1`).
- **Formation** : diplôme ou spécialité d'une école (indice `D1…Dn` propre à l'école dans la fiche CTI).
- **EX** (*execution accuracy*) : part des questions dont le résultat d'exécution coïncide avec celui du SQL de référence.
- **ECE** (*expected calibration error*) : écart moyen entre confiance annoncée et exactitude observée.
- ***Schema linking*** : sélection des vues et colonnes utiles à une question. **Few-shot** : exemples (question, SQL) placés dans le prompt.

## 10. Traçabilité

| Bloc | Exigences | Vérification principale | Phase |
|---|---|---|---|
| Ingestion | F1–F12, NF13 | tests pytest + rapport de qualité d'extraction | 3 |
| Moteur | F13–F22, NF4, NF6, NF7 | tests unitaires (LLM simulé), adversarial, hypothesis | 4 |
| Benchmark | F45–F48, NF10, NF11, NF16 | `make bench`, rapport | 5 |
| Interface | F23–F44, NF15 | Playwright (5 parcours critiques), captures | 6 |
| Déploiement | F49–F53, NF1–NF3, NF12 | installation sur VM vierge, Locust/k6, recette SUS | 7 |
| Livrables | — | rapport LaTeX, vidéo, poster, zip | 8 |
