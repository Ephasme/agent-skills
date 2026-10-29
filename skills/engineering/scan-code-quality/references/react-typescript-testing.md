# TypeScript, testing and the build toolchain (React frontend)

Scope: type-safety of a React codebase (tsconfig, prop/ref/event typing, runtime validation), its test suite (React Testing Library, Vitest, MSW, Playwright, axe), its linter configuration and its build/dependency hygiene. Rules about component design, hooks, state and effects belong to the React-core and architecture packs; they are referenced here only where the *type* or *tool* form is the finding.

## Contents

- [Version baseline](#version-baseline)
- [Rules](#rules)
- [Tools](#tools)

## Version baseline

Versions read from the npm registry (`registry.npmjs.org/<pkg>/latest`) and the projects' own release pages on 2026-10-25.

| Package | Current | Released | Source |
|---|---|---|---|
| TypeScript | 7.0.2 | 2026-07-08 | [TS 7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/) [official]; registry |
| TypeScript (previous majors) | 6.0.3 / 5.9.3 | 2026-04-16 / 2025-09-30 | [TS 6.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/) [official]; registry |
| TypeScript 7.1 | 7.1.0-beta | 2026-10-20 | [TS 7.1 Beta](https://devblogs.microsoft.com/typescript/announcing-typescript-7-1-beta/) [official] |
| React / React DOM | 19.3.1 | 2026-10-14 | [React 19.3](https://react.dev/blog/2026/09/09/react-19-3) [official]; registry |
| `@types/react` / `@types/react-dom` | 19.3.0 | 2026-09-09 | registry |
| React Compiler (`babel-plugin-react-compiler`) | 1.0.0 | 2025-10-07 | [React Compiler v1.0](https://react.dev/blog/2025/10/07/react-compiler-1) [official] |
| Next.js | 16.4.3 | 2026-10-23 | [Next.js 16](https://nextjs.org/blog/next-16) [official]; registry |
| React Router | 8.5.0 | 2026-10-19 | registry |
| Vite | 8.3.5 | 2026-10-21 | [Vite 8.0](https://vite.dev/blog/announcing-vite8) [official]; registry |
| Vitest | 5.0.5 | 2026-10-15 | [Vitest 5.0](https://vitest.dev/blog/vitest-5) [official]; registry |
| Jest | 30.5.2 (latest major: 30, 2025-06) | 2026-09-18 | [Jest 30](https://jestjs.io/blog/2025/06/04/jest-30) [official]; registry |
| ESLint | 10.13.0 | 2026-10-16 | [ESLint blog](https://eslint.org/blog/) [official]; registry |
| typescript-eslint | 8.72.0 | 2026-10-19 | registry; [shared configs](https://typescript-eslint.io/users/configs/) [official] |
| `eslint-plugin-react-hooks` | 7.1.1 | 2026-04-17 | registry; [plugin reference](https://react.dev/reference/eslint-plugin-react-hooks) [official] |
| `eslint-plugin-jsx-a11y` | 6.10.2 | registry |
| `eslint-plugin-testing-library` | 7.16.2 | registry |
| Biome | 2.6.3 | 2026-10-24 | [Biome v2](https://biomejs.dev/blog/biome-v2/) [official]; registry |
| Oxlint | 1.89.0 | 2026-10-19 | [Oxlint docs](https://oxc.rs/docs/guide/usage/linter) [official]; registry |
| `@testing-library/react` | 16.3.3 | registry |
| `@testing-library/user-event` | 14.6.8 | registry |
| `@testing-library/jest-dom` | 7.0.1 | 2026-08-09 | registry |
| MSW | 3.0.3 | 2026-10-10 | [MSW 3.0](https://mswjs.io/blog/introducing-msw-3.0) [official]; registry |
| `@playwright/test` | 1.64.1 | registry |
| Zod | 4.6.7 | 2026-10-12 | [Zod docs](https://zod.dev/basics) [official]; registry |
| Tailwind CSS | 4.3.3 | registry |

## Rules

### 1. Turn on the strictness baseline: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`

**Rule** – Set `"strict": true` in every tsconfig, leave `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `noImplicitAny`, `noImplicitThis`, `useUnknownInCatchVariables` untouched, and additionally enable `noUncheckedIndexedAccess` (indexed reads yield `T | undefined`) and `exactOptionalPropertyTypes` (`{ a?: string }` no longer accepts `{ a: undefined }`).

**Since** – `strict` TS 2.3, the two extras TS 4.1/4.4; **all three** are emitted by `tsc --init` since TS 5.9, so a new project that lacks them starts below the official default.

**Detection signals**
- `tsconfig.json` missing `strict`, or `"strict": false`, or any individual flag set to `false` (`strictNullChecks: false` is the common half-migration).
- `noUncheckedIndexedAccess` / `exactOptionalPropertyTypes` absent while the code does `items[0].id`, `record[key].name`, `arr[i]` or assigns optional props `undefined` explicitly (`<Foo bar={maybeBar} />` where `bar?: string`, `maybeBar: string | undefined`).
- `Record<string, T>` used as a guaranteed lookup (`const cfg = envs[name]` then `.url`); `noPropertyAccessFromIndexSignature: false` alongside `process.env.FOO`.
- Several tsconfigs in a monorepo (`tsconfig.app.json`, `tsconfig.node.json`, `tsconfig.test.json`) where only one has it.
- `tsconfig.json` absent entirely but `.tsx` files present (`allowJs` project with `// @ts-nocheck` at the top of files).
- `"skipLibCheck": false` is *not* a strictness signal — the official template ships `skipLibCheck: true`.

**Severity hint** – Medium (null crashes and `any` leakage that the compiler would have caught).

**Refactor direction** – Flip the flags, then fix errors in dependency order (leaf utilities first); with `noUncheckedIndexedAccess` prefer lookups that return `undefined` and narrow immediately (`.at(0)`, `if (!x) return`), and model "absent" and "present but undefined" as one thing at the boundary: `bar?: string` for props, `bar: string | undefined` when the key must exist.

**Counter-signals** – Vendored/third-party `.d.ts` noise is what `skipLibCheck` is for; do not turn it off. A generated-code folder may carry its own looser tsconfig as long as app code does not import from it untyped. Dense array maths over fixed-length tuples is genuinely noisy under `noUncheckedIndexedAccess`; a localised `as T` at that boundary is acceptable, a project-wide `false` is not.

**Sources** – [TypeScript 5.9 release notes](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-9.html) (TS team, 2025) [official]; [noUncheckedIndexedAccess](https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html) [official]; [exactOptionalPropertyTypes](https://www.typescriptlang.org/tsconfig/exactOptionalPropertyTypes.html) [official].

### 2. Use `verbatimModuleSyntax` and keep `isolatedModules` on

**Rule** – Type-only imports must be written `import type`; no `import { SomeType }` that the bundler would have to elide.

**Since** – `verbatimModuleSyntax` TS 5.0; `isolatedModules` is in the TS 5.9 init template.

**Detection signals**
- `verbatimModuleSyntax` absent, plus `import { FC } from 'react'` / `import { User } from './types'` used only in type position — these become runtime imports (and circular-import or missing-export crashes) once Oxc/esbuild/SWC compiles file-by-file.
- `importsNotUsedAsValues` or `preserveValueImports` present (removed TS 5.5) — a stale-config marker.
- `isolatedModules: false`, or its absence alongside a bundler that transpiles per file (Vite/Oxc, SWC, `ts-jest` with `isolatedModules`).
- Mixed `export { type Foo }` vs `export type { Foo }` style within one repo.

**Severity hint** – Medium (build-time or runtime "does not provide an export named" failures).

**Refactor direction** – Turn the flag on and run `eslint --fix` with `@typescript-eslint/consistent-type-imports`; the compiler error list is mechanical. Vite's `import.meta.env` typing also needs `/// <reference types="vite/client" />`-equivalent `vite-env.d.ts`, not an `any` cast.

**Counter-signals** – A package compiled by `tsc` only (a library published to npm) still wants it, but `jsx: preserve` libraries must keep `verbatimModuleSyntax` compatible with their JSX runtime. Independent of React Compiler; depends on the bundler (Vite/Oxc, SWC) more than on the framework.

**Sources** – [verbatimModuleSyntax](https://www.typescriptlang.org/tsconfig/verbatimModuleSyntax.html) [official]; [TS 5.9 notes](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-9.html) [official]; [Vite env & modes](https://vite.dev/guide/env-and-mode) [official].

### 3. Migrate the tsconfig to `moduleResolution: bundler` before TS 6/7 breaks it

**Rule** – No `moduleResolution: node|node10|classic`, no `target: es5`, no `module: amd|umd|systemjs`, no `baseUrl`, no `esModuleInterop: false`. Use `moduleResolution: "bundler"` (bundled app) or `"nodenext"` (Node/Next server code), and `paths` relative to the project root.

**Since** – `bundler` TS 5.0; every option above is a **hard error with no-op behaviour** from TS 7.0, and TS 6.0 is the stepping stone that reports them.

**Detection signals**
- Grep `compilerOptions` for `"moduleResolution": "node"`, `"node10"`, `"classic"`, `"module": "commonjs"` in a Vite app, `"baseUrl"`, `"target": "es5"`, `"downlevelIteration"`, `"alwaysStrict": false`, `"esModuleInterop": false`, `"allowSyntheticDefaultImports": false`.
- `paths` entries written relative to a `baseUrl` (`"@/*": ["src/*"]` with `"baseUrl": "."`) still resolve, but the `baseUrl` key itself is fatal on 7.
- Namespace with `module` keyword (`declare module Foo { module Bar {} }`), `assert { type: 'json' }` import assertions instead of `with`.
- TS 7 also **stops** auto-including every `node_modules/@types` package (`types` now defaults to `[]`-like behaviour) and defaults `rootDir` to the common source directory: a tsconfig relying on ambient `@types/jest` or on `dist/` mirroring the repo root changes output layout. Symptom: `Cannot find name 'describe'` after the upgrade, or emitted files flattened into `dist/`.
- `"types": ["node", "jest"]` missing in a project that needs the globals.

**Severity hint** – High (the project cannot compile at all, or emits a broken layout, on the current compiler generation).

**Refactor direction**
```jsonc
{
  "compilerOptions": {
    "module": "esnext",
    "moduleResolution": "bundler",
    "rootDir": "./src",
    "types": ["vite/client"],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["./src"]
}
```
Migrate via TS 6.0 first: it reports these as deprecations and offers `--stableTypeOrdering` to diff 6-vs-7 output when declaration emit must be compared.

**Counter-signals** – A library consumed by Node (`main`/`exports` CJS entry) legitimately keeps a second tsconfig with `module: nodenext`. `baseUrl` is fine only while pinned to TS ≤ 6. If `typescript-eslint`'s typed rules are in use, note TS 7.0 ships **no** programmatic API: lint runs on `@typescript/typescript6` until TS 7.1's API lands (preview in 7.1 beta).

**Sources** – [TS 7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/) [official]; [TS 6.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/) [official]; [TS 7.1 Beta](https://devblogs.microsoft.com/typescript/announcing-typescript-7-1-beta/) [official].

### 4. Validate network data at runtime; never cast an API response to a type

**Rule** – Anything crossing the network boundary is parsed by a schema (`z.object(...).parse` / `.safeParse`) and the type is *inferred* from the schema (`z.infer<typeof Response>`), not asserted with `as`.

**Since** – all React versions; Zod 4 is current.

**Detection signals**
- `await res.json() as User`, `as UserDto`, `as unknown as T`, `data as any` on fetch/axios/`useQuery` results.
- `fetch(...).then(r => r.json())` typed by generic parameter only (`useQuery<UserDto>(...)`) — the generic asserts, it does not check.
- `interface UserDto` used both as the wire shape and the UI model, with no parser anywhere.
- `JSON.parse(x) as T` in local storage/session storage readers.
- Zod/superstruct/valibot/arktype absent from `package.json` while API modules exist.

**Severity hint** – High (a contract change turns into `undefined is not a function` in render, or a wrongly typed field flows into a permission check).

**Refactor direction**
```ts
// before
const user = (await res.json()) as User;

// after
const UserSchema = z.object({ id: z.string(), name: z.string(), isAdmin: z.boolean() });
export type User = z.infer<typeof UserSchema>;

const parsed = UserSchema.safeParse(await res.json());
if (!parsed.success) throw new ApiContractError(parsed.error.issues);
const user = parsed.data; // typed, and actually checked
```
Then delete the hand-written `User` interface so the schema is the single source.

**Counter-signals** – `as` is fine for narrowing already-validated values (after a type guard) and for literal widening. Codegen from an OpenAPI/protobuf schema gives real types but still no runtime check — keep the parse at the edge. Server-side Next.js code receives typed props from your own code, so a schema there is optional.

**Sources** – [Zod basics](https://zod.dev/basics) (Zod docs, 2026) [official].

### 5. Ban type escape hatches: `!`, `@ts-ignore`, double casts

**Rule** – Replace non-null assertions with real narrowing, `@ts-ignore` with `@ts-expect-error` (which fails once the error disappears), and `as unknown as T` with a corrected type.

**Since** – all.

**Detection signals**
- `!` in non-null position: `document.getElementById('root')!`, `user!.name`, `ref.current!`, `process.env.API_URL!`.
- `// @ts-ignore` (any occurrence — it silently survives a fix), vs `// @ts-expect-error` with no description.
- `as unknown as`, `as any as`, `<any>` casts, `: any` on exported function parameters or returns.
- `// @ts-nocheck` / `// @ts-expect-error` at file top.
- eslint: `@typescript-eslint/no-non-null-assertion`, `no-explicit-any`, `ban-ts-comment` (default forbids `@ts-ignore`), `no-unsafe-*`. All are in `strictTypeChecked`.
- `skipLibCheck` plus `@ts-ignore` on import lines: usually a missing `@types/*` package, not a compiler bug.

**Severity hint** – Medium (each one is a crash site the compiler was asked to stop checking; High when it hides an auth/permission branch).

**Refactor direction**
```ts
// before
document.getElementById('root')!.innerHTML = html; // + no runtime check

// after
const root = document.getElementById('root');
if (!root) throw new Error('#root missing from index.html');
root.replaceChildren(node);
```
For a genuine library-defect workaround, keep `// @ts-expect-error -- upstream: <issue url>` so the suppression self-deletes when the types are fixed.

**Counter-signals** – Test files may use `!` on fixture lookups and `as any` on deliberately malformed inputs; scope the lint override to `**/*.test.tsx` rather than disabling globally. `satisfies` and `as const` are not escape hatches — they narrow and are preferred.

**Sources** – [typescript-eslint shared configs](https://typescript-eslint.io/users/configs/) [official]; [@types/react index.d.ts](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/types/react/index.d.ts) [official].

### 6. Type props as plain object types, not `React.FC`

**Rule** – Declare `function Button({ label }: ButtonProps) {}`; do not annotate components with `React.FC`/`FunctionComponent`/`VFC`.

**Since** – React 19 types: `FunctionComponent<P>` is `(props: P) => ReactNode | Promise<ReactNode>`, carries no implicit `children`, and still exposes a deprecated `propTypes` field kept only for back-compat.

**Detection signals**
- `React.FC<`, `React.FunctionComponent<`, `React.VFC<` anywhere; `: FC<Props> = (` in an import list.
- Components that rely on implicit `children` (`function Card({ title }) { return <div>{children}</div> }` with a bare `{}` props type) — a `React.FC` habit that no longer types.
- Default-exported anonymous arrow components (`export default (props: Props) => ...`) that lose their name in DevTools and cannot be used in Fast Refresh boundaries.
- `propTypes` / `defaultProps` on function components (deprecated; `defaultProps` no longer applies to function components in React 19).

**Severity hint** – Low (friction), Medium when `defaultProps` silently stops applying defaults.

**Refactor direction**
```tsx
// before
const Button: React.FC<{ label: string }> = ({ label }) => <button>{label}</button>;

// after
type ButtonProps = { label: string; onClick?: () => void };
export function Button({ label, onClick }: ButtonProps) { return <button onClick={onClick}>{label}</button>; }
```
Async server components need no `React.FC` to type: `async function Page({ id }: { id: string })` is inferred as `Promise<ReactNode>`.

**Counter-signals** – Codebases on `@types/react` < 18 may still need `React.FC` for `children`; not a finding there. With React Compiler enabled, `memo()` wrapping is generally redundant (see rule 20) — that is a separate finding from the `FC` annotation.

**Sources** – [@types/react index.d.ts, `interface FunctionComponent`](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/types/react/index.d.ts) [official]; [react.dev Using TypeScript](https://react.dev/learn/typescript) [official]; [React 19 upgrade guide](https://react.dev/blog/2024/04/25/react-19-upgrade-guide) [official].

### 7. Model mutually exclusive props as a discriminated union, not optional booleans

**Rule** – Props that cannot coexist (or that require a companion prop) are one union keyed by a literal, so illegal states do not compile.

**Since** – all.

**Detection signals**
- Several `isLoading?: boolean; isError?: boolean; data?: T; error?: Error` on one component, with `if (isLoading) ... else if (isError)` in the body.
- Boolean + dependent prop: `href?: string; onClick?: () => void` where the body branches on which exists; `as?: 'button' | 'a'` plus an optional `href`.
- `variant: string` with `if (variant === 'primary')` — should be a literal union at minimum.
- `React.ComponentProps` of a wrapper carrying `disabled` while `loading` also exists, with no rule that they conflict.
- Runtime checks `if (props.a && props.b) throw` — the compiler should already have rejected the call.

**Severity hint** – Medium (impossible states reach render and crash).

**Refactor direction**
```tsx
// before
type Props = { href?: string; onClick?: () => void; as?: 'a' | 'button' };

// after
type Props =
  | { as: 'link'; href: string }
  | { as: 'button'; onClick: () => void };

function Action(props: Props) {
  return props.as === 'link'
    ? <a href={props.href}>{/*...*/}</a>
    : <button onClick={props.onClick}>{/*...*/}</button>;
}
```
Exhaustiveness then comes free from `switch (props.as)` + a `never` check.

**Counter-signals** – Data fetched by TanStack Query already has a discriminated `status` field (`'pending' | 'error' | 'success'`); destructure that instead of adding booleans — do not re-model it. A single boolean (`disabled`) needs no union.

**Sources** – [react.dev Using TypeScript](https://react.dev/learn/typescript) [official] (props typing, union examples).

### 8. Derive wrapper props from `ComponentProps<'button'>` instead of retyping native attributes

**Rule** – Components that wrap or forward a DOM element take their props from `React.ComponentProps<'button'>` (or `ComponentPropsWithoutRef`), not a hand-copied subset.

**Since** – all (`ComponentProps` exists in `@types/react` 16.8+).

**Detection signals**
- Hand-written `type ButtonProps = { className?: string; onClick?: () => void; disabled?: boolean; type?: 'button'|'submit' }` on a component that renders `<button>`.
- Spread `{...rest}` typed as `any` or `Record<string, unknown>` because the props type lost the native attributes.
- `onClick?: (e: any) => void` on the wrapper while the inner `<button>` expects `MouseEvent<HTMLButtonElement>`.
- Native prop drift: the wrapper omits `aria-*`, `form`, `name`, `autoFocus` that callers need, and callers work around it.
- `React.HTMLAttributes<HTMLButtonElement>` used where `ComponentProps<'button'>` is meant (loses `type`, `disabled`, `form*`).

**Severity hint** – Medium (accessible attributes silently dropped by wrappers = broken a11y; type drift between wrapper and element).

**Refactor direction**
```tsx
// before
type Props = { label: string; onClick?: () => void; className?: string };

// after
type Props = { label: string } & React.ComponentProps<'button'>;
export function Button({ label, ...rest }: Props) {
  return <button {...rest}>{label}</button>;
}
```
Drop `ref` from the type when the wrapper does not forward it (`ComponentPropsWithoutRef`), or accept and pass `ref` as a normal prop (React 19 — see rule 9).

**Counter-signals** – Use `Omit<ComponentProps<'input'>, 'value' | 'onChange'>` when the wrapper *controls* a prop; inheriting `value` while ignoring it is worse than omitting it. Framework-agnostic rule, applies to Vite SPA, Next.js and React Router apps alike.

**Sources** – [@types/react `ComponentProps`/`ComponentPropsWithoutRef`](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/types/react/index.d.ts) [official] (`T extends keyof JSX.IntrinsicElements ? JSX.IntrinsicElements[T]` — i.e. `ComponentProps<'button'>` is literally the element's attribute type).

### 9. Type component boundaries the React 19 way: refs, `children`, `ReactElement`

**Rule** – `ref` is a plain prop (no `forwardRef` in new code), no `MutableRefObject`, `useRef<T>(null)` with the initial argument; and `children` is typed `React.ReactNode` unless the component must inspect the element, in which case `React.ReactElement<Props>` — never the bare global `JSX.Element`.

**Since** – React 19 types: `RefObject<T> = { current: T }` (mutable), `useRef<T>()` without an argument removed, `MutableRef` deprecated, `ReactElement`'s `props` defaults to `unknown` (was `any`), and the global `JSX` namespace is replaced by `React.JSX`.

**Detection signals — refs**
- `React.forwardRef<HTMLInputElement, Props>(...)` wrappers, `React.MutableRefObject<`, `React.RefObject<HTMLDivElement>` used where `.current` is assigned.
- `useRef<HTMLInputElement>()` with no argument — a type error on `@types/react` 19, still present in a codebase that was never migrated.
- `ref.current!.focus()` (the `!` exists because the type now includes `null` only for the `useRef<T>(null)` overload).
- Custom `useImperativeHandle` with `forwardRef`; the React 19 form takes `ref` from props.
- `elementRef` prop named to dodge the `ref` special prop — no longer needed. Biome's `react` domain flags both patterns directly: `noReactForwardRef`, `noReactStringRefs`.

**Detection signals — `children` and return types**
- `children: JSX.Element` / `JSX.Element | null` prop types (a slot that cannot accept a string or an array).
- `children: React.ReactElement` then `React.Children.map(children, c => c.props.x)` — `c.props` is `unknown` on React 19, so either the code casts (escape hatch) or it was written for 18.
- Ambient `declare global { namespace JSX { ... } }` module augmentation (must now be `declare module "react"` / `"react/jsx-runtime"`); Biome's `noJsxNamespace` flags the stale form.
- Return types annotated `: JSX.Element` on components that can return `null` or a string.
- `ReactNode` used for a value that is later passed to `cloneElement` (not assignable).

**Severity hint** – Low, Medium when a component that should accept text/number children is typed `JSX.Element` and callers wrap it in needless spans, or when a `MutableRef`-typed ref is mutated during render.

**Refactor direction**
```tsx
// before
const Input = React.forwardRef<HTMLInputElement, { id: string }>((props, ref) => (
  <input ref={ref} {...props} />
));
function Card({ children }: { children: JSX.Element }) { /* ... */ }

// after
function Input({ id, ref }: { id: string; ref?: React.Ref<HTMLInputElement> }) {
  return <input id={id} ref={ref} />;
}
function Card({ children }: { children: React.ReactNode }) { /* ... */ }

// when you must inspect the element, type it:
function OnlyOne({ children }: { children: React.ReactElement<{ id: string }> }) {
  return React.cloneElement(children, { id: 'x' }); // props typed, not unknown
}
```
Inside components: `const el = useRef<HTMLDivElement>(null);` and read `el.current` after mount only.

**Counter-signals** – Codebases still on React 18 keep `forwardRef` (not deprecated there) and `MutableRefObject` (before 19, `RefObject.current` was readonly, so a mutable ref had its own type). A component returning `Promise<ReactNode>` (server component) must not be annotated `ReactElement`. Library authors publishing `.d.ts` that must work on both React 18 and 19 keep `@types/react` in `peerDependencies` and test both.

**Sources** – [React 19 upgrade guide](https://react.dev/blog/2024/04/25/react-19-upgrade-guide) [official] (ref types, `ReactElement` props default, `React.JSX`); [@types/react index.d.ts](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/types/react/index.d.ts) [official].

### 10. Query by role first; never reach into the DOM container

**Rule** – Tests find elements the way a user or screen reader does: `getByRole` > `getByLabelText` > `getByPlaceholderText` > `getByText` > `getByDisplayValue` > `getByTestId`. No `container.querySelector`, no `document.querySelector`, no class selectors.

**Since** – Testing Library's priority guide, stable across `@testing-library/react` 13–16.

**Detection signals**
- `container.querySelector(`, `baseElement.querySelector(`, `document.querySelector(`, `document.getElementById(` inside `*.test.tsx`.
- `getByTestId(` used before any role query on the same element; `data-testid` on elements that already have an accessible role (`<button data-testid="submit">`).
- `.className`, `.classList`, `style=` assertions; `wrapper.find('Component')`-style legacy Enzyme API.
- `getByRole('button')` without `{ name: /save/i }` in a component with several buttons (ambiguous query, or a silent `getAllByRole`).
- `eslint-plugin-testing-library` absent from the lint config: `testing-library/no-container`, `no-node-access`, `prefer-screen-queries`, `no-test-id-queries` would each flag this class.

**Severity hint** – Medium (tests break on refactor and pass on real regressions — false negatives and false positives at once).

**Refactor direction**
```tsx
// before
const { container } = render(<Form />);
container.querySelector('.btn-primary')!.click();

// after
render(<Form />);
await user.click(screen.getByRole('button', { name: /save/i }));
expect(screen.getByRole('status')).toHaveTextContent(/saved/i);
```
If a role query is impossible, the markup usually lacks a semantic element or label — fix the component, then the test.

**Counter-signals** – `getByTestId` is the documented last resort for non-semantic output (charts, virtualised lists, third-party widgets) — acceptable when the rest of the query priority is impossible. `within(screen.getByRole('dialog'))` is the right way to scope, not `container`.

**Sources** – [About Queries / priority](https://testing-library.com/docs/queries/about/) (Testing Library docs) [official]; [Testing Implementation Details](https://kentcdodds.com/blog/testing-implementation-details) (Kent C. Dodds, 2020) [power-user].

### 11. Drive interactions with `userEvent`, not `fireEvent`

**Rule** – `await user.click(...)`, `await user.type(...)`, `await user.keyboard('{Enter}')`; `fireEvent` only for events `user-event` cannot produce (scroll, media, some pointer/custom events).

**Since** – `user-event` 14 (current 14.6.8); `fireEvent` has been the weaker option since v13.

**Detection signals**
- `fireEvent.click(`, `fireEvent.change(input, { target: { value: 'x' } })` — the latter bypasses the input's real event sequence and never triggers focus/blur handlers.
- `fireEvent.keyDown(el, { key: 'Enter' })` standing in for a real key press (does not fire keypress/input).
- `userEvent.click(...)` **not awaited** (v14 API is async; unawaited calls leave unflushed updates and produce `act` warnings).
- `userEvent.setup()` called per assertion instead of once per test — loses the clipboard/pointer state model.
- A file that never imports `user-event` but tests typing, selecting, tabbing or pasting.

**Severity hint** – Medium (tests that pass while the real interaction is broken — e.g. a form that only validates on real `change`+`blur`).

**Refactor direction**
```tsx
// before
fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } });
fireEvent.click(screen.getByRole('button', { name: /send/i }));

// after
const user = userEvent.setup();
await user.type(screen.getByLabelText(/email/i), 'a@b.c');
await user.click(screen.getByRole('button', { name: /send/i }));
```
`user-event` fires the full sequence and runs the visibility/interactability checks a real browser would.

**Counter-signals** – `fireEvent.scroll`, `fireEvent.drop` with a synthetic `DataTransfer`, and media events are legitimate. jsdom has no layout, so pointer-position-dependent behaviour still needs a real browser (Vitest browser mode or Playwright).

**Sources** – [user-event introduction](https://testing-library.com/docs/user-event/intro) (Testing Library docs) [official].

### 12. Await async assertions properly: `findBy` instead of `waitFor` + `getBy`, no arbitrary sleeps

**Rule** – Use `await screen.findByRole(...)` for "appears later", `waitFor` only for non-DOM assertions, and never poll with `setTimeout`.

**Since** – all Testing Library versions.

**Detection signals**
- `await waitFor(() => expect(screen.getByText(/x/)).toBeInTheDocument())` — `getBy` inside `waitFor` retries the *whole* callback only because it throws; `findBy*` is the dedicated API (same thing, one line, better errors).
- `await waitFor(() => { expect(el).toHaveClass('open') })` where `el` was captured before the state change (stale node).
- `await new Promise(r => setTimeout(r, 500))`, `await sleep(`, `jest.advanceTimersByTime` mixed with `waitFor`.
- `findBy*` **without** `await`, or `expect(await screen.findBy...).toBe(...)` nested inside another `waitFor` (double retry, 1000 ms × default timeout).
- `waitFor` with a custom `timeout` far above 1000 ms used to paper over a slow provider.
- Console noise: `Warning: An update to X inside a test was not wrapped in act(...)` — a missing `await` on a user action, a state update in a floating promise, or a render outside RTL's `render`/`act`.
- Multiple `getBy` assertions after an async action with no `findBy`/`waitFor` at all.

**Severity hint** – Medium (flaky suite; `act` warnings hide real races, and a `findBy` without `await` never fails).

**Refactor direction**
```tsx
// before
fireEvent.click(screen.getByRole('button', { name: /load/i }));
await waitFor(() => expect(screen.getByText(/loaded/i)).toBeInTheDocument());

// after
await user.click(screen.getByRole('button', { name: /load/i }));
expect(await screen.findByText(/loaded/i)).toBeInTheDocument();
```
When an `act` warning appears, find the unawaited promise (usually a `user.*` call or a state setter in a `.then`) rather than wrapping the assertion in `act`.

**Counter-signals** – `waitFor` is correct for a callback-based assertion that is not a query (a mock call count, a `localStorage` write). Fake timers plus `user-event` need `advanceTimers` wired through `userEvent.setup({ advanceTimers })` — a config choice, not a finding.

**Sources** – [Async methods](https://testing-library.com/docs/dom-testing-library/api-async) (Testing Library docs) [official]; [`act` reference](https://react.dev/reference/react/act) [official].

### 13. Keep snapshots rare and reviewable

**Rule** – No `.snap` files for whole-page or whole-component output; snapshot only small, stable, intentional serialisations, and always commit-and-review the diff.

**Since** – all (Jest/Vitest snapshot behaviour unchanged).

**Detection signals**
- `__snapshots__/` directory with files > a few hundred lines, or `.snap` files whose last modification is a bulk `-u` run.
- `expect(container).toMatchSnapshot()` / `expect(asFragment()).toMatchSnapshot()` — this is the "whole render tree" anti-pattern, and it also locks in class names and DOM structure.
- `toMatchInlineSnapshot()` with dozens of lines of markup.
- `--ci` absent from the test command: on CI Jest/Vitest **write** new snapshots instead of failing (`CI=true` makes missing snapshots fail). Look for a test script without `--ci` or without `CI` in the CI workflow.
- Snapshot count growing faster than test count; `-u` in the `test` script itself.

**Severity hint** – Medium (snapshots that pass on every change are dead weight; ones updated blindly hide regressions).

**Refactor direction** – Replace `toMatchSnapshot()` on a component with role/text assertions on the parts that matter; keep serialisers (e.g. `jest-serializer-html`) only for genuinely structural output (email templates, SVG icons) and assert a handful of properties instead of the tree.

**Counter-signals** – Snapshotting a pure data transform's output, or a deliberately exhaustive list of design tokens, is fine. Visual regression (screenshots) is a different, legitimate tool (Playwright `toHaveScreenshot`).

**Sources** – [Testing Implementation Details](https://kentcdodds.com/blog/testing-implementation-details) (Kent C. Dodds, 2020) [power-user]; [Jest blog](https://jestjs.io/blog) [official].

### 14. One test runner, configured for the current major: Vitest 5 or Jest 30, not both

**Rule** – Pick Vitest (Vite apps) or Jest (Next.js/webpack apps); remove the other's config, globals and typings, and run tests through the same transform pipeline as the app.

**Since** – Vitest 4 (2025-10) made Browser Mode stable; Vitest 5 (2026-09) is current. Jest 30 (2025-06) is current; JSdom `environment` is the default assumption in both.

**Detection signals**
- Both `jest` and `vitest` in `devDependencies`; `jest.config.*` **and** `vitest.config.*`; `"jest"` key in `package.json`.
- `@types/jest` present while tests use `vi.fn()` (or the reverse: `jest.fn()` with `globals: true` from Vitest — works only through compatibility shims).
- `test.environment` unset or `'node'` in a project whose tests call `render()` — `document` is then undefined, and the workaround is usually a per-file `// @vitest-environment jsdom` comment instead of one config setting. Same for `globals: false` with tests relying on bare `describe`.
- Vitest 4→5 leftovers: per-project `extends: true` (no longer required in v5 — inline projects inherit root `plugins`/`resolve.alias` by default), and a `browser.provider` string where v4+ requires the separate `@vitest/browser-playwright` / `-webdriverio` / `-preview` package.
- Vitest 5 `clearMocks` now defaults to `true`; tests relying on the old leak-between-tests behaviour, or mocks reset in a `beforeEach` that is now redundant.
- Unawaited assertions: Vitest 5 fails tests whose assertion was never awaited — a common latent bug it surfaces.
- `ts-jest` + `isolatedModules` false + a `tsconfig` mismatch between build and test.
- jsdom for tests that need layout/`getBoundingClientRect` (returns zeros) — should be Browser Mode or Playwright.

**Severity hint** – Medium (two runners = two configs, two type-global sets, and tests that pass in one pipeline and fail in the other).

**Refactor direction** – Vitest in a Vite app is the low-friction default: it reuses `vite.config.ts` (aliases, `resolve.dedupe`, React plugin), so `npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom` plus a `test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] }` block replaces a Jest config, `babel-jest`/`ts-jest` and a duplicated `moduleNameMapper`. Delete `@types/jest` and add `"types": ["vitest/globals"]` only if `globals: true`.

**Counter-signals** – Next.js apps that must run tests through the Next pipeline, or repos with large `jest`-specific tooling (custom reporters, `jest-circus` hooks), reasonably stay on Jest 30. Vitest Browser Mode is not a drop-in for E2E: it runs component tests in a real browser but has no multi-page/navigation story.

**Sources** – [Vitest 5.0](https://vitest.dev/blog/vitest-5) [official]; [Vitest 4.0](https://vitest.dev/blog/vitest-4) [official]; [Jest 30](https://jestjs.io/blog/2025/06/04/jest-30) [official].

### 15. Mock the network with MSW, not by monkey-patching fetch/axios

**Rule** – Request handlers at the network boundary (`http.get('/api/user', ...)`) shared by tests, Storybook and dev; no `jest.mock('axios')`, no `global.fetch = jest.fn()`.

**Since** – MSW 3 (2026-09) is current; 2.x handlers remain compatible at the root export.

**Detection signals**
- `global.fetch = jest.fn()`, `vi.stubGlobal('fetch', ...)`, `jest.mock('axios')`, `axios-mock-adapter`, `nock` — anything replacing the transport.
- `vi.mock('./api/client')` used to fake *every* network call (module-level mocking of your own data layer is a step removed from what the component does).
- No `msw` in `devDependencies` while components call APIs in tests.
- `setupServer` created per test file rather than once in `setupFiles` with `server.resetHandlers()` in `afterEach` (handler leakage across files).
- MSW 3 migration debt: `rest.*` handlers (removed in 2.0, gone in 3), `msw/node` default export misuse, missing `server.listen({ onUnhandledRequest: 'error' })` — silent passes on unmocked calls.
- Handlers that hard-code response bodies that duplicate the Zod schema (drift: see rule 4).

**Severity hint** – Medium (tests that mock the transport keep working when the URL, method or headers are wrong).

**Refactor direction**
```ts
// src/test/server.ts
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
export const server = setupServer(
  http.get('/api/user/:id', ({ params }) => HttpResponse.json({ id: params.id, name: 'Ada' })),
);
// setup.ts: beforeAll(server.listen({ onUnhandledRequest: 'error' })), afterEach(server.resetHandlers()), afterAll(server.close())
```
Per-test override: `server.use(http.get('/api/user/1', () => HttpResponse.json({}, { status: 500 })))` — the failure path becomes a one-liner.

**Counter-signals** – Mocking a module is right when the dependency is not HTTP (a browser API, `crypto`, an analytics SDK). Next.js Route Handlers/Server Actions invoked in-process are better tested by calling them directly than through MSW.

**Sources** – [Introducing MSW 3.0](https://mswjs.io/blog/introducing-msw-3.0) (Artem Zakharchenko, 2026) [official].

### 16. Cover the user journeys with Playwright; migrate off the removed `@playwright/experimental-ct-*` packages

**Rule** – Playwright tests the app end-to-end against a real browser; component-level Playwright tests now use the built-in `mount()` fixture from `@playwright/test`, not an experimental CT package.

**Since** – The stories + `fixtures.mount()` model landed in Playwright 1.62; from 1.63 the `@playwright/experimental-ct-react`/`-ct-react17`/`-ct-vue` packages are announced as no longer updated, and the current docs state they have been removed and are no longer published. Current is 1.64.

**Detection signals**
- `@playwright/experimental-ct-react` in `devDependencies` (removed upstream; frozen at 1.62 behaviour) and a `playwright-ct.config.ts`.
- `import { test, expect } from '@playwright/experimental-ct-react'`.
- No `playwright.config.*` at all while the repo has auth, checkout or any multi-step flow — the app is only covered by jsdom tests.
- `webServer` block missing (tests hitting a stale/absent dev server) or `reuseExistingServer: true` in CI.
- Selectors: `page.locator('.btn')`/`page.$('div > span')` instead of `getByRole`; `page.waitForTimeout(` (the canonical flake).
- Only unit tests, no `test.describe` with navigation; no `storageState` for auth (every test re-logs in).
- In migrated CT setups: tests still passing JSX props into `mount()` — the new fixture takes a *story* path (`mount('components/Expandable/Stateful')`), and the gallery page + `*.story.tsx` must be owned by the app.

**Severity hint** – Medium (a removed dependency breaks the build on the next install); High when a core flow has zero browser coverage.

**Refactor direction** – Move the CT package out: add a story file per scenario, keep a gallery route served by your own dev server, then `test('expands', async ({ mount }) => { const c = await mount('components/Expandable/Stateful'); await c.getByRole('button').click(); })`. For E2E: `webServer: { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: !process.env.CI }` and `use: { baseURL }`.

**Counter-signals** – Vite SPA + React Router: E2E only, CT is optional. Next.js App Router: E2E exercises server components and routing that a component test cannot; CT of a single client component is lower value there. jsdom-based RTL remains the fast layer — Playwright does not replace it.

**Sources** – [Playwright component testing](https://playwright.dev/docs/test-components) [official]; [Playwright release notes 1.64](https://playwright.dev/docs/release-notes) [official].

### 17. Run an accessibility engine in the test suite

**Rule** – Every rendered page/component gets an `axe` scan with zero violations, at minimum on the core flows.

**Since** – `jest-axe` 11 (2026) for Jest; for Vitest, `axe-core` called directly or `vitest-axe` (last published 2022 — verify before adopting); `@axe-core/playwright` 4.14 for E2E.

**Detection signals**
- No `axe`/`jest-axe`/`@axe-core/*` dependency anywhere.
- `eslint-plugin-jsx-a11y` absent too (both missing = accessibility is untested at every layer).
- axe imported but only asserted in one smoke test; `expect(results).toHaveNoViolations()` replaced by `console.log`.
- Scans run on a component in isolation with no `<main>`/`<h1>`, producing a permanent `region`/`page-has-heading-one` violation that is then ignored wholesale (`disableRules([...])` with a large list).
- Colour contrast: axe in jsdom cannot compute contrast — only Playwright scans catch it.

**Severity hint** – High when a core flow (login, checkout, navigation) has no automated a11y check at all; Medium when only the E2E layer is missing.

**Refactor direction**
```tsx
// Vitest, one scan per page-level test
import axe from 'axe-core';
const { violations } = await axe.run(document.body, { rules: { region: { enabled: false } } });
expect(violations).toEqual([]);
```
```ts
// Playwright
import AxeBuilder from '@axe-core/playwright';
const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
expect(results.violations).toEqual([]);
```
Fail the build on violations; a rule disabled repo-wide needs a comment naming the WCAG criterion it waives.

**Counter-signals** – axe catches roughly a third of WCAG issues — it does not replace keyboard and screen-reader testing, so absence of violations is not a pass. Scanning every component individually is noisy; scan page-level compositions.

**Sources** – [@axe-core/playwright](https://www.npmjs.com/package/@axe-core/playwright) (registry, 4.14) [official]; [jest-axe](https://www.npmjs.com/package/jest-axe) (registry, 11.0.0) [official].

### 18. Use ESLint flat config, on ESLint 10, with no eslintrc leftovers

**Rule** – One `eslint.config.js|mjs|ts` exporting an array; no `.eslintrc*`, no `eslintConfig` key in `package.json`, no `--ext` flag.

**Since** – Flat config became the default in ESLint 9; ESLint 10 (2025-10) is the current major and **rejects** the old format. ESLint 9 reached end-of-life on 2026-08-06.

**Detection signals**
- Any `.eslintrc`, `.eslintrc.json`, `.eslintrc.cjs`, `.eslintignore`; `"eslintConfig"` in `package.json`.
- `eslint` pinned to `^8` or `^9`; a `--ext .ts,.tsx` in the lint script (flat config uses `files` globs).
- `npm run lint` = `next lint` — **removed in Next.js 16**; `next build` no longer lints. Replace with `eslint .` (or Biome/Oxlint) and remove the `next lint` invocation.
- `context.getScope()` / `context.getAncestors()` in a local plugin (removed in ESLint 9/10), `context.parserOptions` in rules.
- `/* eslint-env node */` comments (now reported as errors).
- `no-unused-vars` false positives on components used only in JSX — ESLint 10 tracks JSX references, so a config that disables `no-unused-vars` for `.tsx` files is a v9 workaround to delete.
- Ignore patterns in `.eslintignore` that never migrated to `globalIgnores()`/`ignores:` — the config silently lints `dist/`.
- `eslint-plugin-*` packages that predate flat config (`extends:` strings inside a `plugins` array).

**Severity hint** – Medium (linting silently stops covering files, or CI dies on the next upgrade).

**Refactor direction**
```js
// eslint.config.js
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
export default tseslint.config(
  { ignores: ['dist', 'coverage'] },
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  reactHooks.configs.flat.recommended,
);
```
Next.js: keep `@next/eslint-plugin-next` (`core-web-vitals`, `recommended`) in that array instead of `next lint`.

**Counter-signals** – ESLint 10 requires Node ≥ 20.19 (or ≥ 22.13 / ≥ 24) and `jiti` ≥ 2.2 for a `.ts` config; a repo pinned to old `eslint-plugin-*` majors may need a deliberate staged upgrade. A JS config path is a config-only dependency, not a finding.

**Sources** – [Migrate to v10](https://eslint.org/docs/latest/use/migrate-to-10.0.0) [official]; [ESLint blog — v9 EOL 2026-08-06](https://eslint.org/blog/) [official]; [Next.js 16 breaking changes](https://nextjs.org/blog/next-16) [official].

### 19. Enable type-aware linting: `strictTypeChecked` with `projectService`

**Rule** – Run `typescript-eslint`'s type-checked presets (`strictTypeChecked` or at least `recommendedTypeChecked`) with `parserOptions.projectService: true`.

**Since** – typescript-eslint 8 (current 8.72); `projectService` replaced hand-maintained `project: [...]` arrays.

**Detection signals**
- `tseslint.configs.recommended` without `TypeChecked`, or no `typescript-eslint` at all while the repo is 100 % TypeScript.
- `parserOptions.project: ['./tsconfig.json']` (multi-tsconfig repos break; `projectService` handles them).
- Flaky `parserOptions.project` errors ("file not included in any project") worked around with `allowDefaultProject` or by disabling rules — a sign the config is wrong, not the rule.
- Type-aware rules disabled en masse (`'@typescript-eslint/no-unsafe-assignment': 'off'`) — these are the ones that catch `any` leaking from `JSON.parse`.
- Lint time > several minutes with no `--cache`/no `oxlint`/`biome` on the fast path.
- TS 7 upgrade: TS 7.0 ships **no** programmatic API, so type-aware lint must run against `@typescript/typescript6` (or wait for TS 7.1's API); a repo that force-upgraded `typescript` to 7 while keeping ESLint typed rules silently breaks or crashes.

**Severity hint** – Medium (the entire `no-unsafe-*` class of findings — `any` propagation from network/DOM boundaries — is invisible without it).

**Refactor direction** – Enable incrementally: `strictTypeChecked` on `src/**/*.{ts,tsx}`, keep `stylisticTypeChecked` separate, and set `parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname }`. Keep `eslint . --cache` in the pre-commit hook and leave the full typed pass to CI if it exceeds ~60 s.

**Counter-signals** – Very large monorepos may run type-aware rules only on changed packages. Oxlint's `--type-aware` (via `oxlint-tsgolint`, 59 of 61 typescript-eslint type-aware rules) is a legitimate faster substitute, at some rule-coverage loss.

**Sources** – [Linting with Type Information](https://typescript-eslint.io/getting-started/typed-linting) [official]; [Shared configs](https://typescript-eslint.io/users/configs/) [official]; [TS 7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/) [official]; [Oxlint type-aware linting](https://oxc.rs/docs/guide/usage/linter/type-aware) [official].

### 20. Keep `eslint-plugin-react-hooks` on and never silence `exhaustive-deps`

**Rule** – `react-hooks` rules at `error`. A disabled `exhaustive-deps`, or an inline `// eslint-disable-next-line react-hooks/exhaustive-deps`, is a finding — fix the dependency or move the code into an Effect Event.

**Since** – v6 (2025-10) shipped the compiler-powered rules inside the `recommended` preset; `recommended-latest` adds the bleeding-edge experimental compiler rules; v7.1 (2026-04) added ESLint 10 support.

**Detection signals**
- Plugin absent, or only `rules-of-hooks` enabled (the 2020-era config).
- `'react-hooks/exhaustive-deps': 'off'` / `'warn'`; any `eslint-disable` comment mentioning `exhaustive-deps` (count them — a handful with a reason is fine, a pattern is not).
- Compiler rules present as errors but permanently suppressed with file-level disables; or a hand-picked rule list that omits them.
- Compiler-diagnostic rules firing and being ignored: `purity`, `immutability`, `refs`, `set-state-in-render`, `set-state-in-effect`, `globals`, `static-components`, `preserve-manual-memoization`, `incompatible-library`, `error-boundaries`, `unsupported-syntax`, `config`, `gating`, `use-memo`, `component-hook-factories`.
- React Compiler enabled in the build (`babel-plugin-react-compiler`, Next `reactCompiler: true`, `@vitejs/plugin-react`'s `reactCompilerPreset`) while the lint preset is old — compiler and lint disagree about what is safe.

**Severity hint** – Medium (stale-closure bugs and unmemoised renders), High when `set-state-in-render`/`refs` violations are suppressed (infinite render loops, tearing).

**Refactor direction** – Turn `recommended-latest` on, then work the list down. For a dependency you genuinely want excluded, use `useEffectEvent` (React 19.2+) rather than the disable comment; the rule then passes honestly.

**Counter-signals** – Third-party hooks that return unstable callbacks force a disable — acceptable once, with a link to the issue. The React Compiler rules are worth enabling even when the compiler is not (they detect Rules-of-React violations statically); but if the compiler is off, `preserve-manual-memoization` findings are informational.

**Sources** – [eslint-plugin-react-hooks reference](https://react.dev/reference/eslint-plugin-react-hooks) [official]; [React Compiler v1.0](https://react.dev/blog/2025/10/07/react-compiler-1) [official]; [React Compiler installation](https://react.dev/learn/react-compiler/installation) [official]; [plugin CHANGELOG 7.1](https://github.com/facebook/react/blob/main/packages/eslint-plugin-react-hooks/CHANGELOG.md) [official].

### 21. Lint accessibility statically: `jsx-a11y`

**Rule** – `eslint-plugin-jsx-a11y`'s recommended set is on, with `jsx-a11y/no-autofocus` and `jsx-a11y/anchor-is-valid` as errors.

**Since** – 6.x (current 6.10.2); `flatConfigs.recommended` is the flat-config entry point.

**Detection signals**
- Plugin absent while `onClick` sits on `<div>`s: `jsx-a11y/click-events-have-key-events`, `no-static-element-interactions`, `interactive-supports-focus` each flag it.
- `aria-*` strings that do not exist or are mis-cased: `aria-props`, `aria-proptypes`, `role-has-required-aria-props`, `role-supports-aria-props`.
- `<img>` without `alt` (`alt-text`), `<a>` without `href` (`anchor-is-valid`), `<a onClick>` used as a button (`anchor-is-valid` + `click-events-have-key-events`).
- `autoFocus` on inputs (`no-autofocus`), `tabIndex` > 0 (`tabindex-no-positive`), `aria-hidden` on a focusable node (`no-aria-hidden-on-focusable`), `role="presentation"` on a semantic element (`no-redundant-roles`).
- Form fields without an associated label (`label-has-associated-control`, `control-has-associated-label`).
- Rule overrides set to `'off'` in bulk — check which ones, `anchor-is-valid` and `alt-text` are the ones that matter.

**Severity hint** – High when a core flow is keyboard-inoperable (clickable divs for submit/close), otherwise Medium.

**Refactor direction** – Replace `<div onClick>` with `<button type="button">`; for a genuinely custom widget follow the WAI-ARIA Authoring Practices pattern (role, `tabIndex`, `onKeyDown` for Enter/Space) rather than suppressing the rule. Add `eslint-plugin-testing-library`'s `no-node-access` (rule 10) so the *tests* stop depending on the div.

**Counter-signals** – `jsx-a11y` sees only static JSX: a `role` supplied by a spread prop is invisible to it (false negative), and it cannot check rendered contrast. Pair with rule 17. Next.js/React Router SPAs alike.

**Sources** – [eslint-plugin-jsx-a11y README / supported rules](https://github.com/jsx-eslint/eslint-plugin-jsx-a11y) [official].

### 22. Delete the CRA / react-scripts legacy build

**Rule** – No `react-scripts`, no ejected `config/webpack.config.js`, in a repo that should be on Vite, RSBuild, Parcel or a framework.

**Since** – Create React App was deprecated for new apps on 2025-02-14; the React team's guidance is a framework, or Vite/Parcel/RSBuild for a plain SPA.

**Detection signals**
- `"react-scripts"` in `dependencies`, `"start"/"build"/"test": "react-scripts ..."`, `react-app-env.d.ts`, `src/reportWebVitals.ts`, `%PUBLIC_URL%` in `public/index.html`.
- Ejected layout: `config/`, `scripts/`, `webpack.config.js`, `babel.config.js` with `babel-preset-react-app`, `eslintConfig` extending `react-app`.
- webpack-era config in a Vite repo: `webpack`, `webpack-dev-server`, `html-webpack-plugin`, `mini-css-extract-plugin`, `file-loader`/`url-loader` in `devDependencies` after a partial migration; `process.env.REACT_APP_*` still read at runtime while Vite defines `import.meta.env.VITE_*` (or vice versa — one of the two is then `undefined`).
- No `vite.config.ts`/`rsbuild.config.ts` while `index.html` is at the repo root (the Vite convention) — a half-migrated tree.
- `react-scripts` 5 (2022) which pins webpack 5 + jest 27 and blocks ESLint 9/10.

**Severity hint** – Medium (frozen toolchain: no ESLint 10, no Vite 8/Rolldown, no Vitest, known-vulnerable transitive deps).

**Refactor direction** – `npm i -D vite @vitejs/plugin-react`, move `index.html` to the root with `<script type="module" src="/src/main.tsx">`, rename `REACT_APP_*` → `VITE_*` (and add `vite-env.d.ts` typing for them), replace `process.env.NODE_ENV` with `import.meta.env.MODE`, then delete `react-scripts`, `config/`, `scripts/` and `react-app-env.d.ts`. Do it in one PR; a half-migrated repo builds twice and lints never.

**Counter-signals** – A repo that must keep webpack for a specific loader (Module Federation, unusual asset pipeline) should migrate *forward* to webpack 5 config it owns, which is different from staying on `react-scripts`. Next.js apps have no CRA issue at all.

**Sources** – [Sunsetting Create React App](https://react.dev/blog/2025/02/14/sunsetting-create-react-app) (Matt Carroll, Ricky Hanlon, 2025) [official]; [Vite 8.0](https://vite.dev/blog/announcing-vite8) [official]; [Vite env & modes](https://vite.dev/guide/env-and-mode) [official].

### 23. Ship source maps privately and measure the bundle in CI

**Rule** – `build.sourcemap: 'hidden'` (or `true` if you strip them from the CDN), upload maps to the error tracker, and run a bundle-size report with a budget on every PR.

**Since** – Vite default is `build.sourcemap: false`; Rolldown is the single bundler from Vite 8; Oxc Transformer replaced the `esbuild` option.

**Detection signals**
- `build.sourcemap` absent/false while production error tracking is configured — stack traces are minified and useless.
- `build.sourcemap: true` **and** the `dist/` is served publicly without stripping `*.map` — sources are downloadable; check for a `sourcesContent` leak in a published map.
- `sourcemap: 'inline'` in a production build (a separate ~2× size hit, and the map ships inside the JS).
- No `rollup-plugin-visualizer` (7.1.1, Rolldown-compatible) or no `vite build --mode analyze`; no size budget, no `size-limit`/`bundlemon`/`lhci` in CI.
- Vite 8 debt: `esbuild: { ... }` block in `vite.config.ts` (deprecated, silently converted to `oxc`), `build.rollupOptions` instead of `build.rolldownOptions`, `build.target` overridden to `es2015` (the default is now `baseline-widely-available`, which already excludes ancient Safari).
- Duplicated chunks: the same dependency in two chunks (`index-*.js` and `vendor-*.js` both containing React), or `manualChunks` fighting Rolldown's splitting.
- `vite-plugin-*` packages that require Rollup internals failing after the Vite 8 upgrade.

**Severity hint** – High when maps are publicly exposed in a repo with proprietary code or unredacted secrets in errors; Medium for the missing-budget case.

**Refactor direction**
```ts
// vite.config.ts
export default defineConfig({
  build: { sourcemap: 'hidden' },          // no //# sourceMappingURL comment
  plugins: [react(), visualizer({ filename: 'dist/stats.html', gzipSize: true })],
});
```
Then upload `dist/**/*.map` to Sentry/Datadog in the deploy step and delete them from the published artefact. Add `npx vite build && npx size-limit` (or `bundlemon`) with a threshold so a PR fails on a >10 kB gzip regression.

**Counter-signals** – An internal-only app may publish maps deliberately (readable stack traces > source secrecy) — the finding then is the missing budget, not the maps. Next.js: `productionBrowserSourceMaps: true` is the equivalent switch, and its `next build` output already reports per-route First Load JS.

**Sources** – [Vite build options (`build.sourcemap`)](https://vite.dev/config/build-options) [official]; [Vite 8.0](https://vite.dev/blog/announcing-vite8) [official]; [rollup-plugin-visualizer](https://github.com/btd/rollup-plugin-visualizer) [official].

### 24. One copy of React, one version of `@types/react`

**Rule** – The installed tree contains exactly one `react` and exactly one `react-dom`, matching major versions with each other and with `@types/react`.

**Since** – all; the failure mode is unchanged — "Invalid hook call / more than one copy of React".

**Detection signals**
- `npm ls react` / `pnpm why react` showing the same `react` at two versions (typically app 19.x + a UI library pulling 18.x); `npm ls react-dom` mismatched with `react` (`19.3.0` + `18.2.0` → "Incompatible React versions").
- `@types/react` major ≠ `react` major, or two `@types/react` versions (one from a package's `dependencies` instead of `peerDependencies`).
- Libraries declaring `react` in `dependencies` rather than `peerDependencies` (visible in the lockfile's resolution paths).
- Monorepo with hoisting disabled (pnpm strict) and no `resolve.dedupe: ['react', 'react-dom']` in `vite.config.ts`, or duplicated React in the Rollup/Rolldown chunk output.
- `Invalid hook call` / `Cannot read properties of null (reading 'useState')` in production but not in dev — the classic duplicated-copy symptom.
- Two React majors in one workspace (`apps/web` on 19, `packages/ui` peer-allowing `^18 || ^19` and tested only on 18).

**Severity hint** – High (the app crashes at runtime; nothing else in this pack matters until it is fixed).

**Refactor direction** – Align versions: `pnpm dedupe`, tighten the library's `peerDependencies` to the major you actually support, add `overrides`/`pnpm.overrides` for the offending transitive, and add `resolve.dedupe` as a belt-and-braces measure. Assert it in CI: `npm ls react react-dom | grep -c 'react@'` (or fail on `npm ls --all` ERR).

**Counter-signals** – A micro-frontend that *deliberately* runs two Reacts must isolate them (separate root, no context crossing). `resolve.dedupe` does not apply to SSR ESM output built with `build.rolldownOptions.output` — Vite documents that caveat.

**Sources** – [Rules of Hooks warning page](https://react.dev/warnings/invalid-hook-call-warning) [official]; [Vite `resolve.dedupe`](https://vite.dev/config/shared-options) [official].

### 25. Dependency hygiene: no legacy heavyweight imports, audit clean, lockfile committed

**Rule** – No `moment` in new code (legacy, maintenance mode), no full-`lodash` import in client code, a committed lockfile, and an audit that is either clean or explicitly triaged.

**Since** – all; `moment` has been in maintenance mode since 2020.

**Detection signals**
- `moment` in `dependencies`; `import moment from 'moment'` in components (pulls locales into the main chunk even when unused); `dayjs`/`date-fns`/`Temporal` alternatives absent.
- `import _ from 'lodash'` / `import { debounce } from 'lodash'` — the CJS build defeats tree-shaking; `lodash-es` named imports or `lodash/debounce` is the fix. No `eslint-plugin-lodash`/`no-restricted-imports` guard.
- Barrel imports from large libraries: `import { Button } from 'some-ui-kit'` where the package has no `sideEffects: false` / `exports` map.
- No lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`) in the repo, or a lockfile that is gitignored; CI using `npm install` instead of `npm ci` (which requires a lockfile and installs exactly it).
- `npm audit` / `pnpm audit` never run in CI, or run with `--audit-level=critical` only, or `audit` failing constantly with no `overrides` triage — either no signal at all or a red build everyone ignores.
- `npm outdated` showing majors behind by ≥ 2 for `react`, `vite`, `typescript`, `eslint` (a repo that skipped the 2025–2026 generational changes, which are not incremental).
- Postinstall scripts / `--ignore-scripts` inconsistencies; `resolutions`/`overrides` pinning a vulnerable transitive with no comment.

**Severity hint** – Medium (bundle bloat, unpatched CVEs), High when audit reports a reachable RCE/XSS advisory in a shipped dependency still marked vulnerable.

**Refactor direction**
```jsonc
// package.json — forbid the heavy entry points, keep the escape hatch explicit
"eslint": { "rules": { "no-restricted-imports": ["error", { "paths": [
  { "name": "moment", "message": "Use date-fns or Temporal" },
  { "name": "lodash", "message": "Use lodash-es named imports" }
]]}]}
```
Replace `moment` call-by-call (formatting/parsing is usually 90 % of usage). Then `npm ci` in CI, `npm audit --audit-level=high` as a required check, and a monthly `npm outdated` review for the majors that gate everything else (React, TS, ESLint, Vite).

**Counter-signals** – `lodash` in a Node-only script is harmless; `moment` in a legacy admin page is a scheduling problem, not a bug. Advisories in dev-only tooling are usually not production-reachable — triage with the dependency path, do not blanket-suppress. Do not "upgrade for the sake of it": React 19, ESLint 10 and TS 7 are the ones that change what the code must look like.

**Sources** – [Moment.js docs — "legacy project in maintenance mode"](https://momentjs.com/docs/) [official]; [`npm ci`](https://docs.npmjs.com/cli/v11/commands/npm-ci) [official]; [`npm outdated`](https://docs.npmjs.com/cli/v11/commands/npm-outdated) [official].

## Tools

Commands and rules that produce the evidence above. Run them before concluding; each maps to rule numbers.

**Type checking / tsconfig**
- `npx tsc --noEmit -p tsconfig.json` — the only authority on rules 1–3, 7–9. In a TS 7 repo `tsc` *is* the native binary; keep `tsc6` (from `@typescript/typescript6`) around for tools that still need the JS API.
- `npx tsc --showConfig` — resolved config after `extends` (catches a flag set in only one of several tsconfigs, rule 1).
- `npx tsc --init` in a scratch dir — the current official template; diff it against the repo's tsconfig (rules 1–3).
- `npx @typescript/native-preview` / `tsgo` — try the native port on the repo before committing to the TS 7 migration (rule 3).

**Lint**
- `npx eslint . --max-warnings=0` with flat config (rule 18). `--print-config src/App.tsx` proves which rules are actually active.
- `@typescript-eslint`: `strictTypeChecked`, `recommendedTypeChecked`, plus `no-explicit-any`, `no-non-null-assertion`, `ban-ts-comment`, `consistent-type-imports`, `no-unsafe-assignment|member-access|call|return` (rules 2, 4, 5, 19).
- `eslint-plugin-react-hooks` (`recommended`, or `recommended-latest` for the experimental set): `rules-of-hooks`, `exhaustive-deps`, `purity`, `immutability`, `refs`, `set-state-in-render`, `set-state-in-effect`, `globals`, `static-components`, `preserve-manual-memoization`, `incompatible-library`, `error-boundaries`, `unsupported-syntax`, `config`, `gating`, `use-memo`, `component-hook-factories` (rule 20).
- `eslint-plugin-jsx-a11y`: `alt-text`, `anchor-is-valid`, `click-events-have-key-events`, `no-static-element-interactions`, `interactive-supports-focus`, `label-has-associated-control`, `role-has-required-aria-props`, `aria-props`, `no-autofocus`, `tabindex-no-positive`, `no-aria-hidden-on-focusable` (rule 21).
- `eslint-plugin-testing-library` (`react` config): `no-container`, `no-node-access`, `prefer-screen-queries`, `no-test-id-queries`, `prefer-presence-queries`, `await-async-queries`, `await-async-events`, `no-await-sync-queries`, `no-wait-for-side-effects`, `no-unnecessary-act`, `prefer-find-by`, `prefer-user-event`, `prefer-user-event-setup` (rules 10–12).
- `npx oxlint --type-aware` (`oxlint-tsgolint`): 59/61 typescript-eslint type-aware rules, ~50–100× faster than ESLint; use it as the fast pre-commit path next to the typed ESLint CI pass (rule 19).
- `npx biome check` — type-aware rules from its own inference engine (no `typescript` install needed), plus the `react` domain (`useExhaustiveDependencies`, `useHookAtTopLevel`, `noArrayIndexKey`, `useUniqueElementIds`, `noJsxNamespace`, `noReactForwardRef`, `noReactStringRefs`, `noDangerouslySetInnerHtml`, `noChildrenProp`, `useJsxKeyInIterable`, nursery `useReactCompiler`) and the `a11y` domain (rules 9, 20, 21).

**Tests**
- `npx vitest --coverage` / `npx jest --ci --coverage` — the `--ci` flag makes missing snapshots fail instead of being written (rule 13).
- `CI=true npx vitest run` — same effect for Vitest; without it a new snapshot is silently created (rule 13).
- Vitest Browser Mode (`@vitest/browser-playwright`) — real-browser component tests where jsdom's zero-layout lies (rules 11, 14).
- `npx playwright test --trace on` — E2E and `mount()` component tests; the trace viewer is the evidence for flake (rule 16).
- MSW `server.listen({ onUnhandledRequest: 'error' })` — turns an unmocked request into a failure instead of a real network call (rule 15).
- `axe-core` / `jest-axe` / `@axe-core/playwright` — `expect(await axe.run()).toHaveNoViolations()`-equivalent assertion per page (rule 17).

**Build and dependencies**
- `npx vite build && npx vite preview` — reveals the sourcemap setting and the chunk graph; `dist/**/*.map` presence is the rule 23 evidence.
- `rollup-plugin-visualizer` (`visualizer({ filename: 'dist/stats.html', gzipSize: true })`) or `npx vite-bundle-visualizer` — per-module gzip size, the input for a budget (rule 23).
- `npx size-limit` / `bundlemon` / Lighthouse CI — the budget that actually fails a PR (rule 23).
- `npm ls react react-dom @types/react` / `pnpm why react` — duplicated copies (rule 24).
- `npm ci` (lockfile-exact, fails without one) vs `npm install` in CI (rule 25).
- `npm audit --audit-level=high` / `pnpm audit --audit-level high`, `npm outdated` — advisory and staleness evidence (rule 25).
