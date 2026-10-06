// Mesures typographiques et de contraste sur la page affichée (checklist TYPO, CONT, COLOR).
// Usage : coller dans la console, ou passer le fichier à l'évaluation JavaScript de l'outil navigateur.
// Limites : le fond est le premier ancêtre à background-color opaque (images et dégradés ignorés,
// donc vérifier à l'œil le texte posé sur une image) ; une seule ligne par élément mesuré.
(() => {
  const rgb = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => {
    const c = [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const bgOf = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const c = rgb(getComputedStyle(n).backgroundColor);
      if (c.length >= 3 && (c[3] === undefined || c[3] > 0.9)) return c;
    }
    return [255, 255, 255];
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const out = { families: {}, sizes: {}, weights: {}, small: [], lowContrast: [], pureBlackWhite: [], lineHeight: [], lineLength: [] };
  for (const el of document.querySelectorAll('body *')) {
    const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
    if (!own) continue;
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    if (cs.visibility === 'hidden' || box.width === 0 || box.height === 0) continue;
    const fs = parseFloat(cs.fontSize);
    const bold = Number(cs.fontWeight) >= 700;
    const label = `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''} "${own.slice(0, 40)}"`;
    const fam = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
    out.families[fam] = (out.families[fam] || 0) + 1;
    out.sizes[fs] = (out.sizes[fs] || 0) + 1;
    out.weights[cs.fontWeight] = (out.weights[cs.fontWeight] || 0) + 1;
    if (fs < 12) out.small.push(`${fs}px ${label}`);
    const fg = rgb(cs.color);
    const r = ratio(fg, bgOf(el));
    const large = fs >= 24 || (fs >= 18.66 && bold);
    if (r < (large ? 3 : 4.5)) out.lowContrast.push(`${r.toFixed(2)}:1 ${cs.color} ${label}`);
    if (/^rgba?\(0, 0, 0(, 1)?\)$|^rgba?\(255, 255, 255(, 1)?\)$/.test(cs.color) && own.length > 60) out.pureBlackWhite.push(`${cs.color} ${label}`);
    const lhPx = cs.lineHeight === 'normal' ? fs * 1.2 : parseFloat(cs.lineHeight);
    const lines = Math.round(box.height / lhPx);
    if (own.length > 120) {
      const lh = lhPx / fs;
      if (lh < 1.4 || lh > 2) out.lineHeight.push(`${lh.toFixed(2)} ${label}`);
      if (lines > 1) {
        const cpl = Math.round(own.length / lines);
        if (cpl > 75 || (innerWidth < 600 && cpl > 45)) out.lineLength.push(`${cpl} car./ligne ${label}`);
      }
    }
  }
  return out;
})()
