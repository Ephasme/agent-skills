# React architecture: server state, client state, frameworks

Scope: how a React web app decides *where* state lives and *when* data is fetched — server state vs client state, global stores, RSC/App Router boundaries, route loaders, forms, folder/import boundaries, env-var exposure, error boundaries — for Next.js (App Router and Pages Router), React Router v7/v8 framework mode, TanStack Router/Start and plain Vite SPAs. Router-specific advice says which router it applies to; a Pages Router rule never asks for a Server Component, and an App Router rule never asks for `getServerSideProps`. Not covered: rendering/style/a11y (other packs), generic god-objects/long-functions/dead-code/duplication (generic scanner).

## Contents

- [Version baseline](#version-baseline)
- [Rules](#rules)
- [Tools](#tools)

## Version baseline

| Package | Verified version | Source |
| --- | --- | --- |
| `react` / `react-dom` | 19.3.1 (docs cover 19.3) | [react.dev/versions](https://react.dev/versions) [official]; [npm](https://registry.npmjs.org/react/latest) [official] |
| React Compiler (`babel-plugin-react-compiler`) | 1.0.0 (1.0 shipped 2025-10-07) | [react.dev/versions changelog](https://react.dev/versions) [official]; [npm](https://registry.npmjs.org/babel-plugin-react-compiler/latest) [official] |
| `next` | 16.4.3 (16.4 released 2026-10-06) | [nextjs.org/blog/next-16-4](https://nextjs.org/blog/next-16-4) [official]; [npm](https://registry.npmjs.org/next/latest) [official] |
| `react-router` / `@react-router/dev` | 8.5.0 (v8.0.0 released 2026-06-17) | [reactrouter.com/changelog](https://reactrouter.com/changelog) [official]; [npm](https://registry.npmjs.org/react-router/latest) [official] |
| `@tanstack/react-query` | 5.104.5 | [TanStack Query docs](https://tanstack.com/query/latest/docs/framework/react/overview) [official]; [npm](https://registry.npmjs.org/@tanstack/react-query/latest) [official] |
| `@tanstack/react-router` | 1.170.46 | [npm](https://registry.npmjs.org/@tanstack/react-router/latest) [official] |
| `@tanstack/react-start` | 1.169.4; Start 1.0 stable 2026-10-13 | [TanStack blog: Start 1.0](https://tanstack.com/blog/tanstack-start-1-0) [official]; [npm](https://registry.npmjs.org/@tanstack/react-start/latest) [official] |
| `swr` | 2.5.1 | [npm](https://registry.npmjs.org/swr/latest) [official] |
| `vite` | 8.3.5 | [npm](https://registry.npmjs.org/vite/latest) [official]; baseline React Router v8 requires Vite 7+ |
| `typescript` | 7.0.2 | [npm](https://registry.npmjs.org/typescript/latest) [official]; used by `next build` since 16.3 (16.3 blog) |
| `eslint` | 10.13.0 | [npm](https://registry.npmjs.org/eslint/latest) [official] |
| `eslint-plugin-react-hooks` | 7.1.1 (ships compiler rules) | [plugin README](https://github.com/facebook/react/blob/main/packages/eslint-plugin-react-hooks/README.md) [official]; [npm](https://registry.npmjs.org/eslint-plugin-react-hooks/latest) [official] |
| `eslint-plugin-boundaries` | 7.3.0 | [README](https://github.com/javierbrea/eslint-plugin-boundaries) [official] |
| `zustand` | 5.0.16 | [npm](https://registry.npmjs.org/zustand/latest) [official] |
| `jotai` | 3.0.1 | [npm](https://registry.npmjs.org/jotai/latest) [official] |
| `@reduxjs/toolkit` | 2.13.0 | [npm](https://registry.npmjs.org/@reduxjs/toolkit/latest) [official] |
| `react-hook-form` | 7.91.0 | [npm](https://registry.npmjs.org/react-hook-form/latest) [official] |
| `zod` / `valibot` | 4.6.7 / 1.5.0 | [npm zod](https://registry.npmjs.org/zod/latest), [npm valibot](https://registry.npmjs.org/valibot/latest) [official] |

Framework baselines that change which rules apply: React Router v8 requires Node 22.22+, React 19.2.7+, Vite 7+, and is ESM-only ([changelog v8.0.0](https://reactrouter.com/changelog) [official]). Next.js 16 replaced `middleware.ts` with `proxy.ts`, made Turbopack the default bundler and shipped stable React Compiler support ([Next.js 16 blog](https://nextjs.org/blog/next-16) [official], 2025). Next.js 16.4 recommends Cache Components for every app and enables it by default in `create-next-app`; it becomes the default model in Next.js 17 ([16.4 blog](https://nextjs.org/blog/next-16-4) [official], 2026).

## Rules

### 1. Fetch server data through a data layer, never with `useEffect` + `useState`

**Rule** – Server data comes from a server-state library (TanStack Query, SWR, RTK Query), a route loader, or a Server Component — not from an effect that calls `fetch` and stores the result.
**Since** – all (the effect-fetch pattern has been discouraged since React 18-era docs; every current framework offers a loader or a cache).
**Detection signals** – `useEffect(` whose body contains `fetch(` or `axios` and a `set*` call; missing `AbortController`/`ignore` cleanup; no `@tanstack/react-query`, `swr` or `@reduxjs/toolkit/query` in `package.json` while components fetch; a `useState` whose only writer is an effect; the same endpoint fetched in two components with no dedupe; loading spinners rendered from `useState(true)`.
**Severity hint** – High (race conditions and duplicate requests; a waterfall on every mount that shows up in LCP/INP).
**Refactor direction** – Move the fetch to the nearest data boundary, then read it as data. In an SPA: a `queryOptions` factory + `useQuery`. In the App Router: `await` in a Server Component, or pass the promise down and unwrap it with `use()`.
```tsx
// before
const [user, setUser] = useState(null)
useEffect(() => { fetch(`/api/users/${id}`).then(r => r.json()).then(setUser) }, [id])

// after
const { data: user } = useQuery(userOptions(id))
```
**Counter-signals** – A genuine external subscription (websocket, `matchMedia`, `IntersectionObserver`) belongs in `useEffect`; React's own guidance is `useSyncExternalStore` for that. A one-shot value that never revalidates on the client should be a Server Component `await` (or, in the Next.js Pages Router, `getServerSideProps`/`getStaticProps`; before React 19 there is no `use()` on the client), not a library ([Next.js: client-side data fetching](https://nextjs.org/docs/app/guides/client-side-data-fetching) [official], 2026). A browser-only value read after mount for hydration safety is covered by `react-core` RC-04's counter-signals, not here. When the same effect fetch is the LCP element's data, the root cause is this rule: report it once here and cite `web-platform` rule 2 for the measured impact instead of filing a second finding. Rule does not apply to React Native offline caches.
**Sources** – [React: You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect) [official], React team, 2026 · [React: Synchronizing with Effects](https://react.dev/learn/synchronizing-with-effects) [official] · [TanStack Query: Overview](https://tanstack.com/query/latest/docs/framework/react/overview) [official] · [Next.js: Fetching Data](https://nextjs.org/docs/app/getting-started/fetching-data) [official], 2026.

### 2. Never copy server data into component state

**Rule** – Render server data straight from its source; do not mirror `query.data` or `props.data` into `useState` and sync it with an effect.
**Since** – all (TanStack Query v4/v5 era anti-pattern; documented as "derive state during render" in current React docs).
**Detection signals** – `useState(query.data)`; `useState(props.x)` followed by `useEffect(() => setX(props.x), [props.x])`; `useEffect(() => setForm(query.data), [query.data])`; a `reset`/`sync` effect that runs on every data refetch; state that is never written except from an effect.
**Severity hint** – Medium (stale UI after refetch/invalidation, double renders, a second source of truth that drifts).
**Refactor direction** – Delete the mirror; read the query result in render, and narrow it with `select` when only a slice is needed. For "reset on id change", use a `key` on the component instead of an effect.
```tsx
// before
const [items, setItems] = useState([])
useEffect(() => setItems(data ?? []), [data])

// after
const items = data ?? []            // or: useQuery({ ...opts, select: d => d.items })
```
**Counter-signals** – An editable draft (a form pre-filled once from server data, then owned by the user) is legitimate: initialise `defaultValues` once and key the form by entity id. Optimistic local overlays belong in the query cache (`setQueryData`), not in a parallel `useState`.
**Sources** – [TanStack Query: Does This Replace Client State?](https://tanstack.com/query/latest/docs/framework/react/guides/does-this-replace-client-state) [official] · [TkDodo: React Query as a State Manager](https://tkdodo.eu/blog/react-query-as-a-state-manager) [power-user], Dominik Dorfmeister, 2021.

### 3. Query keys are structured, serialisable, and defined once in an options factory; all inputs live in the key

**Rule** – Every query's identity is a hierarchical array key built by a single factory per resource, and every input (id, filters, pagination, sort) is part of that key — not a piece of state that an effect feeds back into a refetch.
**Since** – all. A single key factory per resource predates the helper; `queryOptions` itself exists only in TanStack Query 5+ (`prefer-query-options` in `@tanstack/eslint-plugin-query` 5). On Query 4 the same rule holds with a plain options object.
**Detection signals** – `queryKey: ['data']` or `queryKey: ['list', JSON.stringify(filters)]`; non-serialisable key members (class instances, `Map`, functions); the same resource keyed three different ways across files (`['user', id]` vs `['users', id]`); key arrays written as literals in more than one file while a factory exists, or no factory at all for a resource used in 2+ places; `queryFn` closing over component state instead of reading it from the key; `useEffect(() => { refetch() }, [filters])` or an `enabled: false` + manual `refetch()` dance; `new QueryClient()` constructed during render of a client component (a module-level singleton in the browser or `useState(() => new QueryClient())` is the fix).
**Severity hint** – Medium (cache misses, wrong-data flashes when a stale key wins, refetch storms, extra requests on every render).
**Refactor direction** – One options factory per resource; spread it into `useQuery`, `prefetchQuery`, `setQueryData` and `ensureQueryData`. Params go in the key, and the effect disappears. Keep the key function separate from the options so `setQueryData`/`invalidateQueries` can rebuild it without importing the `queryFn`.
```ts
// Query 5+ — queryOptions carries the key type into data/error
export const invoicesOptions = (filters: Filters) => queryOptions({
  queryKey: ['invoices', filters],
  queryFn: () => api.invoices(filters),
  staleTime: 30_000,
})
// Query 4 — same factory, plain object; no queryOptions export exists
export const invoicesKey = (filters: Filters) => ['invoices', filters] as const
export const invoicesOptions = (filters: Filters) => ({
  queryKey: invoicesKey(filters),
  queryFn: () => api.invoices(filters),
  staleTime: 30_000,
})
// before: useEffect(() => { refetch() }, [filters])   after: useQuery(invoicesOptions(filters))
```
**Counter-signals** – A generated factory wins over a hand-written one: when the API client is generated (orval, OpenAPI codegen, `openapi-typescript`), the emitted `getXQueryKey()` is the factory — hand-written string keys next to it are the finding, and re-keying the generated query is worse than adopting its key shape. One-off internal queries inside a single leaf component may inline a key, but only if nothing else needs to find that cache entry. Object key members are hashed order-independently, so `{status, page}` and `{page, status}` collide correctly — that is a feature, not a bug. A `createQueryClient()` factory called during render is not the "client per render" defect when its purpose is per-request isolation under SSR: in the Next.js Pages Router the client must be created inside `_app`/`useState`, never at module scope, because a module singleton is shared across requests on the server.
**Sources** – [TanStack Query: Query Keys](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys) [official] · [Query Options](https://tanstack.com/query/latest/docs/framework/react/guides/query-options) [official] · [ESLint Plugin Query (`prefer-query-options`, `stable-query-client`)](https://tanstack.com/query/latest/docs/eslint/eslint-plugin-query) [official] · [TkDodo: Reliable Query Prefetching with TanStack Router](https://tkdodo.eu/blog/reliable-query-prefetching-with-tanstack-router) [power-user], 2026.

### 4. No `onSuccess` / `onError` / `onSettled` callbacks on `useQuery`

**Rule** – Query-level callbacks are gone in v5; side effects belong in `select`/render, in the mutation that caused the change, or in a global `QueryCache` subscription.
**Since** – TanStack Query 5 (the callbacks were removed).
**Detection signals** – `useQuery({ ..., onSuccess })` / `onError` / `onSettled`; the same options object typed as `any` so the removal compiles silently; an effect afterwards that exists only because the old `onSuccess` no longer runs; a toast fired from a query callback rather than from the mutation's `onError`.
**Severity hint** – Medium (dead code that looks live: analytics, redirects or state syncs silently stop after the upgrade).
**Refactor direction** – Delete the callback. For "do something when data arrives", derive it in render; for mutation-driven effects, move them onto `useMutation`; for cross-cutting logging, subscribe once via `QueryCache({ onError })` in the `QueryClient` constructor.
**Counter-signals** – `useMutation` still supports `onSuccess`/`onError`/`onSettled`; keeping them there is correct. On TanStack Query 4 the query-level callbacks still exist and are not a defect by themselves — the subject of this rule does not exist before v5, so it is dropped, not reported. The v4-era bug they cause (an `onSuccess` that mirrors data into `useState`, or fires a toast per cache write) is caught by rule 2 and by the mutation-reconciliation rule 6 instead.
**Sources** – [TanStack Query: Migrating to v5](https://tanstack.com/query/latest/docs/framework/react/guides/migrating-to-v5) [official].

### 5. Client-wide query defaults are set deliberately: `staleTime`, `retry`, `gcTime`

**Rule** – `QueryClient` is configured once with defaults that match the data's freshness, and a bare `new QueryClient()` is treated as a finding.
**Since** – all. The defaults and the "configure once" contract exist in every TanStack Query version; only the option names moved (`cacheTime` → `gcTime` in v5, `staleTime: 'static'` is v5.66+ only).
**Detection signals** – `new QueryClient()` with no `defaultOptions`; zero occurrences of `staleTime` in the repo; `retry` left at the default of 3 for queries that can 4xx/404; `gcTime: 0` (v5) or `cacheTime: 0` (v4); dashboards refetching everything on every window focus; network panel showing the same GET several times per minute; `staleTime: Infinity` used to silence refetches instead of `'static'` where invalidation should also be blocked (v5.66+ only).
**Severity hint** – Medium (request volume, server load, loading flicker, thundering herds after window focus).
**Refactor direction** – Set app-level defaults (`staleTime` 30–60s, a `retry` function that refuses 4xx) and override per resource; use `'static'` only for boot-time config like feature flags or permissions.
**Counter-signals** – Highly volatile data (prices, live counters) legitimately keeps `staleTime: 0` and short `refetchInterval`. In Next.js App Router apps with Cache Components, the server cache — not `staleTime` — is what must be tuned for shared data.
**Sources** – [TanStack Query: Important Defaults](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults) [official] · [Migrating to v5](https://tanstack.com/query/latest/docs/framework/react/guides/migrating-to-v5) [official].

### 6. Mutations use `useMutation` and reconcile the cache; optimistic updates roll back

**Rule** – Writes go through `useMutation` (or a Server Action) and end by invalidating affected keys or by a `setQueryData` update with a snapshot rollback — never by a local `useState` list patch, never by a `queryFn` that POSTs.
**Since** – all. `useMutation`, `invalidateQueries` and `setQueryData` exist unchanged in v4 and v5; only the v5 callback surface differs (rule 4).
**Detection signals** – `queryFn` containing `method: 'POST'`; `useQuery` used to submit; after a successful mutation, no `invalidateQueries`/`setQueryData` and no router `revalidate` — a bare `axios.post()` followed by `refetch()` counts, because the cache is reconciled by a second round trip and the other keys holding the same entity stay stale; optimistic `setQueryData` with no `onError` restoring the snapshot; `mutate()` result ignored while a spinner is driven from separate `useState`; cache keys invalidated with a bare `invalidateQueries()` (invalidates everything).
**Severity hint** – Medium (stale lists after create/delete; optimistic updates that leave phantom rows on failure).
**Refactor direction** – `onMutate` snapshot → `setQueryData` → `onError` restore → `onSettled` invalidate. Narrow invalidation to the resource key prefix.
**Counter-signals** – Fire-and-forget telemetry posts may skip reconciliation, but still belong in a mutation so retries/errors are observable.
**Sources** – [TanStack Query: Query Options](https://tanstack.com/query/latest/docs/framework/react/guides/query-options) [official] · [TanStack Query: Does This Replace Client State?](https://tanstack.com/query/latest/docs/framework/react/guides/does-this-replace-client-state) [official] · [Next.js: Client-side data fetching](https://nextjs.org/docs/app/guides/client-side-data-fetching) [official], 2026 (coordination between server and client caches).

### 7. Server-rendered shells ship their data with them: prefetch/hydrate instead of refetching on the client

**Rule** – If the server already rendered data, the client must start from it (`HydrationBoundary`/`dehydrate`, `initialData`, or a loader) with a `staleTime` that matches, so the first paint does not trigger the same request again.
**Since** – all. `dehydrate`/`HydrationBoundary` exist in v4 and v5; `initialData` + `staleTime` covers any version, and is the only option on Query 3.
**Detection signals** – A `useQuery` in a client component whose key/fn duplicates a server fetch; network panel shows the same payload fetched twice on first load (once in the RSC/flight response or the `__NEXT_DATA__` payload, once by the browser); no `HydrationBoundary`/`dehydrate` while both a server fetch and TanStack Query exist; `initialData` set but `staleTime: 0`, forcing an immediate refetch; loader prefetch using different options than the component (see rule 3). Pages Router: `getServerSideProps`/`getStaticProps` returning data that a `useQuery` then fetches again on mount, with no `initialData`/hydration from the props.
**Severity hint** – Medium (double payload, INP hit on hydration, flicker from server value → loading → same value).
**Refactor direction** – Prefetch the *same* options object on the server (`prefetchQuery(invoicesOptions(f))`), dehydrate, and hydrate; or stream the promise from a Server Component and read it with `use()`. Keep `staleTime` in the shared options so both sides agree. Pages Router (`getServerSideProps`): build a per-request `QueryClient`, `await prefetchQuery(invoicesOptions(f))`, return `dehydratedState` in props, and wrap the tree in `<HydrationBoundary state={pageProps.dehydratedState}>` inside `_app`; on Query 3/4 without the hydration helper, pass `initialData` plus the same `staleTime`.
**Counter-signals** – Data that must be fresh per interaction (search-as-you-type) should refetch by design. A strict SPA has no server pass, so this rule reduces to "preload in the route loader"; the Pages Router equivalent is a `getServerSideProps`/`getStaticProps` payload hydrated once, not an entry in `__NEXT_DATA__` that the component then refetches. A page that is fully static and never revalidates needs no query at all — flag the `useQuery` wrapper itself, not the missing hydration.
**Sources** – [Next.js: Client-side data fetching](https://nextjs.org/docs/app/guides/client-side-data-fetching) [official], 2026 (three cache layers, `updateTag`/`revalidateTag`) · [TkDodo: Reliable Query Prefetching with TanStack Router](https://tkdodo.eu/blog/reliable-query-prefetching-with-tanstack-router) [power-user], 2026 · [TanStack Router: Data Loading](https://tanstack.com/router/latest/docs/guide/data-loading) [official].

### 8. Global stores hold client state only; server data in Redux/Zustand is a finding

**Rule** – A global store owns synchronous client-only state (UI flags, drafts, selection, undo stacks). Anything fetched from an API lives in a server-state cache, not in a slice/store value.
**Since** – all (redux-toolkit + TanStack Query era guidance).
**Detection signals** – `createSlice` fields named after API resources (`products`, `users`, `orders`) written by `createAsyncThunk` `fulfilled` reducers; `useStore(s => s.products)` read as a data source; Redux/RTK installed while every GET uses `createAsyncThunk` instead of RTK Query; Zustand store with `loading`/`error`/`data` triples per endpoint; store devoted to a form.
**Severity hint** – Medium (hand-rolled cache: no dedupe, no invalidation, no staleness; store re-renders on every fetch).
**Refactor direction** – Move the resource to TanStack Query / RTK Query and delete the slice; the remaining global store usually shrinks to a handful of UI fields.
```ts
// after: server data -> query cache; client-only -> tiny store
const useUi = create<{ sidebarOpen: boolean; toggle: () => void }>(...)
```
**Counter-signals** – Heavy offline/undo/editor state (visual editor, DAW, collaborative doc) is legitimately client state and may be large. RTK Query inside an existing Redux app is a fine server-state layer — the smell is duplicating fetched data into hand-written slices, not Redux itself.
**Sources** – [TanStack Query: Does This Replace Client State?](https://tanstack.com/query/latest/docs/framework/react/guides/does-this-replace-client-state) [official] · [Redux FAQ: When should I use Redux?](https://redux.js.org/faq/general) [official] · [RTK Query Overview](https://redux.js.org/toolkit/rtk-query/overview) [official] · [TkDodo: React Query as a State Manager](https://tkdodo.eu/blog/react-query-as-a-state-manager) [power-user], 2021.

### 9. Legacy Redux idioms: `createStore`, hand-written action types, `connect`

**Rule** – Redux code uses `configureStore`, `createSlice`, and `useSelector`/`useDispatch`; `createStore`, action-type constants and `connect` are migration debt.
**Since** – current Redux docs (Redux Toolkit is the documented default; the `createStore` page carries a deprecation notice).
**Detection signals** – `import { createStore }`; `const ADD_ITEM = 'ADD_ITEM'` plus a parallel `addItem()` creator; `switch (action.type)` reducers outside `createSlice`; `mapStateToProps`/`connect()`; immutable spreads of nested state by hand; `redux-saga`/`redux-observable` used for plain CRUD; middleware arrays assembled manually; `combineReducers` + `applyMiddleware` boilerplate.
**Severity hint** – Low (maintenance friction, no safety net from Immer/RTK checks, hard to type).
**Refactor direction** – Convert one slice at a time to `createSlice` under `configureStore`; replace `connect` with hooks; then move GET/POST endpoints to RTK Query (rule 8) if the slice only ever stored fetched data.
**Counter-signals** – `legacy_createStore` in a library that must support Redux 3 is acceptable. Redux-Saga in a codebase with genuine complex orchestration is a design choice, not a defect.
**Sources** – [Redux: `createStore` is deprecated](https://redux.js.org/api/createstore) [official] · [Redux Style Guide](https://redux.js.org/style-guide) [official] (feature folders, serialisable state).

### 10. Context carries low-frequency values, not a store; providers sit as deep as possible

**Rule** – Context is for values that rarely change and are read widely (theme, locale, current user, a client instance). Anything that changes per keystroke belongs in a store with selectors, and providers are mounted at the lowest subtree that needs them.
**Since** – all.
**Detection signals** – `<Ctx.Provider value={{ a, b, dispatch }}>` created inline on every render with no memoisation; context value containing a list that is appended to frequently (cart, notifications feed, form state); a single `AppProviders` wrapping the root with 6+ contexts; `useContext` called in every leaf while only one field is needed; consumers measuring re-renders in Profiler on unrelated state changes.
**Severity hint** – Medium (whole-subtree re-renders; the provider-per-render identity churn is the classic cause).
**Refactor direction** – Split one fat context into per-field contexts, memoise the value object, and move the provider down to the subtree that consumes it. If a field changes often, move it to Zustand/Jotai and select it.
```tsx
// before: every consumer re-renders on any field change
<AppCtx.Provider value={{ user, cart, theme }}>
// after: three contexts (or a selector store), provider mounted at the subtree boundary
<ThemeProvider><CartProvider><Toolbar /></CartProvider></ThemeProvider>
```
**Counter-signals** – With React Compiler enabled, the inline `value` object is memoised automatically, which removes the identity churn — but not the fan-out re-render when a field actually changes. Next.js docs explicitly recommend rendering providers as deep as possible rather than in the root layout.
**Sources** – [React: useContext caveats](https://react.dev/reference/react/useContext) [official], 2026 ("React automatically re-renders all the children that use a particular context") · [Next.js: Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components) [official], 2026 · [Zustand: Prevent rerenders with useShallow](https://github.com/pmndrs/zustand/blob/main/docs/learn/guides/prevent-rerenders-with-use-shallow.md) [official].

### 11. `'use client'` marks leaf interactions, not pages, layouts or the root provider tree

**Rule** – The directive goes on the smallest module that actually needs state, effects or browser APIs; a `'use client'` at the top of `app/layout.tsx`, `page.tsx`, or a root `providers.tsx` is a boundary bug.
**Since** – Next.js 13 App Router / React 19 RSC (Next.js 16 unchanged).
**Detection signals** – `'use client'` in `app/layout.tsx`, `app/**/page.tsx`, or `src/app/providers.tsx` imported by the root layout; a page that only renders markup yet is a client component; every component under a route importing `useState` unnecessarily; server data fetched with TanStack Query inside a tree that could have awaited it; `'use client'` on files with no hooks and no handlers.
**Severity hint** – High (the whole subtree ships to the browser; RSC data fetching and streaming become impossible for that route).
**Refactor direction** – Push the directive to the interactive leaf and pass server-rendered children into it. Providers are mounted inside the smallest client wrapper that needs them, not at the root.
```tsx
// app/page.tsx (server)
export default async function Page() {
  const user = await getUser()
  return <Header user={user}><LikeButton id={user.id} /></Header>   // only LikeButton is 'use client'
}
```
**Counter-signals** – A genuinely interactive app shell (SPA-mode Next, an editor) may legitimately be client at the root; that is a documented, deliberate architecture, not a smell. React Router v7/v8 framework mode has no directive — this rule is Next.js-only. The Pages Router has no Server Components, so every module is client code: the directive does nothing and its absence is never a finding. The Pages Router equivalents are heavy work deferred with `next/dynamic` (rule 12) and server-only imports kept out of `_app`/components; report those under rule 12, not as a missing `'use client'`.
**Sources** – [React: `'use client'`](https://react.dev/reference/rsc/use-client) [official] ("marks the module and its transitive dependencies as client code") · [Next.js: Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components) [official], updated 2026-10-05 · [Next.js: SPAs](https://nextjs.org/docs/app/guides/single-page-applications) [official], 2026.

### 12. Client-only and heavy third-party libraries are isolated at one boundary

**Rule** – Browser-only libraries (carousels, charts, editors, map SDKs, analytics with `window` access) are consumed through a single wrapper client component, and heavy ones are lazily loaded rather than bundled into the initial route.
**Since** – Next.js 13 App Router (`next/dynamic`); React `lazy` in SPAs.
**Detection signals** – A library imported from a Server Component and throwing on `window`/`document`, or worked around with `typeof window !== 'undefined'`; four different files each importing the same chart/editor package; no `next/dynamic`/`React.lazy` for a >100 kB widget rendered below the fold; `ssr: false` used for something that could have been a server component; `document.querySelector` in a component body instead of a ref.
**Severity hint** – Medium (route JS budget, LCP/TBT; a hydration crash when the guard is forgotten).
**Refactor direction** – One `components/carousel.tsx` with `'use client'` re-exporting the third-party component; lazy-load heavy widgets with a real fallback sized like the final content.
**Counter-signals** – In a pure Vite SPA everything is client, so the "boundary" rule reduces to lazy loading + one wrapper. Library authors should ship `"use client"` on their entry points instead of making users wrap them.
**Sources** – [Next.js: Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components) [official], 2026 (wrapping third-party components; advice to library authors) · [React: `'use client'`](https://react.dev/reference/rsc/use-client) [official].

### 13. Secrets never reach the client bundle: `NEXT_PUBLIC_`/`VITE_` prefixes are a public contract, and server modules are fenced with `server-only`

**Rule** – Only values that are safe to publish carry a client prefix; every module touching a DB, an admin SDK, a private key or a privileged API imports `server-only` so an accidental client import fails the build.
**Since** – Next.js (`NEXT_PUBLIC_`); Vite (`VITE_`); `server-only` package.
**Detection signals** – `.env*` entries matching `NEXT_PUBLIC_.*(SECRET|KEY|TOKEN|PASSWORD|PRIVATE|DSN)` or `VITE_.*(SECRET|KEY|TOKEN|PASSWORD)`; `process.env.X` read inside a `'use client'` file with no `NEXT_PUBLIC_` (undefined at runtime, not an error); `lib/db.ts`, `lib/stripe.ts`, `lib/auth.ts` without `import 'server-only'`; a service-role/secret key in `next.config.*`, `vite.config.*` `define`, or in a client-imported constants file; `.env` not in `.gitignore`; secrets passed as props from a Server Component into a client component (serialised into the RSC payload).
**Severity hint** – High (published credentials; full data access for anyone who reads the bundle).
**Refactor direction** – Rename to a non-prefixed variable and read it in a server module; add `import 'server-only'` at the top of every privileged module; move the privileged call behind a Server Action/route handler. Rotate any key that was ever prefixed.
```ts
// lib/billing.ts
import 'server-only'
export async function charge(id: string) { /* STRIPE_SECRET_KEY */ }
```
**Counter-signals** – Public identifiers (Stripe publishable key, Supabase anon key with RLS, Sentry DSN, PostHog key) are designed to be public — flagging them is a false positive. In Vite, `import.meta.env` values are inlined at build time, so a secret in a non-prefixed var is still safe as long as it is not referenced in client code.
**Sources** – [Next.js: Environment Variables](https://nextjs.org/docs/app/guides/environment-variables) [official], 2026 · [Next.js: Preventing environment poisoning](https://nextjs.org/docs/app/getting-started/server-and-client-components) [official] · [Vite: Env Variables and Modes](https://vite.dev/guide/env-and-mode) [official] · [Next.js: Data Security](https://nextjs.org/docs/app/guides/data-security) [official], 2026.

### 14. Every Server Action authenticates, authorises and validates — it is a public HTTP endpoint

**Rule** – Each `'use server'` function re-checks the session and permissions and parses its input through a schema; nothing about "only our UI can call it" is assumed.
**Since** – React 19 Server Functions / Next.js App Router (Next.js 16 unchanged; secure action IDs mitigate but do not replace checks).
**Detection signals** – Files with `'use server'` containing zero calls to `auth()`/`getSession()`/`requireUser()`; `formData.get('x') as string` used straight into a query; no `z.object(...).parse`/`safeParse` (or valibot equivalent) at the action boundary; client-supplied `userId`, `orgId`, `role`, `price` or `status` trusted as-is; `'use server'` on an entire file that also exports helpers; authorisation done only in the page that renders the form (`if (!isAdmin) redirect(...)`) and not in the action.
**Severity hint** – High (privilege escalation / IDOR — the classic post-RSC vulnerability class).
**Refactor direction** – Wrap every action in a guard + parse: session first, schema second, then call a data-access function with server-derived ids. Model expected failures as return values instead of throws.
```ts
'use server'
export async function updateInvoice(prev: State, fd: FormData) {
  const user = await requireUser()                       // authn
  const input = invoiceSchema.safeParse(Object.fromEntries(fd))
  if (!input.success) return { ok: false, errors: input.error.flatten() }
  await assertMember(user.id, input.data.invoiceId)      // authz
  await db.invoices.update(...)
  updateTag(`invoice:${input.data.invoiceId}`)
  return { ok: true }
}
```
**Counter-signals** – Actions in a codebase with a global middleware/proxy guard still need per-action authorisation: the guard cannot know which record the action touches. Next.js's encrypted action IDs raise the bar against guessing IDs but are explicitly documented as no substitute for checks. The Pages Router has no Server Actions: the equivalent public endpoint is `pages/api/*`, and the same rule applies to it (authenticate, authorise the record, validate `req.body` with a schema) — report it there as the API-route equivalent, never as "missing `'use server'`".
**Sources** – [React: `'use server'` caveats](https://react.dev/reference/rsc/use-server) [official] ("Always treat arguments to Server Functions as untrusted") · [Next.js: Forms guide warning](https://nextjs.org/docs/app/guides/forms) [official], 2026 ("Always verify authentication and authorization inside each Server Action, even if the form is only rendered on an authenticated page") · [Next.js: Data Security](https://nextjs.org/docs/app/guides/data-security) [official], 2026.

### 15. Don't assume Server Actions run concurrently, and don't call them from effects

**Rule** – Multiple actions fired from one client are dispatched one at a time; batching many mutations into `Promise.all` or a loop does not parallelise them, and an action invoked from `useEffect` is a red flag for "this should be a query".
**Since** – App Router Server Actions (dispatch model documented in the current Next.js 16 docs).
**Detection signals** – `Promise.all([saveA(), saveB(), saveC()])` or `for (const row of rows) await save(row)` on actions; an action call inside `useEffect` used as a data fetch; a save button whose `isPending` comes from a hand-rolled `useState` instead of `useActionState`/`useTransition`; N separate action calls in a bulk-import feature where one action taking an array would do.
**Severity hint** – Low→Medium (a bulk save of 50 rows becomes 50 serialised round-trips; latency scales linearly and the UI looks hung).
**Refactor direction** – One action that accepts the batch and validates the array; drive pending state with `useActionState`/`useTransition`; keep reads in Server Components or a query layer.
**Counter-signals** – Independent user-triggered clicks are naturally serialised anyway, so no finding there. React Router / TanStack Start actions do not follow Next.js's dispatch model — verify the framework before flagging.
**Sources** – [Next.js: Server Actions and Mutations — sequential dispatch](https://nextjs.org/docs/app/guides/server-actions) [official], updated 2026-10-15 · [React: useActionState](https://react.dev/reference/react/useActionState) [official].

### 16. Caching is declared, not inherited: `use cache` + `cacheLife` + `cacheTag`, with no reliance on the old implicit `fetch` cache

**Rule** – In a Cache Components app, cached work is marked with `use cache`, bounded by `cacheLife`, and invalidated by tag; personalisation is read outside the cached scope and passed in as arguments. Code that assumes implicit `fetch` caching is a finding.
**Since** – Next.js 16 for `cacheComponents`/`use cache` (recommended for all apps in 16.4, default in 17); the current non-Cache-Components model already leaves `fetch` uncached by default.
**Detection signals** – `next.config.*` with `cacheComponents: true` while route segments still export `export const dynamic = 'force-dynamic'` / `revalidate = 60` or `fetch(url, { next: { revalidate } })`; `'use cache'` with no `cacheLife()` and no `cacheTag()`; `cookies()`/`headers()`/`searchParams` read *inside* a `use cache` scope; a cached function closing over the current user instead of taking `userId` as an argument; mutations that call `revalidatePath('/')` on every write instead of `updateTag`/`revalidateTag` on the affected resource; a page that silently caches per-user data and leaks it to the next visitor.
**Severity hint** – High (cross-user data leakage when personalised data is cached, or permanently stale data when tags are missing; both are production incidents, not nits).
**Refactor direction** – Read runtime inputs outside the cache boundary and pass them in; pair every `'use cache'` with a `cacheLife` profile and a `cacheTag`; invalidate with `updateTag(tag)` (read-your-own-writes) or `revalidateTag(tag, profile)` after mutations.
```ts
export async function getCart(userId: string) {
  'use cache'
  cacheLife('minutes')
  cacheTag(`cart:${userId}`)
  return db.carts.byUser(userId)     // userId comes from the caller, not from cookies()
}
```
**Counter-signals** – Apps that have not opted into `cacheComponents` still follow the previous model (uncached `fetch` by default, opt in with `cache: 'force-cache'`) — judge against the config that is actually enabled, and do not report "missing `use cache`" for a plain SPA or a `output: 'export'` app. The Pages Router has no Cache Components at all: its caching is `getStaticProps` + `revalidate`, ISR, and `Cache-Control` on API routes — never ask for `use cache` there. Client-side freshness (`staleTime`, rule 5) is a different layer from server caching; a finding in one is not a finding in the other.
**Sources** – [Next.js: Caching (Cache Components)](https://nextjs.org/docs/app/getting-started/caching) [official], 2026-10-06 · [Revalidating](https://nextjs.org/docs/app/getting-started/revalidating) [official], 2026 · [`use cache`](https://nextjs.org/docs/app/api-reference/directives/use-cache) [official], 2026-09-29 · [Caching (previous model)](https://nextjs.org/docs/app/guides/caching-without-cache-components) [official], 2026 ("By default, `fetch` requests are not cached") · [Next.js 16.4 blog](https://nextjs.org/blog/next-16-4) [official], 2026.

### 17. Parallelise independent awaits in Server Components; preload instead of cascading

**Rule** – Independent server awaits start together; component-level fetches that depend on a parent's slow work are hoisted into a preloaded promise or a `<Suspense>` boundary rather than awaited in sequence.
**Since** – Next.js 13 App Router (RSC); preload/`use()` pattern documented in 2026 docs.
**Detection signals** – Two or more `await` statements for unrelated resources in one async component; `await` inside a `for`/`map` loop; a child Server Component fetching data its parent already fetched (only identical `GET` `fetch` calls are deduped within a render pass — an ORM/SDK call is not); `await params`/`await searchParams` before firing unrelated fetches; a slow page whose network waterfall is 4+ levels deep in DevTools; no `<Suspense>` around the slow segment so the whole route blocks.
**Severity hint** – High (a waterfall is additive latency on LCP and on every navigation).
**Refactor direction** – `Promise.all` the independent awaits; kick off the slow promise early and pass it down for `use()`; put the slow subtree behind `<Suspense>` so the shell streams. In 16.4+, `navigation()`/`prefetch()` control what belongs to the shell versus the full navigation.
```tsx
const [user, invoices] = await Promise.all([getUser(id), getInvoices(id)])   // was: two awaits
```
**Counter-signals** – Sequential fetching is correct when the second call genuinely needs the first's output. `fetch` memoisation already removes duplicate *identical* requests inside one render pass — do not report two components calling the same `fetch(url)` as a waterfall. In the Pages Router the same cascade lives in `getServerSideProps` and is fixed with `Promise.all` (rule 26); there is no `preload`/`use` there, so never recommend Server Component tooling for it.
**Sources** – [Next.js: Fetching Data — sequential/parallel/preloading](https://nextjs.org/docs/app/getting-started/fetching-data) [official], 2026 ("Preloading starts the request earlier so it can run in parallel with that work and avoid a request waterfall") · [`fetch` memoisation](https://nextjs.org/docs/app/api-reference/functions/fetch) [official] · [React: `use`](https://react.dev/reference/react/use) [official] · [Next.js 16.4 blog](https://nextjs.org/blog/next-16-4) [official], 2026.

### 18. SPA data loads in route loaders, in parallel, and `shouldRevalidate` is not `false`

**Rule** – In a Vite/React Router/TanStack Router SPA, route data is fetched by the route's loader (which runs in parallel across matching routes), not by mount effects in leaf components; revalidation is selective rather than disabled.
**Since** – React Router 6.4+/v7 framework mode (v8 unchanged); TanStack Router loaders.
**Detection signals** – No `loader`/`clientLoader` export anywhere while routes mount-fetch; `loader` returning a promise chain for independent resources (`await a(); await b()`); `shouldRevalidate: () => false` at the router root; `defaultShouldRevalidate={false}` sprinkled on links to stop refetches; loader `staleTime: 0` making every hover preload refetch; `useEffect` fetching keyed on `useParams()`; a navigation spinner that appears only after the data arrives (no `HydrateFallback`/`pendingComponent`).
**Severity hint** – Medium (navigation waterfalls, stale screens after mutations, double fetches on preload + mount).
**Refactor direction** – Move the fetch into the route module, keep independent work parallel, and return the promise rather than awaiting where the framework supports streaming. Use a targeted `shouldRevalidate` that falls back to `defaultShouldRevalidate`.
**Counter-signals** – A loader that exists only to `await` the same query the component fetches is worse than no loader: keep options in one place so loader and component cannot diverge. Pure client-side-only data (IndexedDB, local drafts) belongs in a component or a `clientLoader`.
**Sources** – [React Router: Data Loading](https://reactrouter.com/start/framework/data-loading) [official] · [React Router: `shouldRevalidate`](https://reactrouter.com/start/framework/route-module) [official] ("Always returning `false` can leave this route's UI out of sync with the server") · [TanStack Router: Data Loading](https://tanstack.com/router/latest/docs/guide/data-loading) [official] (parallel route loading, SWR cache) · [TkDodo, 2026](https://tkdodo.eu/blog/reliable-query-prefetching-with-tanstack-router) [power-user].

### 19. Every route segment has a streaming fallback and an error boundary

**Rule** – Slow segments render behind `loading.tsx`/`<Suspense>`, failures render behind `error.tsx` (or `catchError`), and the boundary is a client component with a working retry.
**Since** – Next.js 13 App Router; `retry` prop stable in Next.js 16.3 (`unstable_retry` in 16.2); `catchError` in 16.3.
**Detection signals** – `app/**` with no `error.tsx`, no `global-error.tsx`, no `not-found.tsx`; `error.tsx` without `'use client'`; `error.tsx` destructuring `reset` and calling `props.reset()` (pre-16.2 API) while on ≥16.3; `error.tsx` that renders `error.message` raw to users; no `loading.tsx`/`<Suspense>` around an awaited segment, so navigation blocks until the slowest query resolves; a single root-level boundary only, so one failing widget blanks the page; route-level `errorElement` missing in React Router.
**Severity hint** – Medium→High (a thrown error in one card blanks an entire page; a missing fallback turns a 300 ms query into a 300 ms white screen).
**Refactor direction** – Add `loading.tsx` per slow segment (sized like the final content), an `error.tsx` per feature area that reports and offers `retry()`, and `not-found.tsx` where `notFound()` is thrown. In React Router, add `errorElement`/`ErrorBoundary`.
```tsx
'use client'
export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => { report(error) }, [error])
  return <button onClick={retry}>Retry</button>
}
```
**Counter-signals** – A tiny static route does not need a `loading.tsx`; adding one just to have one creates flicker. `catchError` is a Next.js 16.3+ API — do not recommend it for newer-than-repo versions or for React Router apps. The Pages Router has no `loading.tsx`/`error.tsx` conventions at all: its equivalents are `_error.tsx` for the fatal case plus a route-level class boundary (or `react-error-boundary`) and `next/dynamic`'s `loading` option — ask for those, never for segment files.
**Sources** – [`error.js` (props, version history)](https://nextjs.org/docs/app/api-reference/file-conventions/error) [official], 2026-10-15 · [`loading.js`](https://nextjs.org/docs/app/api-reference/file-conventions/loading) [official], 2026-09-23 · [`catchError`](https://nextjs.org/docs/app/api-reference/functions/catchError) [official], 2026-10-15 · [Next.js 16.3 blog](https://nextjs.org/blog/next-16-3) [official], 2026.

### 20. Expected errors are returned, unexpected ones are thrown and reported once

**Rule** – Validation and business failures come back as typed return values from actions/loaders; unexpected exceptions bubble to a boundary that reports them to a service. `console.error` alone is not error handling.
**Since** – React 19 `useActionState`; Next.js App Router conventions.
**Detection signals** – `throw new Error('invalid email')` inside a Server Action; `try { ... } catch { }` with an empty or `console.log` body; `catch (e) { return null }` swallowing a failure that the UI then renders as "empty"; a `reportError`-less `error.tsx`; no `@sentry/*`, OTel or equivalent dependency while `error.tsx` exists; user-facing strings built from `error.message`; a single `onClick` handler that fires three awaited mutations with one try/catch.
**Severity hint** – Medium (silent data loss, invisible production failures, no alerting path).
**Refactor direction** – Return a discriminated result from the action (`{ ok: false, errors }`) and render it from `useActionState`; let unexpected errors throw; report in `error.tsx`/`componentDidCatch` once, with request context.
**Counter-signals** – A boundary that reports to a third-party service is redundant if a global `window.onerror`/instrumentation hook already reports the same exception with context — flagging both is double counting. `console` in dev-only branches is fine.
**Sources** – [Next.js: Error Handling](https://nextjs.org/docs/app/getting-started/error-handling) [official], 2026-10-15 ("avoid using `try`/`catch` blocks and throw errors; model expected errors as return values") · [React: useActionState](https://react.dev/reference/react/useActionState) [official].

### 21. Forms: uncontrolled + `FormData` or React Hook Form, always validated by a schema at the boundary

**Rule** – Fields are uncontrolled by default (`FormData` with Server Actions, `register` with RHF); the same schema validates in the browser for feedback and on the server for truth.
**Since** – all (RHF 7; Zod 4 / Valibot 1 for schemas; React 19 actions).
**Detection signals** – One `useState` per field (or a single object state updated with `setForm({ ...form, [k]: v })` on every `onChange`) for a form with 5+ fields; no `register`/`useForm` while the form has validation rules; `if (!email.includes('@'))` style validation inline in the component; a Zod/Valibot schema imported only in the client component; a Server Action that reads `formData` without parsing it; `required` attributes as the only validation; submit handler with no `isSubmitting`/pending state; error messages not linked to inputs (`aria-invalid`, `aria-describedby`); no `<label htmlFor>`.
**Severity hint** – Medium (a re-render per keystroke on a large form — measurable INP cost — plus bypassable validation; High if the server never validates at all).
**Refactor direction** – Convert to `useForm` + `zodResolver(schema)` (or plain `FormData` + schema parse for server-first forms); keep one schema module shared by client and server. Use `useActionState` for pending/error state on action forms.
```tsx
const form = useForm<Input>({ resolver: zodResolver(invoiceSchema), defaultValues })
<form onSubmit={form.handleSubmit(save)}>  <input {...form.register('title')} aria-invalid={!!form.formState.errors.title} />
```
**Counter-signals** – A two-field search box does not need RHF; controlled inputs are correct when the value is transformed as the user types (masks, currency). Client-side validation never removes the need for server-side validation, but a form with no client validation is a UX choice, not automatically a bug. The Pages Router has no Actions: the server half is a `pages/api/*` handler that parses the same schema, and the client half is still RHF (or uncontrolled + `FormData`); do not flag the absence of `useActionState` there.
**Sources** – [React Hook Form: Get Started](https://react-hook-form.com/get-started) [official] · [Next.js: Forms](https://nextjs.org/docs/app/guides/forms) [official], 2026 (server-side validation before mutation) · [Next.js: Error Handling](https://nextjs.org/docs/app/getting-started/error-handling) [official], 2026 (`useActionState` for field errors) · [React: useActionState](https://react.dev/reference/react/useActionState) [official].

### 22. Feature folders, no cross-feature barrels, no import cycles

**Rule** – Code is grouped by feature (route/domain), each feature exposes a narrow public surface, and imports never reach into another feature's internals or form a cycle.
**Since** – all (Redux style guide "Structure Files as Feature Folders"; `import/no-cycle` long-standing; `eslint-plugin-boundaries` v7).
**Detection signals** – Top-level `components/`, `hooks/`, `utils/`, `services/`, `types/` each holding 30+ unrelated files; a feature imported via `../../other-feature/internal/thing`; `index.ts` barrels re-exporting 20+ modules that are imported from many places (barrels defeat route-level code splitting and make cycles invisible); `import/no-cycle` not enabled, or enabled and disabled inline; no `eslint-plugin-boundaries`/`import/no-restricted-paths` config while the README claims a layered architecture; a `shared`/`common` folder that imports from features.
**Severity hint** – Low→Medium (cycle-induced `undefined` at import time is the nasty case; otherwise it is navigation and ownership friction).
**Refactor direction** – Move to `src/features/<feature>/{components,api,hooks,index.ts}` with the barrel exporting only the feature's public components; forbid feature→feature imports except through that barrel; enable `import/no-cycle` and a boundaries config.
```js
// eslint.config.js
rules: {
  'import/no-cycle': ['error', { maxDepth: 4, ignoreExternal: true }],
}
```
**Counter-signals** – A tiny app (<20 components) does not need boundaries config. Barrel files are fine for a design-system package with tree-shakeable output, and Next.js/bundlers can be told to optimise specific packages. Feature folders are a convention, not a requirement — consistency beats a partial migration.
**Sources** – [Redux Style Guide: Structure Files as Feature Folders](https://redux.js.org/style-guide) [official] · [`import/no-cycle`](https://github.com/import-js/eslint-plugin-import/blob/main/docs/rules/no-cycle.md) [official] · [eslint-plugin-boundaries](https://github.com/javierbrea/eslint-plugin-boundaries) [official].

### 23. No half-migrated routers: Pages Router leftovers in an App Router tree

**Rule** – A Next.js app uses one router. `next/router`, `getServerSideProps`/`getStaticProps`, `_app.tsx` and duplicate `pages/` routes next to `app/` are migration debt with concrete behavioural consequences.
**Since** – Next.js 13 (App Router); Next.js 16 (`proxy.ts` replaces `middleware.ts`).
**Detection signals** – `import { useRouter } from 'next/router'` inside `app/**`; `export async function getServerSideProps` in a file under `app/`; `pages/` and `app/` both defining `/dashboard`; `_app.tsx`/`_document.tsx` alongside `app/layout.tsx`; `next/head` in `app/**` (should be the `metadata` export); `middleware.ts` in a Next.js 16 project (renamed `proxy.ts`); `router.query` read where `searchParams`/`useSearchParams` is the App Router API.
**Severity hint** – Low→Medium (dead configuration, silently ignored exports, two data-fetching mental models, and `getServerSideProps`-style waterfalls in a tree that could stream).
**Refactor direction** – Migrate route by route, deleting the `pages/` file in the same PR; swap `next/router` for `next/navigation`; convert `getServerSideProps` into an async Server Component (or a `fetch` with explicit caching), and `next/head` into `metadata`.
**Counter-signals** – Both routers can coexist by design during a migration, so the finding is a *duplicated* route or an App Router file importing the Pages API — not the mere existence of `pages/`. Next.js versions before 16 legitimately use `middleware.ts`.
**Sources** – [Next.js: Migrating from Pages to the App Router](https://nextjs.org/docs/app/guides/migrating/app-router-migration) [official], 2026-09-28 · [Next.js 16 blog](https://nextjs.org/blog/next-16) [official], 2025 (`proxy.ts`).

### 24. React Compiler readiness: hooks are clean, memoisation is not hand-maintained, `setState` in effects is a bug

**Rule** – Code follows the Rules of React so the compiler can memoise it; hand-written `useMemo`/`useCallback`/`memo` blankets are removed, and state that is set from an effect is restructured.
**Since** – React Compiler 1.0 (2025-10-07); Next.js 16 ships stable compiler support; `eslint-plugin-react-hooks` 7 exposes the compiler rules.
**Detection signals** – `eslint-plugin-react-hooks` below 7.x, or the config missing `react-hooks/set-state-in-effect`, `react-hooks/purity`, `react-hooks/immutability`, `react-hooks/refs`, `react-hooks/static-components`; inline `eslint-disable-next-line react-hooks/exhaustive-deps` (each one is a compiler bail-out candidate); `useCallback` on every handler plus `memo()` on every component while the compiler is enabled; props mutated in place; refs read during render; components defined inside components; `next.config.*` without `reactCompiler` while the team claims automatic memoisation.
**Severity hint** – Medium (missed optimisation plus real correctness bugs: hydration mismatches, stale closures, double renders).
**Refactor direction** – Upgrade to `reactHooks.configs.flat['recommended-latest']`, fix `set-state-in-effect` by deriving during render or keying the component, remove `useMemo`/`useCallback` that only exist for equality, keep manual memoisation only where the compiler is not enabled.
**Counter-signals** – If the compiler is not enabled, `useMemo` for a genuinely expensive computation and `React.memo` on a hot list are correct, not debt — verify `reactCompiler` in the config before flagging. Libraries that ship pre-compiled must keep the runtime contract.
**Sources** – [React Compiler docs](https://react.dev/learn/react-compiler) [official] · [React 19.3 / versions changelog](https://react.dev/versions) [official], 2026 · [Next.js 16 blog: React Compiler support stable](https://nextjs.org/blog/next-16) [official], 2025 · [`eslint-plugin-react-hooks` README (rule names)](https://github.com/facebook/react/blob/main/packages/eslint-plugin-react-hooks/README.md) [official], 2026.

### 25. `queryFn` resolves data or throws — a swallowing wrapper turns every failure into an empty state

**Rule** – The query function either resolves a value that is not `undefined` or throws/rejects. A shared wrapper must rethrow the error and normalise it, not `catch` it into `null`, `[]` or `{}` — otherwise `isError`, `retry` and error boundaries never fire and the UI reports "no data" for a 500.
**Since** – all (same contract in v3, v4 and v5: a resolved `undefined` counts as a failure, and an error only exists if the function threw).
**Detection signals** – `defaultQueryFn` or a `request()` helper ending in `.catch(() => null)` / `try { … } catch { return [] }`; `if (!res.ok) return res.json()` (resolves the error body as data); a `fetch` without an `ok`/`status` check and no throw; `axios` with `validateStatus: () => true`; queries whose `isError` branch is unreachable, or a global `onError`/`QueryCache` handler that never fires in practice; a `retry` config that cannot work because nothing throws.
**Severity hint** – High (silent failures, retry and error boundaries dead, users shown an empty state on outage, no alerting path).
**Refactor direction** – Throw on transport/protocol failure and let the cache model the error; keep domain-level "not found" as a thrown typed error or as data the caller can discriminate. Keep the wrapper's job to attach auth, base URL and parsing only.
```ts
// before: every failure becomes "empty"
queryFn: (ctx) => fetch(ctx.queryKey[0]).then(r => r.json()).catch(() => null)
// after: throw, and let `error` + retry do their job
queryFn: async ({ queryKey: [url], signal }) => {
  const res = await fetch(url, { signal })
  if (!res.ok) throw new HttpError(res.status, await res.text())
  return res.json()
}
```
**Counter-signals** – A deliberately tolerated 404 for an optional record may resolve `null` if the query sets `retry: false` and the component reads `data === null` as a domain state — document that choice where the wrapper is defined. Form-submission mutations may return a discriminated result instead of throwing, because the caller renders field errors; that is rule 20's model, not this rule.
**Sources** – [TanStack Query: Query Functions — handling and throwing errors](https://tanstack.com/query/latest/docs/framework/react/guides/query-functions) [official], 2026 ("the query function must throw or return a rejected Promise") · [TkDodo: React Query Error Handling](https://tkdodo.eu/blog/react-query-error-handling) [power-user], Dominik Dorfmeister, 2022.

### 26. Next.js Pages Router: `getServerSideProps` is the data source, `router.query` is derived input, and the cache is per request

**Rule** – A Pages Router route fetches on the server through `getServerSideProps`/`getStaticProps` (or a per-request prefetch into TanStack Query) and passes the result down; it does not re-fetch the same data on mount, copy `router.query` into state, and it never shares one `QueryClient` across server requests.
**Since** – all (Pages Router API, Next.js 9.3+; unchanged through Next.js 14/15).
**Detection signals** – `getServerSideProps` result ignored by the page component and re-requested in `useEffect`/`useQuery` on mount; `const [page, setPage] = useState(router.query.page)` followed by a sync Effect; `useEffect(() => { fetch(...) }, [router.query])`; a module-scope `const queryClient = new QueryClient()` imported by a server-side function; two sequential `await`s in `getServerSideProps` that do not depend on each other (a waterfall on every request); API-route round trip from `getServerSideProps` to the same Next.js app (`fetch('/api/...')`) instead of calling the data source directly; `getServerSideProps` used on a route whose data does not vary per request (should be `getStaticProps` + revalidation); a MUI/emotion `createCache()` called once at module scope in `_document.tsx` while pages are server-rendered — the cache is then shared across requests and leaks styles between users (the documented pattern builds it inside `renderPage`/a per-request function and passes it to `<CacheProvider>`).
**Severity hint** – Medium (double fetch per navigation, TTFB waterfall, cache bleed between users when the client is shared on the server).
**Refactor direction** – Fetch once on the server, return the payload (or a dehydrated cache) in props, and read it in render; derive pagination/filters from `router.query` during render instead of mirroring them into state; create the `QueryClient` inside the request scope, not at module scope; parallelise independent awaits with `Promise.all`.
```ts
// before: serial, then refetched on the client
const user = await getUser(id); const posts = await getPosts(id)
// after
const [user, posts] = await Promise.all([getUser(id), getPosts(id)])
return { props: { user, posts } }
```
**Counter-signals** – Client-only interactions (search-as-you-type, infinite scroll, polling) legitimately fetch after mount; that is TanStack Query's job, not `getServerSideProps`'s. A route that must be static and CDN-cached should use `getStaticProps` + `revalidate`, and flagging it as "missing getServerSideProps" is wrong. `next/router` itself is correct in this router — rule 23 applies only to a mixed tree.
**Sources** – [Next.js: `getServerSideProps`](https://nextjs.org/docs/pages/building-your-application/data-fetching/get-server-side-props) [official], 2026 ("runs on the server", "can only be exported from a page") · [TanStack Query: Advanced SSR](https://tanstack.com/query/v5/docs/framework/react/guides/advanced-ssr) [official], 2026 (per-request client, no module-level singleton on the server).

### 27. Realtime events write the query cache; they never feed a parallel copy of it

**Rule** – Websocket/SSE messages update the cache that owns the data (`setQueryData`, `invalidateQueries`, or `queryClient.setQueriesData` on a key prefix) or append through a `queryFn`-owned subscription. They do not `setState` a second copy of the list next to a `useQuery` that renders the same rows.
**Since** – all (cache mutation APIs are stable across Query 4 and 5; the anti-pattern exists with SWR/Redux too).
**Detection signals** – A socket handler doing `setMessages(prev => [...prev, msg])` in a component that also renders `useQuery(messagesOptions)`; two sources rendered into one list (query rows + socket rows concatenated); a socket connect Effect that never closes on unmount or reconnects per component mount; inbound events that only touch local state, so a refetch or a second tab never sees them; the same socket subscribed in several components with no shared owner.
**Severity hint** – Medium (duplicated rows, messages lost on refetch/invalidation, drift between tabs, reconnection storms).
**Refactor direction** – One connection owner (a module singleton or a provider mounted once). On message, `queryClient.setQueryData(messagesKey(conversationId), old => old && appendDeduped(old, msg))`; for events that change many keys, `invalidateQueries({ queryKey: ['messages', conversationId] })`. Keep the query as the single rendered source.
```ts
// before
useEffect(() => socket.on('message', m => setMessages(p => [...p, m])), [])
// after
useEffect(() => {
  const onMessage = (m: Message) =>
    queryClient.setQueryData(messagesKey(m.conversationId), (old: Message[] = []) =>
      old.some(x => x.id === m.id) ? old : [...old, m])
  socket.on('message', onMessage)
  return () => { socket.off('message', onMessage) }
}, [queryClient])
```
**Counter-signals** – A transient, non-persisted signal (typing indicator, presence, a toast) belongs in local state or a store; it has no cache entry to own and no server truth to reconcile. A socket that is the *only* transport for a stream with no HTTP source is better modelled as a subscription (`useSyncExternalStore`), per rule 1's counter-signals.
**Sources** – [TkDodo: Using WebSockets with React Query](https://tkdodo.eu/blog/using-web-sockets-with-react-query) [power-user], Dominik Dorfmeister, 2023 (`setQueryData` from the socket handler, one connection owner) · [TanStack Query: Query Invalidations](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation) [official], 2026.

## Tools

Lint (config-level evidence; run `npx eslint . --max-warnings=0`):

```js
// eslint.config.js — the rules this pack leans on
import reactHooks from 'eslint-plugin-react-hooks'
import importPlugin from 'eslint-plugin-import'
import pluginQuery from '@tanstack/eslint-plugin-query'
import boundaries from 'eslint-plugin-boundaries'

export default [
  reactHooks.configs.flat['recommended-latest'],   // rules-of-hooks, set-state-in-effect, purity, immutability, refs, static-components, incompatible-library
  ...pluginQuery.configs['flat/recommended-strict'], // @tanstack/query/prefer-query-options, stable-query-client, exhaustive-deps, no-rest-destructuring
  {
    plugins: { import: importPlugin, boundaries },
    rules: {
      'import/no-cycle': ['error', { maxDepth: 4, ignoreExternal: true }],
      'boundaries/dependencies': ['error', { default: 'disallow', rules: [/* feature -> shared */] }],
    },
  },
]
```

| Command / tool | What it proves for this pack |
| --- | --- |
| `eslint-plugin-react-hooks` 7 (`rules-of-hooks`, `set-state-in-effect`, `set-state-in-render`, `purity`, `immutability`, `refs`, `static-components`, `preserve-manual-memoization`, `incompatible-library`) | Rules 1, 2, 10, 24: state set from effects, impurity, ref reads in render, components defined in render, memoisation the compiler cannot preserve |
| `@tanstack/eslint-plugin-query` 5 (`prefer-query-options`, `stable-query-client`, `exhaustive-deps`, `no-rest-destructuring`, `no-unstable-deps`) | Rules 3, 5, 10: inline keys instead of `queryOptions`, `QueryClient` created in a component, unstable deps in `queryFn` |
| `eslint-plugin-import` → `import/no-cycle` | Rule 22: import cycles (reported as `Dependency cycle detected`) |
| `eslint-plugin-boundaries` 7.3 (`boundaries/dependencies` — formerly `element-types` — plus `entry-point`, `no-private`, `external`, `no-unknown-files`) | Rule 22: feature→feature deep imports, layering violations, imports of another element's internals |
| `npx tsc --noEmit` | Rules 3, 6, 14: missing query-key typing, untyped action arguments, `any` that hides removed v5 callbacks |
| `npx next build` (route table + First Load JS) | Rules 7, 11, 12: routes that are client-heavy, whole-tree `'use client'` cost, `use cache` output, prefetch behaviour |
| `@next/bundle-analyzer` (`ANALYZE=true npx next build`) / `npx vite-bundle-visualizer` | Rule 12: which route pulled a chart/editor/map library into the initial bundle |
| `@tanstack/react-query-devtools` | Rules 1, 3, 5, 7: duplicate keys, refetch storms, cache misses, stale/fresh state per key |
| React DevTools Profiler (+ React Scan) | Rules 10, 24: context fan-out re-renders, memoisation gaps, components re-rendering after unrelated state changes |
| Chrome DevTools Performance + Network (waterfall) / Lighthouse | Rules 7, 17, 18: sequential request chains, LCP and INP regressions against the 2.5 s / 200 ms thresholds |
| `npx knip` | Rules 8, 9, 23: slices/hooks/exports left behind after a state or router migration |
| `rg -n "onSuccess|onError|onSettled" --glob '*.{ts,tsx}'` scoped to `useQuery` blocks | Rule 4: v5-removed query callbacks |
| `rg -n "^'use client'|^\"use client\"" app/` | Rule 11: boundary placement (layout/page hits are the signal) |
| `rg -n "(SECRET|TOKEN|PASSWORD|PRIVATE_KEY|SERVICE_ROLE)" --glob '*.env*'`, plus `rg -n "NEXT_PUBLIC_|import.meta.env.VITE_"` | Rule 13: secret-shaped names behind a client prefix |
| `rg -n "formData.get\(" app/ --glob '*.{ts,tsx}'` cross-checked with schema `parse(` in the same file | Rule 14: Server Actions without input validation |
| `next.config.*` inspection (`cacheComponents`, `partialPrefetching`, `reactCompiler`, `experimental.taint`) | Rules 16, 24: whether the Cache Components model and compiler are actually on; `reactCompiler: true` only works with `babel-plugin-react-compiler` installed ([Next.js `reactCompiler` docs](https://nextjs.org/docs/app/api-reference/config/next-config-js/reactCompiler) [official], 2026-10-02) |
