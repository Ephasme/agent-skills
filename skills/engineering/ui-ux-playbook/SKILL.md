---
name: ui-ux-playbook
description: >
  Exhaustive UI/UX audit-and-fix checklist distilled from "The UI/UX Playbook" (uxpeak):
  visual hierarchy, proximity, clarity, alignment, contrast, simplicity, whitespace, layout,
  balance, consistency, visual cues, depth and shadows, color, typography, interaction cost,
  forms, dialogs, empty and error states, mobile thumb zone. Use it whenever you build or
  change front-end UI (React/MUI/CSS components, pages, styles, design tokens), when asked to
  review a front-end pull request or diff, to audit or polish screens or mockups, or to check
  UI quality, readability, accessibility contrast or design consistency before shipping.
---

# UI/UX Playbook : audit et corrections

Ce skill transforme le livre *The UI/UX Playbook* (uxpeak, 142 pages) en une checklist vérifiable
de 145 règles, chacune avec un identifiant stable, le critère, ce qu'il faut regarder dans le code
ou à l'écran, le correctif type et la page du livre.

- `references/checklist.md` : la checklist complète, dans l'ordre du livre. **À parcourir en entier.**
- `references/examples.md` : les exemples avant/après du livre traduits en consignes de code (CSS, MUI).
- `scripts/text-audit.js` : mesure dans la page affichée les familles, tailles et graisses de police,
  le texte < 12px, les contrastes sous AA, le noir/blanc pur, l'interlignage et la longueur de ligne.

## Quand l'utiliser

- Tu construis ou modifies une interface front (composant, page, style, token de design system).
- On te demande de relire la PR ou le diff front de quelqu'un d'autre.
- On te demande d'auditer, de polir ou de comparer des écrans, des captures ou des maquettes.

## Règles de préséance

1. Accessibilité (contraste AA, état jamais porté par la seule couleur) et exactitude du parcours
   passent avant toute recommandation esthétique.
2. Le design system du projet (thème MUI, tokens, composants partagés, `AGENTS.md`) est la référence
   d'implémentation : on corrige en utilisant ses tokens et composants, jamais en introduisant une
   valeur hors système pour coller au livre. Si un token du système viole lui-même une règle
   (ex. gris de texte sous AA), le signaler comme constat sur le token, sans le modifier en douce.
3. Les valeurs chiffrées du livre (16px, 1.5-1.6, 45-75 caractères, multiples de 4, 4.5:1, 2 polices,
   3 niveaux d'ombre) sont les valeurs par défaut quand le projet n'en définit pas.
4. Le livre admet des exceptions délibérées (DEPTH-11, TYPO-14, CONS-09) : une entorse cohérente,
   assumée et équilibrée n'est pas un constat ; une entorse accidentelle l'est.

## Mode 1 : audit et corrections pendant qu'on construit

1. **Périmètre.** Liste les écrans et composants touchés : `git diff --name-only <base>...HEAD`,
   puis remonte des composants aux routes (`pages/`, `app/`, stories) pour savoir quoi afficher.
2. **Afficher.** Si un navigateur est disponible, lance l'app ou la story et capture chaque écran
   touché en **desktop (1440 px)** et **mobile (375 px)**, avec les états pertinents : vide,
   chargement, erreur, rempli, survol/focus, sélection, modale ouverte. Exécute le contenu de
   `scripts/text-audit.js` (chemin relatif à ce skill) dans la page de chaque écran, via
   l'évaluation JavaScript de l'outil navigateur.
   Sans navigateur, travaille sur le code et les maquettes fournies, et dis-le dans le rapport.
3. **Parcourir TOUTE la checklist**, section par section, dans l'ordre. Pour chaque item note
   `ok`, `ko` ou `n/a` (sans objet, avec une raison courte). Ne saute pas une section parce qu'elle
   « ne semble pas concernée » : décide `n/a` explicitement.
4. **Corriger** chaque `ko` dans le code, en partant des plus graves, avec les tokens du projet.
   Re-capture et relance le script après correction pour prouver le résultat.
5. **Rapporter** au format ci-dessous, avec la grille de couverture.

## Mode 2 : revue de la PR front de quelqu'un d'autre

1. Récupère le diff (`gh pr diff <n>`) et la description de la PR ; identifie écrans,
   composants et états touchés comme en mode 1.
2. Affiche la branche si possible (checkout dans un worktree jetable, app locale ou preview de PR),
   en desktop et mobile ; sinon, revue sur le code et les captures de la PR.
3. Parcours toute la checklist sur **ce que la PR ajoute ou modifie**. Un défaut préexistant non
   touché par la PR va dans une section « hors périmètre » séparée, pas dans les constats.
4. Chaque constat : `fichier:ligne`, gravité, identifiant et règle du livre enfreinte, ce qui est
   observé (valeur mesurée si possible), correctif concret (le code ou le token à utiliser).
5. Par défaut, rapporte sans modifier. Applique les correctifs seulement si l'appelant le demande,
   puis repasse les items concernés. Ne publie rien sur la PR (commentaire, review) sans demande
   explicite ; un texte publié est rédigé comme une revue d'ingénieur, sans mention de l'outil.

## Gravités

| Gravité | Quand |
| --- | --- |
| **bloquant** | Échec d'accessibilité (contraste sous AA, état porté par la seule couleur, texte de corps < 12px), consigne trompeuse ou logique inversée, action destructive mal signalée, tâche principale bloquée. |
| **majeur** | Hiérarchie, cohérence ou lisibilité nettement dégradées et visibles par tout utilisateur (plusieurs CTA primaires, police/rayon/couleur de bouton incohérents, texte pleine largeur, formulaire étiré). |
| **mineur** | Finition : valeur d'espacement hors échelle, ombre dure, bordure trop marquée, icône d'un autre style. |
| **suggestion** | Piste d'amélioration du livre non obligatoire (cartes sélectionnables, effet verre, contenu complémentaire). |

La gravité indiquée dans la checklist est un défaut ; ajuste-la au contexte en le justifiant.

## Format du rapport

```markdown
## Audit UI/UX - <périmètre> (<mode : construction | revue PR <url>>)

Écrans : <liste> · Viewports : 1440 / 375 · États : <liste> · Navigateur : oui/non

### Constats (du plus grave au moins grave)
| # | Gravité | Règle | Fichier:ligne | Constat | Correctif |
| 1 | bloquant | TYPO-21 Contraste AA (p. 92) | src/.../styles.ts:42 | gris #A9A9A9 sur blanc = 2.4:1 | `theme.palette.text.secondary` (#5E5458, 7.3:1) |

### Couverture
| Section | ok | ko | n/a |
| HIER (p. 6-11) | 7 | 1 | 1 |
| ... toutes les sections ... |
Total : 145 items, <ok> ok, <ko> ko, <n/a> n/a.

### n/a justifiés
- ALIGN-05 : produit en français uniquement, pas de RTL.

### Hors périmètre (préexistant)
- ...

### Corrections appliquées (mode 1, ou mode 2 sur demande)
- TYPO-21 : `styles.ts:42` -> token text.secondary, re-mesuré 7.3:1.
```

Le rapport liste toujours la couverture complète des 18 sections : un audit sans grille de
couverture est incomplet.
