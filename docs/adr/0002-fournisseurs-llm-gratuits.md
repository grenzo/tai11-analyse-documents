# ADR 0002 — Fournisseurs LLM gratuits et règles d'envoi des données

- Statut : proposé (26/11/2026), à valider avec SPEC.md
- Décideurs : équipe TAI 11
- Lié à : [ADR 0001](0001-refonte-ou-reprise.md), [modèle de menace](../threat-model.md) (T6, T7), [protocole de benchmark](../benchmark/protocol.md)

## Contexte

Le budget est nul. L'abonnement Claude Code sert à développer, pas à faire tourner l'application ni le benchmark. Le sujet demande pourtant un « benchmark de différentes API LLM » et une solution déployée. Il faut donc :

1. au moins 4 modèles utilisables gratuitement, dont au moins 2 modèles open-weight locaux de tailles différentes ;
2. des règles claires sur ce qui peut être envoyé à une offre gratuite, puisque ces offres peuvent conserver ou réutiliser les données.

Les conditions changent souvent : celles-ci ont été relevées le **26/11/2026**. Le niveau de confiance dépend de la source : page officielle lue (★★★) ou sources secondaires concordantes (★★).

## Relevé des offres (26/11/2026)

| Fournisseur | Modèles gratuits pertinents | Limites gratuites | Conservation / entraînement | Confiance |
|---|---|---|---|---|
| **Groq** | `openai/gpt-oss-20b`, `openai/gpt-oss-120b` (production) ; `qwen/qwen3.8-27b` (aperçu) | 30 req/min, 1 000 req/jour, **8 000 tokens/min, 200 000 tokens/jour**, par modèle et par organisation ; les tokens servis depuis le cache ne comptent pas | Par défaut, aucune conservation des requêtes, sauf des journaux gardés jusqu'à 30 jours pour la fiabilité et les abus (désactivable) ; *Zero Data Retention* activable ; la page ne dit rien de l'entraînement. Les modèles Llama ne sont plus dans l'offre gratuite (accès « Enterprise ») | ★★★ (pages Groq *rate-limits*, *your-data* et *models*) |
| **Google Gemini API** (AI Studio) | Modèles « Flash » | Quotas très bas et changeants : environ 5 req/min et **20 req/jour** pour Flash selon des relevés d'octobre 2026 ; plus de modèles Pro gratuits depuis avril 2026 | Les données de l'offre gratuite **servent à améliorer les produits**, avec relecture humaine possible ; ce n'est plus le cas dès que la facturation est activée | ★★ |
| **Mistral** (La Plateforme) | Offre gratuite (« Experiment »/« Studio ») | Limites qui ne sont plus publiées clairement (auparavant environ 1 req/s) | **Entraînement sur les données par défaut**, désactivable dans la console d'administration | ★★ |
| **OpenRouter** | Modèles suffixés `:free` | 20 req/min ; **50 req/jour**, ou 1 000 req/jour après un achat unique de 10 $ de crédits | Politique propre à chaque hébergeur sous-jacent | ★★ |
| **Cerebras** | — | Plus d'offre gratuite permanente : un crédit d'essai de 5 $ valable 30 jours, avec carte bancaire | — | ★★ |
| **Anthropic, OpenAI** | — | Pas d'offre gratuite d'API connue ; réservés au cas où un budget serait obtenu | Pas d'entraînement sur les données de l'API (offres payantes) | ★★ |
| **Local** (llama.cpp / Ollama) | Open-weight : familles Qwen3.x, gpt-oss-20b, Mistral Small… | Aucune limite de quota ; limité par le matériel (pas de GPU sur les postes de dev ; serveur du département inconnu) | **Aucune donnée ne sort** | ★★★ |

Constat mesuré pendant l'audit : un appel du prototype pèse 5 000 à 7 500 tokens, et une question demande 3 à 6 appels. Avec le quota gratuit de Groq (200 000 tokens/jour), le prototype ne traite qu'**environ 6 à 8 questions par jour et par modèle**. La taille des prompts est donc une contrainte économique autant qu'une contrainte de fiabilité.

