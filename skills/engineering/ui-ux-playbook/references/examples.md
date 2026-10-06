# Exemples avant/après du livre, traduits en code

Les valeurs viennent des exemples du livre (pages indiquées). Le code est en CSS et en MUI 5
(`sx`, `tss-react` `makeStyles`) ; dans un projet, remplace les valeurs littérales par les tokens du
thème équivalents. Chaque section renvoie aux items de `checklist.md`.

## Contents

1. [Hiérarchie des boutons (HIER-01, HIER-02, CONS-03 · p. 6-7, 39-40)](#hierarchie-des-boutons)
2. [Fiche hiérarchisée au lieu de « libellé : valeur » (HIER-09 · p. 11)](#fiche-hierarchisee)
3. [Badges de statut lisibles (CONT-01 · p. 20)](#badges-de-statut)
4. [Texte sur image (CONT-07 · p. 21)](#texte-sur-image)
5. [Échelle d'espacement et proximité (PROX-01, SPACE-03, SPACE-06 · p. 12, 27-28)](#espacement)
6. [Cartes sélectionnables (LAYOUT-04 · p. 32)](#cartes-selectionnables)
7. [Images hétérogènes dans un contenant uniforme (CONS-04 · p. 40-42)](#images-heterogenes)
8. [Cartes de même hauteur, CTA en bas (CONS-05, CONS-07 · p. 42-43)](#cartes-de-meme-hauteur)
9. [Ombres (DEPTH-03, DEPTH-04, DEPTH-05 · p. 51-55)](#ombres)
10. [Couleurs de texte (HIER-07, TYPO-12, TYPO-15 · p. 10, 82, 85)](#couleurs-de-texte)
11. [Carte typographique « avant/après » du livre (TYPO-12 à TYPO-23 · p. 94)](#carte-typographique)
12. [Longueur de ligne et texte pleine largeur (TYPO-07, TYPO-09 · p. 75-79)](#longueur-de-ligne)
13. [État d'erreur sans dépendre de la couleur (COLOR-06, COLOR-07 · p. 69-70)](#erreur-de-champ)
14. [Options visibles et quantité directe (COST-10, COST-11, COST-12 · p. 106-107)](#options-visibles)
15. [Champs adaptés au type de donnée (BONUS-02, BONUS-03 · p. 113-115)](#champs-par-type)
16. [Mot de passe (BONUS-04 à BONUS-06 · p. 116-118)](#mot-de-passe)
17. [Dialogue de suppression (BONUS-07 à BONUS-09 · p. 119-121)](#dialogue-destructif)
18. [Formulaire contenu sur grand écran (BONUS-17 · p. 129-130)](#formulaire-contenu)
19. [État vide (BONUS-20 · p. 135-136)](#etat-vide)
20. [Zone du pouce (BONUS-19 · p. 133-135)](#zone-du-pouce)

<a id="hierarchie-des-boutons"></a>
## Hiérarchie des boutons (HIER-01, HIER-02, CONS-03 · p. 6-7, 39-40)

Avant : « Retirer », « Continuer mes achats » et « Payer » sont trois boutons pleins de même taille
(et parfois de trois couleurs). Après : un primaire, un secondaire neutre, un tertiaire en lien.

```tsx
// Avant
<Button variant="contained">Retirer</Button>
<Button variant="contained">Continuer mes achats</Button>
<Button variant="contained">Payer</Button>

// Après
<Link component="button" color="error" underline="always">Retirer</Link>      {/* tertiaire, dans la ligne */}
<Button variant="outlined" color="inherit" fullWidth>Continuer mes achats</Button> {/* secondaire */}
<Button variant="contained" color="primary" fullWidth>Payer</Button>              {/* primaire, unique */}
```

Mêmes couleurs de bouton sur toutes les cartes d'une liste : ne jamais dériver `color` du contenu.

<a id="fiche-hierarchisee"></a>
## Fiche hiérarchisée au lieu de « libellé : valeur » (HIER-09 · p. 11)

```tsx
// Avant : 8 lignes identiques « Type : À vendre », « Prix : 1 273 279 € »…
// Après
<Stack spacing={1}>
  <Stack direction="row" justifyContent="space-between" alignItems="center">
    <Typography variant="h5" fontWeight={700}>1 273 279 €</Typography>
    <Chip label="À vendre" size="small" sx={{ bgcolor: 'warning.light', color: 'warning.dark' }} />
  </Stack>
  <Typography variant="subtitle1" fontWeight={600}>Villa 5 chambres</Typography>
  <Stack direction="row" spacing={0.5} alignItems="center" color="text.secondary">
    <PlaceOutlined fontSize="small" /><Typography variant="body2">29 Terrace Rd</Typography>
  </Stack>
  <Divider />
  <Stack direction="row" spacing={2}>{/* icône + chiffre en gras + unité */}</Stack>
</Stack>
```

<a id="badges-de-statut"></a>
## Badges de statut lisibles (CONT-01 · p. 20)

Avant : texte blanc sur rouge, orange, vert moyens (1.8:1 à 2.8:1). Après : fond teinté clair,
texte foncé de la même teinte (4.8:1 à 6.5:1).

```css
/* Avant */ .badge--blocked { background: #F2606A; color: #fff; }
/* Après */ .badge--blocked { background: #FDE2E4; color: #A11D2B; }
            .badge--progress { background: #FFEBD6; color: #8A4B08; }
            .badge--done     { background: #DDF5E3; color: #1E6B34; }
```

Et toujours un libellé texte dans le badge (COLOR-06).

<a id="texte-sur-image"></a>
## Texte sur image (CONT-07 · p. 21)

```css
.media-card { position: relative; }
.media-card__caption {
  position: absolute; inset: auto 0 0 0; padding: 16px; color: #F2F2F2;
  /* option 1 : dégradé qui garantit le contraste quelle que soit l'image */
  background: linear-gradient(to top, rgba(0, 0, 0, 0.65), rgba(0, 0, 0, 0));
  /* option 2 : bandeau flouté
  background: rgba(20, 20, 20, 0.35); backdrop-filter: blur(12px); */
}
```

Tester avec l'image la plus claire du jeu de données.

<a id="espacement"></a>
## Échelle d'espacement et proximité (PROX-01, SPACE-03, SPACE-06 · p. 12, 27-28)

Avant (formulaire du livre) : 7, 19, 8, 19, 21, 19 px. Après : 16, 40, 8, 24, 24, 24, 40 px.

```ts
// styles.ts (tss-react)
export const useStyles = makeStyles()((theme) => ({
  header: { marginBottom: theme.spacing(5) },          // 40 : sépare l'en-tête du formulaire
  field: { display: 'flex', flexDirection: 'column', gap: theme.spacing(1) }, // 8 : libellé -> champ
  fields: { display: 'flex', flexDirection: 'column', gap: theme.spacing(3) }, // 24 : champ -> champ
  submit: { marginTop: theme.spacing(5) },             // 40 : avant l'action
}));
```

<a id="cartes-selectionnables"></a>
## Cartes sélectionnables (LAYOUT-04 · p. 32)

```tsx
<Stack direction="row" spacing={2} role="radiogroup" aria-label="Formule">
  {plans.map((p) => (
    <Card
      key={p.id} role="radio" aria-checked={value === p.id} tabIndex={0}
      onClick={() => setValue(p.id)}
      onKeyDown={(e) => (e.key === ' ' || e.key === 'Enter') && setValue(p.id)}
      variant="outlined"
      sx={{ p: 2, cursor: 'pointer', borderColor: value === p.id ? 'primary.main' : 'divider',
            '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' } }}
    >
      <Chip label={p.name} size="small" />
      <Typography variant="h6" fontWeight={700}>{p.credits} <small>crédits</small></Typography>
      <Typography variant="body2" color="text.secondary">{p.price} / mois</Typography>
    </Card>
  ))}
</Stack>
```

<a id="images-heterogenes"></a>
## Images hétérogènes dans un contenant uniforme (CONS-04 · p. 40-42)

```css
.thumb {
  width: 96px; height: 96px; border-radius: 50%;
  display: grid; place-items: center; background: var(--tint, #F3F1FA);
}
.thumb img { width: 72%; height: 72%; object-fit: contain; }
```

<a id="cartes-de-meme-hauteur"></a>
## Cartes de même hauteur, CTA en bas (CONS-05, CONS-07 · p. 42-43)

```css
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; align-items: stretch; }
.card { display: flex; flex-direction: column; height: 100%; }
.card__cta { margin-top: auto; } /* l'espace en trop reste au milieu, les boutons s'alignent */
```

<a id="ombres"></a>
## Ombres (DEPTH-03, DEPTH-04, DEPTH-05 · p. 51-55)

Valeurs du livre : dure `0 0 48px #9F9F9F` -> douce `0 12px 48px #E9E9E9` ; sur fond violet clair,
grise `0 19px 48px #C7C7C7` -> teintée `0 19px 56px #CFC9DD` ; sur fond beige `#E3D5B2`.

```ts
// Un système à niveaux plutôt que des box-shadow locales
const shadows = {
  soft:   '0 2px 8px rgba(17, 12, 34, 0.06)',  // boutons, petites cartes, vignettes
  medium: '0 8px 24px rgba(17, 12, 34, 0.10)', // modales, pop-ups
  strong: '0 12px 48px rgba(17, 12, 34, 0.14)', // menus déroulants, alertes importantes
};
// Sur un fond teinté, la couleur d'ombre reprend la teinte du fond :
// background: #F4F1FB ; box-shadow: 0 12px 48px rgba(91, 72, 160, 0.16)
```

<a id="couleurs-de-texte"></a>
## Couleurs de texte (HIER-07, TYPO-12, TYPO-15 · p. 10, 82, 85)

```ts
// Clair : jamais #000 ; corps assez foncé pour AA
text: { primary: '#1A1A1A', secondary: '#4E4E4E' } // #A9A9A9 échoue AA, #626262 passe
// Sombre : jamais #FFF pur
text: { primary: '#F2F2F2', secondary: '#CACACA' }
```

<a id="carte-typographique"></a>
## Carte typographique « avant/après » du livre (TYPO-12 à TYPO-23 · p. 94)

| Élément | Avant (à éviter) | Après (livre) |
| --- | --- | --- |
| Titre | 22px, medium, interligne 170 %, #000, centré | 28px, bold, interligne 120 %, #1B000D, à gauche |
| Corps | 18px, regular, interligne 110 %, #000, centré | 18px, regular, interligne 160 %, #5E5458, à gauche |
| Bouton | 22px regular blanc sur rose clair (échec AA) | 18px semibold #141B12 sur rose (AA et AAA) |

```css
.card__title { font-size: 28px; font-weight: 700; line-height: 1.2; color: #1B000D; }
.card__body  { font-size: 18px; font-weight: 400; line-height: 1.6; color: #5E5458; max-width: 65ch; }
.card__cta   { font-size: 18px; font-weight: 600; color: #141B12; }
```

<a id="longueur-de-ligne"></a>
## Longueur de ligne et texte pleine largeur (TYPO-07, TYPO-09 · p. 75-79)

```css
.prose { max-width: 65ch; }                 /* 45-75 caractères sur desktop */
@media (max-width: 600px) { .prose { max-width: 38ch; } } /* repère 30-40 sur mobile, si la colonne le permet */
.prose p + p { margin-top: 0.75em; }        /* TYPO-10 */
```

<a id="erreur-de-champ"></a>
## État d'erreur sans dépendre de la couleur (COLOR-06, COLOR-07 · p. 69-70)

```tsx
<TextField
  label="Montant" value={amount} error={amount < 1}
  helperText={amount < 1 ? 'Saisissez un montant supérieur à 1 €' : ' '}
  InputProps={{ endAdornment: amount < 1 && <ErrorOutline color="error" aria-hidden /> }}
/>
```

<a id="options-visibles"></a>
## Options visibles et quantité directe (COST-10, COST-11, COST-12 · p. 106-107)

Avant : couleur et quantité dans deux `Select` (5 clics, 1 défilement). Après :

```tsx
<ToggleButtonGroup exclusive value={color} onChange={(_, c) => c && setColor(c)} aria-label="Couleur">
  {colors.map((c) => (
    <ToggleButton key={c.id} value={c.id} aria-label={c.label} sx={{ borderRadius: '50%', p: 0.5 }}>
      <Box sx={{ width: 24, height: 24, borderRadius: '50%', bgcolor: c.hex }} />
    </ToggleButton>
  ))}
</ToggleButtonGroup>
<Stack direction="row" spacing={2} alignItems="center">
  <QuantityStepper value={qty} onChange={setQty} />{/* − | champ numérique | + */}
  <Button variant="contained">Ajouter au panier</Button>{/* juste à côté du dernier réglage */}
</Stack>
```

<a id="champs-par-type"></a>
## Champs adaptés au type de donnée (BONUS-02, BONUS-03 · p. 113-115)

```tsx
// Code de vérification : une case par chiffre
<Stack direction="row" spacing={1}>
  {digits.map((d, i) => (
    <input key={i} inputMode="numeric" autoComplete={i === 0 ? 'one-time-code' : 'off'} maxLength={1}
      aria-label={`Chiffre ${i + 1}`} style={{ width: 48, height: 56, fontSize: 24, textAlign: 'center' }} />
  ))}
</Stack>
// Paiement : champs courts côte à côte
<Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
  <TextField label="Expiration" placeholder="MM/AA" inputProps={{ autoComplete: 'cc-exp' }} />
  <TextField label="CVC" inputProps={{ autoComplete: 'cc-csc', inputMode: 'numeric' }} />
</Box>
```

<a id="mot-de-passe"></a>
## Mot de passe (BONUS-04 à BONUS-06 · p. 116-118)

Un seul champ, bouton afficher/masquer, robustesse affichée pendant la saisie :

```tsx
<TextField
  type={visible ? 'text' : 'password'} label="Mot de passe" autoComplete="new-password"
  InputProps={{ endAdornment: (
    <IconButton aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
      aria-pressed={visible} onClick={() => setVisible((v) => !v)}>
      {visible ? <VisibilityOffOutlined /> : <VisibilityOutlined />}
    </IconButton>) }}
  helperText={<PasswordStrength value={password} />} // 4 barres + libellé « Faible / Correct / Fort »
/>
```

<a id="dialogue-destructif"></a>
## Dialogue de suppression (BONUS-07 à BONUS-09 · p. 119-121)

```tsx
<Dialog open={open} onClose={onClose} aria-labelledby="delete-title">
  <DialogTitle id="delete-title">Supprimer vos données ?</DialogTitle>
  <IconButton aria-label="Fermer" onClick={onClose} sx={{ position: 'absolute', right: 8, top: 8 }}><Close /></IconButton>
  <DialogContent><DialogContentText>Cette action est irréversible.</DialogContentText></DialogContent>
  <DialogActions>
    <Button onClick={onClose}>Annuler</Button>                                {/* à gauche */}
    <Button onClick={onConfirm} variant="contained" color="error">Supprimer</Button> {/* à droite, rouge */}
  </DialogActions>
</Dialog>
```

<a id="formulaire-contenu"></a>
## Formulaire contenu sur grand écran (BONUS-17 · p. 129-130)

```css
.auth-page { min-height: 100vh; display: grid; place-items: center; background: #F7F7F8; padding: 24px; }
.auth-card { width: 100%; max-width: 480px; padding: 32px; background: #fff; border-radius: 16px; }
```

<a id="etat-vide"></a>
## État vide (BONUS-20 · p. 135-136)

Avant : « Vous n'avez aucun projet ! » seul au milieu de l'écran. Après : illustration, titre qui
propose une issue (« Organisez vos projets et gardez le cap »), deux conseils actionnables, CTA
« Créer un projet ».

<a id="zone-du-pouce"></a>
## Zone du pouce (BONUS-19 · p. 133-135)

Avant : « Se connecter » en haut à droite. Après : « S'inscrire » (primaire) et « Se connecter »
(secondaire) empilés en bas de l'écran.

```css
@media (max-width: 600px) {
  .mobile-actions { position: sticky; bottom: 0; padding: 16px; display: grid; gap: 12px;
                    padding-bottom: calc(16px + env(safe-area-inset-bottom)); }
}
```
