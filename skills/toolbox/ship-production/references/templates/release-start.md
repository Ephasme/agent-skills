# Modèle — début de release (#builders)

À envoyer sur `#builders`, juste avant le dispatch. Ce fichier **est** le message : on
remplit les `{{…}}`, on ne recompose pas les phrases.

```
🚀 **Release {{API|front|back-office}} en production**

Je lance un déploiement {{de l'API|du front|du back-office}} en production depuis `dev` (`{{sha-court}}`), maintenant — {{n}} commits depuis la dernière mise en production ({{date}}).

Dont, côté visible : {{#PR (libellé court)}}, {{#PR (libellé court)}} ; le reste en CI / tests / documentation ({{#PR}}).

{{Au besoin — dépôt déjà en ligne : Le {{back-office|front}} n'est pas concerné : il tourne déjà sur le `dev` du jour (`{{sha-court}}`, déployé à {{HH:MM}}).}}

{{API uniquement, s'il y a des migrations : {{n}} migrations passent au déploiement ({{effet observé : colonne instantanée, index sur une petite table, nouvelle table}}) : aucun blocage d'écriture attendu.}}

Je poste ici dès que c'est terminé ({{durée}} de run).
```

## Ce que le message doit porter

- **Le dépôt, le SHA, et ce qu'il contient** en une ligne : les numéros de PR suffisent, et
  ils se regroupent — côté visible d'un côté, CI / tests / documentation de l'autre.
- **Un dépôt non concerné par la release se dit ici**, dans ce message : sinon la question
  se pose dans le fil.
- **La ligne sur les migrations ne s'écrit que pour l'API**, et seulement après avoir lu les
  fichiers de migration. Elle dit ce que le déploiement fera aux écritures — jamais au jugé.
- **« Je poste ici dès que c'est terminé »** engage : la fin se poste réellement après la
  vérification, pas à la fin du run.

Le message part **juste avant** le dispatch, pas la veille : c'est une annonce de début, sa
valeur est d'être vraie au moment où on la lit.
