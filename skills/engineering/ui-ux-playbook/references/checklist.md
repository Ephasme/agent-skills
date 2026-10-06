# Checklist UI/UX Playbook

Une entrée par technique, astuce ou règle du livre, dans l'ordre du livre. Les numéros de page sont
ceux imprimés dans le livre (page PDF = page imprimée + 1). Chaque entrée : identifiant stable,
gravité par défaut, **Critère** vérifiable, **Vérifier** (où regarder dans le code, le CSS, la page
ou la maquette), **Correctif** type. Les exemples avant/après traduits en code sont dans
`examples.md` (renvoi « ex. »).

Sections : INTRO · HIER · PROX · CLAR · ALIGN · CONT · SIMP · SPACE · LAYOUT · BAL · CONS · CUE ·
DEPTH · COLOR · TYPO · COST · BONUS · LVL (145 items).

---

## Contents

1. [INTRO - UI et UX ensemble (p. 2-5)](#intro---ui-et-ux-ensemble-p-2-5)
2. [HIER - Hiérarchie visuelle (p. 6-11)](#hier---hiérarchie-visuelle-p-6-11)
3. [PROX - Proximité (p. 12)](#prox---proximité-p-12)
4. [CLAR - Clarté (p. 13-15)](#clar---clarté-p-13-15)
5. [ALIGN - Alignement (p. 16-19)](#align---alignement-p-16-19)
6. [CONT - Contraste (p. 20-21)](#cont---contraste-p-20-21)
7. [SIMP - Simplicité (p. 22-23)](#simp---simplicité-p-22-23)
8. [SPACE - Espace blanc (p. 24-28)](#space---espace-blanc-p-24-28)
9. [LAYOUT - Mise en page (p. 29-34)](#layout---mise-en-page-p-29-34)
10. [BAL - Équilibre et harmonie (p. 35-36)](#bal---équilibre-et-harmonie-p-35-36)
11. [CONS - Cohérence (p. 37-45)](#cons---cohérence-p-37-45)
12. [CUE - Repères visuels (p. 46-48)](#cue---repères-visuels-p-46-48)
13. [DEPTH - Profondeur et texture (p. 49-64)](#depth---profondeur-et-texture-p-49-64)
14. [COLOR - Couleur (p. 65-70)](#color---couleur-p-65-70)
15. [TYPO - Typographie (p. 71-96)](#typo---typographie-p-71-96)
16. [COST - Coût d'interaction (p. 97-108)](#cost---coût-dinteraction-p-97-108)
17. [BONUS - Astuces bonus (p. 109-141)](#bonus---astuces-bonus-p-109-141)
18. [LVL - Aller plus loin (p. 142)](#lvl---aller-plus-loin-p-142)

## INTRO - UI et UX ensemble (p. 2-5)

### INTRO-01 · L'écran est à la fois utile et soigné · p. 2-4 · majeur
- **Critère** : la tâche principale de l'écran est accessible dès la première vue (pas seulement un
  visuel accrocheur), et sa présentation est soignée (pas un formulaire brut sans hiérarchie).
- **Vérifier** : à 1440 et 375 px, ce que voit l'utilisateur sans défiler ; présence de l'entrée de
  la tâche (recherche, formulaire, CTA) ; styles par défaut du navigateur restés en place.
- **Correctif** : remonter le point d'entrée de la tâche dans la zone visible et lui appliquer la
  hiérarchie, l'espacement et les composants du design system.

---

## HIER - Hiérarchie visuelle (p. 6-11)

### HIER-01 · Les éléments n'ont pas tous le même poids · p. 6 · majeur
- **Critère** : l'importance relative se lit par la taille, la couleur, la graisse et la position ;
  aucun groupe où tout a même taille et même couleur.
- **Vérifier** : boutons d'un même écran (variant, color, size), titres et textes d'une même carte.
- **Correctif** : attribuer un niveau (primaire, secondaire, tertiaire) à chaque élément et le
  traduire en styles distincts.

### HIER-02 · Un seul bouton primaire par zone de décision · p. 6-7 · majeur
- **Critère** : une seule action primaire (pleine, couleur vive) par écran ou groupe ; l'action
  secondaire est neutre (gris, contour) même à taille égale ; les actions tertiaires ou de retrait
  dans une liste sont des liens texte (ex. « Retirer » rouge souligné). Des couleurs différentes à
  taille et style identiques ne suffisent pas.
- **Vérifier** : nombre de `variant="contained"` / boutons pleins visibles ensemble ; boutons
  « Supprimer » répétés en plein dans des listes.
- **Correctif** : primaire = `contained` couleur principale ; secondaire = `outlined`/gris ;
  tertiaire = `text`/lien. Ex. `examples.md#hierarchie-des-boutons`.

### HIER-03 · Les visuels ne volent pas la vedette aux infos clés · p. 8 · majeur
- **Critère** : vignettes et images restent proportionnées aux informations utiles (nom, prix,
  quantité) et ne dominent pas la ligne ou la carte.
- **Vérifier** : largeur/hauteur des images dans les listes et cartes par rapport au bloc texte.
- **Correctif** : réduire la vignette (ex. 40-64 px en liste) et laisser le texte porter l'information.

### HIER-04 · L'information secondaire reste secondaire · p. 8 · majeur
- **Critère** : une donnée annexe (quantité, métadonnée, date) n'est ni plus grande ni plus
  contrastée que l'information principale (nom, prix).
- **Vérifier** : `font-size`, `font-weight`, `color` des lignes d'une même carte/ligne de liste.
- **Correctif** : passer la donnée annexe en petit corps et couleur secondaire ; nom et prix en
  couleur principale.

### HIER-05 · Les éléments sont classés par importance pour l'utilisateur · p. 9 · majeur
- **Critère** : on peut énoncer l'ordre d'importance des éléments de l'écran pour l'utilisateur, et
  l'emphase visuelle (couleur, taille, position, contraste) suit cet ordre.
- **Vérifier** : écrire le classement (3-5 éléments) puis comparer avec ce qui ressort à l'écran.
- **Correctif** : réattribuer taille, position et contraste selon le classement.

### HIER-06 · Dans un indicateur, la valeur prime sur le libellé · p. 9 · majeur
- **Critère** : sur une carte de métrique, la valeur (« 591 », « 4 981 € ») est nettement plus grande
  et plus grasse que son libellé (« Ventes »).
- **Vérifier** : tailles du libellé et de la valeur dans les cartes KPI, statistiques, compteurs.
- **Correctif** : libellé petit et secondaire au-dessus, valeur grande et grasse dessous.

### HIER-07 · Titre plus foncé que le texte · p. 10 · majeur
- **Critère** : les titres sont dans la couleur de texte la plus foncée ; le corps est en gris plus
  clair ; jamais un titre gris au-dessus d'un paragraphe noir.
- **Vérifier** : `color` du titre et du paragraphe d'une même carte/section.
- **Correctif** : titre = `text.primary`, corps = `text.secondary` (toujours au-dessus de 4.5:1).

### HIER-08 · L'action à remarquer porte une couleur vive · p. 10 · mineur
- **Critère** : le bouton ou lien que l'on veut faire cliquer utilise la couleur d'accent, qui
  contraste avec le texte autour.
- **Vérifier** : couleur du CTA principal par rapport au reste du bloc.
- **Correctif** : appliquer la couleur primaire du thème au CTA, et seulement à lui (voir COLOR-01).

### HIER-09 · Pas de liste uniforme « libellé : valeur » pour des infos hétérogènes · p. 11 · majeur
- **Critère** : quand une fiche mélange infos de natures différentes (prix, statut, adresse,
  caractéristiques, contact), elles sont différenciées par taille, graisse, couleur, badges et
  icônes, pas alignées en lignes `Libellé : valeur` identiques.
- **Vérifier** : fiches, cartes de détail, récapitulatifs construits en paires label/valeur.
- **Correctif** : prix en grand, statut en badge, adresse avec icône de lieu, caractéristiques en
  ligne d'icônes + chiffres en gras, contact avec avatar. Ex. `examples.md#fiche-hierarchisee`.

---

## PROX - Proximité (p. 12)

### PROX-01 · Un libellé est plus près de son champ que du champ précédent · p. 12 · majeur
- **Critère** : l'écart libellé-champ est nettement plus petit que l'écart entre deux champs
  (ordre de grandeur 8-12 px contre 24-32 px), jamais égal.
- **Vérifier** : `margin`/`gap` entre `label` et `input`, et entre deux groupes de champ.
- **Correctif** : espacement interne petit (`theme.spacing(1)`), externe grand (`theme.spacing(3-4)`).

### PROX-02 · Ce qui va ensemble est groupé, le reste est séparé · p. 12 · majeur
- **Critère** : dans tout composant, l'espace à l'intérieur d'un groupe est inférieur à l'espace
  entre groupes, de sorte que les relations se lisent sans bordure.
- **Vérifier** : listes, cartes, barres d'actions : boutons d'actions sans lien collés ensemble,
  éléments liés éloignés.
- **Correctif** : rapprocher les éléments liés, éloigner les groupes distincts.

---

## CLAR - Clarté (p. 13-15)

### CLAR-01 · Pas de sur-simplification : les commandes ont un libellé · p. 13 · bloquant
- **Critère** : interrupteurs, boutons et tuiles ne reposent pas sur une icône seule dont le sens
  n'est pas universel ; chacun a un libellé visible.
- **Vérifier** : `IconButton`, `Switch`, tuiles sans texte ; `aria-label` présent mais rien de visible.
- **Correctif** : ajouter un libellé texte visible sous ou à côté de l'icône.

### CLAR-02 · Pas de complexité écrasante · p. 14 · majeur
- **Critère** : l'écran ne cumule pas options, boutons et données concurrents ; un point focal
  clair, le reste regroupé ou déplacé.
- **Vérifier** : nombre de boutons, de blocs et de couleurs vives visibles en même temps.
- **Correctif** : retirer, regrouper ou déplacer vers un écran secondaire ce qui ne sert pas la tâche.

### CLAR-03 · Consigne et logique dans le bon sens · p. 15 · bloquant
- **Critère** : la consigne décrit l'action réelle et l'état coché correspond à ce qu'elle annonce
  (« Sélectionnez ce que vous voulez retirer », pas « Désélectionnez ce que vous voulez retirer ») ;
  pas de double négation.
- **Vérifier** : textes de cases à cocher, interrupteurs (« Ne pas… »), consignes de sélection.
- **Correctif** : reformuler en positif et aligner l'état coché sur l'action.

---

## ALIGN - Alignement (p. 16-19)

### ALIGN-01 · Pas de décalage créé par une icône · p. 16 · mineur
- **Critère** : une icône placée devant un paragraphe ne décale pas le texte et le bouton par
  rapport au titre ; titre, texte et CTA partagent le même bord gauche.
- **Vérifier** : cartes avec icône en colonne gauche et contenu indenté.
- **Correctif** : mettre l'icône sur la ligne du titre (flex row, `align-items: center`), le texte
  et le CTA en pleine largeur dessous.

### ALIGN-02 · Les éléments d'une liste partagent les mêmes bords · p. 17 · mineur
- **Critère** : items de menu, lignes de liste, pastilles empilées alignés à gauche et à droite.
- **Vérifier** : `margin-left`, `padding` ou largeurs différentes d'un item à l'autre ; décalages
  au pixel dans la capture.
- **Correctif** : même conteneur, même largeur, même padding pour tous les items.

### ALIGN-03 · Texte courant aligné à gauche · p. 17, 93 · majeur
- **Critère** : paragraphes, listes et textes longs sont alignés à gauche.
- **Vérifier** : `text-align: center|justify` sur des blocs de plus de deux lignes.
- **Correctif** : `text-align: left` (ou `start`).

### ALIGN-04 · Nombres alignés à droite dans les tableaux · p. 17 · mineur
- **Critère** : prix, montants et données chiffrées en colonne sont alignés à droite pour se comparer.
- **Vérifier** : colonnes numériques de tableaux et récapitulatifs.
- **Correctif** : `text-align: right` (+ `font-variant-numeric: tabular-nums` pour des chiffres
  de même chasse) sur cellules et en-têtes de ces colonnes.

### ALIGN-05 · Langues RTL alignées à droite · p. 17 · mineur
- **Critère** : en arabe ou hébreu, texte et mise en page sont alignés à droite.
- **Vérifier** : `dir="rtl"`, propriétés logiques (`margin-inline-start`) plutôt que left/right.
- **Correctif** : propriétés logiques CSS et `dir` sur le document. Souvent `n/a` (produit mono-langue LTR).

### ALIGN-06 · Centrage réservé aux titres, textes courts et CTA · p. 17 · mineur
- **Critère** : le centrage n'est utilisé que pour des titres, accroches courtes ou boutons, jamais
  pour un bloc de plusieurs lignes.
- **Vérifier** : `text-align: center` sur des paragraphes de plus de 2-3 lignes.
- **Correctif** : aligner à gauche le texte long ; garder le centrage pour le titre seul.

### ALIGN-07 · Une grille structure la page · p. 18 · mineur
- **Critère** : la page s'appuie sur une grille (colonnes, gouttières, marges) commune aux sections.
- **Vérifier** : largeurs max de conteneur, gouttières identiques entre sections ; usage de
  `Grid`/`Container`/CSS grid plutôt que des largeurs ad hoc.
- **Correctif** : utiliser le conteneur et la grille du design system.

### ALIGN-08 · Mise en page automatique, pas de positionnement manuel · p. 18-19 · mineur
- **Critère** : les empilements utilisent flex/grid avec `gap` ; pas de marges négatives, de
  `position: absolute` ou de décalages au pixel pour « recaler » un élément.
- **Vérifier** : `top/left` en px, marges négatives, `transform: translate` d'ajustement.
- **Correctif** : `display: flex; flex-direction: column; gap: …` ou `Stack spacing`.

### ALIGN-09 · Une seule stratégie d'alignement par composant · p. 19 · mineur
- **Critère** : dans une carte ou un bloc, tous les éléments suivent le même alignement (tout à
  gauche, ou tout centré), pas un mélange.
- **Vérifier** : un auteur centré au milieu d'une carte alignée à gauche, etc.
- **Correctif** : unifier l'alignement du composant.

---

## CONT - Contraste (p. 20-21)

### CONT-01 · Badges et pastilles lisibles · p. 20 · bloquant
- **Critère** : le texte d'un badge de statut atteint 4.5:1 ; on préfère un fond teinté clair avec
  un texte foncé de la même teinte au texte blanc sur couleur moyenne.
- **Vérifier** : `Chip`, badges de statut ; mesurer le contraste (script, outil).
- **Correctif** : fond = teinte claire (50/100), texte = teinte foncée (700/800). Ex.
  `examples.md#badges-de-statut`.

### CONT-02 · Différencier par la couleur, sans sacrifier l'accessibilité · p. 21 · mineur
- **Critère** : les éléments à distinguer le sont par des couleurs complémentaires ou analogues
  qui restent conformes aux contrastes.
- **Vérifier** : éléments voisins indistincts car de couleurs trop proches.
- **Correctif** : choisir des couleurs de la palette du thème suffisamment écartées.

### CONT-03 · Contraste par la graisse et le style · p. 21 · mineur
- **Critère** : les niveaux de texte se distinguent aussi par la graisse (et le style) ; pas tout
  en regular.
- **Vérifier** : `font-weight` des différents niveaux.
- **Correctif** : 600-700 pour titres et valeurs, 400 pour le corps.

### CONT-04 · Contraste par la taille · p. 21 · mineur
- **Critère** : les écarts de taille entre niveaux sont francs (pas 15 contre 16 px).
- **Vérifier** : échelle de tailles réellement utilisée sur l'écran (script).
- **Correctif** : utiliser des niveaux de l'échelle typographique nettement espacés.

### CONT-05 · Bordure quand fond et élément se confondent · p. 21 · mineur
- **Critère** : un élément de même couleur que son fond (carte blanche sur blanc, champ blanc sur
  blanc) a une bordure fine ou un fond différencié.
- **Vérifier** : surfaces sans limite visible dans la capture.
- **Correctif** : bordure 1 px gris clair (`divider`) ou fond de page gris clair (DEPTH-07).

### CONT-06 · Ombre pour détacher un élément · p. 21 · mineur
- **Critère** : un élément qui doit ressortir de son fond (carte, élément flottant) est détaché par
  une ombre douce du système.
- **Vérifier** : surfaces surélevées sans ombre ni bordure.
- **Correctif** : token d'ombre du système (voir DEPTH-05).

### CONT-07 · Texte sur image lisible quelle que soit l'image · p. 21 · bloquant
- **Critère** : un texte posé sur une image reste lisible avec une image claire comme sombre
  (composant réutilisé avec des contenus variés).
- **Vérifier** : tester le composant avec une image claire ; repérer du texte blanc posé
  directement sur `background-image` ou `<img>`.
- **Correctif** : dégradé sombre sous le texte, bandeau flouté (`backdrop-filter: blur`) ou voile
  semi-opaque. Ex. `examples.md#texte-sur-image`.

---

## SIMP - Simplicité (p. 22-23)

### SIMP-01 · Seulement ce qui sert la tâche en cours · p. 22-23 · majeur
- **Critère** : l'écran n'affiche que les informations utiles à la tâche (au panier : produit,
  options choisies, prix, quantité ; pas les vues, ventes, matière, politique de retour).
- **Vérifier** : chaque bloc et ligne de texte : à quoi sert-il pour finir la tâche ?
- **Correctif** : retirer ou déplacer vers l'écran de détail ce qui n'aide pas la tâche.

### SIMP-02 · Clarté par l'espace, la graisse et la couleur, pas par l'ajout · p. 23 · mineur
- **Critère** : l'image est dimensionnée à sa juste place ; la lisibilité vient de l'espace blanc,
  des graisses et des couleurs de texte, pas de cadres, séparateurs ou éléments ajoutés.
- **Vérifier** : vignettes surdimensionnées, séparateurs et encadrés multiples.
- **Correctif** : réduire, espacer, hiérarchiser par la typographie.

### SIMP-03 · Chaque élément supplémentaire est justifié · p. 23 · majeur
- **Critère** : tout bouton, image ou ligne ajouté répond à un besoin de l'utilisateur pour cette
  tâche ; sinon il encombre.
- **Vérifier** : éléments ajoutés par le diff : que se passe-t-il si on les retire ?
- **Correctif** : supprimer l'élément ou le rendre accessible à la demande (lien « Détails »).

---

## SPACE - Espace blanc (p. 24-28)

### SPACE-01 · Assez d'espace pour respirer · p. 24-25 · majeur
- **Critère** : paddings internes et écarts entre groupes suffisants ; l'interface ne paraît pas
  tassée (ex. barre latérale : sections nettement espacées, items aérés).
- **Vérifier** : paddings < 8 px dans des conteneurs, groupes collés, lignes de liste serrées.
- **Correctif** : augmenter padding et `gap` avec l'échelle d'espacement.

### SPACE-02 · Partir de trop d'espace puis resserrer · p. 25-26 · mineur
- **Critère** : l'équilibre final n'est ni tassé ni démesurément vide (pas de grands trous non
  intentionnels entre un graphique et sa liste, par exemple).
- **Vérifier** : comparer visuellement les écarts verticaux d'un même composant.
- **Correctif** : réduire les écarts excessifs et augmenter les écarts trop serrés jusqu'à
  équilibre, sur l'échelle.

### SPACE-03 · Échelle d'espacement sur une unité de base · p. 27-28 · mineur
- **Critère** : marges, paddings et `gap` sont des multiples d'une unité de base (4 ou 8 px :
  4, 8, 16, 24, 32, 40…), via les tokens du thème.
- **Vérifier** : valeurs en px codées en dur dans `styles.ts`/CSS ; `theme.spacing(n)` utilisé ?
- **Correctif** : remplacer par `theme.spacing(n)` ou les tokens d'espacement.

### SPACE-04 · Échelle de tailles pour les composants · p. 27 · mineur
- **Critère** : hauteurs de boutons et champs, tailles d'icônes et d'avatars suivent la même
  logique de multiples (ex. 32/40/48 px).
- **Vérifier** : `height`, `width`, `size` codés en dur et hors échelle.
- **Correctif** : utiliser les tailles prévues du design system.

### SPACE-05 · Même relation, même espacement partout · p. 28 · mineur
- **Critère** : une relation donnée (libellé-champ, titre-texte, carte-carte) a la même valeur
  dans toute l'interface.
- **Vérifier** : comparer ces écarts entre écrans/composants voisins.
- **Correctif** : fixer la valeur par relation et l'appliquer partout.

### SPACE-06 · Pas de valeurs au hasard · p. 28 · mineur
- **Critère** : aucune valeur d'espacement isolée hors échelle (7, 19, 21, 31 px…).
- **Vérifier** : `grep -nE '[^0-9](7|9|11|13|15|17|19|21|23|25|27|29|31|33|35)px'` dans le diff,
  puis vérifier au cas par cas.
- **Correctif** : arrondir à la valeur de l'échelle la plus proche.

---

## LAYOUT - Mise en page (p. 29-34)

### LAYOUT-01 · La mise en page sert ce qui compte pour l'utilisateur · p. 29-30 · majeur
- **Critère** : la disposition met en avant ce qui déclenche la décision dans ce domaine (en
  restauration le visuel, en finance le chiffre…) avec une structure simple (souvent une colonne)
  et de l'espace, plutôt que tout aligner sur une ligne découpée de séparateurs.
- **Vérifier** : quelle information domine la carte, et est-ce le bon critère de choix ?
- **Correctif** : réorganiser la carte autour de l'élément décisif ; simplifier en colonne.

### LAYOUT-02 · Des options répétées faciles à balayer · p. 30 · mineur
- **Critère** : dans une liste de cartes comparables, la structure identique et épurée permet de
  balayer plusieurs options sans s'arrêter sur les détails.
- **Vérifier** : cartes surchargées ou de structures différentes dans une même liste.
- **Correctif** : même gabarit pour toutes les cartes, détails déplacés vers la fiche.

### LAYOUT-03 · Ordre logique des éléments · p. 31 · majeur
- **Critère** : l'ordre suit la lecture et la décision : visuel, nom, description, prix, puis CTA
  en dernier (le CTA vient après les informations nécessaires pour décider).
- **Vérifier** : ordre DOM et visuel des cartes produit/offre ; CTA avant la description ou prix
  isolé en haut.
- **Correctif** : réordonner (et garder l'ordre DOM égal à l'ordre visuel pour le clavier).

### LAYOUT-04 · Cartes sélectionnables plutôt qu'une liste de boutons radio · p. 32 · suggestion
- **Critère** : pour quelques options riches (offres, forfaits), des cartes sélectionnables avec
  libellé, couleur, icône et état sélectionné net sont préférées à une liste radio textuelle.
- **Vérifier** : `RadioGroup` de 2 à 4 options riches.
- **Correctif** : cartes cliquables (`role="radio"`, `aria-checked`, focus visible) avec bordure et
  pastille d'état sélectionné. Ex. `examples.md#cartes-selectionnables`.

### LAYOUT-05 · Formulaire calqué sur le rendu final · p. 33-34 · suggestion
- **Critère** : quand un formulaire crée un objet affiché ensuite (annonce, profil, carte), sa
  disposition reprend celle du rendu final (zone image en haut, titre et prix côte à côte…).
- **Vérifier** : formulaires de création linéaires sans lien visuel avec le résultat.
- **Correctif** : disposer les champs comme dans l'affichage final, avec placeholders explicites.

---

## BAL - Équilibre et harmonie (p. 35-36)

### BAL-01 · Proportion et échelle · p. 35-36 · majeur
- **Critère** : aucun élément (image, CTA, titre) n'écrase les autres ; chacun a sa place sans
  devenir une distraction.
- **Vérifier** : bouton pleine largeur très haut dans une petite carte, image démesurée.
- **Correctif** : réduire l'élément dominant à une taille en rapport avec le reste.

### BAL-02 · Harmonie des couleurs · p. 35-36 · majeur
- **Critère** : une même couleur n'est pas appliquée partout (fond d'image, CTA, décor, icônes) ;
  la palette varie avec des couleurs complémentaires ou analogues.
- **Vérifier** : nombre d'éléments portant la couleur principale sur l'écran.
- **Correctif** : réserver la couleur forte au CTA, utiliser des teintes douces pour le décor.

### BAL-03 · Relations cohérentes entre éléments · p. 35 · mineur
- **Critère** : espacements, typographie et tailles d'éléments sont cohérents entre les
  composants d'un même écran.
- **Vérifier** : cartes voisines aux paddings, tailles de titre ou de bouton différents.
- **Correctif** : aligner sur les mêmes tokens.

---

## CONS - Cohérence (p. 37-45)

### CONS-01 · Composants essentiels identiques partout · p. 37 · majeur
- **Critère** : titres, boutons et champs ont le même aspect et le même comportement d'un écran à
  l'autre (les visuels de contenu peuvent varier).
- **Vérifier** : boutons ou champs stylés à la main au lieu du composant partagé ; variantes
  locales d'un composant existant.
- **Correctif** : utiliser le composant du design system ; supprimer la variante locale.

### CONS-02 · Formes et rayons d'angle cohérents · p. 38-39 · mineur
- **Critère** : images, boutons et cartes partagent une échelle de rayons ; pas de bouton carré
  parmi des boutons arrondis, ni d'image carrée parmi des images rondes.
- **Vérifier** : `border-radius` codés en dur et différents dans le diff.
- **Correctif** : `theme.shape.borderRadius` ou tokens de rayon.

### CONS-03 · Couleurs de boutons fixes par rôle · p. 39-40 · majeur
- **Critère** : primaire, secondaire et tertiaire ont chacun une seule couleur dans toute l'appli ;
  pas de couleur de bouton assortie à l'image de chaque carte.
- **Vérifier** : `color`/`bgcolor` de boutons calculés à partir du contenu ou variables par carte.
- **Correctif** : variantes de bouton du thème uniquement.

### CONS-04 · Images de formes variées dans un contenant uniforme · p. 40-42 · mineur
- **Critère** : des visuels de formes et tailles hétérogènes sont placés dans un même contenant
  (cercle ou carré de fond), de même taille et même position.
- **Vérifier** : grilles d'illustrations ou de logos aux silhouettes disparates.
- **Correctif** : conteneur fixe (`width/height`, `border-radius`, fond teinté) et
  `object-fit: contain`. Ex. `examples.md#images-heterogenes`.

### CONS-05 · Cartes d'une même rangée à la même hauteur · p. 42 · mineur
- **Critère** : dans une rangée de 3 cartes ou plus, toutes ont la même hauteur.
- **Vérifier** : grille de cartes à `height: auto` sans étirement.
- **Correctif** : `align-items: stretch` sur la grille et `height: 100%` sur les cartes.

### CONS-06 · Textes de cartes de longueur comparable · p. 42-43 · mineur
- **Critère** : quand on maîtrise les textes, titres et descriptions ont un nombre de lignes
  identique d'une carte à l'autre.
- **Vérifier** : contenus statiques (messages i18n) de longueurs très différentes.
- **Correctif** : réécrire les textes à longueur égale, ou limiter (`-webkit-line-clamp`).

### CONS-07 · CTA calé en bas quand le contenu varie · p. 43 · mineur
- **Critère** : avec des contenus de longueur imprévisible, les cartes ont la même hauteur et les
  CTA sont alignés en bas, l'espace en trop restant au milieu.
- **Vérifier** : boutons de cartes voisines à des hauteurs différentes.
- **Correctif** : carte en `flex-direction: column`, CTA en `margin-top: auto`. Ex.
  `examples.md#cartes-de-meme-hauteur`.

### CONS-08 · Icônes d'un même style et d'une même taille · p. 44 · mineur
- **Critère** : sur un écran, les icônes sont toutes en contour ou toutes pleines, de même taille,
  même épaisseur de trait et même niveau de détail.
- **Vérifier** : mélange d'icônes `Outlined` et pleines, tailles différentes dans une liste.
- **Correctif** : une seule variante et une seule taille d'icône.

### CONS-09 · Changement de style d'icône réservé aux états · p. 44-45 · mineur
- **Critère** : le mélange plein/contour n'est admis que pour signaler un état (onglet actif plein,
  autres en contour).
- **Vérifier** : icônes pleines sans signification d'état.
- **Correctif** : contour par défaut, plein uniquement pour l'élément actif/sélectionné.

### CONS-10 · Une seule bibliothèque d'icônes, accordée à la marque · p. 45 · mineur
- **Critère** : pas de mélange de deux jeux d'icônes aux propriétés différentes ; le jeu choisi
  correspond à l'identité visuelle.
- **Vérifier** : imports d'icônes de plusieurs bibliothèques dans le diff.
- **Correctif** : remplacer par l'équivalent du jeu officiel du projet.

---

## CUE - Repères visuels (p. 46-48)

### CUE-01 · Des visuels pour faire comprendre plus vite · p. 46 · suggestion
- **Critère** : les contenus explicatifs (étapes, fonctionnalités) s'appuient sur des
  illustrations, icônes ou indicateurs (barre de progression d'étape) plutôt que sur le texte seul.
- **Vérifier** : blocs « Étape 1/2/3 » ou explications en texte nu.
- **Correctif** : ajouter illustration ou icône cohérente et un indicateur de progression.

### CUE-02 · Chaque personne ou entité a un repère visuel · p. 47 · mineur
- **Critère** : expéditeurs, profils et organisations dans une liste ont un avatar (à défaut,
  initiale sur pastille de couleur).
- **Vérifier** : listes de conversations, d'utilisateurs, de contacts sans avatar.
- **Correctif** : composant avatar avec repli sur l'initiale colorée.

### CUE-03 · Photos et logos réels de préférence · p. 48 · suggestion
- **Critère** : quand une photo ou un logo existe, il est affiché ; l'initiale n'est qu'un repli.
- **Vérifier** : avatar à initiale alors que l'URL de photo est disponible.
- **Correctif** : afficher l'image, initiale en `fallback`.

---

## DEPTH - Profondeur et texture (p. 49-64)

### DEPTH-01 · Surfaces flottantes avec ombre · p. 49-50 · majeur
- **Critère** : menus déroulants, popovers et menus de navigation se détachent de la page par une
  ombre (pas posés à plat sans séparation).
- **Vérifier** : `Menu`, `Popover`, dropdowns custom avec `box-shadow: none` ou `elevation={0}`.
- **Correctif** : niveau d'ombre « fort » du système (DEPTH-05).

### DEPTH-02 · Ombre sur les éléments posés sur un fond dynamique · p. 50 · majeur
- **Critère** : étiquettes, boutons et contrôles posés sur une carte, une image ou une vidéo ont une
  ombre ou un fond qui les sépare du fond variable.
- **Vérifier** : boutons de zoom, étiquettes de carte, contrôles de lecteur.
- **Correctif** : fond plein + ombre douce.

### DEPTH-03 · Ombres douces · p. 51 · mineur
- **Critère** : les ombres sont légères, décalées vers le bas, à grand flou et faible opacité ; pas
  d'ombre sombre centrée et dure.
- **Vérifier** : `box-shadow` avec couleur foncée opaque (`#9F9F9F`, `rgba(0,0,0,.3+)`) et
  décalage nul.
- **Correctif** : ex. `0 12px 48px rgba(…, 0.08-0.12)`. Ex. `examples.md#ombres`.

### DEPTH-04 · Ombre teintée comme le fond · p. 52-53 · mineur
- **Critère** : sur un fond coloré, l'ombre reprend la teinte du fond (violet sur violet clair,
  beige sur beige) ; jamais gris ou noir pur sur fond coloré.
- **Vérifier** : ombres grises sur sections à fond teinté.
- **Correctif** : couleur d'ombre = teinte du fond assombrie, faible opacité.

### DEPTH-05 · Système d'ombres à niveaux · p. 54-55 · mineur
- **Critère** : les ombres viennent d'une échelle de tokens (au moins 3 niveaux : douce pour
  boutons, petites cartes, vignettes ; moyenne pour modales et pop-ups ; forte pour menus déroulants
  et alertes importantes) ; aucune `box-shadow` ad hoc.
- **Vérifier** : `box-shadow` codées en dur dans le diff au lieu de `theme.shadows[n]`/tokens.
- **Correctif** : remplacer par le token du niveau adapté.

### DEPTH-06 · Variantes d'ombre déclarées dans le système · p. 55 · mineur
- **Critère** : une variante (ombre teintée pour un avertissement, très subtile pour un champ) est
  un token nommé, pas une valeur locale.
- **Vérifier** : ombres spéciales isolées dans un composant.
- **Correctif** : ajouter la variante au thème ou réutiliser une existante.

### DEPTH-07 · Profondeur par les fonds : page grise, cartes blanches · p. 55-56 · mineur
- **Critère** : les interfaces denses (tableaux de bord, listes de blocs) distinguent leurs
  sections par un fond de page légèrement gris et des cartes blanches, plutôt que tout en blanc.
- **Vérifier** : écrans tout blanc où les sections se confondent.
- **Correctif** : `background.default` gris très clair, `background.paper` blanc pour les blocs.

### DEPTH-08 · Ou des contours fins pour segmenter · p. 57 · mineur
- **Critère** : à défaut de fonds différenciés, des contours fins délimitent les zones.
- **Vérifier** : zones juxtaposées sans séparation lisible.
- **Correctif** : `border: 1px solid` couleur `divider`.

### DEPTH-09 · Pas d'excès de bordures et de fonds · p. 58-59 · mineur
- **Critère** : pas de bordure sur chaque ligne et section combinée à plusieurs couleurs de fond ;
  l'espace blanc et une couleur de fond suffisent souvent à séparer.
- **Vérifier** : séparateurs entre tous les items + encadré + fond d'en-tête + fond de pied.
- **Correctif** : retirer les séparateurs redondants, espacer.

### DEPTH-10 · Bordures fines et claires · p. 59-60 · mineur
- **Critère** : bordures et séparateurs font 1 px dans un gris clair ; pas de traits épais ou
  foncés qui alourdissent (lignes de tableau notamment).
- **Vérifier** : `border` > 1 px ou de couleur foncée ; `Divider` foncés.
- **Correctif** : `1px solid` `divider`/gris clair.

### DEPTH-11 · Une entorse aux règles est délibérée · p. 61 · suggestion
- **Critère** : quand une règle est enfreinte (ex. bordure épaisse de 10 px), c'est un choix
  assumé, cohérent avec la marque et équilibré (trait doux), pas un accident.
- **Vérifier** : l'entorse est-elle répétée de façon cohérente et justifiée par le style ?
- **Correctif** : soit l'assumer partout (token), soit revenir à la règle.

### DEPTH-12 · Effet verre seulement s'il sert la marque · p. 62-63 · suggestion
- **Critère** : le glassmorphisme (`backdrop-filter: blur`) n'est utilisé que s'il correspond à
  l'identité et apporte quelque chose à l'utilisateur.
- **Vérifier** : flou décoratif isolé, hors style du produit.
- **Correctif** : surface pleine si l'effet n'apporte rien.

### DEPTH-13 · Effet verre lisible sur le fond réel · p. 63-64 · bloquant
- **Critère** : le texte d'une surface translucide atteint 4.5:1 sur les fonds réels (y compris
  clairs) ; une tendance ne passe jamais avant la lisibilité.
- **Vérifier** : mesurer le contraste sur la capture, avec le fond le plus clair possible.
- **Correctif** : augmenter l'opacité/l'assombrissement du verre ou passer en surface pleine.

---

## COLOR - Couleur (p. 65-70)

### COLOR-01 · Couleur primaire réservée aux éléments interactifs · p. 65-66 · majeur
- **Critère** : la couleur principale signale ce qui est cliquable (boutons, liens, état actif) ;
  elle n'est pas étalée sur titres, icônes décoratives, fonds et textes.
- **Vérifier** : usages de `primary.main` hors éléments interactifs dans le diff et à l'écran.
- **Correctif** : passer les usages décoratifs en neutre ; garder le primaire pour l'action.

### COLOR-02 · Palette restreinte et équilibrée · p. 66 · majeur
- **Critère** : l'écran n'empile pas de nombreuses couleurs sans rôle ; chaque couleur a une
  fonction (action, état, catégorie).
- **Vérifier** : couleurs codées en dur hors palette ; plus de 3-4 teintes vives sur un écran.
- **Correctif** : ramener aux couleurs de la palette du thème, une fonction par couleur.

### COLOR-03 · Fonds neutres pour le contenu · p. 66-67 · majeur
- **Critère** : les écrans de contenu ou de tâche ont un fond neutre (blanc, gris très clair,
  beige) ; pas de fond vif plein écran derrière du texte et des contrôles.
- **Vérifier** : `background` saturé sur un écran de travail.
- **Correctif** : fond neutre, la couleur passe sur l'en-tête ou un bloc d'accent.

### COLOR-04 · Fond coloré réservé aux zones spéciales · p. 68 · suggestion
- **Critère** : un fond coloré n'apparaît que pour un écran d'accueil, un en-tête ou une section
  mise en avant.
- **Vérifier** : sections colorées successives sans hiérarchie.
- **Correctif** : limiter le fond coloré à une zone d'accent par écran.

### COLOR-05 · Fond sombre et mode sombre maîtrisés · p. 68-69 · suggestion
- **Critère** : un fond sombre est un choix assumé et cohérent avec la marque ; si le produit
  propose un mode sombre, chaque écran modifié le respecte (tokens, pas de couleurs en dur).
- **Vérifier** : couleurs codées en dur qui cassent le thème sombre ; contraste en mode sombre.
- **Correctif** : couleurs via la palette du thème. `n/a` si le produit n'a pas de mode sombre.

### COLOR-06 · Un état n'est jamais porté par la seule couleur · p. 69 · bloquant
- **Critère** : erreur, succès, avertissement combinent couleur + icône + texte explicite
  (ex. bordure rouge + icône « ! » + « Saisissez un montant supérieur à 1 € »).
- **Vérifier** : champs en erreur seulement rougis, statuts seulement colorés, graphiques
  légendés par la couleur seule.
- **Correctif** : ajouter message (`helperText`, relié par `aria-describedby`) et icône.

### COLOR-07 · Conventions de couleurs d'état · p. 70 · bloquant
- **Critère** : rouge = erreur/destructif, vert = succès, orange/ambre = avertissement ; on peut
  ajuster la nuance à la marque, pas changer la teinte (pas de jaune pour l'erreur ni de rose pour
  le succès).
- **Vérifier** : couleurs d'erreur et de succès utilisées dans le diff.
- **Correctif** : `error.main`, `success.main`, `warning.main` du thème.

---

## TYPO - Typographie (p. 71-96)

### TYPO-01 · Police adaptée au secteur et au ton · p. 71-72 · suggestion
- **Critère** : le caractère de la police correspond au registre du produit (serif pour un ton
  institutionnel, script seulement en titrage décoratif, sans-serif pour une appli moderne).
- **Vérifier** : polices introduites par le diff.
- **Correctif** : rester sur les polices du design system.

### TYPO-02 · Police lisible et agréable · p. 73 · majeur
- **Critère** : aucune police décorative (gothique, fantaisie) pour des titres ou du texte à lire.
- **Vérifier** : `font-family` des titres et paragraphes.
- **Correctif** : police de texte du système.

### TYPO-03 · Familles éprouvées · p. 74 · suggestion
- **Critère** : les polices de texte sont des familles reconnues pour leur lisibilité (Inter, Lato,
  Open Sans, Roboto, Manrope, Helvetica, SF, Gotham…).
- **Vérifier** : nouvelle police ajoutée sans justification.
- **Correctif** : préférer une famille éprouvée.

### TYPO-04 · Licence de police vérifiée · p. 74 · majeur
- **Critère** : toute police ajoutée a une licence compatible avec l'usage commercial (Google
  Fonts ou licence achetée).
- **Vérifier** : nouveaux `@font-face`, fichiers `.woff2`, imports de polices.
- **Correctif** : remplacer par une police sous licence libre ou documenter la licence.

### TYPO-05 · Deux familles au maximum, une idéalement · p. 74-75 · majeur
- **Critère** : au plus deux familles sur le produit ; idéalement une seule déclinée en graisses
  et tailles.
- **Vérifier** : `families` du script ; `font-family` codés en dur dans le diff.
- **Correctif** : supprimer les familles en trop, utiliser les variantes typographiques du thème.

### TYPO-06 · Si deux familles : une pour les titres, une pour le texte · p. 75 · mineur
- **Critère** : avec deux familles, l'une sert les titres et l'autre le texte, en paire éprouvée
  (ex. Playfair Display + Source Sans Pro, Montserrat + Open Sans).
- **Vérifier** : familles mélangées au sein d'un même niveau.
- **Correctif** : une famille par rôle, fixée dans les variantes du thème.

### TYPO-07 · Longueur de ligne 45-75 caractères (30-40 sur mobile) · p. 75-76 · majeur
- **Critère** : le texte courant fait 45 à 75 caractères par ligne sur desktop, 30 à 40 sur
  mobile.
- **Vérifier** : `lineLength` du script ; conteneurs de texte sans `max-width`.
- **Correctif** : `max-width: 65ch` (ou 60-75ch) sur les blocs de texte.

### TYPO-08 · Longueur mesurée et ajustée par appareil · p. 76 · mineur
- **Critère** : la longueur est mesurée (outil, unité `ch`) et ajustée au contenu et à l'écran
  plutôt que devinée.
- **Vérifier** : largeur exprimée en px fixes qui donne des lignes trop longues à certains
  breakpoints.
- **Correctif** : largeur en `ch`, ajustée par breakpoint si besoin.

### TYPO-09 · Pas de texte pleine largeur sur grand écran · p. 77-79 · majeur
- **Critère** : sur un écran large, un paragraphe n'occupe pas toute la largeur ; il est contenu
  dans une colonne (centrée ou alignée à gauche) de 75 caractères au plus.
- **Vérifier** : capture 1440 px ; paragraphes dans des conteneurs `width: 100%`.
- **Correctif** : colonne de texte `max-width: 65ch`.

### TYPO-10 · Paragraphes courts et espacés · p. 80, 96 · mineur
- **Critère** : les textes longs sont découpés en paragraphes courts séparés par un espace net.
- **Vérifier** : blocs de plus de 5-6 lignes sans coupure ; paragraphes collés (`margin: 0`).
- **Correctif** : découper la copie, espacer les paragraphes (≈ 0.75-1em).

### TYPO-11 · Intertitres pour les contenus longs · p. 81 · mineur
- **Critère** : un contenu de plusieurs paragraphes a des intertitres qui résument chaque partie
  (avec éventuellement icône, filet ou espace supplémentaire).
- **Vérifier** : longues descriptions sans structure.
- **Correctif** : intertitres (`h3`/`h4` sémantiques) + espacement.

### TYPO-12 · Pas de noir ou blanc purs pour le texte · p. 82, 95 · mineur
- **Critère** : pas de `#000` sur blanc ni `#FFF` sur fond sombre pour le texte ; titres en
  quasi-noir, corps en gris foncé (en sombre : titres blanc cassé, corps gris clair).
- **Vérifier** : `pureBlackWhite` du script ; `#000`, `black`, `#fff` dans les styles de texte.
- **Correctif** : `text.primary`/`text.secondary` du thème (ex. #1A1A1A / #4E4E4E,
  sombre #F2F2F2 / #CACACA), toujours ≥ 4.5:1.

### TYPO-13 · Titres plus gras que le texte · p. 83, 95-96 · majeur
- **Critère** : titres en medium, semibold ou bold ; texte en regular (parfois light) ; jamais la
  même graisse pour les deux.
- **Vérifier** : `font-weight` des titres et paragraphes.
- **Correctif** : variantes typographiques du thème.

### TYPO-14 · Titres fins seulement si taille et couleur portent la hiérarchie · p. 84 · suggestion
- **Critère** : un titre en graisse légère est admis si sa taille est nettement supérieure au texte
  et sa couleur plus foncée.
- **Vérifier** : titres light/regular de taille proche du texte.
- **Correctif** : agrandir nettement le titre ou augmenter sa graisse.

### TYPO-15 · Pas de gris trop clair pour le texte · p. 85, 95 · bloquant
- **Critère** : aucun texte gris clair sous le seuil AA (ex. #A9A9A9 sur blanc échoue, #626262
  passe).
- **Vérifier** : `lowContrast` du script.
- **Correctif** : gris plus foncé de la palette.

### TYPO-16 · Pas de graisses extra-fines pour le texte · p. 86, 95 · majeur
- **Critère** : le texte courant est en regular ou medium ; pas de thin/extra-light/light (100-300).
- **Vérifier** : `font-weight` < 400 sur des paragraphes ; `weights` du script.
- **Correctif** : `font-weight: 400` (ou 500).

### TYPO-17 · La taille dit l'importance · p. 87-88 · majeur
- **Critère** : le message le plus important est le plus grand ; un titre est nettement plus grand
  que le texte qui le suit (jamais à la même taille).
- **Vérifier** : comparer tailles du titre et du corps ; message clé plus petit qu'un message
  secondaire.
- **Correctif** : remonter la taille du message principal, réduire le secondaire.

### TYPO-18 · Tailles lisibles : 16 px pour le corps, jamais moins de 12 px · p. 89, 95-96 · bloquant
- **Critère** : texte principal autour de 16 px (ajustable selon plateforme et police) ; aucun
  texte principal sous 12 px ; aucun texte sous 10 px.
- **Vérifier** : `small` du script ; `font-size` codés en dur.
- **Correctif** : variantes `body1`/`body2` du thème ; texte annexe 12-14 px minimum.

### TYPO-19 · Interlignage du corps 1.5 à 1.6 · p. 90 · majeur
- **Critère** : `line-height` du texte courant entre 1.5 et 1.6 ; jamais sous 1.2 ni au-dessus de 2.
- **Vérifier** : `lineHeight` du script.
- **Correctif** : `line-height: 1.5` (ou la variante du thème).

### TYPO-20 · Interlignage plus serré pour les titres · p. 91, 95-96 · mineur
- **Critère** : titres plus serrés que le texte (≈ 1.1-1.3 ; ex. 36 px -> 1.3) ; plus le texte est
  grand, plus l'interlignage est petit ; jamais un titre plus aéré que ses paragraphes.
- **Vérifier** : `line-height` des titres multi-lignes.
- **Correctif** : `line-height: 1.2` à `1.3` pour les titres.

### TYPO-21 · Contraste texte/fond au moins AA · p. 92, 96 · bloquant
- **Critère** : contraste ≥ 4.5:1 pour le texte normal (≥ 3:1 pour le grand texte : ≥ 24 px, ou
  ≥ 18.66 px gras), y compris texte sur fond coloré et texte des boutons.
- **Vérifier** : `lowContrast` du script ; outils WebAIM Contrast Checker, plugin Figma Contrast.
- **Correctif** : assombrir le texte ou le fond avec les tokens conformes.

### TYPO-22 · Alignement du texte · p. 93, 96 · majeur
- **Critère** : paragraphes, listes, contenus longs alignés à gauche ; centrage pour titres et
  textes courts ; alignement droit ou centré seulement pour des éléments décoratifs.
- **Vérifier** : `text-align` sur les blocs de texte du diff.
- **Correctif** : `text-align: start` sur les textes longs (voir ALIGN-03, ALIGN-06).

### TYPO-23 · Libellés de boutons lisibles · p. 94 · bloquant
- **Critère** : le texte d'un bouton atteint 4.5:1 sur son fond et a une graisse suffisante
  (semibold) ; pas de texte blanc fin sur un fond pastel.
- **Vérifier** : contraste et graisse des libellés de boutons, notamment colorés clairs.
- **Correctif** : texte foncé sur fond clair, ou fond plus soutenu ; `font-weight: 600`.
  Ex. `examples.md#carte-typographique`.

### TYPO-24 · Sans-serif pour le texte courant · p. 96 · mineur
- **Critère** : le corps de texte est en sans-serif (Inter, Open Sans, Roboto…), plus lisible à
  l'écran qu'une serif (Times, Georgia) ; la serif peut rester en titrage.
- **Vérifier** : `font-family` des paragraphes.
- **Correctif** : variante de corps du thème.

### TYPO-25 · Passe finale « à éviter / à faire » du livre · p. 95-96 · majeur
- **Critère** : sur le texte de l'écran, aucun des écueils récapitulés : noir ou blanc purs pour
  titres et texte, même couleur ou même graisse titres/texte, interlignage des titres plus grand
  que celui du texte, mauvais contraste pour l'esthétique, texte < 10 px, graisses extra-fines,
  plus de deux polices, police qui sacrifie esthétique ou lisibilité.
- **Vérifier** : relire la sortie complète du script et la capture.
- **Correctif** : renvoyer chaque écueil trouvé à son item (TYPO-05, 12, 13, 15, 16, 18, 20, 21).

---

## COST - Coût d'interaction (p. 97-108)

### COST-01 · Effort cognitif, physique et temporel minimal · p. 97 · majeur
- **Critère** : pour la tâche principale, le nombre d'étapes, clics, frappes et défilements est le
  plus bas possible, et rien n'oblige à réfléchir pour savoir quoi faire.
- **Vérifier** : compter les interactions du parcours principal avant/après le diff.
- **Correctif** : supprimer les étapes ou interactions qui n'apportent rien.

### COST-02 · Moins lire, chercher, taper, attendre, mémoriser · p. 98 · majeur
- **Critère** : le parcours limite la lecture, le défilement, la recherche d'information, les
  erreurs de clic, la saisie, l'attente et ce qu'il faut retenir d'un écran à l'autre.
- **Vérifier** : informations à recopier d'un écran à l'autre, attentes sans retour visuel,
  saisies évitables.
- **Correctif** : préremplir, afficher l'info au bon endroit, état de chargement, valeurs par défaut.

### COST-03 · Actions proches de leur objet, cibles assez grandes (Fitts) · p. 99 · majeur
- **Critère** : une action est placée à côté de l'élément qu'elle concerne ; sa zone cliquable est
  suffisante (repère courant : 44 × 44 px au tactile) ; les commandes fréquentes restent à portée
  (barre fixe).
- **Vérifier** : actions regroupées loin de leur objet ; `IconButton` < 40 px ; liens minuscules.
- **Correctif** : rapprocher l'action ; agrandir la zone (padding) sans changer le visuel.

### COST-04 · Moins de choix (Hick) · p. 100 · majeur
- **Critère** : on ne présente pas une liste interminable ; une sélection recommandée ou
  populaire, des valeurs par défaut et des filtres raccourcissent la décision.
- **Vérifier** : listes longues non triées, menus à 15 options, pas de préselection.
- **Correctif** : mettre en avant 3-6 recommandations, « Voir tout » pour le reste.

### COST-05 · Information découpée en blocs (mémoire de travail) · p. 100-101 · mineur
- **Critère** : l'information est groupée en blocs titrés d'environ 7 éléments au plus, plutôt
  qu'un mur de texte.
- **Vérifier** : longues listes plates ou paragraphes descriptifs uniques.
- **Correctif** : sections titrées, listes d'équipements en grille avec icônes, « Afficher plus ».

### COST-06 · Pas de distraction pendant une tâche · p. 102 · majeur
- **Critère** : pas de bannière animée, pop-up ou visuel superflu qui détourne pendant la lecture
  ou un parcours.
- **Vérifier** : modales automatiques, carrousels animés, bandeaux promotionnels dans le parcours.
- **Correctif** : retirer ou différer ces éléments hors du parcours.

### COST-07 · Reconnaissance plutôt que rappel · p. 103 · majeur
- **Critère** : l'utilisateur reconnaît au lieu de se souvenir : icônes et termes familiers,
  disposition logique, état retenu (« reprendre où j'en étais », éléments récents, valeurs déjà
  saisies).
- **Vérifier** : informations à retenir entre deux écrans ; vocabulaire maison obscur ; perte de
  l'état au retour.
- **Correctif** : afficher le contexte, persister l'état, utiliser les termes et icônes standards.

### COST-08 · Tâches rationalisées · p. 104 · majeur
- **Critère** : les étapes supprimables ou combinables le sont ; adresse, carte, identité
  préremplies ou autocomplétées.
- **Vérifier** : attributs `autocomplete` manquants sur les champs d'adresse, e-mail, téléphone,
  carte ; étapes en double.
- **Correctif** : `autocomplete` standards, autocomplétion d'adresse, fusion d'étapes.

### COST-09 · Moins de répétition · p. 105 · mineur
- **Critère** : une action répétitive peut être faite en lot ou automatisée (sélection multiple,
  « appliquer à tous », mémorisation du choix).
- **Vérifier** : actions à refaire élément par élément.
- **Correctif** : action groupée ou préférence mémorisée.

### COST-10 · Options visibles plutôt que cachées dans un menu déroulant · p. 106-107 · majeur
- **Critère** : quand il y a peu d'options, elles sont affichées directement (pastilles de
  couleur, boutons segmentés, radios) avec un aperçu visuel plutôt qu'un `select` qui les cache.
- **Vérifier** : `Select` de 2 à 5 options ; choix de couleur ou de format en texte dans un menu.
- **Correctif** : `ToggleButtonGroup`, radios en pastilles, échantillons visuels. Ex.
  `examples.md#options-visibles`.

### COST-11 · Sélecteur de quantité direct · p. 107 · mineur
- **Critère** : une quantité se règle par boutons − / + avec saisie directe possible, pas par un
  menu déroulant.
- **Vérifier** : `Select` numérique pour une quantité.
- **Correctif** : stepper − / champ numérique / +.

### COST-12 · CTA final proche de la dernière saisie · p. 107 · mineur
- **Critère** : le bouton de validation est placé juste après le dernier réglage, sans grand
  déplacement du pointeur.
- **Vérifier** : CTA éloigné du dernier champ.
- **Correctif** : rapprocher le bouton du dernier contrôle.

### COST-13 · Raccourci de parcours quand c'est possible · p. 108 · suggestion
- **Critère** : si le modèle le permet, un chemin court réutilise les données connues (achat en un
  clic, « Réserver maintenant » à côté de « Ajouter au panier »).
- **Vérifier** : parcours long imposé alors que les données sont déjà enregistrées.
- **Correctif** : proposer le raccourci comme action primaire ou secondaire selon l'objectif.

---

## BONUS - Astuces bonus (p. 109-141)

### BONUS-01 · Montrer le contenu au lieu d'une bannière qui y mène · p. 110-112 · majeur
- **Critère** : la page d'accueil ou de découverte expose directement les éléments (liste de
  recettes, cours, profils) avec « Voir tout », au lieu de bannières « Découvrez 100+ … » qu'il
  faut ouvrir.
- **Vérifier** : bannières dont la seule fonction est d'ouvrir une liste.
- **Correctif** : remplacer par un aperçu des premiers éléments + lien « Voir tout ».

### BONUS-02 · Champ de code : une case par caractère · p. 113-114 · mineur
- **Critère** : un code de vérification se saisit dans des cases séparées, chiffres en grand.
- **Vérifier** : champ unique générique pour un OTP.
- **Correctif** : cases individuelles avec `inputmode="numeric"`,
  `autocomplete="one-time-code"`, collage du code entier accepté, focus qui avance.

### BONUS-03 · Largeur du champ proportionnée à la donnée · p. 114-115 · mineur
- **Critère** : champs courts pour données courtes (CVC, expiration, code postal), regroupés côte
  à côte ; champ long pour une donnée longue.
- **Vérifier** : tous les champs en pleine largeur dans un formulaire de paiement ou d'adresse.
- **Correctif** : grille à deux colonnes pour expiration/CVC, pays/code postal.

### BONUS-04 · Pas de champ « confirmer le mot de passe » · p. 116-117 · majeur
- **Critère** : la création de mot de passe n'a qu'un champ.
- **Vérifier** : second champ de confirmation dans inscription ou réinitialisation.
- **Correctif** : supprimer la confirmation, ajouter BONUS-05 et BONUS-06.

### BONUS-05 · Bouton afficher/masquer le mot de passe · p. 117 · majeur
- **Critère** : chaque champ mot de passe a une bascule afficher/masquer accessible.
- **Vérifier** : `type="password"` sans `InputAdornment` de visibilité.
- **Correctif** : bouton œil avec `aria-label` et `aria-pressed`.

### BONUS-06 · Validation du mot de passe en direct · p. 118 · mineur
- **Critère** : les exigences et la robustesse s'affichent pendant la saisie (barres, coches,
  message sous le champ), pas seulement après envoi.
- **Vérifier** : erreurs de règles de mot de passe uniquement au submit.
- **Correctif** : indicateur de robustesse et liste de critères cochés en temps réel.

### BONUS-07 · Confirmation destructive : bouton rouge au verbe explicite · p. 119 · bloquant
- **Critère** : dans une confirmation de suppression, le bouton d'action est rouge (jamais vert),
  libellé par le verbe (« Supprimer »), et la conséquence est dite (« Action irréversible »).
- **Vérifier** : `Dialog` de suppression : couleur et libellé du bouton, texte de conséquence.
- **Correctif** : `color="error"`, libellé verbe, phrase de conséquence.

### BONUS-08 · Toujours une sortie : Annuler · p. 120 · bloquant
- **Critère** : toute confirmation propose « Annuler » (et une fermeture) en plus de l'action.
- **Vérifier** : dialogues à bouton unique pour une action irréversible.
- **Correctif** : ajouter le bouton Annuler (secondaire) et la croix de fermeture.

### BONUS-09 · Annuler à gauche, action à droite · p. 121 · majeur
- **Critère** : dans les dialogues, l'action qui fait avancer est à droite, le retour/annulation à
  gauche, partout dans le produit.
- **Vérifier** : ordre des boutons dans `DialogActions` et pieds de formulaire.
- **Correctif** : réordonner (le DOM suit le même ordre).

### BONUS-10 · Pas de long bloc de texte monolithique · p. 122 · majeur
- **Critère** : une description de produit ou d'offre n'est pas un seul long paragraphe dense.
- **Vérifier** : paragraphes de plus de ~6 lignes dans des fiches.
- **Correctif** : voir BONUS-11 et BONUS-12.

### BONUS-11 · Sections courtes avec icônes · p. 123 · mineur
- **Critère** : le contenu est découpé en sections logiques ; les points clés sont listés avec des
  icônes (coches pour les atouts, étoiles pour la note).
- **Vérifier** : avantages noyés dans un paragraphe.
- **Correctif** : liste « Points clés » avec icône + titre court + phrase.

### BONUS-12 · Deux colonnes pour les caractéristiques · p. 124 · suggestion
- **Critère** : quand la place le permet, les caractéristiques sont présentées en grille à deux
  colonnes pour être comparées d'un coup d'œil.
- **Vérifier** : longue liste verticale de 4+ atouts sur desktop.
- **Correctif** : `grid-template-columns: repeat(2, 1fr)` au-dessus du breakpoint mobile.

### BONUS-13 · Aller au-delà du brief · p. 125-126 · suggestion
- **Critère** : on a envisagé les contenus qui aideraient la décision au-delà de la consigne
  (comparaison, témoignages, preuve sociale) et proposé les pertinents.
- **Vérifier** : la page répond-elle aux questions que se pose l'utilisateur ?
- **Correctif** : proposer l'ajout (en revue : suggestion, pas exigence).

### BONUS-14 · Créatif mais toujours pertinent · p. 126 · majeur
- **Critère** : chaque information répond à une question, résout un problème ou éclaire
  l'utilisateur ; sinon elle est coupée ou reformulée.
- **Vérifier** : appliquer la question à chaque bloc de texte ajouté.
- **Correctif** : couper ou reformuler.

### BONUS-15 · Pas de distraction à côté d'une tâche · p. 127 · majeur
- **Critère** : aucune promotion, publicité ou CTA sans rapport à côté d'un parcours
  (inscription, paiement, réservation).
- **Vérifier** : panneaux latéraux avec CTA concurrent sur les écrans de formulaire.
- **Correctif** : retirer le CTA concurrent.

### BONUS-16 · Visuel décoratif sans action · p. 128 · suggestion
- **Critère** : un visuel à côté d'un formulaire est admis s'il est fidèle à la marque et ne porte
  ni texte d'appel ni bouton.
- **Vérifier** : visuel latéral avec texte ou bouton.
- **Correctif** : garder l'image seule, `alt=""` si purement décorative.

### BONUS-17 · Ne pas remplir tout l'écran · p. 129-130 · majeur
- **Critère** : sur grand écran, formulaires et CTA ne s'étirent pas sur toute la largeur ; ils
  sont contenus dans un bloc de largeur utile entouré d'espace.
- **Vérifier** : capture 1440 px ; champs ou boutons `fullWidth` dans un conteneur sans `max-width`.
- **Correctif** : conteneur `max-width` (≈ 400-560 px) centré, fond de page distinct si besoin.

### BONUS-18 · Chevauchements d'images propres · p. 131-132 · suggestion
- **Critère** : quand une image chevauche une autre ou un fond, un liseré de la couleur du fond
  les sépare ; pas de chevauchement aux couleurs qui se heurtent.
- **Vérifier** : avatars empilés, médaillons sur bannière.
- **Correctif** : `border: 3-4px solid` couleur du fond (ou `box-shadow: 0 0 0 3px`).

### BONUS-19 · Zone du pouce sur mobile · p. 133-135 · majeur
- **Critère** : sur mobile, les CTA principaux et actions fréquentes sont dans la moitié basse de
  l'écran, atteignables d'une main ; pas dans les coins hauts.
- **Vérifier** : capture 375 px : position du CTA principal et des actions clés.
- **Correctif** : CTA en bas (bloc ou barre fixe en bas), actions secondaires à côté.

### BONUS-20 · États vides utiles · p. 135-136 · majeur
- **Critère** : un état vide explique et guide : titre qui propose une issue, illustration,
  conseils concrets, CTA pour démarrer ; jamais un simple « Aucun élément ».
- **Vérifier** : rendu quand la liste est vide (tester l'état).
- **Correctif** : composant d'état vide du système avec titre, texte, CTA.

### BONUS-21 · États d'erreur qui remettent sur les rails · p. 137 · bloquant
- **Critère** : une erreur (validation, réseau, page) dit clairement ce qui s'est passé, propose
  une solution actionnable et garde le style du produit.
- **Vérifier** : messages d'erreur génériques (« Une erreur est survenue »), erreurs techniques
  brutes, pages d'erreur hors charte.
- **Correctif** : message précis + action (« Réessayer », lien) + composants du système.

### BONUS-22 · Page 404 avec des issues · p. 138 · majeur
- **Critère** : la page introuvable propose des liens utiles, une recherche ou la navigation
  principale.
- **Vérifier** : `pages/404` et pages d'erreur.
- **Correctif** : ajouter liens vers les pages clés et recherche.

### BONUS-23 · Erreurs et 404 à l'image de la marque · p. 139 · suggestion
- **Critère** : la page d'erreur est un moment de marque (illustration maison, ton humain) tout en
  guidant vers la suite.
- **Vérifier** : page d'erreur générique.
- **Correctif** : illustration et texte de marque + issues de BONUS-22.

### BONUS-24 · Menus de navigation avec icônes et catégories · p. 140-141 · mineur
- **Critère** : les menus déroulants de navigation riches ont une icône et une courte description
  par entrée, et regroupent les entrées sous des catégories titrées.
- **Vérifier** : méga-menus en liste de liens nus.
- **Correctif** : icône + titre + description, groupes titrés.

### BONUS-25 · Images de menu seulement pour ce qu'on met en avant · p. 141 · suggestion
- **Critère** : les images dans un menu sont réservées aux quelques entrées à mettre en avant
  (articles récents, nouveauté), pas à chaque entrée.
- **Vérifier** : vignettes sur toutes les entrées d'un menu.
- **Correctif** : vignettes uniquement sur la colonne mise en avant, badge « Nouveau » au besoin.

---

## LVL - Aller plus loin (p. 142)

### LVL-01 · Valider avec de vrais utilisateurs · p. 142 · suggestion
- **Critère** : les règles du livre sont une base ; les choix structurants (parcours, libellés,
  disposition) sont confrontés à des tests avec la cible.
- **Vérifier** : changements de parcours importants sans test ni mesure prévue.
- **Correctif** : signaler dans le rapport ce qui mérite un test utilisateur ou une mesure (A/B,
  analytics).
