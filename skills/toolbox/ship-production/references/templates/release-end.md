# Modèle — fin de release (#builders)

À envoyer sur `#builders`, **après** la vérification AWS. Tout ce qu'il contient doit avoir
été lu, pas déduit : le label vient d'Elastic Beanstalk, l'URL du run du run lui-même.

```
✅ **Release {{API|front|back-office}} en production terminée**

{{L'API|Le front}} tourne sur `{{sha-court}}` depuis {{HH:MM}} (label EB `{{label-lu-dans-AWS}}`). Run vert en {{n}} min : {{URL du run}}

Instances vérifiées dans AWS : `Ready` / `Green`, les deux sur la nouvelle version. Tag `prod-{{n}}`.
```

Blocs à ajouter selon le cas :

```
L'API est bien sur `{{sha-court}}` (label `{{label}}`) : les deux moitiés sont alignées.
```

```
Le back-office tourne sur `{{sha-court}}` (publication S3, run {{URL}}) : il n'a pas de label de version à lire.
```

## Ce que le message doit porter

- **Le SHA en ligne et le label l'un à côté de l'autre** : le label est la preuve, un SHA
  seul ne prouve rien.
- **L'état des trois dépôts**, y compris celui qui n'a pas bougé dans cette release — sinon
  « et le front ? » arrive dans le fil.
- **Le tag du run** quand le dépôt en pose un.
- Deux dépôts dans la même fenêtre se terminent par la phrase qui dit que les deux moitiés
  sont alignées : c'est la question que tout le monde se pose.

Ce message ne se poste pas sur un run rouge, ni sur une vérification incomplète : l'incident
se rapporte tel quel, en nommant ce qui n'a pas bougé.
