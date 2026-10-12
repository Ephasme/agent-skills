# Changelog (#general)

Le gabarit du changelog, ses règles de rédaction et la présentation du brouillon
appartiennent au skill `post-deploy-changelog` : l'appeler, et écrire depuis son gabarit.

Ce fichier porte les règles qui viennent de la release elle-même :

## La plage

C'est celle de l'état des lieux : ce qui était en ligne avant, ce qui l'est après. Elle se
borne avec ce que les gens ont reçu, pas avec l'historique des tags ni avec ce qui a été
dispatché.

## Un correctif parti en hotfix reste à annoncer

S'il a été livré plus tôt en hotfix et jamais annoncé publiquement, il apparaît dans la
plage : on le garde. Le public de #general ne connaît pas la différence entre une release et
un hotfix, il connaît ce qu'il a reçu.

## Une fonctionnalité derrière un drapeau éteint se dit « pas encore activé »

Elle est livrée — c'est un fait — mais elle ne change rien pour personne tant que le drapeau
est fermé. Le taire serait mentir par omission, et la présenter comme active le serait aussi.

## Un message par version livrée

Deux déploiements le même jour, ce sont deux versions, donc deux messages. Et un second
message dans le même canal ne se justifie pas par « pour compléter » : il se justifie par des
faits nouveaux.
