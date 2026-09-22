---
name: post-deploy-changelog
description: >-
  Rédige et publie sur Slack le changelog d'un déploiement backend/API déjà
  effectué (staging ou production) — un résumé en français, en langage clair,
  sans jargon technique, à partir des commits shippés dans ce lot. Utilise
  cette skill dès que l'utilisateur demande de préparer, rédiger, annoncer ou
  poster un changelog, une note de version, un récap de déploiement, ou un
  message "ce qu'on vient de livrer" — même sans dire explicitement
  "changelog" (ex : "préviens l'équipe de ce qu'on a déployé", "fais un
  message pour annoncer la mise en prod", "résume ce batch pour le général").
  Ne couvre PAS le déploiement lui-même (dispatch, migrations, vérifications
  post-déploiement) : cette skill part du principe que le déploiement a déjà
  eu lieu et que le SHA/la plage de commits est connue ou trouvable dans le
  repo.
compatibility: >-
  Publie via un serveur MCP Slack (n'importe lequel exposant l'équivalent de
  "poster un message" et "lire l'historique d'un canal" — ex. les serveurs
  MCP Slack usuels). Sans accès Slack, produit quand même le texte du
  changelog et s'arrête là, en indiquant qu'il reste à poster manuellement.
---

# Post-deploy changelog

Transforme une liste de commits techniques en message Slack lisible par
n'importe qui dans l'entreprise — CS, sales, ops, marketing — pas seulement
les devs. Le lecteur ne sait pas ce qu'est une migration, un endpoint, une
clé étrangère ou un webhook ; il veut savoir ce qui a changé pour lui ou pour
les clients.

## Pourquoi ce filtre est le cœur de la skill

Le piège naturel est de résumer les messages de commit tels quels, un peu
raccourcis. Un message de commit répond à "qu'est-ce que ce diff fait au
code" ; un changelog répond à "qu'est-ce qui est différent maintenant pour
quelqu'un qui utilise le produit ou qui doit répondre aux clients". Ce sont
deux questions différentes, et traduire l'une en l'autre demande de
reformuler, pas de recopier.

Un commit comme `fix(invoice): scope the title UNIQUE index to newly issued
invoices` ne veut rien dire pour quelqu'un hors tech. Ce qui compte pour
cette personne, c'est que **les numéros de facture ne se dupliquent plus**.
Le nom de la table, l'index, la contrainte SQL — tout ça reste dans le
commit, jamais dans le message.

## 1. Déterminer ce qui a été livré

Le point de départ habituel est une plage de commits entre ce qui tournait
avant en production et ce qui tourne maintenant :

```bash
git log --oneline <sha-avant>..<sha-après>
```

Si l'utilisateur n'a pas donné les deux SHA, les retrouver :
- Le SHA "après" est en général déjà connu (celui qu'on vient de déployer,
  ou la branche livrée).
- Le SHA "avant" est la version précédemment en production — dans l'outil de
  déploiement/l'infra du projet (ex. le label de version d'un environnement
  AWS Elastic Beanstalk avant le déploiement). Sinon, demander à
  l'utilisateur.

Lire chaque commit avec `git show <sha> --stat` ou `git log -1 <sha>` quand
le message seul ne suffit pas à comprendre l'impact utilisateur — surtout
pour les fix, où la ligne de commit décrit souvent la cause technique et pas
le symptôme corrigé.

## 2. Classer et filtrer

Chaque commit tombe dans une catégorie. Le préfixe conventionnel
(`feat`/`fix`/`chore`/`docs`/`refactor`) est un point de départ, pas une
vérité absolue — un `fix` peut être un changement purement interne, un
`feat` peut être invisible pour l'utilisateur final. Se fier au contenu du
commit, pas seulement à son préfixe.

- **✨ Feature** — nouvelle capacité ou nouveau comportement visible.
- **🐛 Fix** — corrige quelque chose qui ne marchait pas comme prévu.
- **🧹 Chore / interne** — ne change rien d'observable pour qui que ce soit
  hors des devs (nettoyage de code, doc, migration technique sans effet de
  bord visible, config CI). Regrouper ces commits ensemble plutôt que leur
  donner chacun leur ligne — voir plus bas.

