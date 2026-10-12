# Repos, dispatch et vérification

Les trois dépôts, leurs cibles, leurs durées, et comment lire ce qui tourne en production.
Toutes les commandes passent par l'API GitHub de l'organisation et par l'API Elastic
Beanstalk : elles se copient telles quelles, sans chemin à adapter.

## Contents

- [Les trois dépôts](#les-trois-dépôts)
- [Lire ce qui est en ligne](#lire-ce-qui-est-en-ligne)
- [Dispatcher une release](#dispatcher-une-release)
- [Vérifier après déploiement](#vérifier-après-déploiement)
- [Rollback, et ce qu'il ne répare pas](#rollback-et-ce-quil-ne-répare-pas)

## Les trois dépôts

| | API | Front | Back-office |
| --- | --- | --- | --- |
| Dépôt | `Les-Sherpas/sherpas-api` | `Les-Sherpas/sherpas-front-static` | `Les-Sherpas/sherpas-bo` |
| Cible prod | EB `prod-sherpas-api-v2` | EB `prod-sherpas-front` | S3 `bo.sherpas.com` |
| Cible staging | EB `edu-sherpas-api` | EB `edu-sherpas-front` | S3 `boedu.sherpas.com` |
| Durée du run prod | ~13-16 min | ~28 min | ~6-8 min |
| Journal | tag `prod-<n>[-hotfix]` + label EB | tag `prod-<n>[-hotfix]` + label EB | rien : le run lui-même |
| Migrations | oui, exécutées au déploiement | non | non |
| Garde `assert-deployable.sh` | oui | oui | non |
| Skill hotfix du dépôt | `.agents/skills/ship-hotfix/` | idem | idem (publication S3 directe) |

Une release est un dépôt à la fois : chaque dépôt a son run, son tag et son label. Le BO part
moins souvent que l'API et le front, et le front moins souvent que l'API — un dépôt en retard
de plusieurs jours est le cas normal, pas une anomalie.

## Lire ce qui est en ligne

Deux lectures, une par famille de dépôt.

**API et front** : la vérité est le label de version de l'environnement Elastic Beanstalk.
Il porte `<env>-<sha>-<run>.<attempt>[-hotfix]`, donc l'environnement dit lui-même quel
commit il exécute :

```sh
aws elasticbeanstalk describe-environments \
  --region eu-west-3 --environment-names prod-sherpas-api-v2 --no-include-deleted \
  --query 'Environments[0].[Status,Health,HealthStatus,VersionLabel,DateUpdated]' --output text

aws elasticbeanstalk describe-instances-health \
  --region eu-west-3 --environment-name prod-sherpas-api-v2 --attribute-names Deployment \
  --query 'InstanceHealthList[].[InstanceId,Deployment.VersionLabel,HealthStatus]' --output text
```

Les identifiants viennent de votre environnement (`AWS_PROFILE` s'il en faut un), et des
droits de lecture suffisent. Un clone du dépôt, quand il est à portée, donne la même réponse
— et refuse de répondre quand elle est douteuse (environnement pas `Ready`, label sans SHA,
instances sur des versions différentes) :

```sh
DEV_REF=origin/dev .github/scripts/assert-deployable.sh live-sha   # imprime le SHA en ligne
```

**Back-office** : aucun marqueur en ligne, aucun tag. Ce qui tourne est le SHA du dernier run
de déploiement prod réussi, et il se lit dans le log de sa garde :

```sh
gh run list -R Les-Sherpas/sherpas-bo --workflow deploy.yml --limit 15 \
  --json databaseId,event,conclusion,createdAt -q '.[]|select(.event=="workflow_dispatch")'
gh run view -R Les-Sherpas/sherpas-bo <run-id> --log | grep -m1 "is on dev"
```

La garde imprime `Commit <sha> is on dev (status: identical|behind)` : `identical` signifie que
le BO tourne déjà sur la tête de `dev`, donc qu'il n'y a rien à livrer — le redéployer
reconstruirait le même paquet.

**La cible** est la tête de `dev` du dépôt, jamais une branche de travail :

```sh
gh api repos/Les-Sherpas/sherpas-api/commits/dev --jq .sha
```

**La plage** entre les deux — le contenu du changelog — se lit sans clone non plus :

```sh
gh api "repos/Les-Sherpas/sherpas-api/compare/<en-ligne>...<cible>" --jq '.commits[] | "\(.sha[0:9]) \(.commit.message)"'
```

## Dispatcher une release

Depuis `dev`, avec le SHA complet à 40 caractères. Un SHA court, une branche ou un tag sont
refusés par la garde, et c'est voulu : un SHA est immuable, le contrôle et ce qui part ne
peuvent pas diverger.

```sh
gh workflow run deploy.yml -R Les-Sherpas/sherpas-api          --ref dev -f sha=<sha-40>
gh workflow run deploy.yml -R Les-Sherpas/sherpas-front-static --ref dev -f sha=<sha-40>
gh workflow run deploy.yml -R Les-Sherpas/sherpas-bo           --ref dev -f sha=<sha-40>
```

Suivre le run sans sonder : l'attente se fait en tâche de fond, et le résultat arrive tout
seul. Un run rouge arrête la release en cours : lire les jobs en échec, rapporter, ne pas
annoncer de fin.

```sh
gh run list -R Les-Sherpas/sherpas-api --workflow deploy.yml --limit 3
gh run view -R Les-Sherpas/sherpas-api <run-id> \
  --json status,conclusion,jobs -q '{status,conclusion,jobs:[.jobs[]|{name,conclusion}]}'
```

Le workflow écrit un tag `prod-<numéro>` (API et front) et un label
`<env>-<sha>-<run>.<attempt>[-hotfix]`. Ce sont des journaux : ils ne se modifient pas à la
main.

## Vérifier après déploiement

Un run vert n'est pas une preuve : c'est le deployeur qui se félicite. La preuve est la même
lecture que celle de l'état des lieux — le label de l'environnement et la version de chaque
instance, relus **après** le déploiement.

```sh
aws elasticbeanstalk describe-environments \
  --region eu-west-3 --environment-names prod-sherpas-api-v2 --no-include-deleted \
  --query 'Environments[0].[Status,Health,HealthStatus,VersionLabel]' --output text
```

Ce qui valide la release :

1. le SHA dans le label est **exactement** la cible ;
2. le statut est `Ready` et la santé `Green` ;
3. **toutes** les instances portent ce même label.

Ce qui l'invalide, et ce que ça veut dire :

| Lecture | Signification | Suite |
| --- | --- | --- |
| label ancien, run vert | le run n'a pas déployé ce qu'il prétend | lire l'étape EB du run et la console EB avant tout |
| instances sur deux labels | déploiement roulant arrêté à mi-chemin | traiter comme un incident : redéployer, pas annoncer |
| `Status` ≠ `Ready` | un déploiement est en cours | attendre la fin, relire |
| label sans SHA | déploiement fait à la main depuis la console | signaler, corriger par une release normale |
| accès AWS refusé ou expiré | pas d'identifiants en lecture utilisables | le préflight le nomme avant de commencer |

Le back-office n'a pas d'environnement à lire : sa preuve est le run prod vert et son SHA
d'entrée, tous deux dans le log de la garde (section précédente).

## Rollback, et ce qu'il ne répare pas

```sh
gh workflow run deploy.yml -R Les-Sherpas/sherpas-front-static --ref dev -f sha=<sha-connu-bon>
gh workflow run deploy.yml -R Les-Sherpas/sherpas-api --ref dev -f sha=<sha-connu-bon> -f rollback=true
```

Ne rien faire de tout cela sans lecture préalable, et sans demande explicite de l'utilisateur :

- **API** : le déploiement exécute les migrations, et aucune migration n'est jamais annulée
  automatiquement. Revenir sur un commit antérieur à une migration laisse du vieux code sur un
  schéma neuf. Le bloc ROLLBACK en tête de `deploy.yml` dit quoi faire, et il se lit avant, pas
  pendant.
- **Front** : application seule, sans migration — un retour en arrière est sûr.
- **BO** : la publication S3 écrase le paquet en place et ne garde aucun historique. Le seul
  retour possible est de redispatch un SHA connu-bon.
- Le paramètre `rollback=true` existe pour repasser volontairement en dessous de ce qui est en
  ligne (un hotfix, typiquement). Il ne se pose pas « au cas où » : la garde refuse par défaut
  tout ce qui retirerait un commit en ligne.
