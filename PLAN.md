# PLAN — TAI 11 (26/11/2026 → 29/01/2027)

> Version 0.1 du 26/11/2026, mise à jour à chaque fin de phase. Les réunions et rendus intermédiaires fixés par les encadrants (S. Ayache, J.-M. Latarjet) seront ajoutés ici dès qu'ils seront connus : **aucun n'est connu à ce jour**.

## 1. Jalons

| Jalon | Date | Contenu | Critère de passage |
|---|---|---|---|
| **J0** | jeu. 26/11 | Phases 0–1 : audit, ADR 0001–0002, SPEC, PLAN, modèle de menace, protocole (PR `docs/cadrage`) | PR ouverte |
| **J1** | lun. 30/11 | Validation de SPEC.md et de l'ADR 0001 ; réponses aux questions de cadrage | PR fusionnée ; prototype déplacé dans `legacy/` |
| **J2** | ven. 04/12 | Phase 2 : fondations (dev container, Makefile, CI, pre-commit, `CLAUDE.md`, `.claude/`), contrat OpenAPI v1 et moteur simulé | CI verte sur `main` ; `make check` passe depuis l'hôte |
| **J3** | mer. 09/12 | MCD/MLD validés (Mermaid) ; schéma `analytics` v1 figé (interface entre binômes) | Validation écrite dans la PR du MCD |
| **J4** | ven. 18/12 | Démo interne de bout en bout : 43 documents ingérés, moteur S2 réel, page Question et réponse branchée | Parcours « poser une question » vert en local |
| — | 19/12 → 03/01 | Vacances (capacité estimée à 30 %) : rédaction et double validation des questions du banc, PDF annotés, exécutions locales du banc pendant la nuit | ≥ 150 questions rédigées au 03/01 |
| **J5** | ven. 08/01 | Protocole de benchmark **figé** ; jeu de test haché ; stratégies S0–S6 implémentées ; préproduction sur le serveur (si l'accès est obtenu) | Hachage consigné dans `protocol.md` |
| **J6** | ven. 15/01 | Matrice dev complète ; calibration de la confiance ; ADR « stratégie et modèle de production » ; tableaux de bord complets | `docs/benchmark/report.md` généré |
| **J7** | ven. 22/01 | Déploiement de production, tests de charge, recette avec 3 à 5 collègues (scénarios + SUS), corrections | Installation sur VM vierge réussie ; rapport de recette |
| **J8** | **dim. 24/01** | **Gel du code** ; `make bench-test` lancé **une seule fois** | Tag `v1.0.0` |
| **J9** | **mer. 27/01, 23 h 59** | **Rendu** : `TAI_11_rapport_NOM1_NOM2.pdf`, `TAI_11_code_NOM1_NOM2.zip`, `TAI_11_video_NOM1_NOM2.mp4` | Fichiers déposés |
| **J10** | **ven. 29/01** | **Soutenance** (30 min, format poster) | Poster imprimé le jeudi 28/01 |

## 2. Découpage en deux lots parallèles

| | **Binôme A — Données et IA** | **Binôme B — Produit et déploiement** |
|---|---|---|
| Répertoires | `ingestion/`, `nl2sql/`, `llm/`, `eval/` | `backend/` (routes, authentification, schéma `app`), `frontend/`, `deploy/` |
| Phases principales | 3, 4, 5 | 6, 7 |
| Exigences | F1–F22, F45–F48, NF4, NF6, NF7, NF10, NF11, NF13, NF16 | F23–F44, F49–F53, NF1–NF3, NF8, NF12, NF15 |
| Livre à l'autre lot | Schéma `analytics` (J3), moteur réel derrière le contrat (J4), stratégie de production (J6) | Pages et parcours, journal des questions (données pour la calibration), environnement de préproduction |
| Ensemble | Phases 0, 1, 2 et 8 ; relecture croisée de toutes les PR ; seconde validation du SQL de référence du banc | |

**Interfaces figées** (voir [SPEC §8](SPEC.md#8-contrats-dinterface-entre-les-binômes)) :

1. le **contrat de réponse** (Pydantic + OpenAPI, instantané versionné et testé) ;
2. le **schéma `analytics`** (vues et colonnes commentées).

Le binôme B développe contre un **moteur simulé** qui renvoie des réponses enregistrées (succès, vide, abstention, clarification, erreur), jusqu'au jalon J4.

### Lots de travail et estimation (jours-personne d'ingénierie)

| Lot | Contenu | Prio | Estimation |
|---|---|---|---|
| A1 | Portage des extracteurs en plugins, idempotence, unicité, test oracle (≥ 99,5 %) | M | 6 |
| A2 | MCD/MLD, migrations Alembic, catalogue d'indicateurs et correspondances, vues `analytics` commentées | M | 7 |
| A3 | Validateur sqlglot, rôle en lecture seule, corpus adversarial, puis pipeline S0–S6 et confiance | M | 11 |
| A4 | Abstraction `llm/` : fournisseurs, cache, limiteur, coûts | M | 3 |
| A5 | Banc : 150 à 200 questions doublement validées, runner, statistiques, rapport, figures | M | 10 |
| A6 | Qualité d'extraction : 10 à 20 PDF annotés, P/R/F1 ; comparaison Docling | M / S | 3 |
| B1 | API FastAPI, authentification et rôles, schéma `app`, journal des questions | M | 5 |
| B2 | Page Question et réponse (états, confiance, sources, SQL, avertissements, retours) | M | 5 |
| B3 | Tableaux de bord (épingler, grille, rafraîchir, filtres, partage, exports) | M / S | 6 |
| B4 | Pages Documents et Administration (métriques, curation few-shot, comptes) | M / S | 3 |
| B5 | Déploiement (Compose de production, Caddy HTTPS, sauvegardes et restauration, installation en une commande) | M | 4 |
| B6 | Playwright (5 parcours), tests de charge, recette SUS | M | 3 |
| C1 | Génération assistée de tableaux de bord, export PDF, repli LLM d'extraction | C | 4 |
| Ensemble | Fondations (phase 2) ; livrables (rapport, vidéo, poster, zip) | M | 10 |
| **Total** | | | **≈ 80 (≈ 66 hors C et hors « S » secondaires)** |

**Capacité supposée** : 4 personnes × environ 2 jours par semaine × 8 semaines, vacances comptées à 30 %, soit **environ 55 à 60 jours-personne humains**. L'implémentation assistée par Claude Code réduit fortement le temps de codage, mais la relecture, l'annotation, la recette et la rédaction restent humaines. **Les exigences C et les « S » secondaires (F36, F38, F44) sont la variable d'ajustement**, à arbitrer au jalon J5. Hypothèse D8 de SPEC, à confirmer.

## 3. Calendrier détaillé

| Semaine | Binôme A | Binôme B | Ensemble |
|---|---|---|---|
| S48 (26–29/11) | — | — | Audit, SPEC, PLAN, ADR, modèle de menace, protocole |
| S49 (30/11–06/12) | Contrat Pydantic du moteur ; script oracle (extraction du prototype → JSON) | Squelette FastAPI ; moteur simulé ; squelette React | Phase 2 ; déplacement dans `legacy/` |
| S50 (07–13/12) | MCD → J3 ; migrations ; portage CTI/DEFI ; validateur + rôle + adversarial | Authentification et rôles ; page Question et réponse (sur le simulé) ; page Documents | Revue croisée du MCD |
| S51 (14–20/12) | Ingestion des 43 documents ; vues `analytics` ; S0–S2 ; 60 premières questions | Confiance, sources, SQL, avertissements ; grille des tableaux de bord | **J4** démo de bout en bout |
| Vacances (21/12–03/01) | Questions du banc (≥ 150) ; PDF annotés ; exécutions locales | Exports, partage | Seconde validation du SQL de référence |
| S01 (04–10/01) | S3–S6, confiance ; **protocole figé (J5)** | Administration ; préproduction | — |
| S02 (11–17/01) | Matrice dev ; calibration ; ADR de production (**J6**) | Compose de production ; sauvegardes ; installation sur VM ; Playwright | Plan du rapport |
| S03 (18–24/01) | Corrections ; figures du rapport | Tests de charge ; recette SUS (**J7**) | Rapport ; **gel le 24/01** ; `make bench-test` |
| S04 (25–29/01) | — | — | Vidéo, zip, **rendu le 27/01**, poster, **soutenance le 29/01** |

## 4. Risques et plans B

| # | Risque | P | I | Signal d'alerte | Plan B |
|---|---|---|---|---|---|
| R1 | Pas de GPU, ni sur les postes ni sur le serveur : banc local très lent | E | M | Une question locale prend plus de 2 min | Machine GPU du département ou mésocentre AMU ; à défaut, petit modèle local (≈ 4 Mds) et matrice locale réduite |
| R2 | Quotas gratuits trop bas ou modifiés (déjà constaté : 6 à 8 questions/jour pour le prototype) | E | M | Erreurs 429 répétées | Prompts ≤ 2 500 tokens (NF4), cache, plusieurs fournisseurs, sous-ensemble de questions pour les API |
| R3 | Accès au serveur du département tardif ou impossible | M | E | Pas d'accès au 08/01 | Installation validée sur VM vierge ; démo sur machine portable ; procédure transmise à l'administrateur |
| R4 | Régression de l'extraction lors du portage | M | M | Test oracle < 99,5 % | Les écarts sont expliqués un par un ; on garde la fonction du prototype telle quelle si besoin |
| R5 | Périmètre trop large pour la capacité | E | E | Retard de plus d'une semaine sur J4 | Arbitrage MoSCoW à J5 : on retire d'abord les C, puis F36, F38, F44 |
| R6 | Annotation du banc (150 à 200 questions, double validation) sous-estimée | E | E | < 100 questions au 03/01 | Gabarits de questions tirés du catalogue ; répartition sur les 4 personnes ; 150 au minimum |
| R7 | Faible disponibilité pendant les vacances et les examens | E | M | — | Travail asynchrone sur les questions ; exécutions de nuit |
| R8 | Données incohérentes dans les nouveaux PDF (campagnes, doublons) | M | M | Avertissements à l'ingestion | Contrôles F3/F4 et statut « à décider » |
| R9 | Auteur du prototype indisponible | M | F | — | Audit et tests oracle suffisent pour reprendre l'extraction |
| R10 | Mesure « avant » incomplète (quota, clé) | M | M | < 20 questions au 04/12 | Relancer le script chaque jour ; sinon mesure sur un modèle local, avec mention explicite |
| R11 | Fournisseur d'API qui modifie un modèle sans prévenir | M | M | `system_fingerprint` qui change | Identifiant et empreinte enregistrés ; exécutions de test regroupées le 24/01 |

## 5. Rituels et règles

- Une branche par tâche (`feat/…`, `fix/…`, `docs/…`, `bench/…`) et une PR par sujet, relisible en 10 minutes ; fusion après CI verte et relecture humaine par l'autre binôme.
- Point d'équipe hebdomadaire (30 min, lundi) : avancement des jalons, risques, arbitrages ; compte rendu dans la PR de mise à jour de ce PLAN.
- Fin de chaque phase : compte rendu (fait, preuves, écarts à SPEC, ADR, risques) et mise à jour de ce fichier.

## 6. Suivi

| Phase | Statut | Date | Compte rendu |
|---|---|---|---|
| 0 — Audit | ✅ fait (mesure « avant » en attente de la clé Groq) | 26/11 | [docs/audit.md](docs/audit.md) |
| 1 — Spécification et plan | ✅ proposé, en attente de validation | 26/11 | PR `docs/cadrage` |
| 2 — Fondations | à faire | — | — |
| 3 — Modélisation et ingestion | à faire | — | — |
| 4 — Moteur Text-to-SQL | à faire | — | — |
| 5 — Benchmark | à faire | — | — |
| 6 — Application web | à faire | — | — |
| 7 — Déploiement et tests | à faire | — | — |
| 8 — Livrables | à faire | — | — |
