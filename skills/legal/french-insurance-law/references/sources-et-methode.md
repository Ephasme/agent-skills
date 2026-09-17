# Sources primaires, accès, et table des délais

## Contents

- [1. Hiérarchie des sources en droit des assurances](#1-hiérarchie-des-sources-en-droit-des-assurances)
- [2. Lire Légifrance quand un fetch ordinaire échoue](#2-lire-légifrance-quand-un-fetch-ordinaire-échoue)
- [3. Table des délais](#3-table-des-délais)
- [4. Réflexes de vérification](#4-réflexes-de-vérification)

## 1. Hiérarchie des sources en droit des assurances

| Rang | Source | Où |
|---|---|---|
| 1 | Traités et droit dérivé de l'Union (directives 2009/138/CE Solvabilité II, 2016/97 DDA, 2021/2118 auto ; règlements délégués) | [EUR-Lex](https://eur-lex.europa.eu) |
| 2 | Loi et ordonnances — Code des assurances, Code civil, Code de la mutualité, CSS livre IX, Code de la consommation, lois non codifiées (loi Badinter n° 85-677) | [Légifrance](https://www.legifrance.gouv.fr) |
| 3 | Décrets (articles R.) et arrêtés (articles A., clauses types) | Légifrance, mêmes codes |
| 4 | Jurisprudence — Cour de cassation (2e civ. surtout, 3e civ. en construction, com. en maritime et en distribution bancaire), CJUE, Conseil constitutionnel | [courdecassation.fr](https://www.courdecassation.fr) · [curia.europa.eu](https://curia.europa.eu) |
| 5 | Doctrine administrative — recommandations et positions de l'ACPR, orientations EIOPA. **Non normatives** : opposables à l'organisme contrôlé par la voie du contrôle, pas au juge du contrat | [acpr.banque-france.fr](https://acpr.banque-france.fr) · [eiopa.europa.eu](https://www.eiopa.europa.eu) |
| 6 | Chartes et recommandations professionnelles, avis du médiateur | sites des organismes |

Une position de l'ACPR ne renverse pas un texte, et un avis de médiateur ne fait pas
jurisprudence. Le dire explicitement quand on s'en sert.

## 2. Lire Légifrance quand un fetch ordinaire échoue

Légifrance répond **403** aux récupérateurs ordinaires (protection anti-bot), y compris
via un proxy de lecture. Recette qui fonctionne, testée le 2026-08-13 — actor Apify
`apify/rag-web-browser`, navigateur réel, proxy résidentiel France :

```json
{
  "actor": "apify/rag-web-browser",
  "callOptions": { "memory": 1024 },
  "input": {
    "query": "<URL Légifrance>",
    "maxResults": 1,
    "outputFormats": ["markdown"],
    "scrapingTool": "browser-playwright",
    "proxyConfiguration": {
      "useApifyProxy": true,
      "apifyProxyGroups": ["RESIDENTIAL"],
      "apifyProxyCountry": "FR"
    }
  },
  "waitSecs": 0
}
```

Puis récupérer le résultat par `datasetId`, avec `limit: 1` et **sans champ `fields`** :
la projection par `fields` a renvoyé des objets vides lors des essais, l'item complet
passe. Points appris à l'usage, tous vérifiés le 2026-08-13 :

- `waitSecs: 0` puis relecture du dataset. N'attends pas via l'appel de statut avec
  `waitSecs` : il dépasse le délai de la couche MCP. Boucle plutôt sur la lecture du
  dataset avec une pause de quinze à vingt secondes ; une page se rend en vingt à
  soixante secondes.
- `memory: 1024` suffit ; la valeur par défaut de 8 Go sature le quota du compte dès deux
  exécutions simultanées.
- **Pour lire des articles : viser une page de section**, pas d'article. Une URL
  `codes/section_lc/<LEGITEXT>/<LEGISCTA>/` renvoie le texte intégral de tous les articles
  de la section en une requête, avec pour chacun sa date d'entrée en vigueur, le texte
  modificateur et son identifiant `LEGIARTI`. Meilleur rapport signal/coût, et c'est ainsi
  qu'on récupère un identifiant d'article fiable.
- **Pour trouver un identifiant de section : viser la page du code entier**,
  `codes/texte_lc/<LEGITEXT>/`. Elle rend le sommaire complet avec tous les `LEGISCTA`.
  Une page de **section** ne rend que sa propre branche du sommaire — ne compte pas
  dessus pour naviguer ailleurs dans le code.
- Codes utiles : Code des assurances `LEGITEXT000006073984`, Code civil
  `LEGITEXT000006070721`. Les identifiants de section déjà relevés sont en tête de
  `contrat.md`, `dommages.md`, `personnes.md` et `distribution.md`.
- **Textes non codifiés (fonds LODA)** : `loda/article_lc/<LEGIARTI>` fonctionne, et la
  page rend au passage le sommaire du texte avec les identifiants de ses autres articles.
  En revanche `loda/id/<LEGISCTA>` répond 403 — n'essaie pas de passer par la section.
- La recherche Google de l'actor (`site:legifrance.gouv.fr "Article 2224"`) a renvoyé un
  dataset vide lors des essais : ne compte pas dessus pour résoudre un numéro d'article.
  Si tu n'as aucun identifiant, pars du sommaire du code ; en dernier recours, les
  sommaires officiels de Judilibre citent fréquemment le texte des articles appliqués et
  sont lisibles directement.
- La date affichée « Version en vigueur depuis le … » et la ligne « Modifié par … » sont
  la seule preuve de la version applicable. Relève-les avec la citation.

Autres sources lisibles **directement** avec `read`, sans passer par Apify :
courdecassation.fr, curia.europa.eu, acpr.banque-france.fr, orias.fr. EUR-Lex oppose un
pare-feu applicatif en HTML mais **sert le PDF** : préfère
`legal-content/FR/TXT/PDF/?uri=CELEX:…`.

Pour Judilibre, voir la recette dédiée dans `jurisprudence.md`.

## 3. Table des délais

Chaque ligne renvoie à l'article qui la fonde, tous vérifiés à la source le 2026-08-13
(le détail et les citations sont dans `contrat.md`, `dommages.md`, `personnes.md`).

| Délai | Point de départ | Texte |
|---|---|---|
| **2 ans** — prescription de toutes actions dérivant du contrat | l'événement qui y donne naissance ; reports en cas de réticence, de sinistre ignoré, ou de recours d'un tiers | L. 114-1 |
| **5 ans** — même prescription, sécheresse-réhydratation reconnue CatNat | idem ; ne s'applique pas aux contrats en cours au 30/12/2021 | L. 114-1 |
| **10 ans** — assurance vie, bénéficiaire distinct du souscripteur ; accidents corporels, ayants droit | idem | L. 114-1 |
| **30 ans** — butoir de l'action du bénéficiaire en assurance vie | décès de l'assuré | L. 114-1 |
| **15 jours** — déclaration d'une aggravation du risque | connaissance de la circonstance nouvelle | L. 113-2, 3° |
| **5 jours ouvrés** (minimum contractuel) — déclaration de sinistre | connaissance du sinistre | L. 113-2, 4° |
| **2 jours ouvrés** — déclaration de vol | idem | L. 113-2, 4° |
| **10 / 30 / 10 jours** — impayé de prime : exigibilité, puis suspension 30 jours après mise en demeure, puis résiliation 10 jours plus tard | échéance de la prime | L. 113-3 |
| **2 mois** — préavis de résiliation annuelle | échéance du contrat | L. 113-12 |
| **6 mois** — préavis de l'assureur envers une collectivité territoriale | échéance | L. 113-12 |
| **1 mois** — effet de la résiliation infra-annuelle (particuliers, et PME depuis 2026) | notification | L. 113-15-2 ; L. 113-15-2-1 |
| **20 jours** — dénonciation lorsque l'avis d'échéance est tardif (loi Chatel) | envoi de l'avis | L. 113-15-1 |
| **30 jours** — restitution du trop-perçu de prime après résiliation | date d'effet de la résiliation | L. 113-15-1 ; L. 113-15-2 |
| **30 jours calendaires**, dans la limite de **8 ans** — prorogation de la renonciation en assurance vie, souscripteur de bonne foi | remise effective des documents manquants | L. 132-5-2 |
| **2 mois** — versement de la valeur de rachat | demande de rachat | L. 132-21 |
| **3 mois** — information préalable des adhérents d'un contrat de groupe sur une modification | entrée en vigueur de la modification | L. 141-4 |
| **3 mois** — offre motivée en automobile, responsabilité non contestée et dommage quantifié | demande d'indemnisation | L. 211-9 |
| **8 mois** — offre en cas d'atteinte à la personne | accident | L. 211-9 |
| **5 mois** — offre définitive après consolidation | information de l'assureur sur la consolidation | L. 211-9 |
| **double du taux légal** — sanction du dépassement | expiration du délai jusqu'à l'offre ou au jugement définitif | L. 211-13 |
| **60 jours** — position de l'assureur DO sur le principe de la garantie | réception de la déclaration de sinistre | L. 242-1 |
| **90 jours** — offre d'indemnité DO | réception de la déclaration de sinistre | L. 242-1 |
| **15 jours** — règlement après acceptation de l'offre DO | acceptation | L. 242-1 |
| **135 jours** — plafond du délai supplémentaire DO, sur acceptation expresse | — | L. 242-1 |
| **10 ans** — décharge de la responsabilité décennale | réception des travaux | C. civ. art. 1792-4-1 |
| **1 mois** puis **1 mois** — information puis proposition d'indemnisation en CatNat ; **2 mois** pour la provision | déclaration ou publication de l'arrêté | L. 125-2 |
| **24 mois** — forclusion de la demande communale de reconnaissance CatNat | début de l'événement naturel | L. 125-1 |
| **5 ans** — prescription de droit commun (à retenir quand le délai biennal est inopposable) | jour où le titulaire a connu ou aurait dû connaître les faits | C. civ. art. 2224 |
| **10 ans** — action en responsabilité pour **dommage corporel** | consolidation du dommage initial ou aggravé | C. civ. art. 2226 |

**Non vérifiés dans cette compilation**, à ouvrir avant usage : délai butoir (C. civ.
art. 2232), délais de procédure civile (art. 145, 750-1 et 761 CPC), délai de
rétractation en démarchage, et l'effet de la médiation sur le cours de la prescription
(suspension de l'art. 2238 C. civ. — texte non relevé ici).

## 4. Réflexes de vérification

1. Relever la **date du contrat** et la **date du sinistre** avant de citer un texte : ce
   sont elles qui désignent la version applicable.
2. Demander systématiquement quatre pièces : conditions générales **et** particulières,
   questionnaire de souscription, courrier de refus, déclaration de sinistre datée.
3. Face à une prescription opposée : lire la police, chercher le rappel de L. 114-1
   **et** des causes d'interruption de L. 114-2 (R. 112-1).
4. Face à une exclusion : vérifier les caractères très apparents (L. 112-4), le caractère
   formel et limité (L. 113-1), et si la clause ne vide pas la garantie.
5. Face à une nullité : exiger la preuve de l'intention (L. 113-8) et vérifier que la
   question était réellement posée (L. 113-2, 2° et L. 112-3 al. 4).
6. Face à un contrat de groupe : demander la preuve de la remise de la notice (L. 141-4).
