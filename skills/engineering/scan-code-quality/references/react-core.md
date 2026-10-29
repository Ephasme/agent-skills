# React — components, hooks and rendering model

Scope: component purity and hook discipline, Effect misuse, state placement, keys, refs, the React 19 API surface (Actions, `use`, metadata, preloading), the React Compiler, Context/Suspense/Error Boundary structure, StrictMode, and legacy APIs removed in React 19. Framework-specific advice is flagged inline; Tailwind, accessibility, bundler and network concerns live in sibling packs.

## Contents

- [Version baseline](#version-baseline)
- [Rules](#rules)
- [Tools](#tools)

## Version baseline

| Package | Current stable | Verified against |
|---|---|---|
| `react` / `react-dom` | 19.3.1 | [react.dev/versions](https://react.dev/versions) [official], npm `latest` |
| `babel-plugin-react-compiler` | 1.0.x (1.0 shipped 2025-10-07) | [React Compiler v1.0](https://react.dev/blog/2025/10/07/react-compiler-1) [official] |
| `eslint-plugin-react-hooks` | 7.1.1 | npm `latest`; rule list at [react.dev/reference/eslint-plugin-react-hooks](https://react.dev/reference/eslint-plugin-react-hooks) [official] |
| `next` | 16.4.3 | [nextjs.org/blog](https://nextjs.org/blog) [official], npm `latest` |
| `react-router` | 8.5.0 | npm `latest` |
| `vite` | 8.3.5 | npm `latest` |
| `@vitejs/plugin-react` | 6.x (`reactCompilerPreset` arrives in 6.0.0) | [compiler installation](https://react.dev/learn/react-compiler/installation) [official] |
| `typescript` | 7.0.2 | npm `latest` |
| `@tanstack/react-query` | 5.104.5 | npm `latest` |
| `eslint` | 10.13.0 | npm `latest` |
| `vitest` | 5.0.5 | npm `latest` |

React 19.0 = Dec 2024, 19.1 = Jun 2025, 19.2 = Oct 2025, 19.3 = Sep 2026. There is no React 20.

---

## Rules

### RC-01 — Keep the component body pure: no clocks, no randomness, no global writes during render

**Since** all (pure render has always been required; StrictMode double-invocation surfaced it since 16.3, and the compiler made it a hard bail-out in 19 — the `purity`/`globals` lints only exist in `eslint-plugin-react-hooks` 6+)

**Detection signals**
- In a function whose name is Capitalized or starts with `use`, before the `return`: `Date.now()`, argument-less `new Date()`, `Math.random()`, `crypto.randomUUID()`, `performance.now()`, `nanoid()`, `uuid()`. `new Date(value)` / `new Date(string)` is a pure parse and is not a signal.
- Writes to module scope or browser globals during render: `window.`, `document.`, `localStorage.setItem`, `document.cookie =`, `analytics.track(`, `console.log(` outside an event handler or Effect.
- A module-level `let` or object mutated inside the component body.
- `eslint-plugin-react-hooks` reports `purity` or `globals` for the component.
- Symptom: two different values on the server and client (hydration mismatch), or a value that changes on every re-render without any state change.

**Severity hint** High — hydration mismatch, broken memoization, and compiler bail-out.

**Refactor direction** Move the impure read out of render. Unique ids: `useId()`. Timestamps and randomness: compute once in `useState`'s lazy initializer or in the event handler that needs them.

```tsx
// before — new id every render, breaks keys and hydration
function Row() {
  const id = crypto.randomUUID();
  return <li id={id} />;
}

// after
function Row() {
  const id = useId();
  return <li id={id} />;
}
```

**Counter-signals** Reading `Date.now()` inside an event handler, an Effect, or a `"use client"`-only module evaluated at import time in a pure-SPA is fine. Parsing an existing timestamp or date string in render (`new Date(createdAt)`, `new Date(iso)`, `Intl.DateTimeFormat().format(date)`) is deterministic for the same input and is not impurity. Server Components are also never re-executed on the client, so a timestamp there is not an impurity — but it will differ from the client tree if the same value reaches a client component's render.

**Sources** React Team, [Rules of React — Components and Hooks must be pure](https://react.dev/reference/rules) (2024) [official]; React Team, [StrictMode](https://react.dev/reference/react/StrictMode) (2024) [official].

---

### RC-02 — Never mutate props or state in place

**Since** all

**Detection signals**
- Mutating calls on something bound from props or `useState`: `.push(`, `.pop(`, `.shift(`, `.unshift(`, `.splice(`, `.sort(`, `.reverse(`, `.fill(`.
- `props.x = …`, `obj.field = …` where `obj` came from props or state, or destructured from `useState`.
- `useState` holding a Map/Set that is mutated and then "refreshed" with `setMap(map)` / `setList([...list])` using the *same* array reference.
- `eslint-plugin-react-hooks` reports `immutability` or `set-state-in-render`.
- Symptom: a list that only updates after a second unrelated state change; children that never re-render because the reference is unchanged.

**Severity hint** High — silent stale UI: the DOM disagrees with the data, and `Object.is` bail-outs plus the compiler both treat the value as unchanged.

**Refactor direction** Copy before writing, and use the updater form so the copy starts from the latest state.

```tsx
// before
function add(item) { items.push(item); setItems(items); }

// after
function add(item) { setItems(prev => [...prev, item]); }

// before — sorting the prop reorders the parent's array
function Sorted({ rows }) { return <ul>{rows.sort(cmp).map(r => <li key={r.id}>{r.name}</li>)}</ul>; }

// after
function Sorted({ rows }) {
  const sorted = [...rows].sort(cmp);
  return <ul>{sorted.map(r => <li key={r.id}>{r.name}</li>)}</ul>;
}
```

**Counter-signals** Mutating a value you created during this render (a fresh `[...spread]`, a `new Map()` built locally) is fine. Mutating `ref.current` is not "props or state" — see RC-14.

**Sources** React Team, [Rules of React](https://react.dev/reference/rules) (2024) [official]; React Team, [Choosing the State Structure](https://react.dev/learn/choosing-the-state-structure) (2023) [official].

---

### RC-03 — Call Hooks unconditionally, at the top level, in the same order every render

**Since** all (Rules of Hooks, 16.8)

**Detection signals**
- A `use*` call lexically inside `if`, `else`, `for`, `while`, `switch`, `try`, or any nested function (including `useMemo(() => { … }, [])` callbacks).
- A `use*` call after an early `return` / `throw` in the same function.
- A `use*` call in a function whose name is neither capitalized nor `use`-prefixed.
- Two different `return` paths where one reaches more Hooks than the other.
- `rules-of-hooks` lint fires.
- Crash text in the field: `Rendered more hooks than during the previous render` or `Rendered fewer hooks than expected`.

**Severity hint** High — hard crash, not a degradation.

**Refactor direction** Hoist every Hook above the condition, then branch in JSX. Extract the conditional part into its own component so the conditional Hook becomes unconditional inside a component that only mounts when needed.

```tsx
// before
function Panel({ user, isAdmin }) {
  if (!user) return null;
  const perms = usePermissions();      // 🔴 skipped when user is null
  return <div>{perms.length}</div>;
}

// after
function Panel({ user, isAdmin }) {
  if (!user) return null;
  return isAdmin ? <AdminPanel /> : <UserPanel />;  // each child owns its Hooks
}
```

**Counter-signals** `use(resource)` may be called inside loops and conditionals — that is an explicit documented exception and does not violate the Rules of Hooks. `React 19` also warns when `use` is used conditionally in a way that is not a resource read.

**Sources** React Team, [eslint-plugin-react-hooks — rules-of-hooks](https://react.dev/reference/eslint-plugin-react-hooks) (2025) [official]; React Team, [use](https://react.dev/reference/react/use) (2024) [official].

---

### RC-04 — Do not use an Effect to derive state from props or from other state

**Since** all (the pattern is a bug on every React version; the `set-state-in-effect` lint that flags it mechanically only exists in `eslint-plugin-react-hooks` 6+, so on 4.x/5.x the reviewer must find it by reading the Effect)

**Detection signals**
- `useEffect` whose body's only work is one or more synchronous setters: `useEffect(() => { setX(f(props)) }, [props])`.
- `useState([])` followed by `useEffect(() => setItems(data), [data])`.
- `useEffect(() => { setIsLoading(true) }, [query])` — setting a loading flag synchronously in an Effect.
- `useEffect(() => { setFullName(first + ' ' + last) }, [first, last])`.
- Lint: `set-state-in-effect` (recommended preset since eslint-plugin-react-hooks 6) — absent on 4.x/5.x, so silence from the linter proves nothing.
- Measurable: React DevTools Profiler shows two commits per one user interaction, the first with identical DOM output.

**Severity hint** Medium — an extra full render + commit per change; on large trees, visible jank.

**Refactor direction** Compute during render. Keep an Effect only for actual external synchronisation.

```tsx
// before
const [items, setItems] = useState<Item[]>([]);
useEffect(() => { setItems(data.filter(d => d.active)); }, [data]);

// after — derive during render
const items = data.filter(d => d.active);
// or, if genuinely expensive:
const items = useMemo(() => expensiveFilter(data), [data]);
```

**Counter-signals** Legitimately needing two commits is rare but real: measuring DOM after a layout change, or a value that must lag behind (see `useDeferredValue`). A value that exists only on the client and cannot be known at render on the server — `localStorage`/`sessionStorage`, `window.matchMedia`, the browser time zone, `navigator` — is the documented hydration-safe pattern: render the server-safe default, then read it in an Effect and set state. On SSR frameworks (Next.js Pages Router, Remix, `renderToString`) this is correct, not a violation; on a pure client-only SPA the same read can happen in a lazy `useState` initialiser. Server or query data mirrored into state is a different root cause: report it once under `react-architecture` rule 2, not here. React Compiler does *not* remove this cost — it only memoizes, so the rule still applies with the compiler on.

**Sources** React Team, [You Might Not Need an Effect — Updating state based on props or state](https://react.dev/learn/you-might-not-need-an-effect) (2024) [official]; React Team, [set-state-in-effect](https://react.dev/reference/eslint-plugin-react-hooks/lints/set-state-in-effect) (2025) [official].

---

### RC-05 — Replace chains of Effects that feed each other with one event handler or a reducer

**Since** all

**Detection signals**
- Two or more `useEffect` blocks in one component where Effect A calls `setB`, and `b` appears in Effect B's dependency array, which calls `setC`, and so on.
- `useEffect` whose body begins with a guard on state that only another Effect writes.
- A component with 3+ `useEffect`s and 4+ `useState`s where the state names read like a pipeline (`card`, `count`, `round`, `isOver`).
- Profiler: N commits for a single click, where N ≈ number of Effects in the chain.

**Severity hint** Medium — quadratic render cost per interaction and a state machine nobody can trace.

**Refactor direction** Do the whole transition in the event handler that started it, using one state object, or move the logic into `useReducer`.

```tsx
// before: three Effects
useEffect(() => { if (card?.gold) setGold(g => g + 1); }, [card]);
useEffect(() => { if (gold > 3) { setRound(r => r + 1); setGold(0); } }, [gold]);
useEffect(() => { if (round > 5) setOver(true); }, [round]);

// after: one reducer, one dispatch
const [state, dispatch] = useReducer(gameReducer, initialState);
function handlePlay(card: Card) { dispatch({ type: 'play', card }); }
```

**Counter-signals** Effects that each own a genuinely independent external system (one for a WebSocket, one for `document.title`) are not a chain — do not merge them. React Compiler does not help here; the problem is the render count, not the identity of values.

**Sources** React Team, [You Might Not Need an Effect — Chains of computations](https://react.dev/learn/you-might-not-need-an-effect) (2024) [official].

---

### RC-06 — Any data fetch inside an Effect needs abort or ignore-stale cleanup

**Since** all

**Detection signals**
- `useEffect` containing `fetch(`, `axios.`, `ky(`, `got(`, `graphqlRequest`, `supabase.from(`, `firebase/…` with **no** `return () => …` that either aborts or flips an ignore flag.
- `.then(json => setResults(json))` with no `cancelled` / `ignore` guard and no `signal`.
- `new AbortController()` created but its `signal` never passed to `fetch`.
- Missing `controller.abort()` in the cleanup.
- Symptom: typing fast in a search box shows results for a prefix; `Warning: Can't perform a React state update on an unmounted component`; a `setState` after route change.
- Package signal: no data-fetching library in `package.json` (`@tanstack/react-query`, `swr`, `urql`, `@apollo/client`) while the codebase has ≥3 fetch-in-Effect sites.

**Severity hint** High — race conditions render wrong data, which users read as data loss.

**Refactor direction** Preferred: delete the Effect and use the framework's loader/RSC path or a query library. If the Effect must stay, ignore stale responses.

```tsx
useEffect(() => {
  const controller = new AbortController();
  let ignore = false;
  setResults(null);                                  // reset before re-fetch
  fetchResults(query, page, { signal: controller.signal })
    .then(json => { if (!ignore) setResults(json); })
    .catch(err => { if (!controller.signal.aborted) setError(err); });
  return () => { ignore = true; controller.abort(); };
}, [query, page]);
```

**Counter-signals** In Next.js App Router, fetch in a Server Component or a route handler instead — the rule does not apply, and adding an Effect fetch there is a regression. React Router 8 `loader`/`clientLoader` and TanStack Router loaders likewise remove the Effect entirely. `Suspense` does **not** catch a fetch started in an Effect, so wrapping such a component in `<Suspense>` is not a fix (RC-21).

**Sources** React Team, [You Might Not Need an Effect — Fetching data](https://react.dev/learn/you-might-not-need-an-effect) (2024) [official]; Dominik Dorfmeister, [Simplifying useEffect](https://tkdodo.eu/blog/simplifying-use-effect) (2021) [power-user].

---

### RC-07 — Never silence `exhaustive-deps`

**Since** all

**Detection signals**
- `// eslint-disable-next-line react-hooks/exhaustive-deps`, `// eslint-disable react-hooks/exhaustive-deps`, or a file-level `/* eslint-disable */` above a Hooks-heavy file.
- `eslint.config.*` setting `'react-hooks/exhaustive-deps': 'off'` or `'warn'` while the repo has zero suppressions — a signal the rule is not enforced at all.
- `}, [])` on an Effect whose body reads `props.*` or a `useState` value.
- `}, [someObj])` where `someObj` is re-created inline each render — the opposite failure: the Effect re-runs every render.
- `.eslintrc` `overrides` that disable the rule for `src/**`.

**Severity hint** Medium — stale closures produce bugs that only reproduce after a specific prop changes.

**Refactor direction** The disable comment is almost always one of three problems: (a) the value should be excluded because it is non-reactive — use `useEffectEvent` (RC-08); (b) the Effect should not exist (RC-04/RC-06); (c) a dependency is unstable and must be memoized or hoisted out of the component.

```tsx
// before
useEffect(() => { connection.on('connected', () => showToast(theme)); }, []); // eslint-disable-line

// after
const onConnected = useEffectEvent(() => showToast(theme));
useEffect(() => { connection.on('connected', onConnected); return () => connection.off('connected', onConnected); }, []);
```

**Counter-signals** A dependency that is a stable module-level constant (`import.meta.env.*` read into a const, a `useRef` object) legitimately stays out. Some third-party Hook APIs are genuinely unstable; wrap the *call site* in a custom Hook and suppress once there, not at twenty call sites.

**Sources** React Team, [Lifecycle of Reactive Effects](https://react.dev/learn/lifecycle-of-reactive-effects) (2024) [official]; React Team, [exhaustive-deps](https://react.dev/reference/eslint-plugin-react-hooks) (2025) [official].

---

### RC-08 — Use `useEffectEvent` for logic an Effect must read but must not re-subscribe for

**Since** 19.2 (stable)

**Detection signals**
- An Effect whose dependency array is kept short by omitting a prop, a state value, or a callback prop that its body reads.
- An Effect that re-subscribes (`addEventListener`, WebSocket `on`, `setInterval` reset) every time an unrelated value like `theme` or `toastText` changes.
- Callback props in an Effect's deps that are inline arrow functions from the parent.
- Pre-19.2 codebases: the `useRef` + `latest.current = fn` trick inside an Effect, or an `useRef` holding a "latest props" bag.
- `eslint-plugin-react-hooks` version < 7.1.1 → the linter will wrongly demand Effect Events as dependencies.

**Severity hint** Low–Medium — churn (reconnect storms, duplicate subscriptions) rather than a crash.

**Refactor direction** Wrap the non-reactive part in `useEffectEvent`, call it from the Effect, keep it out of the dependency array.

```tsx
// before: reconnects on every theme change
useEffect(() => {
  const c = createConnection(roomId);
  c.on('connected', () => showToast('Connected!', theme));
  c.connect();
  return () => c.disconnect();
}, [roomId, theme]);

// after
const onConnected = useEffectEvent(() => showToast('Connected!', theme));
useEffect(() => {
  const c = createConnection(roomId);
  c.on('connected', onConnected);
  c.connect();
  return () => c.disconnect();
}, [roomId]);
```

**Counter-signals** Do not wrap everything. A value the Effect genuinely reacts to (`roomId`, `url`) belongs in the deps. Effect Events may only be declared in the same component/Hook as their Effect, and may only be called from inside an Effect — calling one from a click handler is a bug. If the repo runs `eslint-plugin-react-hooks` < 7.1.1, upgrade before adopting.

**Sources** React Team, [React 19.2 — useEffectEvent](https://react.dev/blog/2025/10/01/react-19-2) (2025) [official]; React Team, [useEffectEvent](https://react.dev/reference/react/useEffectEvent) (2025) [official].

---

### RC-09 — Subscribe to external stores with `useSyncExternalStore`, not with an Effect

**Since** all. The hand-rolled `useState` + `useEffect` subscription is a tearing/stale-read bug on every version; `useSyncExternalStore` is the sanctioned fix from React 18, and on 16.8–17 the same contract is the `use-subscription` package (React's own, later deprecated) or a store hook that reads the snapshot during render and subscribes in an Effect. Server Components caveats start at 19.

**Detection signals**
- `useState` + `useEffect` + `addEventListener('online'|'offline'|'storage'|'change'|'resize'|'visibilitychange')` returning a cleanup: the classic hand-rolled store subscription.
- `useEffect(() => { const unsub = store.subscribe(() => setX(store.get())); return unsub; }, [])` over a third-party store (Zustand's vanilla store, a Redux store used directly, a media query, `matchMedia`).
- `useState(matchMedia('(prefers-color-scheme: dark)').matches)` read at render — a value React does not know can change.
- Missing `getServerSnapshot` in a component that renders on the server → `Missing getServerSnapshot` throw or a hydration mismatch.
- `getSnapshot` that returns a fresh object/array each call → infinite re-render loop (`The result of getSnapshot should be cached`).

**Severity hint** Medium — tearing under concurrent rendering: two components in one commit showing different values of the same store.

**Refactor direction** Pass `subscribe`, `getSnapshot` and (for SSR) `getServerSnapshot`. The snapshot must be a stable primitive or a cached object reference.

```tsx
// before
function useOnline() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    addEventListener('online', update); addEventListener('offline', update);
    return () => { removeEventListener('online', update); removeEventListener('offline', update); };
  }, []);
  return online;
}

// after
const subscribe = (cb: () => void) => {
  addEventListener('online', cb); addEventListener('offline', cb);
  return () => { removeEventListener('online', cb); removeEventListener('offline', cb); };
};
const getSnapshot = () => navigator.onLine;
const getServerSnapshot = () => true;
const useOnline = () => useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
```

**Counter-signals** If the library already exposes a React binding (`useSelector`, `useStore`, Zustand's hook), use that — it is built on `useSyncExternalStore` internally. In a pure client SPA `getServerSnapshot` is optional; in Next.js / React Router SSR it is required.

**Sources** React Team, [useSyncExternalStore](https://react.dev/reference/react/useSyncExternalStore) (2024) [official]; React Team, [You Might Not Need an Effect — Subscribing to an external store](https://react.dev/learn/you-might-not-need-an-effect) (2024) [official].

---

### RC-10 — Use stable, data-derived keys; never an index in a list that can reorder

**Since** all

**Detection signals**
- `key={index}`, `key={i}`, `key={idx}`, `key={position}` inside a `.map` whose array can be sorted, filtered, prepended to, or spliced.
- Keyless `.map` returning JSX (console warning `Each child in a list should have a unique "key" prop`).
- `key={Math.random()}`, `key={crypto.randomUUID()}`, `key={uuid()}`, `key={JSON.stringify(obj)}` — new key every render, so the subtree remounts every render.
- `key={item.name}` or `key={item.title}` on data where two rows can share the value (React dedupes and warns).
- Symptom: an `<input>`'s value jumps to a neighbour's row after a delete; focus lands on the wrong row; a `<details>` collapses on sort.

**Severity hint** High for unstable or random keys (state loss, focus loss, screen-reader confusion, full subtree remount per render); Medium for index keys in genuinely static lists.

**Refactor direction** Key from the entity id. If the data has no id, add one at the boundary where the data enters the app, not inside the render.

```tsx
// before
{rows.map((row, i) => <Row key={i} row={row} />)}

// after
{rows.map(row => <Row key={row.id} row={row} />)}
```

**Counter-signals** Index keys are acceptable when the list is immutable for its lifetime (a static menu, a fixed set of tabs rendered from a literal array) — there is nothing to reorder. Deriving a key from content (`${a}-${b}`) is fine only if the concatenation is genuinely unique and stable.

**Sources** React Team, [Rendering Lists — Rules of keys](https://react.dev/learn/rendering-lists) (2023) [official].

---

### RC-11 — Reset a component's state with `key`, not with a reset Effect

**Since** all

**Detection signals**
- `useEffect(() => { setComment(''); setDraft(null); setTab(0); }, [userId])` — a multi-setter Effect keyed on an entity id.
- `useEffect(() => { if (prevId !== id) { setX(initial) } }, [id])`.
- A component receiving an `id`/`userId`/`productId` prop that owns 3+ pieces of local state and never gets a key at its call site.
- `<Profile id={id} />` where `id` changes on navigation and the component keeps stale state.

**Severity hint** Low–Medium — one wasted render, plus state that can be observed mid-transition.

**Refactor direction** Give the component a `key` equal to the identity that should own the state. React discards the old state and mounts fresh.

```tsx
// before
function Profile({ userId }: { userId: string }) {
  const [comment, setComment] = useState('');
  useEffect(() => { setComment(''); }, [userId]);
  // …
}

// after — parent
<Profile key={userId} userId={userId} />
```

**Counter-signals** Do not key a subtree that must keep its DOM (an animated container, a `<video>`, an element with a `ViewTransition` in flight) — the remount restarts it. If the intent is to *preserve* state across navigation instead of resetting it, that is `<Activity>`, not a key (RC-24). Keying also discards scroll position and focus, so do not key on a value that changes per keystroke.

**Sources** React Team, [Preserving and Resetting State](https://react.dev/learn/preserving-and-resetting-state) (2023) [official]; React Team, [You Might Not Need an Effect — Resetting all state when a prop changes](https://react.dev/learn/you-might-not-need-an-effect) (2024) [official].

---

### RC-12 — Hold the minimum state: no redundancy, no contradictions, no mirrored props, no duplicated objects

**Since** all

**Detection signals**
- Redundant: a `useState` whose value is computable from other state or props — `total`/`count`/`isEmpty`/`filtered`/`fullName`/`isValid` sitting alongside the inputs they derive from.
- Contradictory: two booleans that encode one status — `isSending` + `isSent`, `isLoading` + `error` + `data` as three independent `useState`s.
- Mirrored props: `const [x, setX] = useState(props.x)` (React's own example of a bug: `setX` never sees later prop changes, and the prop change is silently dropped).
- Duplicated objects: storing the selected item object *and* its id, or storing a copy of a row from the list (`selectedUser`) that goes stale when the list refreshes.
- `useState` with 5+ independent fields that always change together → one object or a reducer is missing.

**Severity hint** Medium — the two copies drift and the UI contradicts itself.

**Refactor direction** Derive what can be derived during render; store the id, look the object up from the source list; collapse mutually exclusive booleans into one union or into the state object that Actions already give you.

```tsx
// before — two sources of truth, can contradict
const [isSending, setIsSending] = useState(false);
const [isSent, setIsSent] = useState(false);

// after — one status
const [status, setStatus] = useState<'idle' | 'sending' | 'sent'>('idle');

// before — duplicated object goes stale
const [selected, setSelected] = useState<User | null>(null);
// after — id only
const [selectedId, setSelectedId] = useState<string | null>(null);
const selected = users.find(u => u.id === selectedId) ?? null;
```

**Counter-signals** "Mirroring" is legitimate when the prop is only an *initial* value and the intent is explicitly "uncontrolled" — then name it `initialX` (or `defaultValue`) so the contract is visible. When the redundant state is a copy of server or query data (`useState(query.data)`, 18 fields synced by one Effect), the root cause is where server state lives: report it once under `react-architecture` rule 2 (with rule 1 if the fetch itself is in an Effect), and do not double-count it here. RC-12 is for state that is derivable from *client* state or props.

**Sources** React Team, [Choosing the State Structure](https://react.dev/learn/choosing-the-state-structure) (2023) [official].

---

### RC-13 — Colocate state with its only consumer; do not lift it to the page root by reflex

**Since** all

**Detection signals**
- A `useState` in a route/page component whose value is read by exactly one descendant, passed through ≥2 intermediate components that never read it (prop drilling).
- A text input's `value`/`onChange` living in the same component that renders a long list, a chart, or a data table — every keystroke re-renders the whole subtree.
- A context provider mounted at the app root for state that only one route subtree reads.
- Profiler: a single keystroke produces ≥50 component renders, or a commit whose duration scales with list length while the input is what changed.
- `React.memo` sprinkled on 10+ leaf components in an attempt to stop the cascade — a symptom, not a fix.

**Severity hint** Medium — measurable per-interaction cost; on large trees it is the difference between a responsive and a laggy form.

**Refactor direction** Push state down to the smallest component that needs it. Where a stateful wrapper must re-render often, pass the expensive subtree as `children` so its element identity is preserved and it is not re-rendered.

```tsx
// before — every keystroke re-renders <ExpensiveTree />
function Page() {
  const [q, setQ] = useState('');
  return (<><input value={q} onChange={e => setQ(e.target.value)} /><ExpensiveTree /></>);
}

// after — ExpensiveTree arrives as children, so it is not re-rendered
function SearchBox({ children }: { children: ReactNode }) {
  const [q, setQ] = useState('');
  return (<><input value={q} onChange={e => setQ(e.target.value)} />{children}</>);
}
function Page() { return <SearchBox><ExpensiveTree /></SearchBox>; }
```

**Counter-signals** State shared by siblings must be lifted — that is not over-lifting. With React Compiler enabled, memoization of `children` and of JSX subtrees is automatic, so some of this cascade disappears; the structural fix is still worth making because the compiler cannot skip re-rendering a component whose own state changed. For an input that filters a large list, `useDeferredValue` or `startTransition` is the cheaper fix than restructuring.

**Sources** React Team, [Passing Data Deeply with Context — Before you use context](https://react.dev/learn/passing-data-deeply-with-context) (2023) [official]; React Team, [Preserving and Resetting State](https://react.dev/learn/preserving-and-resetting-state) (2023) [official].

---

### RC-14 — A ref is not state: never drive rendered output from `ref.current`

**Since** all

**Detection signals**
- `ref.current = value` followed by nothing, where `value` appears in the returned JSX.
- Reading `ref.current` during render (outside `useEffect`/`useLayoutEffect`/event handlers) — e.g. `{ref.current?.offsetHeight}` in JSX, or `const x = ref.current` at the top of the body.
- The `useRef` + force-update pattern: `const [, force] = useState(0); ref.current.x = 1; force(n => n + 1)`.
- `useRef` holding a "previous value" or a mutable accumulator that is then compared during render to decide what to show.
- `useRef` used to store `isMounted`, `didInit`, `prevProps` and then to branch in JSX.
- Symptom: UI that is stale until an unrelated state change; a value that differs between StrictMode's two renders.

**Severity hint** Medium — the UI is out of sync with its own data, and the compiler treats it as an impurity (`refs` diagnostic).

**Refactor direction** If React should render it, it is state. If it must survive renders without causing one, it is a ref — and then it must never be read during render.

```tsx
// before — nothing re-renders
const count = useRef(0);
const increment = () => { count.current++; };

// after
const [count, setCount] = useState(0);
const increment = () => setCount(c => c + 1);
```

**Counter-signals** Refs are correct for: DOM nodes, timer/interval ids, "latest callback" storage that Effects read, subscription handles, and one-time initialisation guards. `useLayoutEffect` reading `ref.current` to measure the DOM is idiomatic. React 19.3's Fragment Refs (`<Fragment ref={…}>` → `FragmentInstance` with `focus()`, `observeUsing(observer)` / `unobserveUsing(observer)` and `scrollIntoView()`) exist precisely for the "group of siblings, no wrapper element" case.

**Sources** React Team, [useRef — Caveats](https://react.dev/reference/react/useRef) (2024) [official]; React Team, [React 19.3 — Fragment Refs](https://react.dev/blog/2026/09/09/react-19-3) (2026) [official].

---

### RC-15 — Pass `ref` as a normal prop; stop using `forwardRef`

**Since** 19 (`forwardRef` deprecated)

**Detection signals**
- `import { forwardRef } from 'react'` anywhere.
- `const X = forwardRef(function X(props, ref) { … })` / `forwardRef<HTMLDivElement, Props>((props, ref) => …)`.
- `forwardRef` + `useImperativeHandle` pairs in a component that has no other reason to exist.
- Access to `element.ref` on a React element (removed in 19; `element.props.ref` is the supported read).
- `.d.ts` files with `React.forwardRef<…>` in library-facing types.

**Severity hint** Low — friction plus a future removal; not a runtime bug today.

**Refactor direction** Accept `ref` in props with a normal type. In React 19, function components receive `ref` like any other prop.

```tsx
// before
const Input = forwardRef<HTMLInputElement, Props>((props, ref) => (
  <input {...props} ref={ref} />
));

// after
function Input({ ref, ...props }: Props & { ref?: Ref<HTMLInputElement> }) {
  return <input {...props} ref={ref} />;
}
```

**Counter-signals** `useImperativeHandle` is still the correct tool for exposing an imperative API; only the `forwardRef` wrapper is obsolete — in React 19 it can take `ref` from props directly. Libraries that support React 17/18 must keep `forwardRef` (the compiler itself supports 17+), so a library `.d.ts` using it is not a defect. `forwardRef` still works in 19.3; deprecation is announced, removal is not scheduled.

**Sources** React Team, [forwardRef](https://react.dev/reference/react/forwardRef) (2024) [official]; Ricky Hanlon, [React 19 Upgrade Guide](https://react.dev/blog/2024/04/25/react-19-upgrade-guide) (2024) [official].

---

### RC-16 — Use form Actions (`useActionState`, `useOptimistic`, `useFormStatus`) instead of hand-rolled pending/error state

**Since** 19

**Detection signals**
- `const [isPending, setIsPending] = useState(false)` next to `onSubmit={async (e) => { e.preventDefault(); setIsPending(true); try {…} catch {…} finally { setIsPending(false) } }}`.
- `setError(e.message)` inside a submit handler, rendered as `{error && <p>…</p>}`.
- `e.preventDefault()` on a `<form>` whose only purpose is to call one async function.
- A submit button that renders `{isPending ? 'Saving…' : 'Save'}` from a local `isPending` instead of `useFormStatus().pending` in a child component.
- `useState` tracking "optimistically added row" alongside the confirmed list, with manual rollback in a `catch`.
- `useTransition` wrapping a submit handler by hand where `useActionState` would give `isPending` for free.

**Severity hint** Low–Medium — three-state boilerplate repeated per form, with the usual gaps (no double-submit guard, no rollback, reset lost on error).

**Refactor direction** Pass an async function to `<form action={…}>`; read the returned state and pending flag from `useActionState`; use `useOptimistic` for the optimistic row; use `useFormStatus` inside the submit button (it must be a child component — it reads the *parent* form's status).

```tsx
// before: manual isPending + error + reset
// after:
const [error, submit, isPending] = useActionState(async (_prev, formData: FormData) => {
  const res = await updateName(String(formData.get('name')));
  return res.error ?? null;
}, null);

return (
  <form action={submit}>
    <input name="name" defaultValue={name} />
    <SubmitButton />          {/* calls useFormStatus().pending */}
    {error && <p role="alert">{error}</p>}
  </form>
);
```

**Counter-signals** A form library (`react-hook-form`, TanStack Form, Conform) with its own submission model is not a defect — do not rewrite it. Framework specifics: Next.js App Router Server Actions are the intended target for `<form action>`; in a Vite SPA client Actions still work (function actions run on the client), but there is no server round-trip. React Router 8 `<Form>`/`fetcher` has its own submission API — mixing both in one form is worse than either.

**Sources** React Team, [React v19 — Actions](https://react.dev/blog/2024/12/05/react-19) (2024) [official]; React Team, [useActionState](https://react.dev/reference/react/useActionState) (2024) [official]; React Team, [useFormStatus](https://react.dev/reference/react-dom/hooks/useFormStatus) (2024) [official].

---

### RC-17 — Render `<title>`/`<meta>`/`<link>` and use `react-dom` preload APIs instead of Effect-driven head manipulation

**Since** 19 (metadata tags and preload APIs)

**Detection signals**
- `package.json` dependencies: `react-helmet`, `react-helmet-async`, `react-side-effect`, `next/head` imported from a `"use client"` file in an App Router project.
- `useEffect(() => { document.title = … })`, `document.querySelector('meta[name=description]')?.setAttribute(…)`, `document.head.appendChild(link)`.
- A `<link rel="preload">` written by hand into `index.html` (or injected in an Effect) for a route-specific asset, or client-side `new FontFace(...)` + `document.fonts.add` where `preload(href, { as: 'font' })` would do.
- `react-helmet-async` still in `package.json` while `react` is `^19`.

**Severity hint** Low — friction; measurable only when it costs an LCP round-trip or a duplicate `<title>`.

**Refactor direction** Render the tags from the component that knows the data; React hoists them into `<head>`. For eagerly needed assets, call the `react-dom` import for the resource kind.

```tsx
// before
useEffect(() => { document.title = post.title; }, [post.title]);

// after
function BlogPost({ post }: { post: Post }) {
  return (
    <article>
      <title>{post.title}</title>
      <meta name="author" content={post.author} />
      <h1>{post.title}</h1>
    </article>
  );
}
```

For a route-specific hero image or font: `preload(url, { as: 'image' })` / `preinit(url, { as: 'style' })` / `preconnect(origin)` / `prefetchDNS(host)` from `react-dom`.

**Counter-signals** Framework-specific: Next.js App Router has `export const metadata` / `generateMetadata` — use that rather than raw `<title>` tags, and never `next/head` from a Server Component. React Router 8 has its own `meta` export. On React 17/18 — and therefore on any Next.js Pages Router app — `next/head` (or React Helmet) is the supported API; a `<title>` tag rendered in the component body is inert there, so this rule is dropped, not applied. Plain `<title>`/`<meta>` rendering is lowest priority for dedupe/override logic, so a metadata library is still legitimate when you need cascading overrides across nested routes.

**Sources** React Team, [React v19 — Support for Document Metadata](https://react.dev/blog/2024/12/05/react-19) (2024) [official]; React Team, [preload](https://react.dev/reference/react-dom/preload) (2024) [official].

---

### RC-18 — With React Compiler enabled, delete manual `useMemo`/`useCallback`/`memo` used only for referential stability

**Since** React Compiler 1.0 (stable 2025-10-07)

**Detection signals**
- Compiler is on: `reactCompiler: true` in `next.config.*`, or `reactCompilerPreset()` from `@vitejs/plugin-react` ≥ 6 in `vite.config.*`, or `'babel-plugin-react-compiler'` in `babel.config.*`, or `babel-plugin-react-compiler` in `devDependencies` with a wired build.
- AND: `useMemo(() => x, [])` whose body is a cheap expression; `useCallback(fn, [deps])` passed to a child that is itself compiled; `React.memo(function X…)` wrapping a component whose only unstable prop was a callback.
- Density signal: `useCallback` appears more than `useState` in a file — memoisation as a reflex.
- Already-present but broken: `useCallback` with a missing dep, plus an inline `onClick={() => handle(item)}` next to it — manual memoisation that never worked.

**Severity hint** Low — noise and maintenance cost; the hooks become load-bearing-looking code that does nothing.

**Refactor direction** Delete the wrapper. Keep the inner function/expression. Verify the compiler actually covers the file (see RC-19) before deleting.

```tsx
// before (compiler on)
const handleClick = useCallback((id: string) => onClick(id), [onClick]);
const total = useMemo(() => items.reduce((s, i) => s + i.price, 0), [items]);

// after
const handleClick = (id: string) => onClick(id);
const total = items.reduce((s, i) => s + i.price, 0);
```

**Counter-signals** Keep `useMemo` when the identity is *semantically* load-bearing, not merely performance: a value passed into another Hook's dependency array that must not retrigger it, a context `value` consumed by a non-compiled subtree, an argument to `useSyncExternalStore`'s `subscribe`, a deps entry of a `useEffect` whose re-run is destructive, or a value handed to a third-party library that compares by reference. Also keep `memo` around a component whose parent is *not* compiled (a JSX element from a non-compiled file cannot be stabilized). `useMemo` is never a correctness guarantee — React may discard memoised values — so it must not be used to make an impure expression "safe".

**Sources** Lauren Tan, Joe Savona, Mofei Zhang, [React Compiler v1.0](https://react.dev/blog/2025/10/07/react-compiler-1) (2025) [official]; React Team, [React Compiler introduction](https://react.dev/learn/react-compiler/introduction) (2025) [official]; Josh W. Comeau, [Understanding useMemo and useCallback](https://www.joshwcomeau.com/react/usememo-and-usecallback/) (2022) [power-user].

---

### RC-19 — Treat every React Compiler bailed-out component as a defect, not a setting

**Since** React Compiler 1.0

**Detection signals**
- `"use no memo"` / `"use no forget"` string directives in source. Count them: each is a component the compiler silently skips. Cap at 0 for new code.
- Compiler config in `infer` mode (the default) — heuristics skip components; `annotation` mode means **only** `"use memo"` files are compiled, so check which mode is set.
- `eslint-plugin-react-hooks` `recommended` diagnostics firing on React Compiler rules: `component-hook-factories`, `error-boundaries`, `gating`, `purity`, `refs`, `set-state-in-effect`, `set-state-in-render`, `static-components`, `preserve-manual-memoization`, `immutability`, `globals`, `unsupported-syntax`, `incompatible-library`, `use-memo`, `config`.
- `incompatible-library` is the one to read carefully: a library that mutates its arguments (some chart, form and animation libs) poisons the call site.
- A component defined inside another component's body (`function Inner() {}` in the render path) — `static-components`; a new type every render, so it always remounts regardless of the compiler.
- Hooks called from a factory/HOC that builds components at runtime — `component-hook-factories`.

**Severity hint** Medium — a silent performance cliff: the file looks compiled, is not, and manual memoisation was deleted elsewhere (RC-18).

**Refactor direction** Fix the impurity rather than the annotation. Hoist nested component definitions to module scope; give props instead of closing over the parent's scope; stop mutating library arguments — copy them first.

```tsx
// before — new component type each render, always remounts, compiler skips it
function Page({ rows }: { rows: Row[] }) {
  function Row({ r }: { r: Row }) { return <li>{r.name}</li>; }
  return <ul>{rows.map(r => <Row key={r.id} r={r} />)}</ul>;
}

// after
function Row({ r }: { r: Row }) { return <li>{r.name}</li>; }
function Page({ rows }: { rows: Row[] }) {
  return <ul>{rows.map(r => <Row key={r.id} r={r} />)}</ul>;
}
```

**Counter-signals** `"use no memo"` is the documented, legitimate escape hatch while debugging — it just must not be permanent. Vendored or generated files may stay opted out. Diagnosis of *why* a component is skipped requires the compiler's debugging output, not guesswork; a non-zero `use no memo` count is a prompt to look, not automatically a bug.

**Sources** React Team, [eslint-plugin-react-hooks](https://react.dev/reference/eslint-plugin-react-hooks) (2025) [official]; React Team, [Directives](https://react.dev/reference/react-compiler/directives) and ["use no memo"](https://react.dev/reference/react-compiler/directives/use-no-memo) (2025) [official]; React Team, [React Compiler installation](https://react.dev/learn/react-compiler/installation) (2025) [official]; Next.js, [reactCompiler config](https://nextjs.org/docs/app/api-reference/config/next-config-js/reactCompiler) (2026) [official].

---

### RC-20 — Stop using Context as a state-management bus; memoise its value and split it

**Since** all

**Detection signals**
- `<Ctx.Provider value={{ a, b, setA, setB }}>` — a fresh object literal every render; with the compiler *off*, every consumer re-renders on every provider render.
- One `AppContext` carrying user, theme, locale, feature flags, cart, modal state and toasts.
- `useContext(AppContext)` in a leaf that destructures exactly one field.
- A provider mounted at the app root (above the router) for state only one route reads.
- `memo(Component)` on consumers, added in an attempt to stop context propagation — it does not work: `memo` cannot prevent a child from receiving a new context value.
- Symptom: typing in one form re-renders a distant sidebar; Profiler shows the provider's entire subtree committing on unrelated state.

**Severity hint** Medium — a whole-subtree re-render per provider render, and a component that is impossible to test in isolation.

**Refactor direction** Split by change frequency (a static `ThemeContext` separate from a fast-changing `CartContext`); memoise the value object; prefer props or `children` for one-hop data.

```tsx
// before
<AppCtx.Provider value={{ user, theme, setTheme }}>{children}</AppCtx.Provider>

// after
const themeValue = useMemo(() => ({ theme, setTheme }), [theme]);
<ThemeCtx.Provider value={themeValue}>
  <UserCtx.Provider value={user}>{children}</UserCtx.Provider>
</ThemeCtx.Provider>
```

**Counter-signals** The docs' ordering is explicit: pass props first, then pass JSX as `children` to cut out intermediate layers, and only then reach for context. The legitimate uses are theming, the current account, and routing. With React Compiler enabled the inline `value={{}}` object *is* auto-memoized — so the memoisation half of this rule stops being a finding, while the split/colocation half still applies. Deep-consumer subscriptions with selector semantics need a store (Zustand, Redux, `useSyncExternalStore`), not context. This rule owns the *shape and memoisation* of a context value; when the finding is "a context is being used as the app's state bus, providers should sit lower, split by change frequency", that is an architecture finding — report it under `react-architecture` rule 10 and cite RC-20 only for the inline-object identity churn, never as a second finding for the same provider.

**Sources** React Team, [Passing Data Deeply with Context — Before you use context](https://react.dev/learn/passing-data-deeply-with-context) (2023) [official]; React Team, [useContext — Caveats](https://react.dev/reference/react/useContext) (2024) [official].

---

### RC-21 — Place Suspense and Error Boundaries at the granularity of a recoverable region

**Since** all. Error boundaries exist since React 16 and `Suspense`/`lazy` since 16.6, so a missing or misplaced boundary is a defect on every version. Version differences are in the refactor, not the rule: SSR streaming of suspended content needs React 18, and 19 improves reveal order.

**Detection signals**
- No error boundary anywhere: `grep -L 'ErrorBoundary\|componentDidCatch\|getDerivedStateFromError\|react-error-boundary'` across route files, and `react-error-boundary` absent from `package.json` — one thrown render blanks the whole app.
- A single boundary at the root only, wrapping `<App />`, so a failing sidebar kills the page.
- A boundary around every leaf (`<ErrorBoundary><Avatar /></ErrorBoundary>`) — React's own guidance says an avatar-sized region is too small.
- `<Suspense>` wrapping a component that fetches in `useEffect` — it will never show its fallback, because Suspense does not detect Effect fetches.
- `lazy(() => import(…))` with no `<Suspense>` above it → `A component suspended while rendering, but no fallback UI was specified`, or a blank area where the lazy chunk should be.
- `<Suspense fallback={null}>` on a route-level boundary — layout shift with no loading signal.
- Error boundaries placed *inside* the component that throws (they only catch descendants).

**Severity hint** High for a missing root boundary (one bug = blank screen, unrecoverable without reload); Medium for wrong granularity.

**Refactor direction** One boundary per region a user can meaningfully retry (route, panel, message row). Keep the root boundary as the last resort. Put `<Suspense>` around the component that *reads* suspended data, and give it a fallback shaped like the content.

```tsx
<ErrorBoundary fallback={<PanelError onRetry={refetch} />}>
  <Suspense fallback={<MessagesSkeleton />}>
    <Messages />          {/* suspends on a promise/resource, not on an Effect fetch */}
  </Suspense>
</ErrorBoundary>
```

**Counter-signals** Error boundaries must still be class components — there is no Hook form, so `react-error-boundary` (or one hand-written class) is the standard answer; its presence is not "legacy code". A boundary that is intentionally high because the region has no local recovery (a checkout step) is fine. In Next.js App Router, `error.tsx` and `loading.tsx` already provide per-route boundaries — hand-rolled ones duplicate them. The Pages Router has neither: its equivalents are `_error.tsx` (fatal/page-level), a route-level class boundary or `react-error-boundary`, and `next/dynamic`'s `loading` option for a chunk — so a hand-rolled boundary there is the fix, not duplication. Suspense itself does not preserve state for content that suspended before first mount.

**Sources** React Team, [Suspense — Caveats](https://react.dev/reference/react/Suspense) (2024) [official]; React Team, [Component — Catching rendering errors with an Error Boundary](https://react.dev/reference/react/Component) (2024) [official].

---

### RC-22 — Run StrictMode in development, and treat every double-invocation as a real bug

**Since** 18 (dev-only double-mount of Effects); 19.3 also double-invokes Effects during hydration

**Detection signals**
- `<StrictMode>` absent from the client entry (`main.tsx`, `index.tsx`, `app/layout.tsx`). Grep: `createRoot(` whose argument is not `<StrictMode>`.
- `<StrictMode>` present but commented out, or removed in a commit with a message about "double fetch".
- Symptoms in dev only: two GET requests per mount, two WebSocket connections, two analytics events, two `setInterval`s running, a counter incrementing by 2.
- Suppressions added *because of* StrictMode: `if (didInit.current) return;` used to hide duplicate subscriptions, `useRef` mount guards around fetches.

**Severity hint** Medium — the double-invocation is a detector; removing it hides the leak rather than fixing it.

**Refactor direction** Keep StrictMode on. Make every Effect idempotent: it must clean up exactly what it set up, so mount → unmount → mount leaves one subscription, not two.

```tsx
// before — leaks: no cleanup, so StrictMode shows two connections
useEffect(() => { const c = createConnection(roomId); c.connect(); }, [roomId]);

// after
useEffect(() => {
  const c = createConnection(roomId);
  c.connect();
  return () => c.disconnect();
}, [roomId]);
```

**Counter-signals** StrictMode is development-only; production does not double-invoke, so a bug that *only* exists because of double-invocation and is otherwise correct (a third-party script that cannot be torn down, a payment SDK) is a reason to keep the Effect out of the double-invoked path, not to remove StrictMode. React Query dedupes requests, which is why some StrictMode duplicate fetches are invisible.

**Sources** React Team, [StrictMode](https://react.dev/reference/react/StrictMode) (2024) [official]; React Team, [React 19.3 changelog](https://react.dev/blog/2026/09/09/react-19-3) (2026) [official]; React Team, [Lifecycle of Reactive Effects](https://react.dev/learn/lifecycle-of-reactive-effects) (2024) [official].

---

### RC-23 — Remove class components and the APIs React 19 deleted

**Since** 19 for the removals; the class-component migration is open-ended but these APIs now fail hard

**Detection signals**
- `extends React.Component`, `extends Component`, `extends PureComponent` in `src/`.
- `defaultProps` on a **function** component (`X.defaultProps = {...}` or `X.defaultProps` in a `.d.ts`) — removed in 19; only `defaultProps` on classes still works.
- `propTypes` / `X.propTypes = {...}` — removed in 19; the `prop-types` package is now dead weight.
- String refs: `ref="input"`, `this.refs.input` — removed.
- `ReactDOM.findDOMNode(this)` — removed.
- Legacy context: `contextTypes`, `childContextTypes`, `getChildContext` — removed.
- `ReactDOM.render(...)`, `ReactDOM.hydrate(...)`, `unmountComponentAtNode(...)` — removed; `createRoot` / `hydrateRoot` only.
- `react-test-renderer` in `package.json` — deprecated in 19.
- Legacy lifecycles still in classes: `componentWillMount`, `componentWillReceiveProps`, `componentWillUpdate`.
- `import React from 'react'` in every file with no other React reference (the JSX transform has been automatic since 17) — dead import, and a false signal about the React version.

**Severity hint** High for the removed APIs (the app throws on React 19); Medium for the remaining class components (no Hooks, no compiler coverage, `this` bugs).

**Refactor direction** Class → function component with Hooks; `createRoot` for the entry; `ref` callback for string refs; `useContext` for legacy context; plain parameters + TypeScript for defaults.

```tsx
// before
class Greeting extends React.Component {
  render() { return <h1>Hello, {this.props.name}</h1>; }
}
Greeting.defaultProps = { name: 'world' };

// after
function Greeting({ name = 'world' }: { name?: string }) {
  return <h1>Hello, {name}</h1>;
}
```

**Counter-signals** Error boundaries and `getSnapshotBeforeUpdate` have no Hook equivalent — those two class components are legitimate. A dependency that still supports React 17/18 may keep `defaultProps` on a class. Third-party `node_modules` hits are out of scope; only report first-party source.

**Sources** Ricky Hanlon, [React 19 Upgrade Guide — Removed APIs](https://react.dev/blog/2024/04/25/react-19-upgrade-guide) (2024) [official]; React Team, [React v19](https://react.dev/blog/2024/12/05/react-19) (2024) [official].

---

### RC-24 — Replace mounted-state and CSS-hide hacks with `<Activity>` and `browser()`

**Since** 19.2 (`<Activity>`), 19.3 (`browser()`)

**Detection signals**
- The classic mount flag: `const [mounted, setMounted] = useState(false); useEffect(() => setMounted(true), []); if (!mounted) return null;` — the React 19.3 replacement is `use(browser())`.
- `typeof window !== 'undefined'` / `typeof document !== 'undefined'` used to branch what renders, rather than to guard a module-scope access.
- `style={{ display: isVisible ? 'block' : 'none' }}` on a subtree that should keep its state, or `{isVisible && <Panel />}` where the state should survive being hidden.
- Hand-rolled keep-alive: rendering all tabs and toggling `hidden`/`visibility`/`opacity` to preserve form state and scroll position.
- A `mounted`/`hydrated` flag used purely to suppress a hydration mismatch warning.

**Severity hint** Low–Medium — an extra render pass, `null` flashes, and layout/state thrown away on every toggle.

**Refactor direction** `use(browser())` opts a component out of server rendering. `<Activity mode="hidden">` hides, unmounts Effects and defers updates while preserving state and DOM for the next reveal.

```tsx
// before
const [mounted, setMounted] = useState(false);
useEffect(() => setMounted(true), []);
if (!mounted) return null;
return <LocalTime />;

// after (SSR app)
use(browser());
return <LocalTime />;

// before — state lost on every tab switch
{tab === 'form' && <Form />}

// after — state kept, Effects torn down while hidden
<Activity mode={tab === 'form' ? 'visible' : 'hidden'}><Form /></Activity>
```

**Counter-signals** `browser()` is meaningless in a client-only SPA — there is no server render to opt out of, so the mount flag was already unnecessary there. `Activity` in `hidden` mode **unmounts Effects**, so it is wrong for anything that must keep polling, streaming, or listening; it also renders with `display: none`, which does not preserve layout measurements. `typeof window !== 'undefined'` inside a `useEffect` body, or at module scope to pick an adapter, remains correct and is not this pattern.

**Sources** React Team, [React 19.2 — Activity](https://react.dev/blog/2025/10/01/react-19-2) (2025) [official]; React Team, [Activity](https://react.dev/reference/react/Activity) (2025) [official]; React Team, [React 19.3 — browser](https://react.dev/blog/2026/09/09/react-19-3) (2026) [official].

---

### RC-25 — In RSC code, tie cached work to `cacheSignal()` so aborted renders stop working

**Since** 19.2 (Server Components only)

**Detection signals**
- Next.js App Router or any RSC setup (`"use client"` directives present, `experimental.reactServerComponents`, a `server/` layer) with `cache(fetch)` / `cache(loadUser)` where the wrapped function does **not** accept or forward a `signal`.
- `await longQuery()` inside a `cache()`d function with no `cacheSignal()` abort path.
- A `cache()`d function that starts a background job on first call and never cancels it when the render aborts (user navigated away).
- Long-running `cache()`d fetches without `AbortSignal` → the server keeps executing after the response is gone.

**Severity hint** Low (correctness) / Medium (wasted server work and leaked connections under navigation churn).

**Refactor direction** Pass `signal: cacheSignal()` into the underlying I/O; it aborts when the rendering completes, is aborted, or fails.

```ts
import { cache, cacheSignal } from 'react';

const getUser = cache(async (id: string) => {
  const res = await fetch(`/api/users/${id}`, { signal: cacheSignal() });
  return res.json();
});
```

**Counter-signals** Client Components cannot use `cacheSignal` — this rule only applies to RSC modules. A `cache()`d function whose work is cheap and synchronous has nothing to abort. Projects on Vite + React Router 8 SPA have no RSC and no `cache()`.

**Sources** React Team, [React 19.2 — cacheSignal](https://react.dev/blog/2025/10/01/react-19-2) (2025) [official].

---

## Tools

| Command / rule | Detects |
|---|---|
| `npx eslint . --rule '{"react-hooks/rules-of-hooks":"error","react-hooks/exhaustive-deps":"error"}'` | Hook order violations and missing dependencies (RC-03, RC-07). |
| `eslint-plugin-react-hooks` `recommended` preset (17 rules): `exhaustive-deps`, `rules-of-hooks`, `component-hook-factories`, `config`, `error-boundaries`, `gating`, `purity`, `refs`, `set-state-in-effect`, `set-state-in-render`, `static-components`, `preserve-manual-memoization`, `immutability`, `globals`, `unsupported-syntax`, `incompatible-library`, `use-memo` | Compiler-diagnostic rules surface bail-outs without running the compiler (RC-01, RC-02, RC-04, RC-14, RC-19). |
| `npx react-compiler-healthcheck` (`react-compiler-healthcheck@1.0.0`) | Scans a codebase for Rules of React violations — the patterns that make the compiler skip a component. The gate before enabling the compiler or deleting memoisation (RC-18, RC-19). |
| `reactCompiler: true` in `next.config.*`; `reactCompilerPreset()` + `@rolldown/plugin-babel` in `vite.config.*`; `'babel-plugin-react-compiler'` in `babel.config.js` (must run first) | Establishes whether RC-18 applies at all. |
| `grep -rn '"use no memo"\|"use no forget"' src/` | Per-file compiler opt-outs (RC-19). |
| `grep -rn 'eslint-disable.*react-hooks/exhaustive-deps' src/ \| wc -l` | Suppression count (RC-07). Any non-zero needs a reason. |
| `npx codemod@latest react/19/migration-recipe` | Runs the React 19 removal codemods: `replace-reactdom-render`, `replace-string-ref`, `replace-use-form-state`, `prop-types-typescript` (RC-16, RC-23). |
| `npx types-react-codemod@latest preset-19` | Types for `ref` as prop, `useActionState` naming, `ReactElement` props (RC-15, RC-16). |
| React DevTools **Profiler** (record → "Highlight updates" / flamegraph) | Commit count per interaction: >1 commit for one `setState`-free interaction points at RC-04/RC-05; whole-tree highlight points at RC-13/RC-20. |
| React DevTools **Components** panel, `⚙ → "Highlight updates when components render"` | Visualises the re-render storm for RC-13 and RC-20. |
| React DevTools React Compiler panel / ✨ badge | Which components are actually memoized by the compiler (RC-18, RC-19). |
| `<Profiler>` from `react` (`onRender` with `actualDuration`, `phase`) | Per-subtree render cost, to justify a memoisation or colocation claim with numbers. |
| React 19.2+ **Performance Tracks** (Chrome DevTools performance panel shows React scheduler/component tracks) | Scheduler work and per-component render attribution in the browser timeline. Replaces guesswork for RC-13. |
| StrictMode in dev (`<StrictMode>` in `main.tsx` / `app/layout.tsx`) | Double-invokes render and Effects: duplicate subscriptions, duplicate requests and non-idempotent Effects surface immediately (RC-22). |
| `grep -rn 'key={\(i\|index\|idx\)}' src/` | Index keys (RC-10). Cross-check that the surrounding array is never reordered. |
| `grep -rn 'forwardRef\|defaultProps\|findDOMNode\|contextTypes\|ReactDOM.render\|this\.refs' src/` | Removed and deprecated APIs (RC-15, RC-23). |
| `grep -rn 'document.title\s*=\|document.head.appendChild\|react-helmet' src/ package.json` | Effect-driven head manipulation (RC-17). |
| `npm ls react react-dom eslint-plugin-react-hooks babel-plugin-react-compiler` | Version skew: two React copies break context identity; an old `eslint-plugin-react-hooks` mis-handles `useEffectEvent` (RC-08, RC-20). |
| `@testing-library/react` + `@testing-library/user-event`, assert with `findBy*`/`waitFor` | Renders under `StrictMode` by default in a test harness; catches missing cleanup and non-idempotent Effects (RC-06, RC-22). |
| React DevTools "Suspended by" / Network panel with `<Suspense>` | Confirms a boundary actually triggers — an Effect fetch shows no suspended render (RC-21). |