Sources : [Groq — Rate limits](https://console.groq.com/docs/rate-limits), [Groq — Your data](https://console.groq.com/docs/your-data), [Groq — Models](https://console.groq.com/docs/models), [Gemini API free tier (aifreeapi, oct. 2026)](https://www.aifreeapi.com/en/posts/gemini-api-rate-limits-per-tier), [Mistral La Plateforme et entraînement (shieldra, juil. 2026)](https://www.shieldra.ai/ai-vendors/mistral-la-plateforme), [OpenRouter free tier (klymentiev)](https://klymentiev.com/blog/openrouter-free-tier), [Cerebras free tier remplacé (toolfreebie)](https://toolfreebie.com/cerebras-free-api/).

## Options

1. **Tout en local** : confidentialité maximale et aucun quota, mais lent sans GPU, et pas de « benchmark d'API » au sens du sujet.
2. **Tout en API gratuite** : rapide à mettre en place, mais les quotas sont incompatibles avec la matrice complète du benchmark, et la réutilisation des données est incertaine.
3. **Mixte** (retenu) : modèles locaux pour la matrice complète et pour le mode « souverain » ; offres gratuites d'API pour comparer, sur un sous-ensemble défini dans le protocole.

## Décision

1. **Matrice par défaut** (à figer dans le protocole, avec les identifiants exacts) :
   - Groq `openai/gpt-oss-20b` et Groq `openai/gpt-oss-120b` ;
   - Mistral, offre gratuite, avec l'entraînement désactivé dans la console, si l'offre est encore disponible au démarrage de la phase 5 ;
   - 2 modèles open-weight locaux de tailles différentes, par exemple Qwen3.x autour de 4 Mds de paramètres et `gpt-oss-20b` local. Le choix final dépend du matériel disponible (question posée au département).
   - Gemini Flash gratuit est **exclu de la matrice principale** (20 req/jour) et sert seulement au *smoke bench* de 20 questions, si le quota le permet.
2. **Règles d'envoi vers une API externe** : seulement le schéma `analytics` (DDL et `COMMENT ON`), la question et les exemples few-shot validés.
   - Jamais les lignes de résultat.
   - Jamais les valeurs de colonnes marquées « personnelles » dans le catalogue, par exemple `I.10 Nom du directeur / de la directrice`.
   - Les valeurs d'exemple ne viennent que de colonnes catégorielles en liste blanche, et peuvent être désactivées par fournisseur.
3. **Réglages des comptes**, à faire par le titulaire de chaque compte : activer *Zero Data Retention* chez Groq ; désactiver l'entraînement chez Mistral.
4. **Garde-fous de coût**, dès le premier jour :
   - cache disque des réponses (même modèle, mêmes messages, mêmes paramètres : pas de nouvel appel) ;
   - limiteur de débit propre à chaque fournisseur (req/min, tokens/min, tokens/jour) ;
   - reprise après interruption ;
   - table des prix par modèle, comptage du coût par appel, plafond journalier configurable (0 $ par défaut).
5. **Fournisseur payant plus tard** : une clé dans `.env` et une ligne dans la configuration des modèles, sans changement de code.
6. **Revérifier ce relevé** au démarrage de la phase 5 et consigner les écarts dans cet ADR.

## Conséquences

- Le nouveau moteur doit tenir dans **environ 2 500 tokens par appel** (schéma restreint par le *schema linking*, prompt court), sinon la matrice API ne tient pas dans les quotas. Cet objectif devient une exigence non fonctionnelle de SPEC.md.
- La matrice complète (7 stratégies, ablation, 3 répétitions pour la stabilité) tourne sur les modèles locaux. Les API gratuites tournent sur un sous-ensemble défini dans le protocole (stratégies S0, S2 et la meilleure, au minimum).
- Sans GPU, le benchmark local est lent : c'est un risque du PLAN (plan B : machine GPU du département ou de la plateforme de calcul de l'université).
- Le « mode local » est un vrai mode de production, pas seulement une option de test.
