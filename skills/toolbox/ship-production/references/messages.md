# Canaux et règles de forme

Où chaque message va, et comment on l'écrit. Les messages eux-mêmes sont des modèles à
recopier, un fichier par message, dans `references/templates/` :

| Message | Fichier |
| --- | --- |
| Début de release | `references/templates/release-start.md` |
| Fin de release | `references/templates/release-end.md` |
| Changelog | `references/templates/changelog.md` |

## Contents

- [Canaux](#canaux)
- [Règles de forme](#règles-de-forme)

## Canaux

| Canal | Identifiant | Public | Ce qui y va |
| --- | --- | --- | --- |
| #builders | `C0BKNE2J4UU` | privé | le début et la fin de chaque release |
| #general | `C15GTGEBA` | toute l'entreprise | le changelog d'une version livrée |

`#builders` est un canal interne : ce qui y est posté s'adresse à l'équipe, pas aux clients.
En cas de doute sur le canal visé, le faire confirmer avant d'envoyer.

## Règles de forme

- **Un modèle se remplit, il ne se recompose pas** : les `{{…}}` portent ce qui change d'une
  release à l'autre, le reste est ce sur quoi les relecteurs comptent.
- **Markdown standard en entrée** (`**gras**`, listes) : l'outil de messagerie convertit
  lui-même vers la syntaxe maison. Ne jamais écrire la syntaxe Slack en croyant gagner du
  temps — la conversion se ferait deux fois et casserait le rendu.
- **Emoji Unicode en clair** (🚀 🐛 ✨ 🧹 ✅), jamais de code `:rocket:`.
- **Relire le message après envoi**, dans le canal : un envoi qui réussit peut être mal
  formaté, et c'est le rendu qui compte, pas le code retour.
- **Un message envoyé ne s'édite pas pour être corrigé** : on republie une version corrigée.
  Si l'utilisateur a supprimé le message fautif, on republie également — on ne cherche pas
  à « réparer ».
- **Un texte fourni par l'utilisateur ne se réécrit pas** ; une faute ne se corrige que s'il
  le demande.
