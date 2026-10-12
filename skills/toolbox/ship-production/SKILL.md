---
name: ship-production
description: >-
  Mène une release Sherpas en production de bout en bout, dans un ordre imposé :
  établir par dépôt ce qui est en ligne et ce qui part (API, back-office, front),
  annoncer le début sur #builders, dispatcher le workflow Deploy de chaque dépôt
  avec le SHA de `dev`, suivre le run, vérifier dans AWS que la prod tourne bien
  sur le nouveau SHA, annoncer la fin, puis publier le changelog sur #general.
  Utilise ce skill dès qu'il est question de mettre en
  production — « release l'API / le BO / le front », « déploie la release en
  prod », « préviens #builders », « fais le changelog de ce qu'on vient de
  livrer », « annonce la nouvelle version » — ou de dérouler la séquence
  annonce → release → vérification → annonce → changelog, même sans le mot
  « release ». Pas pour un hotfix (un correctif seul par-dessus la prod en
  cours) : chaque dépôt porte son propre skill `ship-hotfix`.
compatibility: >-
  Les trois dépôts Les-Sherpas (sherpas-api, sherpas-bo, sherpas-front-static),
  la CLI `gh` authentifiée sur ces dépôts, un accès AWS en lecture à Elastic
  Beanstalk (compte 226016658082, eu-west-3) et le Slack Les-Sherpas
  (canaux #builders et #general).
---

# Release Sherpas en production

Une release, c'est un préflight puis sept phases, dans cet ordre. Aucune ne se saute : les
messages encadrent le déploiement, et le changelog vient après la vérification.

| # | Phase | Ce qui est produit | Où |
| - | ----- | ------------------ | -- |
| 0 | Préflight | les dépendances disponibles : outils, GitHub, AWS, clones, skills | local |
| 1 | État des lieux | ce qui est en ligne, ce qui part, par dépôt | local + AWS |
| 2 | Brouillons | les textes exacts, validés par l'utilisateur | chat |
| 3 | Début | « je lance la release » | #builders |
| 4 | Release | le dispatch et le run suivis jusqu'au bout | GitHub Actions |
| 5 | Vérification | le SHA réellement en ligne, lu dans AWS | AWS |
| 6 | Fin | SHA, label, run, tag, état des trois dépôts | #builders |
| 7 | Changelog | ce qui change, en langage clair | #general |

Détail des dépôts, des commandes de dispatch et de la lecture de l'état en ligne :
`references/repos.md`. Canaux et règles de forme des messages : `references/messages.md`.
Les trois messages sont des **modèles à recopier**, un fichier par message :

| Message | Modèle |
| ------- | ------ |
| Début de release | `references/templates/release-start.md` |
| Fin de release | `references/templates/release-end.md` |
| Changelog | `references/templates/changelog.md` (le gabarit appartient à `post-deploy-changelog`) |

## 0. Préflight — les dépendances d'abord

Avant tout, vérifier que ce dont la release dépend est là : l'outillage, l'accès GitHub aux
trois dépôts, un accès AWS en lecture au SHA en ligne, le skill compagnon. Le script les
interroge un par un, imprime le remède quand l'un manque, et sort en erreur dès qu'une
dépendance bloquante est absente. `$SKILL_DIR` est la notation du dossier de ce skill — pas
une variable exportée :

```sh
$SKILL_DIR/scripts/preflight.sh
```

Corriger chaque `FAIL` **avant** de commencer une phase, jamais pendant. Deux variables
d'environnement adaptent le préflight à la machine qui l'exécute : `AWS_PROFILE` quand la
chaîne d'identifiants par défaut réclame un MFA interactif, `SKILLS_STORES` quand les skills
vivent dans un autre dossier.

**La messagerie** se contrôle par un appel, et par l'agent : les serveurs MCP vivent dans la
configuration de l'agent, hors de portée d'un script. Avant la phase 3, appeler une fois
l'outil de messagerie — lire le dernier message des deux canaux visés. C'est le contrôle qui
prouve que le serveur répond ; sans réponse, la release ne se lance pas.

Le premier envoi est aussi le vrai test d'écriture, et il précède le dispatch : un refus se voit
donc avant que quoi que ce soit d'irréversible ait eu lieu.

## 1. État des lieux par dépôt

Trois dépôts, trois durées, trois façons de savoir ce qui est en ligne — jamais une seule
réponse globale : `references/repos.md` porte le tableau et les commandes.

Ce qu'il faut sortir de cette phase, pour chaque dépôt :

- **la cible** : le SHA complet de `dev`, lu par l'API GitHub
  (`gh api repos/<org>/<repo>/commits/dev --jq .sha`), ou un commit plus ancien si
  l'utilisateur en désigne un ;
- **le SHA en ligne**, lu dans AWS ou dans le dernier déploiement prod, jamais déduit d'un tag ;
- **la plage** entre les deux, qui est le contenu du changelog (phase 7) — l'API de
  comparaison la rend (`gh api repos/<org>/<repo>/compare/<en-ligne>...<cible>`).

Tout passe par `gh`. Un clone local sert à juger à blanc avant de dispatcher : c'est une
commodité, pas une dépendance.

Trois verdicts possibles, et ils se disent à l'utilisateur **avant** d'annoncer quoi que
ce soit :

| Verdict | Quand | Ce qu'on fait |
| ------- | ----- | ------------- |
| Rien à livrer | la cible est déjà en ligne | on le dit, on ne redéploie pas : le même commit reconstruit le même paquet |
| Release | la cible est sur `dev` et postérieure | le déroulé complet |
| Refus | la garde refuse le SHA | on lit le message de la garde, on ne contourne jamais |

Un dépôt en retard de plusieurs jours se déploie quand même (c'est le cas normal du front,
qui part moins souvent que l'API) — la plage du changelog s'allonge d'autant.

Avant de dispatcher l'API ou le front, la garde du dépôt sait juger à blanc, si un clone du
dépôt est à portée :

```sh
DEV_REF=origin/dev .github/scripts/assert-deployable.sh check <sha-40>
```

Elle imprime `release`, ou refuse en nommant la raison. Le contrôle à blanc évite de lancer un
run pour rien : la garde du run tranche de toute façon, et un SHA qu'elle refuse fait échouer
le job `guard`, sa raison dans le log.

## 2. Brouillons, puis accord explicite

Rien ne part sans que l'utilisateur ait vu les textes. Montrer les brouillons, et
faire confirmer en même temps :

- **les textes** des deux messages #builders et du changelog ;
- **le canal** visé, nommément — `#builders` est interne à l'équipe, `#general` parle à
  toute l'entreprise : se tromper envoie le bon texte au mauvais public ;
- **le go de production** : un déploiement prod est irréversible dans ses effets
  (les utilisateurs le reçoivent tout de suite ; l'API exécute ses migrations).
  L'accord doit porter sur cette release-ci, jamais sur une release précédente.

Une question, groupée, avec les brouillons affichés en clair : contenu, canal, go. Une
précision demandée ensuite se recompose en un nouveau brouillon, pas en une retouche
silencieuse.

## 3. Annonce de début, sur #builders

Juste avant le dispatch, pas la veille. Le message dit : le dépôt, le SHA, ce qu'il
contient en une ligne (les numéros de PR suffisent), et quand la fin sera annoncée. Un
dépôt non concerné se dit aussi — sinon la question se pose dans le fil.

Modèle `references/templates/release-start.md`, recopié tel quel.

## 4. Dispatch et suivi

Une release est un dispatch manuel du workflow `Deploy` du dépôt, depuis `dev`, avec le
SHA complet en entrée. Commande exacte par dépôt : `references/repos.md`.

- **Suivre le run** jusqu'à sa conclusion, en tâche de fond : jamais de sondage actif, et
  pas d'autre travail lancé en parallèle sur la même prod. Les durées usuelles sont dans
  `references/repos.md` (l'API ~13-16 min, le front ~28 min).
- **Un dépôt après l'autre** : chaque dépôt a son run, son tag et son label, et un run se
  suit jusqu'au bout avant de lancer le suivant.
- **Un run rouge arrête tout.** On lit les jobs en échec, on rapporte, et on ne poste pas la
  fin : un run rouge laisse la production inchangée, sauf si l'étape de déploiement a tourné
  avant l'échec — ce qui se lit dans le run.
- Le workflow ouvre un tag `prod-<numéro>` (API et front) : il sert de journal, on n'y
  touche pas à la main.

## 5. Vérification dans AWS

Un run vert atteste que le déploiement est passé ; il ne prouve pas ce que la production
exécute. La preuve est le label de version de l'environnement et la version de **chaque**
instance, relus après coup.

Des droits de lecture suffisent : cette vérification ne demande ni session d'administration
ni code MFA. Commandes, cas d'échec et ce qu'ils veulent dire : `references/repos.md`.

Ce qui compte : le SHA du label égale la cible, le statut est `Ready`, et les instances
tournent **toutes** la même version (une version mixte, c'est un déploiement roulant
arrêté à mi-chemin, et c'est un incident à traiter avant d'annoncer quoi que ce soit).

Le BO ne se lit pas dans Elastic Beanstalk : il publie un paquet statique sur S3, sans
historique de version. Sa preuve est le run de déploiement prod lui-même.

## 6. Annonce de fin, sur #builders

Elle se poste une fois la vérification faite, et elle porte les faits vérifiables : le
SHA, le label lu dans AWS, l'URL du run, le tag, et l'état des trois dépôts — y compris
celui qui n'a pas bougé. Une release en deux dépôts se termine par une phrase qui dit que
les deux moitiés sont alignées.

Modèle `references/templates/release-end.md`, recopié tel quel.

## 7. Changelog, sur #general

La rédaction (langage clair, une ligne par sujet, emoji de catégorie, filtrage des
commits purement internes, brouillon avant envoi) et le gabarit du message appartiennent au
skill `post-deploy-changelog` : le charger, le suivre, et le laisser seul porter ces règles.

Les règles propres au changelog d'une release — la plage, le correctif parti plus tôt en
hotfix, la fonctionnalité derrière un drapeau éteint, un message par version livrée — sont
dans `references/templates/changelog.md`.

## Ce qui ne se fait jamais

- Dispatcher depuis une autre référence que `dev` — la garde refuse, et c'est elle qui a
  raison.
- Poster ou dispatcher sur un accord implicite, ou réutiliser l'accord d'une release
  précédente.
- Redéployer un dépôt déjà à la cible pour « être sûr » : même commit, même paquet.
- Éditer un message envoyé pour le corriger, ou contourner la garde pour faire passer un
  SHA qu'elle refuse.
- Déclencher quelque chose qui n'est pas prévu par l'utilisateur parce qu'il n'y a « rien
  à faire » sur un dépôt — un dépôt à jour se constate et se dit, rien de plus.