**Ne rien omettre**, sauf instruction explicite contraire de l'utilisateur.
Un commit qui n'a aucun effet visible mérite quand même sa ligne, sous
"Nettoyage interne" ou équivalent — la transparence sur ce qui a été livré
compte plus que la longueur du message. Si plusieurs commits purement
internes n'ont individuellement rien à raconter, les regrouper en une seule
ligne plutôt que de gonfler la liste avec des entrées creuses.

Deux commits qui sont en réalité la même fonctionnalité livrée en plusieurs
étapes (un fix suivi d'un fix du fix, par exemple) peuvent fusionner en une
seule ligne — le lecteur se moque du nombre de tentatives, seul le résultat
final compte.

## 3. Rédiger

Contraintes non négociables, apprises sur le terrain :

- **En français**, toujours, quel que soit le contexte technique.
- **Langage clair, zéro jargon.** Pas de nom de table, de colonne, de
  endpoint, de statut HTTP, de framework. Si une phrase a besoin d'un terme
  technique pour être vraie, chercher la reformulation côté utilisateur — le
  symptôme corrigé, pas le mécanisme du fix.
- **Une ligne par sujet**, avec un titre court en gras suivi d'un tiret et
  d'une explication d'une phrase.
- **Un emoji de catégorie en tête de ligne**, pas de mot ("Fix"/"Feature")
  à côté — l'emoji porte l'information de type à lui seul :
  `🐛` fix, `✨` feature, `🧹` chore/interne. Rester cohérent sur ces trois-là
  sauf si le contenu appelle clairement un autre pictogramme déjà en usage
  dans le canal — regarder les messages précédents du canal pour rester dans
  le même vocabulaire visuel si l'historique est accessible.
- **Titre du message** : une phrase d'intro très courte annonçant qu'une
  nouvelle version vient d'être mise en ligne, avec la date. Exemple :
  `🚀 *On vient de déployer une nouvelle version de la plateforme (22
  septembre)*` — pas de sous-titre générique du type "Nouveautés" qui
  n'ajoute rien à ce que la liste dit déjà.
- **Pas de conclusion, pas de closing.** Le message s'arrête à la dernière
  ligne de la liste. Pas de "N'hésitez pas si questions", pas de résumé
  final — ça n'apporte rien et ça dilue le sujet.

### Gabarit

```
🚀 *On vient de déployer une nouvelle version de la plateforme (<date>)*

Voici ce qui change :

🐛 *<Titre court>* — <une phrase, langage clair>.
✨ *<Titre court>* — <une phrase, langage clair>.
🧹 *<Titre court>* — <une phrase, langage clair>.
```

## 4. Format Slack — le piège du markdown

Un serveur MCP Slack qui poste un message attend en général du **Markdown
standard** en entrée (`**gras**`) et le convertit lui-même en syntaxe Slack
native (`*gras*`). **Ne jamais envoyer directement de la syntaxe Slack**
(`*gras*`, `:emoji:`) en pensant "gagner du temps" — si l'outil fait déjà
cette conversion, le double traitement casse le rendu (astérisques
littéraux ou gras cassé). Vérifier le paramètre de type de contenu de
l'outil utilisé ; par défaut, écrire en Markdown standard et laisser l'outil
convertir.

Utiliser les vrais caractères emoji Unicode (🚀 🐛 ✨ 🧹) dans le texte
envoyé plutôt que les codes type `:rocket:` — les deux fonctionnent
généralement côté Slack, mais l'emoji Unicode direct est plus lisible dans
le brouillon présenté à l'utilisateur.

**Toujours vérifier le rendu après envoi** : relire le message posté
(lecture de l'historique du canal, message le plus récent) pour confirmer
que le gras et les puces sont bien rendus, pas juste "postage réussi" — un
post qui réussit techniquement peut toujours être mal formaté.

## 5. Présenter avant d'envoyer

**Toujours montrer le brouillon à l'utilisateur et obtenir confirmation
avant de poster** — publier sur Slack est une action irréversible et
visible de toute l'entreprise. Ne jamais poster au premier essai sans avoir
montré le texte final.

Toujours confirmer le canal cible avec l'utilisateur avant d'envoyer, ne
jamais supposer silencieusement un canal par défaut.

Si l'utilisateur demande une correction (formatage, ton, contenu manquant),
republier un nouveau message plutôt que d'éditer le précédent, sauf
indication contraire — et si l'utilisateur signale avoir supprimé le premier
message, ne pas chercher à le "réparer", simplement reposter la version
corrigée.
