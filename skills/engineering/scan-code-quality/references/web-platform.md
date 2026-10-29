# Web platform quality for React apps

Scope: performance (Core Web Vitals), accessibility, security, internationalisation and indexability — the rules a browser and an assistive technology enforce on a React frontend, as opposed to the ones React enforces on itself.

## Contents

- [Version baseline](#version-baseline)
- [Rules](#rules)
- [Tools](#tools)

## Version baseline

| Package | Version | Verified from |
|---|---|---|
| React | 19.3.1 (19.3 released 2026-09-09) | react.dev/versions, npm registry |
| React Compiler | 1.0 (2025-10-07) | react.dev/versions changelog |
| Next.js | 16.4.3 (16.4.0 2026-10-06, 16.4.1 security 2026-10-14); 15.5.28 is Maintenance LTS | nextjs.org/blog, npm registry |
| Vite | 8.3.5 (8.0 Rolldown-powered 2026-03-12; 8.1 2026-06-23) | vite.dev/blog, npm registry |
| TypeScript | 7.0.2 (native compiler) | npm registry |
| React Router | 8.5.0 | npm registry |
| TanStack Query | 5.104.5 | npm registry |
| ESLint | 10.13.0; eslint-plugin-react-hooks 7.1.1; eslint-plugin-jsx-a11y 6.10.2 | npm registry |
| Vitest | 5.0.5 | npm registry |
| Tailwind CSS | 4.3 (2026-05-08) | tailwindcss.com/blog |
| Core Web Vitals | LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1, at p75 | web.dev/articles/vitals |

"Since" below means the version from which the rule applies. Where a rule is enforced by the browser rather than by a package, "all" means every React version.

## Rules

### 1. Split the bundle at route boundaries and hold a per-route JS budget

**Rule** – Give every route its own chunk, and fail CI when the entry chunk exceeds its budget.

**Since** – all (React 16.6 for `React.lazy`; chassis-agnostic).

**Detection signals**
- No occurrence of `lazy(`, `import(`, or a router-level lazy option in `src/**`, and a single `<script type="module" src="/src/main.tsx">` entry in `index.html`.
- Route components all imported statically in one `routes.tsx` / `App.tsx`.
- `vite.config.*` without `build.rollupOptions.output.manualChunks`, or `next.config.*` without route-level dynamic imports.
- Measurable: total initial JS > 200 kB gzip, or any single chunk > 250 kB gzip. Read it from `npx vite build` output, `.next/` build summary, or `npx source-map-explorer dist/assets/*.js`.
- Whole-library imports for one symbol: `import _ from 'lodash'`, `import moment from 'moment'`, `import { Check } from 'lucide-react'` pulled through a barrel `import * as Icons`.
- Barrel re-export files (`index.ts` re-exporting 50 modules) consumed by an app entry point — this defeats tree-shaking in Vite/webpack unless the bundler is told otherwise.

**Severity hint** – High (LCP regression on every cold navigation; on mobile 3G a 200 kB extra chunk is roughly 1 s of LCP).

**Refactor direction** – Move each route's component into its own module and load it lazily, keeping a real fallback that reserves layout height so the swap does not shift content.

```tsx
// before
import Settings from './pages/Settings';
// after
const Settings = lazy(() => import('./pages/Settings'));
<Suspense fallback={<PageSkeleton />}><Settings /></Suspense>
```

Import the single symbol instead of the library (`import debounce from 'lodash/debounce'`), or replace it with `structuredClone`/`Array.prototype` methods.

**Counter-signals** – A genuinely single-screen app (an embedded widget, a kiosk) has nothing to split; splitting there costs a network round trip for no benefit. Barrel files are fine when their consumers already import the whole surface. In Next.js App Router, route splitting is automatic — flag only large client components and oversized `'use client'` leaves (see rule 8). The Pages Router splits per page file the same way (`pages/*` is one chunk each), so "add `React.lazy` to routes" is not a finding there either; what remains actionable is a heavy shared chunk imported by `_app.tsx` (icons, moment, a charting library), and a component that ships a library it only needs after an interaction. Do not count Node-only dependencies into the client budget.

**Sources**
- https://react.dev/reference/react/lazy [official] (React Team, 2024)
- https://vite.dev/blog — Vite 8 ships Rolldown-powered production builds [official] (Vite team, 2026)
- https://web.dev/articles/vitals [official] (Philip Walton, 2024)

---

### 2. Never put LCP-critical data behind a `useEffect` fetch

**Rule** – Render the largest above-the-fold element from HTML the server or the prerender step produced; do not wait for a mount effect round trip.

**Since** – all.

**Detection signals**
- `useEffect(() => { fetch(...).then(setData) }, [])` in the component that renders the hero/header/product image, where the same data is not also prefetched.
- Data libraries configured with SSR disabled: TanStack Query without `initialData`/`hydrate` on a route whose first paint is data-dependent, or `staleTime: 0` plus `refetchOnMount: 'always'`.
- On the rendered page: LCP element's `performance.getEntriesByType('largest-contentful-paint')` `loadTime` occurring after the first data request completes; a visible skeleton that is the LCP element.
- `React.lazy` on an *above-the-fold* component — the fallback becomes the LCP candidate and the real content arrives a chunk later.

**Severity hint** – High (this is the single most common cause of an LCP of 4 s+ on an otherwise fast app).

**Refactor direction** – Fetch in the route loader / Server Component, or prefetch and pass as `initialData`; keep `useEffect` fetching for non-LCP regions only.

```tsx
// before: waterfall — HTML → JS → effect → data → hero image
// after (React Router): loader resolves before render
export async function loader() { return { product: await getProduct() }; }
// after (Next.js Pages Router): resolve on the server, render from props
export async function getServerSideProps() {
  return { props: { product: await getProduct() } }; // pass into the component
}
```

**Counter-signals** – Data that only exists after authentication and cannot be cached (a personalised dashboard behind a login) legitimately arrives late; measure LCP on a representative logged-in page, not the marketing page. In a pure client-rendered SPA with no SSR at all, this rule is unfixable without adding a prerender step — report it as an architecture finding, not a component defect. Pages Router pages that already fetch in `getServerSideProps` and render the hero from props are compliant even though there is no `app/` tree; do not ask for a loader. The *fix* belongs to `react-architecture` rules 1 and 7; this rule only owns the measured LCP impact, so file one finding, not two.

**Sources**
- https://web.dev/articles/lcp — LCP definition and causes [official] (Philip Walton & Barry Pollard, 2024); thresholds from https://web.dev/articles/vitals [official] (2024)
- https://tanstack.com/query/latest/docs/framework/react/guides/ssr [official] (TkDodo / TanStack, 2026)

---

### 3. Give every image intrinsic dimensions, and make the LCP image eager and high-priority

**Rule** – Declare width/height (or `aspect-ratio`) on every `<img>`, use `srcset`+`sizes` for responsive art, and set `fetchpriority="high"` on exactly one above-the-fold image.

**Since** – `fetchpriority` all modern browsers; `next/image` `preload` prop from Next.js 16 only (it replaces `priority`, which is merely deprecated in 16 — on Next.js 13/14/15 `priority` is the correct prop, and `preload` does not exist, so a `priority` image is not a finding before 16).

**Detection signals**
- `<img` without both `width` and `height`, and without a CSS `aspect-ratio`, in a component that renders above the fold.
- `<img>` inside a flex/grid container with `height: auto` and no reserved box — CLS on load.
- On Next.js 16+ only: `next/image` with `priority` (deprecated there in favour of `preload`). Before 16 this is the correct prop — do not flag it. Independently: `layout="fill"` (Next 12) / `fill` without a positioned parent.
- Missing `sizes` on a `fill` image: Next.js then generates a `100vw` srcset and the browser downloads a desktop-sized image for a phone.
- Hero image loaded with `loading="lazy"` — a lazy LCP image is a guaranteed multi-second LCP.
- `public/` containing PNG/JPEG hero assets > 300 kB while `next/image` is not used at all.

**Severity hint** – High (CLS above 0.1 and LCP regressions are both scored; an unsized hero alone can push a page from "good" to "poor").

**Refactor direction**

```tsx
// before
<img src="/hero.jpg" className="w-full" />
// after (Next.js 16+)
<Image src="/hero.jpg" alt="" width={1600} height={900} sizes="100vw" preload fetchPriority="high" />
// after (Next.js 13–15) — `preload` does not exist yet
<Image src="/hero.jpg" alt="" width={1600} height={900} sizes="100vw" priority />
// plain HTML equivalent
<img src="/hero.jpg" width={1600} height={900} sizes="100vw"
     srcSet="/hero-800.jpg 800w, /hero-1600.jpg 1600w" fetchPriority="high" alt="" />
```

`alt=""` is correct for a decorative hero; a content image needs a real description (rule 12).

**Counter-signals** – Exactly one image per page should be high priority; setting it on several makes them compete and worsens LCP. Below-the-fold images should keep `loading="lazy"`. A `fill` image is legitimate inside an `aspect-ratio`-styled wrapper. In a Next.js 16 codebase, flag `priority` as *deprecated*, not as a correctness bug.

**Sources**
- https://nextjs.org/docs/app/api-reference/components/image — `preload`, `priority` deprecated in 16, `sizes` guidance [official] (Vercel, updated 2026-09-28)
- https://web.dev/articles/cls [official] (2024)
- https://web.dev/articles/preload-responsive-images — `<link rel="preload" as="image" fetchpriority="high">`, `imagesrcset`/`imagesizes` [official] (web.dev, 2024)

---

### 4. Self-host and preload the primary font, and cap the number of weights

**Rule** – Serve fonts from your own origin with `font-display: swap`, a preloaded primary file, and a metric-matched fallback so the swap does not shift text.

**Since** – `next/font` since Next.js 13; the rule applies to any stack via `@font-face` + `size-adjust`.

**Detection signals**
- `@import url('https://fonts.googleapis.com/...')` or `<link href="https://fonts.googleapis.com/...">` in `index.html` / `globals.css` — a third-party connection on the critical path, and a privacy issue for EU sites.
- Google Fonts URL with more than one family or ≥4 weights (`family=Inter:wght@100;200;300;400;500;600;700;800;900`).
- No `font-display` declaration, i.e. browsers block text for up to 3 s (FOIT).
- `next/font/local` used without `display: 'swap'`; `adjustFontFallback: false` on a custom font used for body copy.
- Measured: CLS attributable to the font swap in a Lighthouse trace, or `document.fonts` loaded after first paint with no `preload` link.

**Severity hint** – Medium (a font swap is usually 0.05–0.15 CLS plus a render-blocking request).

**Refactor direction**

```tsx
// before: <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap">
// after (Next.js)
import { Inter } from 'next/font/google';
const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-inter' });
```

Outside Next.js: download the woff2, `@font-face` it with `font-display: swap` and `size-adjust` matched to the fallback, and add `<link rel="preload" as="font" type="font/woff2" crossorigin>`.

**Counter-signals** – A single weight of a variable font is one request and is fine. A brand font loaded only for a logo/heading below the fold does not need preloading. `next/font` already self-hosts and injects `size-adjust`, so flagging a `next/font` usage for "external request" is a false positive.

**Sources**
- https://nextjs.org/docs/app/api-reference/components/font — automatic self-hosting, "no layout shift", `display` [official] (Vercel, updated 2026-09-24)
- https://web.dev/articles/cls [official] (2024)

---

### 5. Virtualise lists that exceed a few hundred rows

**Rule** – Render only the visible window of a long list, not one DOM node per record.

**Since** – all (library-level: `react-window`, `@tanstack/react-virtual`).

**Detection signals**
- `.map(` rendering server data of unbounded length directly into JSX: `items.map(i => <Row ... />)` where `items` comes from an API with no pagination or `limit`.
- No dependency on `react-window`, `react-virtualized`, `@tanstack/react-virtual`, or a table library's virtualisation feature.
- Measured: `document.querySelectorAll('*').length > 1500` on the route; a `Performance` trace showing a single `React` commit > 100 ms while scrolling; INP > 200 ms on scroll-triggered handlers.
- `useDeferredValue` or `useTransition` bolted onto a `.map()` of 5000 rows — a symptom of the same problem (rule 6).

**Severity hint** – Medium (long tasks block input, so it surfaces as an INP failure rather than a crash).

**Refactor direction** – Introduce a virtualiser and keep the row component's props stable.

```tsx
const virtualizer = useVirtualizer({
  count: rows.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 48,
});
{/* render only virtualizer.getVirtualItems() */}
```

**Counter-signals** – Lists bounded by design (a 20-item settings page, a static nav) gain nothing and lose Ctrl-F, print and screen-reader browse mode. Virtualisation breaks browser find-in-page and full-page accessibility tree traversal unless the virtualiser sets `aria-setsize`/`aria-posinset`; do not apply it to a page whose whole content a user may want to search. Pagination is a valid alternative.

**Sources**
- https://web.dev/articles/virtualize-long-lists-react-window [official] (Jason Miller & Houssein Djirdeh, 2019, still the canonical guidance)
- https://web.dev/articles/inp [official] (Jeremy Wagner, 2024)

---

### 6. Keep the main thread free during interaction: defer expensive renders with `useTransition` / `useDeferredValue`

**Rule** – When a keystroke or click triggers a genuinely expensive render, mark the expensive update as a transition instead of blocking input.

**Since** – all: a blocked main thread on keystroke is a defect on every React version (`useTransition`/`useDeferredValue` are the React 18+ fix; React 19 adds Actions and `useDeferredValue`'s `initialValue`). On 16.8–17, defer with a debounced/throttled handler or memoised derived value around the input, and virtualise or paginate the expensive output.

**Detection signals**
- A controlled input (`value={q} onChange={e => setQ(e.target.value)}`) whose change also re-renders a heavy sibling tree, with no `useDeferredValue`/`startTransition` anywhere.
- A filter/search over an unindexed array inside the render path: `items.filter(i => i.text.includes(query))` over thousands of items on every keystroke.
- `useDeferredValue` passed an object literal created during render — React then re-renders in the background on every pass.
- Measured: INP > 200 ms on typing; a `Performance` trace showing a long task (>50 ms) per keystroke; React DevTools Profiler commit durations > 16 ms on input.
- Synchronous work in an event handler: `JSON.parse` of a large payload, `new Intl.*` per call, deep clone, or sort of >1000 items, before `setState`.

**Severity hint** – High when the interaction is a core flow (typing in search, toggling a filter) — INP is a scored CWV.

**Refactor direction**

```tsx
// before: every keystroke blocks
const [q, setQ] = useState('');
// after
const [q, setQ] = useState('');
const deferred = useDeferredValue(q);
const results = useMemo(() => expensiveFilter(deferred), [deferred]);
<input value={q} onChange={e => setQ(e.target.value)} />
{isStale ? <Spinner /> : null}
```

Never put the input's own `value` behind the deferral — only the expensive output.

**Counter-signals** – With the React Compiler (v1.0, 2025-10-07) enabled, automatic memoisation removes many of these re-renders, so verify with a profile before flagging memo-shaped code. `useDeferredValue`/`useTransition` are the wrong tool for network latency (that is Suspense/loaders) and useless when the DOM itself is too large (rule 5). An expensive update triggered by an *intentional* submit (a form POST) is expected to be urgent.

**Sources**
- https://react.dev/reference/react/useTransition [official] (React Team, 2026)
- https://react.dev/reference/react/useDeferredValue — including the "objects created during rendering" caveat [official] (React Team, 2026)
- https://web.dev/articles/inp [official] (Jeremy Wagner, 2024)

---

### 7. Load third-party scripts off the critical path and review each one

**Rule** – Every third-party tag is deferred, scoped, and justified; none sits render-blocking in `<head>`.

**Since** – all (`next/script` since Next.js 11).

**Detection signals**
- Raw `<script src="https://...">` inside `index.html`, `_document`, or a component that renders above the fold, with no `async`/`defer`.
- `next/script` with `strategy="beforeInteractive"` for analytics, chat widgets, A/B testing, or tag managers.
- Chat/support widgets, heatmaps, session replay, or ad tags in `package.json` or inline snippets — each is hundreds of kB.
- No CSP and no `next/script` `nonce`; no consent gate in front of a tracker on an EU-facing site.
- Measured: a Lighthouse "Reduce the impact of third-party code" entry with main-thread time > 250 ms, or a long task at load attributable to a third-party origin.

**Severity hint** – Medium (High if the script is a session recorder capturing form fields — that is a data-protection incident).

**Refactor direction** – `strategy="afterInteractive"` (or `lazyOnload` for non-essential), load on interaction for chat widgets, and gate marketing tags behind consent. `next/script` moves the tag out of the render-blocking path and deduplicates it.

**Counter-signals** – A payment provider's SDK on the checkout route (Stripe) must load eagerly; deferring it breaks the core flow. A tag manager is a legitimate pattern — the finding is the render-blocking placement or the absence of consent, not the tag manager itself. Server-side tagging removes the client cost entirely.

**Sources**
- https://nextjs.org/docs/app/guides/scripts [official] (Vercel, 2026)
- https://web.dev/articles/vitals [official] (2024)

---

### 8. Keep the `'use client'` boundary as low as possible

**Rule** – Ship interactive leaves to the client, not whole page trees; a page that is `'use client'` at the top has thrown away server rendering and streaming.

**Since** – Next.js App Router 13+; React Server Components.

**Detection signals**
- `'use client'` at the top of `app/**/page.tsx` or `app/**/layout.tsx` rather than on the small interactive component.
- `'use client'` at the top of a shared UI module that exports 20 components, only one of which uses state.
- A Context provider file marked `'use client'` and imported by every layout — React 19.3 lets Server Components render `<Context>` directly, so the wrapper is often unnecessary.
- `typeof window !== 'undefined'` or a `mounted` flag guarding browser-only output — the pre-19.3 workaround for a hydration mismatch.
- Measured: client bundle contains markdown parsers, date libraries, or full icon sets that are only used in static markup.

**Severity hint** – Medium (direct hit on LCP and TBT; also loses streaming).

**Refactor direction**

```tsx
// before: app/page.tsx
'use client';
export default function Page() { /* static article + one toggle */ }
// after: keep Page a Server Component, isolate the toggle
// components/ThemeToggle.tsx
'use client';
export function ThemeToggle() { /* useState only here */ }
```

For genuinely browser-only UI (local time zone, `localStorage`), React 19.3 provides `use(browser())` from `react-dom`, which opts a component out of SSR and triggers Suspense instead of a `mounted` flag. Before 19.3 the same isolation is `dynamic(() => import('./Widget'), { ssr: false })` (Next.js) or a `lazy()` boundary rendered only after mount; on the Pages Router that dynamic import is the only tool, since there is no RSC split to make.

**Counter-signals** – App Router only. A Vite/React Router SPA has no RSC at all; the rule does not apply, and "add 'use client'" is never a valid finding there. A Next.js Pages Router app has no Server Components either: every page and component is a client component by construction, `'use client'` is meaningless, and the Pages Router equivalents are `next/dynamic` with `ssr: false` for browser-only widgets (`react-architecture` rule 12) and keeping `getServerSideProps` payloads out of `_app`'s bundle — report those, never a missing directive. A page whose entire content is interactive (a canvas editor, a spreadsheet) is legitimately one client component. `browser()` still costs a Suspense fallback — the content is absent from the initial HTML, so never use it for indexable copy.

**Sources**
- https://react.dev/blog/2026/09/09/react-19-3 — `browser()`, `<Context>` in Server Components [official] (React Team, 2026)
- https://react.dev/reference/rsc/use-client [official] (React Team, 2026)

---

### 9. Use semantic elements; never put `onClick` on a `div`

**Rule** – A click handler on a non-interactive element must become a `<button>` (action) or an `<a href>` (navigation).

**Since** – all.

**Detection signals**
- `<div onClick=` or `<span onClick=` anywhere; same for `onKeyDown` bolted on to imitate Enter/Space.
- `role="button"` on a `div` without `tabIndex={0}` and without Enter *and* Space handlers.
- A link rendered as `<a onClick={e => { e.preventDefault(); navigate(...) }}>` with no `href` — not focusable, not openable in a new tab, invisible to crawlers.
- `<button>` wrapping a route change (`onClick={() => navigate('/x')}`) where a link belongs: no middle-click, no "open in new tab", no status-bar preview.
- `<button>` inside a `<form>` without `type="button"` — the default type is `submit`, so a "Cancel"/"Delete" control submits the form and navigates to a nonexistent response.
- `eslint-plugin-jsx-a11y` violations: `click-events-have-key-events`, `no-static-element-interactions`, `anchor-is-valid`.

**Severity hint** – High (a keyboard or screen-reader user cannot complete the flow at all).

**Refactor direction**

```tsx
// before
<div className="btn" onClick={save}>Save</div>
// after
<button type="button" className="btn" onClick={save}>Save</button>
// navigation
<Link to="/orders">Orders</Link>
```

Style the element rather than replacing it: `button { all: unset }` or utility classes keep the design while restoring semantics. Give every non-submitting button `type="button"` — the HTML default is `submit`. Remove the `role`/`tabIndex` scaffolding once the real element is in place.

**Counter-signals** – A wrapper `div` that *contains* the interactive element is fine. `onClick` on a container for event delegation (closing a menu on outside click) is fine when the container is not presented as a control. A `<div role="presentation">` that swallows clicks is fine. Some canvas/graph surfaces genuinely need pointer handling — they then need a keyboard-accessible equivalent, not a `div onClick`.

**Sources**
- https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/ [official] (W3C WAI, 2024)
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/button [official] (MDN, 2026)

---

### 10. Every form control has a programmatic label, and errors are tied to the field

**Rule** – Each input has a `<label for>` or `aria-label`, and each validation error is associated via `aria-describedby` and `aria-invalid`.

**Since** – all.

**Detection signals**
- `<input`, `<select`, `<textarea>` with a sibling text node or a `placeholder` used as the only label.
- `placeholder="Email"` with no `aria-label` and no `htmlFor` pairing — the label vanishes on first keystroke.
- Error text rendered in a `<span className="error">` with no `id` and no `aria-describedby` on the input; `aria-invalid="true"` absent when an error is shown.
- Required fields marked only with a red asterisk in a `<span aria-hidden>` or with CSS `::after { content: '*' }`.
- A `<label>` wrapping a `div` that contains the input but no `htmlFor` where the input is inside a custom component that drops the id.
- `eslint-plugin-jsx-a11y` rules `label-has-associated-control`, `no-autofocus` (autofocus steals focus on load).

**Severity hint** – High (unlabelled fields make a form unusable with a screen reader and are a WCAG 2.2 A/AA failure).

**Refactor direction**

```tsx
// before
<input placeholder="Email" className={err ? 'error' : ''} />
// after
<label htmlFor="email">Email</label>
<input id="email" aria-invalid={!!err} aria-describedby={err ? 'email-err' : undefined} />
{err && <p id="email-err">{err}</p>}
```

Use `useId()` for generated ids so SSR and client agree.

**Counter-signals** – A search box with a visible magnifier icon and `aria-label="Search"` is fine. `placeholder` may accompany a label, never replace it. A visually hidden label (`.sr-only`) satisfies the rule. Do not demand `aria-required` when the native `required` attribute is present — the native attribute is better.

**Sources**
- https://www.w3.org/WAI/tutorials/forms/labels/ [official] (W3C WAI, 2023)
- https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ — 3.3.7 redundant entry, 3.3.8 accessible authentication [official] (W3C, 2023)

---

### 11. Manage focus and announce the page on client-side route change

**Rule** – After an SPA navigation, move focus to the new content (or a heading) and update the document title, so keyboard and screen-reader users know the page changed.

**Since** – all SPAs (React Router, Next.js client transitions, TanStack Router). Native browser navigation does this for free; React removes it.

**Detection signals**
- No `useEffect` on `location.pathname` / `useLocation()` that sets focus, and no `<FocusOnNavigate>`-style component, in a router-based app.
- No route-level `title` update: a single static `<title>` in `index.html` and no `document.title =` / `<title>` in route components.
- A skip-link component absent, or present but pointing to an id that does not exist.
- After navigation, `document.activeElement === document.body` (verifiable in DevTools) — focus fell back to the top of the DOM silently.
- Router without an announcer: no `aria-live` region bound to route changes (Next.js App Router ships a route announcer; React Router does not).

**Severity hint** – High (a screen-reader user gets no feedback that navigation happened; they re-read the old page).

**Refactor direction**

```tsx
function FocusOnNavigate() {
  const { pathname } = useLocation();
  useEffect(() => {
    const h1 = document.querySelector('h1');
    (h1 ?? document.body).focus({ preventScroll: true });
  }, [pathname]);
  return null;
}
// h1 needs tabIndex={-1}
```

**Counter-signals** – Next.js App Router already announces route changes and manages scroll; flagging it there is a false positive — check the router before reporting. A modal route change (a dialog opening over the same page) should *not* move focus to the page body. In-page hash anchors keep native behaviour.

**Sources**
- https://nextjs.org/docs/architecture/accessibility — Next.js route announcer: `document.title`, then `<h1>`, then pathname [official] (Vercel, 2024)
- https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/ — tab sequence and focus management [official] (W3C WAI, 2024)

---

### 12. Build modals on `<dialog>` and `inert`, not on a hand-rolled overlay

**Rule** – Use the native `<dialog>` element with `showModal()`, which gives focus trapping, Escape handling, backdrop, and background inertness for free.

**Since** – `<dialog>` and `inert` are Baseline; the rule applies to every React version.

**Detection signals**
- A modal component built from `position: fixed` + `z-index` + a custom `keydown` listener checking `e.key === 'Escape'`.
- A hand-written focus trap (`if (e.key === 'Tab') { ...first/last... }`) — the signal that the native element was not used.
- Background content not made `inert` while the modal is open: `document.body` children keep `tabIndex`/focusability, so Tab escapes the dialog.
- `aria-modal="true"` on a `div` without `role="dialog"`, or `role="dialog"` without `aria-labelledby` pointing at the heading.
- No focus restoration: the triggering button is not re-focused on close (`previouslyFocused.focus()` absent).
- `createPortal(..., document.body)` used *instead of* `showModal()` to escape stacking contexts.

**Severity hint** – High (focus escaping a modal is a broken core flow; WCAG 2.4.3 / 2.1.2 failures).

**Refactor direction**

```tsx
// before: div overlay + manual trap + manual Escape
// after
const ref = useRef<HTMLDialogElement>(null);
useEffect(() => { ref.current?.showModal(); return () => ref.current?.close(); }, []);
<dialog ref={ref} aria-labelledby="t"><h2 id="t">Delete order?</h2>…</dialog>
```

`showModal()` makes everything outside inert, so no manual trap is needed; `<dialog>` also restores focus to the invoker on close.

**Counter-signals** – A non-modal popover (menu, tooltip, toasts) should use the Popover API (`popover` attribute) rather than `<dialog>`; popovers created with that API are always non-modal by definition. A `<dialog>` is still required for anything that must block the rest of the page. Styling `<dialog>::backdrop` is normal, not a smell. React portals remain correct for a non-modal layer that must escape `overflow: hidden`.

**Sources**
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/inert — modal dialogs from `showModal()` escape inertness [official] (MDN, 2026)
- https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ — focus containment, Escape, return focus [official] (W3C WAI, 2024)
- https://developer.mozilla.org/en-US/docs/Web/API/Popover_API — popovers are always non-modal [official] (MDN, 2026)

---

### 13. Do not add ARIA you do not need — no ARIA is better than bad ARIA

**Rule** – Use the native element's semantics first; add `role`, `aria-*` only to fill a gap the platform leaves.

**Since** – all.

**Detection signals**
- `<button role="button">`, `<nav role="navigation">`, `<input role="textbox">` — redundant roles.
- `aria-label` on a `<div>` with no role (ignored by many ATs), or `aria-label` that duplicates visible text and breaks voice control ("click Send" no longer matches).
- `aria-hidden="true"` on an element that contains a focusable child (focusable-but-hidden is an automatic accessibility violation).
- `role="menu"`/`role="menuitem"` on a navigation list — implies application-menu keyboard semantics (arrow keys, typeahead) that the component does not implement.
- `aria-expanded` without a corresponding visible state change, or `aria-checked` on a native checkbox.
- `aria-describedby` pointing at a non-existent id; `id` duplicated in the document (the classic `map()` without `key`-safe ids).
- `eslint-plugin-jsx-a11y` `no-redundant-roles`, `aria-props`, `aria-role`, `role-has-required-aria-props`.

**Severity hint** – Medium (High when `aria-hidden` hides focusable content or `role="menu"` breaks keyboard use).

**Refactor direction** – Delete the redundant attribute. When a custom widget needs a role, copy the WAI-ARIA Authoring Practices keyboard contract for that exact pattern, and test with a screen reader.

**Counter-signals** – Some ARIA is genuinely required: `aria-live` on a status region, `aria-invalid`/`aria-describedby` on a form error, `aria-expanded` on a disclosure, `aria-setsize`/`aria-posinset` in a virtualised list. WCAG 2.2 removed 4.1.1 "Parsing", so a duplicate `id` is no longer a WCAG failure *per se* — but it still breaks every `aria-*` reference that targets it, so report it on those grounds, not as a 4.1.1 violation.

**Sources**
- https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/ [official] (W3C WAI, 2024)
- https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ — 4.1.1 Parsing obsolete in WCAG 2.2 [official] (W3C, 2023)

---

### 14. Honour `prefers-reduced-motion` for every animation you ship

**Rule** – Wrap non-essential motion (parallax, large scale/pan, auto-playing carousels) in a `prefers-reduced-motion: reduce` branch.

**Since** – all browsers supporting the media feature.

**Detection signals**
- `animation:` / `transition:` / `@keyframes` in CSS with no `@media (prefers-reduced-motion: reduce)` block anywhere in the stylesheet.
- Motion libraries in `package.json` (`framer-motion`, `motion`, `react-spring`, `gsap`) with no `useReducedMotion()` call and no `MotionConfig reducedMotion="user"`.
- Carousel/auto-advancing hero with a `setInterval` and no pause control (also a WCAG 2.2.2 failure independent of motion).
- `<ViewTransition>` / `view-transition-name` / `document.startViewTransition` with no reduced-motion guard.
- Transform-based animation on large elements: `scale()` or `translateY` over a full-viewport surface.

**Severity hint** – Medium (High for a full-screen parallax or auto-playing video — vestibular triggers can cause nausea).

**Refactor direction**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
```

For a library, use its own hook so the animation never starts: `const reduce = useReducedMotion()`.

**Counter-signals** – A hover colour transition, a focus ring, and a spinner are not vestibular triggers; stripping them harms usability feedback. A `0.01ms` global reset is a blunt instrument that also kills meaningful state-change cues — prefer scoping it. View Transitions are exempt when they only cross-fade opacity.

**Sources**
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion [official] (MDN, 2026)
- https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API [official] (MDN, 2026)

---

### 15. Meet 4.5:1 text contrast and never encode meaning in colour alone

**Rule** – Body text reaches 4.5:1 against its actual background (3:1 for ≥24 px or ≥18.66 px bold), and every status carries text or an icon in addition to colour.

**Since** – WCAG 2.1 AA; unchanged in 2.2.

**Detection signals**
- Hard-coded low-contrast pairs in Tailwind/CSS: `text-gray-400` on `bg-white`, `text-white/70` over an image, `opacity-50` on text, `text-blue-400` on `bg-gray-100`.
- Placeholder styling `::placeholder { color: #aaa }` — placeholders are text and need contrast too.
- Status conveyed only by colour: `<span className="text-red-500">Failed</span>` with no word/icon; a chart with a colour-only legend; a form field with a red border and no message.
- `disabled` states styled below 3:1 — disabled controls are exempt, but "disabled-looking enabled" controls are not.
- Focus indicator removed: `outline: none` / `focus:outline-none` with no `focus-visible:` replacement (a 2.4.7 / 2.4.11 failure).
- Measured: axe-core `color-contrast` violations; Lighthouse accessibility score deductions.

**Severity hint** – High (a WCAG AA failure, and now a legal exposure under the EAA — see rule 17).

**Refactor direction**

```tsx
// before
<span className="text-red-500">{status}</span>
// after
<span className="text-red-700"><ErrorIcon aria-hidden /> Failed: {reason}</span>
```

Swap the token for one that passes (`text-gray-600` on white is 7:1), keep `focus-visible:ring-2` alongside any `outline-none`.

**Counter-signals** – Large text (≥24 px, or ≥18.66 px bold) legitimately uses 3:1. Logos and incidental decoration are exempt. Text over a user-supplied image needs a scrim, not a fixed token — report the missing scrim, not the token. Automated tools misreport text over gradients and images; confirm by pixel sampling before flagging.

**Sources**
- https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html [official] (W3C, 2023)
- https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html [official] (W3C, 2023)

---

### 16. Announce asynchronous updates through a live region

**Rule** – Results that arrive without a navigation or focus change (search results, save confirmations, validation summaries, cart updates) must be announced from an `aria-live`/`role="status"` region that exists in the DOM before the update.

**Since** – all; `ariaNotify()` is the emerging replacement in Chromium.

**Detection signals**
- Toast/snackbar components rendered on demand by mounting a new node — the region did not exist when the update happened, so nothing is announced.
- No `role="status"`, `role="alert"`, or `aria-live` anywhere in `src/`, in an app with async mutations.
- A "no results" / "loading" / "3 items found" counter that changes silently after a fetch.
- `aria-live="assertive"` used for routine success messages (should be `polite`; assertive interrupts).
- Optimistic UI where the failure is only signalled visually (a red border reappearing).

**Severity hint** – Medium (High when the async result *is* the task, e.g. a search page).

**Refactor direction**

```tsx
// the region is always mounted; only its text changes
<p role="status" className="sr-only">{message}</p>
```

Keep the empty region in the tree at mount, then set its text content in the same commit as the data. Prefer `role="status"` (= `aria-live="polite"` + `aria-atomic="true"`) over hand-set attributes.

**Counter-signals** – If focus moves to the result (a dialog opening, a route change), the announcement is redundant and can double-speak. `role="alert"` is correct for a genuine error needing immediate attention, but APG requires that it not move keyboard focus and not disappear automatically — a toast that vanishes in 4 s fails WCAG 2.2.3 regardless of how it is announced. Do not put a live region around text that updates on every keystroke — it will read the whole thing continuously. Next.js App Router already ships a route announcer, so a route-change live region there is duplicate.

**Sources**
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live [official] (MDN, 2026)
- https://www.w3.org/WAI/ARIA/apg/patterns/alert/ [official] (W3C WAI, 2024)

---

### 17. Treat WCAG 2.2 AA as a release gate — it is now a legal requirement in the EU

**Rule** – Accessibility is a compliance criterion, not a nice-to-have: verify the WCAG 2.2 additions, not just 2.1.

**Since** – WCAG 2.2 became a W3C Recommendation on 2023-10-05; the European Accessibility Act applies to services provided to consumers **from 28 June 2025**.

**Detection signals**
- No automated a11y check in CI: no `jest-axe`/`vitest-axe` in tests, no `@axe-core/playwright`, no Lighthouse CI accessibility assertion, no `eslint-plugin-jsx-a11y` in `eslint.config.*`.
- WCAG 2.2-specific failures, each with a distinct signal:
  - **2.5.8 Target Size (Minimum), 24×24 px** — icon buttons with `h-4 w-4`, `p-0`, or negative margins shrinking the hit area; adjacent inline links in a paragraph.
  - **2.4.11 Focus Not Obscured** — a sticky header/footer that covers the focused element; `scroll-margin-top` absent while `position: sticky` is used.
  - **2.5.7 Dragging Movements** — a slider/reorder implemented only with pointer drags (no arrow-key or button alternative).
  - **3.2.6 Consistent Help** — a help/contact link that moves between routes.
  - **3.3.8 Accessible Authentication** — a login that forbids paste, or a CAPTCHA with no alternative.
- No accessibility statement page on an EU consumer service (EAA Art. 13 information obligation).
- A `<video>`/carousel with no pause control (2.2.2), critical when the EAA scope applies.

**Severity hint** – High (legal exposure with a named enforcement date, plus a broken core flow).

**Refactor direction** – Add `eslint-plugin-jsx-a11y` and an axe assertion to CI, then fix the 2.2 criteria above in the order 2.5.8 → 2.4.11 → 3.3.8, since those bite real flows. Publish an accessibility statement.

**Counter-signals** – The EAA has a microenterprise exemption (fewer than 10 staff and ≤ €2 m turnover) and excludes some service categories; do not assert non-compliance without knowing the entity and the service. B2B-only internal tools are out of EAA scope, though the WCAG criteria still apply as quality. 2.5.8 has an exception for inline links in a sentence and for targets with an equivalent control elsewhere on the page.

**Sources**
- https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32019L0882 — Art. 2 and 32(2): services provided to consumers after 28 June 2025 [official] (EU, 2019)
- https://commission.europa.eu/strategy-and-policy/policies/justice-and-fundamental-rights/disability/european-accessibility-act-eaa_en — transposition and monitoring [official] (European Commission, 2026)
- https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ — the nine new success criteria [official] (W3C, 2023)

---

### 18. Sanitise every `dangerouslySetInnerHTML`

**Rule** – Any HTML string from a CMS, a user, or an API goes through a sanitiser (DOMPurify) before `dangerouslySetInnerHTML`; otherwise render it as text.

**Since** – all.

**Detection signals**
- `dangerouslySetInnerHTML={{ __html: ... }}` where the value is not a compile-time constant — trace the variable to `props`, a fetch response, `location`, or a markdown renderer.
- Markdown rendering pipelines (`react-markdown` with `rehype-raw`, `marked` + `innerHTML`) with no `rehype-sanitize` / DOMPurify step.
- `dompurify` absent from `package.json` while `dangerouslySetInnerHTML` is present.
- `DOMPurify.sanitize` used with `ALLOW_UNKNOWN_PROTOCOLS: true`, or a custom `ALLOWED_ATTR` including `on*`/`style`, or `ADD_TAGS: ['script']`.
- `element.innerHTML =` / `insertAdjacentHTML` in a non-React escape hatch (a chart tooltip, a map popup, a third-party callback).
- `eval(`, `new Function(`, `setTimeout("string")` in client code.

**Severity hint** – High (stored XSS → account takeover, and session/token theft).

**Refactor direction**

```tsx
// before
<div dangerouslySetInnerHTML={{ __html: post.body }} />
// after
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(post.body) }} />
```

If the content is plain text, drop `dangerouslySetInnerHTML` entirely — React escapes it. Sanitise on the server for stored content so the client never handles a raw payload.

**Counter-signals** – A constant, developer-authored string (`__html: '<br/>'`) has no injection path. `dangerouslySetInnerHTML` with a `TrustedHTML` object (React 19.3 passes it through without coercion) is the intended integration point with a Trusted Types policy — do not flag it. Sanitising server-side once, in a shared renderer, is not a defect.

**Sources**
- https://react.dev/reference/react-dom/components/common — "should be used with extreme caution… you risk introducing an XSS vulnerability"; accepts `TrustedHTML` [official] (React Team, 2026)
- https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html — "React's `dangerouslySetInnerHTML` without sanitizing the HTML" [official] (OWASP, 2026)

---

### 19. Allow-list URL schemes and redirect targets — never interpolate user input into `href`/`src`/`window.location`

**Rule** – A URL built from user or API input is validated against `https:`/`http:` (plus `mailto:`/`tel:` where relevant) before it reaches an `href`, `src`, or a navigation call.

**Since** – React 19 blocks `javascript:` URLs in `href`/`src` as a defence in depth, but application-level validation is still required (OWASP).

**Detection signals**
- `href={user.website}`, `href={data.url}`, `src={avatar}` where the value is not validated at a trust boundary.
- Template-built links: `` href={`/redirect?to=${next}`} `` with no allow-list of hosts or paths.
- Post-login redirect: `navigate(searchParams.get('next'))` / `router.push(next)` — a classic open redirect (`?next=https://evil.example`).
- `window.location.href = data.url`, `window.open(url)`, or `location.assign()` with an unvalidated value.
- A validation regex that only checks `startsWith('http')` — `http://` and `https://evil.com` both pass, and `javascript:` with a leading space bypasses naive checks.
- `rel="nofollow"` absent on user-supplied outbound links (SEO/abuse, low severity).

**Severity hint** – High (open redirect is a phishing primitive used against your own domain; `javascript:` is XSS in older React or any escape hatch).

**Refactor direction**

```ts
const SAFE = /^(https?:|mailto:|tel:)/i;
export const safeHref = (u: string) =>
  SAFE.test(u.trim()) && !/^\s*(javascript|data|vbscript):/i.test(u) ? u.trim() : '#';

// redirect: resolve and compare origins
const target = new URL(next ?? '/', location.origin);
return target.origin === location.origin ? target.pathname + target.search : '/';
```

Parse with `new URL()` and compare `origin` rather than pattern-matching the string.

**Counter-signals** – A hard-coded internal path needs no validation. `<a href={sanitised}>` with `rel` set by a trusted component is fine. On the server, an allow-list configured by an operator (a known SSRF-fetch list) is not the same rule. React 19's built-in `javascript:` blocking means the *XSS* severity is reduced on 19+, but the open-redirect half of the rule is unaffected.

**Sources**
- https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html — "Unvalidated URL values: React 19 blocks `javascript:` URLs in…" [official] (OWASP, 2026)
- https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html [official] (OWASP, 2026)

---

### 20. Do not store session tokens in `localStorage` or `sessionStorage`

**Rule** – Authenticate with `HttpOnly; Secure; SameSite` cookies; treat web storage as readable by any script on the origin, including a third-party tag.

**Since** – all.

**Detection signals**
- `localStorage.setItem('token', …)`, `sessionStorage.setItem('access_token', …)`, or `localStorage.getItem('jwt')`.
- An `Authorization: Bearer ${localStorage.getItem('token')}` interceptor in an axios/fetch wrapper.
- A token in a component's state persisted via `zustand/middleware` `persist` with default storage (localStorage).
- `document.cookie = \`token=${token}\`` without `HttpOnly` (impossible to set from JS anyway) or without `Secure`/`SameSite`.
- Tokens or passwords in a URL query string (`?token=…`) — leaked by Referer, history, and logs.
- Measured/structural: any XSS in the app (rule 18) then escalates to persistent account takeover.

**Severity hint** – High (turns any XSS or malicious third-party script into session theft).

**Refactor direction** – Move the token to an `HttpOnly` cookie set by the server (`SameSite=Lax` for top-level navigation, `Strict` where possible), keep only non-sensitive UI state in storage, and add CSRF protection (double-submit token or `SameSite` plus origin check) as the trade-off for cookie auth.

**Counter-signals** – A non-sensitive UI preference (theme, collapsed sidebar, locale draft) in `localStorage` is correct. With a cookie-based session, a short-lived in-memory access token (React state / a module variable, lost on reload, refreshed by an HttpOnly refresh cookie) is a legitimate pattern — do not flag `useState<Token>` as storage. Some third-party SDKs write their own tokens; report the finding at the SDK integration, not the component.

**Sources**
- https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html — local storage and session hijacking [official] (OWASP, 2026)
- https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html [official] (OWASP, 2026)

---

### 21. Ship a Content-Security-Policy, and add Trusted Types on React 19.3+

**Rule** – Serve a restrictive CSP (`script-src 'self'` + nonces/hashes, no `unsafe-inline`, no `unsafe-eval`) and, on React 19.3 or later, add `require-trusted-types-for 'script'`.

**Since** – CSP all; Trusted Types enforcement works with React 19.3+, which stopped coercing values to strings before DOM sink calls.

**Detection signals**
- No CSP header at all: absent in `next.config.*` `headers()`, in `vercel.json`, in the CDN/nginx config, and no `<meta http-equiv="Content-Security-Policy">`.
- `script-src 'unsafe-inline'` or `'unsafe-eval'` — negates most of the XSS protection.
- `default-src *` / `script-src *`.
- No `report-uri`/`report-to` and no `Content-Security-Policy-Report-Only` staging step.
- `require-trusted-types-for 'script'` set while React is < 19.3 — React then string-coerces `TrustedHTML` back and the sink throws.
- Inline scripts (`<script>`) with no nonce and no hash.
- Missing the cheap headers alongside it: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`.

**Severity hint** – High (CSP is the mitigating control that keeps an XSS from becoming script execution).

**Refactor direction**

```js
// next.config.ts
async headers() {
  return [{ source: '/(.*)', headers: [
    { key: 'Content-Security-Policy', value:
      "default-src 'self'; script-src 'self' 'nonce-<generated>'; object-src 'none'; base-uri 'self'; require-trusted-types-for 'script'" },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
  ]}];
}
```

Roll out in Report-Only first, then enforce. Tighten `script-src` to nonces; avoid `strict-dynamic` unless the bundler's chunk loading requires it.

**Counter-signals** – Trusted Types is Chromium-only (not Baseline) — it is defence in depth, not a substitute for rule 18, and Firefox/Safari ignore it, so absence is not a finding on its own. A CSP with `'unsafe-inline'` in a static-hosted environment that cannot inject nonces is a known trade-off, still worth flagging as Medium. A `<meta>` CSP cannot use `frame-ancestors` or `report-to`; that needs a header.

**Sources**
- https://react.dev/blog/2026/09/09/react-19-3 — "React now passes these values through without coercion" [official] (React Team, 2026)
- https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API [official] (MDN, 2026)
- https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html — Trusted Types recommended, Chromium-only today [official] (OWASP, 2026)

---

### 22. Never put a secret in client-reachable configuration, and keep the framework patched

**Rule** – Anything reachable from the browser bundle is public; and an unpatched framework is a vulnerability, not a version preference.

**Since** – `NEXT_PUBLIC_*` and `VITE_*` since their respective frameworks; the advisory floor is Next.js ≥ 15.2.3 / 14.2.25 (CVE-2025-29927) and ≥ 16.4.1 / 15.5.28 (Oct 2026 advisories).

**Detection signals**
- `NEXT_PUBLIC_`/`VITE_`/`REACT_APP_` prefixed variables holding `*_SECRET`, `*_KEY`, `*_TOKEN`, `DATABASE_URL`, `STRIPE_SECRET`, a service-role key, or an SMTP password, in `.env*` or `next.config.*` `env`.
- `next.config.*` `env: { … }` — inlines values into the client bundle at build time.
- A server secret passed as a prop from a Server Component into a `'use client'` component, or into `dangerouslySetInnerHTML`, or into a `<meta>`/`window.__ENV__` blob.
- `.env` committed; service keys readable in `dist/assets/*.js` (`grep -r "sk_live\|service_role\|AKIA" dist/ .next/static/`).
- Vulnerable Next.js version in `package.json` / lockfile: `< 15.2.3` or `< 14.2.25` (CVE-2025-29927, critical, middleware authorization bypass via the `x-middleware-subrequest` header); `< 16.4.1` / `< 15.5.28` (2026 critical RCEs: `use cache` typed arrays GHSA-673q-mjm6-r5xr, image-optimisation SVG CVE-2026-96889).
- Authorization enforced *only* in `middleware.ts` — the CVE-2025-29927 lesson: middleware is not a security boundary.

**Severity hint** – High (leaked secret = direct financial/account compromise; unpatched critical = unauthenticated RCE or authz bypass).

**Refactor direction** – Move the value to a server-only module (`import 'server-only'` in Next.js), call the third-party API from a route handler, and expose only a scoped, short-lived client credential. Upgrade Next.js to the patched line, and duplicate the authorization check inside the data access layer rather than relying on middleware.

**Counter-signals** – Public keys are public by design: Stripe's publishable key, a Firebase web config, a Mapbox public token, a Sentry DSN, a PostHog project key. Do not flag those. `NEXT_PUBLIC_` on a non-secret is idiomatic. An LTS line that is genuinely patched (15.5.28) is not vulnerable just because it is not 16.x.

**Sources**
- https://vercel.com/blog/postmortem-on-next-js-middleware-bypass — CVE-2025-29927, patched 15.2.3 / 14.2.25 [official] (Vercel, 2025)
- https://nextjs.org/blog/nextjs-security-update-october-14-2026 — 16.4.1 / 15.5.28, GHSA-673q-mjm6-r5xr, CVE-2026-96889 [official] (Vercel, 2026)
- https://nextjs.org/docs/app/guides/environment-variables [official] (Vercel, 2026)

---

### 23. Route every user-facing string through a message catalogue, and build `Intl` formatters once per locale

**Rule** – No user-visible literal in JSX or in an attribute; plurals and interpolation go through ICU messages; every number, date and currency is formatted by an `Intl` formatter created once and given an explicit locale.

**Since** – all (library-level: `react-i18next`, `next-intl`, `react-intl`/FormatJS, Lingui).

**Detection signals**
- Literal text nodes in JSX: `>Save changes<`, `{"Delete"}`, `placeholder="Search…"`, `aria-label="Close"` — even in a single-language app, these are the strings that never get extracted.
- String concatenation for grammar: `` `${count} items` ``, `t('hello') + ' ' + name`, `count === 1 ? 'item' : 'items'`.
- Missing `Intl.PluralRules` / ICU `{count, plural, …}` for any count-bearing message, including zero and fractional cases. English needs 2 categories, Arabic 6 — a `=== 1` check is wrong in most locales.
- `new Intl.NumberFormat(...)` or `new Intl.DateTimeFormat(...)` inside a component body or directly in JSX (`{new Intl.NumberFormat('de-DE').format(n)}`) — reconstructed on every render, and among the costlier platform constructors.
- `toLocaleString()` / `toLocaleDateString()` with no locale argument (browser default, not UI locale), or `Intl` with a hard-coded `'en-US'` while the app supports other locales.
- Hand-rolled number/date formatting: `toFixed(2)`, `'$' + price`, `'€' + n`, manual thousands separators, two decimals forced on JPY, `'3 days ago'` built from string maths instead of `Intl.RelativeTimeFormat`.
- No i18n library in `package.json` on a product with more than one locale, or an `en.json` whose keys are the English text (`t('Save changes')`).
- `<html lang="en">` hard-coded while a locale switcher exists.

**Severity hint** – Medium (High for an RTL locale or plural-bearing UI, where the output is simply wrong; the per-render formatter is also a measurable cost in long lists).

**Refactor direction**

```tsx
// before
<p>{count} item{count === 1 ? '' : 's'}</p>
<span>{new Intl.NumberFormat('de-DE').format(price)}</span>
// after (ICU message + module-scope formatter)
const priceFmt = new Intl.NumberFormat(locale, { style: 'currency', currency });
<p>{t('cart.items', { count })}</p>
<span>{priceFmt.format(price)}</span>
// en: "{count, plural, =0 {No items} one {# item} other {# items}}"
```

Extract literals with the library's extractor, keep keys stable and semantic (`cart.items`, not the English text), and pass an explicit `locale`. For a locale that changes at runtime, `useMemo(() => new Intl.NumberFormat(locale), [locale])`.

**Counter-signals** – A deliberately single-locale internal tool may keep literals; report it as Low and once per file, not per string. Developer-facing strings (console logs, error codes) are not user-facing. Using the English string as the i18n key is a legitimate translator-ergonomics choice. Test fixtures and Storybook stories are exempt. A formatter created once per module is already correct. `toLocaleString()` with no argument is intentional where the *user's* device locale is the point (a log viewer with no UI locale) — check intent. Server-side formatting for a client in another zone needs an explicit `timeZone`.

**Sources**
- https://formatjs.github.io/docs/core-concepts/icu-syntax/ — `{plural}`, `{select}`, `other` required [official] (FormatJS, 2025)
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/PluralRules — "Chinese has only one form, and Arabic has six" [official] (MDN, 2026)
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat [official] (MDN, 2026)
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat [official] (MDN, 2026)

---

### 24. Set `lang` and `dir` on `<html>`, and use logical CSS properties

**Rule** – The document declares its language, direction follows the locale via the `dir` attribute (never CSS), and spacing/alignment uses logical properties.

**Since** – all.

**Detection signals**
- `<html>` without `lang`, or a hard-coded `lang="en"` independent of the active locale.
- RTL support attempted with CSS only: `body { direction: rtl }`, or `direction` toggled on a wrapper div.
- Physical CSS properties in RTL-relevant code: `margin-left`, `padding-right`, `left: 0`, `text-align: left`, `border-left`, `float: right`. Tailwind's `ml-*`/`pr-*`/`left-*` are physical; `ms-*`/`pe-*`/`start-*` are logical — a Tailwind codebase with `ml-`/`mr-` and an `rtl:` variant is a strong signal.
- `dir="rtl"` set on `<html>` but no `dir="auto"` on user-generated inputs (a Latin username in an Arabic page renders in the wrong order).
- Bidirectional inline values (a phone number, a Latin brand name inside Arabic text) not wrapped in `<bdi>`.
- Hard-coded directional icons (a "next" chevron pointing right) without `rtl:rotate-180` or a logical equivalent.

**Severity hint** – Medium (High for an RTL locale — the layout mirrors incorrectly and screen readers use the wrong pronunciation rules).

**Refactor direction**

```tsx
// app/layout.tsx
<html lang={locale} dir={dir}>
```

then replace `ml-4` → `ms-4`, `pr-2` → `pe-2`, `text-left` → `text-start`, and use `inset-inline-start` in custom CSS.

**Counter-signals** – A single-locale LTR app needs `lang` (it drives hyphenation, screen-reader voice, and translation prompts) but has no `dir` problem — report the missing `lang` as Low, the physical properties not at all. A `direction: rtl` in a print stylesheet or a deliberately LTR code block inside an RTL page is correct. Tailwind v4 (4.3) ships logical-property utilities, so `ps-`/`pe-` are available without a plugin.

**Sources**
- https://www.w3.org/International/questions/qa-html-dir — "add `dir="rtl"` to the `html` tag", "Never use CSS to apply the base direction", logical properties, `dir="auto"` [official] (W3C i18n, 2024)
- https://tailwindcss.com/blog — v4.3 adds more logical-property utilities [official] (Tailwind Labs, 2026)

---

### 25. Ship indexable HTML: prerender or server-render the content crawlers must see

**Rule** – A route whose content matters for search, sharing, or legal disclosure must exist in the initial HTML response, with its own title, description, canonical and social metadata.

**Since** – all; framework-specific (`next` SSR/SSG/Cache Components, `vite-plugin-ssr`/React Router framework mode).

**Detection signals**
- Root HTML is an empty shell: `<div id="root"></div>` with all copy injected client-side, and no prerender/SSR plugin in `vite.config.*`.
- `curl -s https://site/route | grep -c "<h1"` returns 0 while the rendered page shows an `<h1>` — the definitive test.
- One shared `<title>` for all routes (no `document.title` per route, no `metadata` export, no route `handle.title`).
- No `<link rel="canonical">`, no `<meta name="description">`, no OG/Twitter tags per route → link previews are blank.
- `next.config.*` with `output: 'export'` on a route that needs per-request data, or `dynamic = 'force-dynamic'` on a static marketing page (cost, not correctness).
- Metadata defined only in a `useEffect` (invisible to crawlers that do not execute JS, and racing the social scraper).
- No `sitemap.xml` / `robots.txt`; `noindex` accidentally inherited from a layout.
- In Next.js App Router, metadata is streamed and *deferred for bots* — a `generateMetadata` that awaits a slow API makes the bot wait for the full response.

**Severity hint** – Medium (High when the product's acquisition depends on organic search or the route is a legal/price disclosure that must be crawlable).

**Refactor direction** – Move to SSR/SSG for public routes (Next.js App Router, React Router framework mode, or a prerender step for a Vite SPA). Export a per-route `metadata` object with `title`, `description`, `alternates.canonical`, and `openGraph`. Keep client-only rendering for authenticated app screens behind a login.

```ts
export const metadata: Metadata = { title: 'Pricing', alternates: { canonical: '/pricing' } };
```

**Counter-signals** – An authenticated dashboard, an admin panel, and a checkout step have nothing to index; client-only rendering is correct there and the SPA is not a defect. Googlebot executes JavaScript, so a client-rendered SPA is not automatically invisible — but the initial HTML is what social scrapers, most other crawlers, and the first paint see. If the app is behind `noindex` by design, this rule does not apply at all.

**Sources**
- https://nextjs.org/docs/app/getting-started/metadata-and-og-images — `metadata` / `generateMetadata`, defaults, streaming and bot behaviour [official] (Vercel, updated 2026-08-25)
- https://web.dev/articles/vitals [official] (2024) — LCP and the initial HTML

---

## Tools

Commands and rule sets that produce the evidence for the checks above. Run them on a production build, never on a dev server.

| Command / tool | Detects |
|---|---|
| `npx lighthouse http://localhost:4173 --preset=desktop --only-categories=performance,accessibility,seo --view` | LCP/INP-proxy(TBT)/CLS, image and font opportunities, missing `lang`, contrast, crawlability. Use `--preset=desktop` and also a mobile run: CWV thresholds are p75 mobile. |
| `npx @lhci/cli autorun --collect.url=… --assert.assertions.categories:accessibility=0.95` | Fails CI on an accessibility or performance regression. |
| Chrome DevTools → Performance panel, "Web Vitals" lane | Real long tasks (>50 ms), the interaction that produced a bad INP, React commit durations. Enable React DevTools' "Highlight updates" to correlate. |
| Chrome DevTools → Lighthouse → "Treemap" / `npx source-map-explorer 'dist/assets/*.js'` | Which dependency owns the bytes in the initial chunk (rules 1, 7, 8). |
| `npx vite build --mode production` then read the chunk table; `npx next build` and read the route table | Per-route First Load JS; route marked `○`/`●`/`ƒ` shows static vs dynamic rendering (rule 25). |
| `npx vite-bundle-visualizer` / `@next/bundle-analyzer` (`ANALYZE=true npx next build`) | Barrel-file and whole-library bloat. |
| `npx size-limit` with a `size-limit` config | Hard budget on the entry chunk in CI (rule 1). |
| `curl -s https://site/route \| grep -E '<h1\|<title\|canonical'` | Server-rendered content and per-route metadata (rule 25). |
| `npx axe http://localhost:4173` or the axe DevTools extension | Colour contrast, missing labels, invalid ARIA, duplicate ids, focusable-but-`aria-hidden` (rules 9, 10, 13, 15). |
| `@axe-core/playwright` + `expect(await axe.analyze()).toHaveNoViolations()` in a Playwright test | The same, per route, in CI. |
| `jest-axe` / `vitest-axe` | Per-component a11y regressions. |
| `eslint-plugin-jsx-a11y` (6.10.2) — enable `recommended` | `click-events-have-key-events`, `no-static-element-interactions`, `label-has-associated-control`, `anchor-is-valid`, `no-redundant-roles`, `aria-props`, `role-has-required-aria-props`. |
| `eslint-plugin-react-hooks` (7.1.1) — `react-hooks/rules-of-hooks`, `exhaustive-deps`, and the React Compiler rules | Stale-closure bugs that silently disable an effect; compiler-incompatible code. |
| Manual keyboard pass: Tab through the flow with the mouse unplugged; Escape a modal; Tab past a modal | Focus trap, focus restoration, invisible focus, skip link (rules 11, 12, 15). |
| macOS VoiceOver (⌘F5) / NVDA (Windows) + a real form | Label association, live-region announcements, route-change announcement (rules 10, 11, 16). |
| `prefers-reduced-motion` toggle: macOS System Settings → Accessibility → Display → Reduce motion; DevTools → Rendering → "Emulate CSS prefers-reduced-motion" | Unconditional animations (rule 14). |
| DevTools → Rendering → "Emulate `prefers-color-scheme`", and a forced-colors check | Contrast assumptions that break in the other theme. |
| Contrast: Chrome DevTools colour picker (shows the ratio) or the WebAIM Contrast Checker | 4.5:1 / 3:1 against the real, composited background (rule 15). |
| `npx license-checker` is *not* it — for secrets use `grep -rE 'sk_live\|service_role\|AKIA\|-----BEGIN' dist/ .next/static/` | Secret leaking into the client bundle (rule 22). |
| `npx better-npm-audit audit` / `npm audit --omit=dev` | Vulnerable framework versions, including the Next.js advisories in rule 22. Renovate/Dependabot pinned to the LTS lines. |
| `curl -sI https://site/ \| grep -iE 'content-security-policy\|strict-transport\|x-content-type'` | Missing or weak CSP and companion headers (rule 21). |
| MDN HTTP Observatory: `npx observatory https://site/` | Grades CSP, HSTS, X-Frame-Options, Referrer-Policy (rule 21). |
| `webstatus.dev` / `npx baseline-browser-mapping` | Whether a platform feature you rely on (`inert`, `<dialog>`, Popover, View Transitions, Trusted Types) is Baseline or Chromium-only — the check behind every counter-signal above. |
| React DevTools Profiler ("Record", then interact) | Which commit blocked the interaction, and whether the React Compiler already memoised it (rule 6). |
