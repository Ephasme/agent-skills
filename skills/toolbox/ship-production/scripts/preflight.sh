#!/usr/bin/env bash
#
# Préflight d'une release en production : les dépendances sont-elles là ?
#
# Une ligne par dépendance, avec le remède quand elle manque. Sortie non nulle
# dès qu'une dépendance bloquante est absente — la release ne commence pas sur un
# préflight rouge.
#
# Rien ici n'est propre à une personne : les dépôts, les environnements, le
# store de skills et les canaux sont ceux de l'organisation. Ce qui dépend de la
# machine se règle par variable d'environnement.
#
# Usage :
#   scripts/preflight.sh
#   AWS_PROFILE=<profil en lecture> scripts/preflight.sh    # si la chaîne
#       d'identifiants par défaut réclame un MFA interactif
#   SKILLS_STORES="/un/store /un/autre" scripts/preflight.sh
#
# Sans -e : on veut aller au bout et tout rapporter, pas s'arrêter au premier échec.

set -uo pipefail

ORG=Les-Sherpas
REPOS=(sherpas-api sherpas-bo sherpas-front-static)
EB_ENVS=(prod-sherpas-api-v2 prod-sherpas-front)
AWS_REGION=eu-west-3
SKILLS_STORES="${SKILLS_STORES:-$HOME/.agents/skills}"
COMPANION_SKILL=post-deploy-changelog

fail=0
ok() { printf '  OK   %s\n' "$1"; }
warn() { printf '  WARN %s\n       → %s\n' "$1" "$2"; }
bad() { printf '  FAIL %s\n       → %s\n' "$1" "$2"; fail=1; }
info() { printf '  ·    %s\n' "$1"; }
section() { printf '\n%s\n' "$1"; }

section "Outils"
for bin in gh aws; do
  if command -v "$bin" >/dev/null 2>&1; then
    ok "$bin présent ($(command -v "$bin"))"
  else
    bad "$bin absent" "installer $bin, puis relancer ce préflight"
  fi
done
if command -v git >/dev/null 2>&1; then
  info "git présent — utile seulement pour lancer la garde du dépôt à blanc"
else
  info "git absent — sans clone local, la garde du dépôt s'exécute de toute façon dans le run"
fi

section "GitHub (dispatch des workflows)"
if gh auth status >/dev/null 2>&1; then
  ok "gh authentifié ($(gh api user --jq .login 2>/dev/null || echo 'compte inconnu'))"
else
  bad "gh non authentifié" "gh auth login"
fi
for repo in "${REPOS[@]}"; do
  if gh api "repos/$ORG/$repo" --jq .full_name >/dev/null 2>&1; then
    ok "accès à $ORG/$repo"
  else
    bad "accès refusé à $ORG/$repo" "vérifier le compte actif (gh auth status) et l'accès au dépôt"
  fi
done

section "AWS (lecture du SHA en ligne)"
for env_name in "${EB_ENVS[@]}"; do
  out="$(aws elasticbeanstalk describe-environments --region "$AWS_REGION" \
    --environment-names "$env_name" --no-include-deleted \
    --query 'Environments[0].[Status,VersionLabel]' --output text 2>&1)" && {
    ok "$env_name : $(printf '%s' "$out" | tr '\t' ' ')"
    continue
  }
  bad "$env_name illisible" "aucun identifiant AWS en lecture utilisable ($(printf '%s' "$out" | tr -s '[:space:]' ' ')) — AWS_PROFILE=<profil en lecture>, ou une session par le skill assume-aws-admin si le compte n'en a pas"
done

section "Skills compagnons"
found=""
for store in $SKILLS_STORES; do
  if [ -f "$store/$COMPANION_SKILL/SKILL.md" ]; then
    found="$store"
    break
  fi
done
if [ -n "$found" ]; then
  ok "$COMPANION_SKILL présent ($found)"
else
  warn "$COMPANION_SKILL introuvable dans : $SKILLS_STORES" "npx -y skills add git@github.com:Ephasme/agent-skills.git --skill $COMPANION_SKILL -g --yes — le vrai test reste de pouvoir le charger"
fi

if [ "$fail" -eq 0 ]; then
  printf '\nPréflight OK.\n'
else
  printf '\nDépendances manquantes : corriger chaque FAIL avant de commencer.\n'
fi
exit "$fail"
