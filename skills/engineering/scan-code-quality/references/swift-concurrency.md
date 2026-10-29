# Swift concurrency & data-race safety

Baseline for this catalog: Swift 6.4 (shipped 2026-09-14, in Xcode 27 and later; Xcode 27.1 is current), Swift 6.3 (released 2026-03-24, Xcode 26.x), Swift 6.2 (Xcode 26). Anything marked "next release" is on `main` but not in a shipping toolchain.

## Contents

- [Rules](#rules)
- [Tools](#tools)

## Rules

### Compile every target in Swift 6 language mode with complete checking

**Rule** – Build all app, extension and package targets with `SWIFT_VERSION = 6.0` (or Swift 5 plus `SWIFT_STRICT_CONCURRENCY = complete` while migrating); never ship a target at `minimal`/unset checking, which silently drops every data-race diagnostic.

**Since** – Swift 6.0 / Xcode 16 (complete checking available since Swift 5.7).

**Detection signals** – `SWIFT_VERSION = 5.0` with no `SWIFT_STRICT_CONCURRENCY` in `project.yml`/`*.pbxproj`/`*.xcconfig`; `SWIFT_STRICT_CONCURRENCY = minimal|targeted`; `Package.swift` targets without `swiftLanguageMode(.v6)` (or `.v5` + `.enableUpcomingFeature("StrictConcurrency")`); a target whose sources are excluded from the strict build ("we build that module in Swift 5"); CI that passes `-suppress-warnings` or `SWIFT_TREAT_WARNINGS_AS_ERRORS = NO` on concurrency diagnostics.

**Severity hint** – High — unchecked targets hide races that only surface in production.

**Refactor direction** – Raise `SWIFT_VERSION` to `6.0` per target, then fix errors in dependency order (leaf modules first); keep `SWIFT_STRICT_CONCURRENCY = complete` on Swift 5 targets during the transition so warnings appear before they become errors.

**Counter-signals** – A target pinned to Swift 5 for a bounded, dated migration with `complete` checking on; vendored third-party code excluded from the scan.

**Sources** – [Migrating to Swift 6](https://www.swift.org/migration/documentation/migrationguide/) [official, 2024–2026]; [WWDC24-10169 "Migrate your app to Swift 6"](https://developer.apple.com/videos/play/wwdc2024/10169/) [official, 2024].

### Choose the default actor isolation per target deliberately, and identically for shared sources

**Rule** – Set `SWIFT_DEFAULT_ACTOR_ISOLATION` (`MainActor` or `nonisolated`) per target on purpose; when one source file is compiled into several targets, all of them must use the same value.

**Since** – Swift 6.2 / Xcode 26 (`-default-isolation`, `SwiftSetting.defaultIsolation`, SE-0466).

**Detection signals** – `SWIFT_DEFAULT_ACTOR_ISOLATION` absent from a target that has UI code; the setting differing between the app target and an extension, widget or monitor target while `sources:` overlap (e.g. `App, Shared` vs `Widget, Shared` in `project.yml`); `SWIFT_APPROACHABLE_CONCURRENCY` set on one target only (it flips `DisableOutwardActorInference`, `GlobalActorIsolatedTypesUsability`, `InferIsolatedConformances`, `InferSendableFromCaptures`, `NonisolatedNonsendingByDefault` together); inconsistent `Package.swift` `.defaultIsolation(MainActor.self)`; a file that compiles clean in the app but errors in the extension (isolation flipped by build settings, not by code).

**Severity hint** – High — the same code acquires two different isolation domains depending on which target builds it.

**Refactor direction** – Pick `MainActor` for UI-heavy app targets and `nonisolated` for shared/library code, write both into the project file (or `.defaultIsolation(...)`), and mirror shared-file ownership so one module owns them; when migrating, `default @MainActor` at file scope (SE-0478, accepted, next release) is the per-file alternative to a target-wide switch.

**Counter-signals** – A deliberately `nonisolated` library target consumed by a `MainActor` app (that is the intended split); a mixed repo where the *shared* target is the only place the shared files are compiled.

**Sources** – [SE-0466 Control default actor isolation inference](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0466-control-default-actor-isolation.md) [official, 2025]; [Apple Build Settings Reference, `SWIFT_DEFAULT_ACTOR_ISOLATION` / `SWIFT_APPROACHABLE_CONCURRENCY`](https://developer.apple.com/documentation/xcode/build-settings-reference) [official]; [Donny Wals, "What is Approachable Concurrency in Xcode 26?"](https://www.donnywals.com/what-is-approachable-concurrency-in-xcode-26/) [power-user, 2025].

### Give genuinely concurrent work `@concurrent`; `nonisolated async` no longer leaves the caller's actor

**Rule** – With `NonisolatedNonsendingByDefault` enabled (part of Approachable Concurrency), a `nonisolated async` function runs on the caller's actor. Mark CPU-heavy or blocking async functions `@concurrent`, or they keep running on the main actor.

**Since** – Swift 6.2 (SE-0461); the behavior becomes the default for async functions when the upcoming feature is on.

**Detection signals** – `nonisolated func … async` bodies containing `JSONDecoder().decode`, image decode/resize, CryptoKit/compression work, file IO, `Data(contentsOf:)`, sorting/large loops — with no `@concurrent`; `SWIFT_UPCOMING_FEATURE_NONISOLATED_NONSENDING_BY_DEFAULT = YES` plus such functions; `Task.detached` used purely to "get off main" (see the `Task.detached` entry); Instruments Time Profiler showing the work under the main-thread track while the code claims `nonisolated`.

**Severity hint** – Medium — main-thread stalls and hitches that no compiler warning surfaces.

**Refactor direction** – Annotate only the heavy function, keep the rest MainActor:
```swift
// before: stays on the caller (main) actor in Swift 6.2+
nonisolated func decode(_ data: Data) async throws -> Image { … }

// after
@concurrent func decode(_ data: Data) async throws -> Image { … }
```
Pass `Sendable`/`sending` values in and out; a `@concurrent` function cannot touch the caller's non-`Sendable` state.

**Counter-signals** – Async functions whose body only awaits other async APIs and does no CPU work (hopping is pure overhead); functions already isolated to a background actor.

**Sources** – [SE-0461 Run nonisolated async functions on the caller's actor by default](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0461-async-function-isolation.md) [official, 2025]; [WWDC25-268 "Embracing Swift concurrency"](https://developer.apple.com/videos/play/wwdc2025/268/) (`@concurrent` demo, main-actor mode) [official, 2025]; [WWDC26-262 "What's new in Swift"](https://developer.apple.com/videos/play/wwdc2026/262/) [official, 2026].

### Do not dissolve isolation with `nonisolated` to silence diagnostics

**Rule** – Keep `nonisolated` for stateless helpers and values that never touch actor state; a `nonisolated` type or member that reads/writes shared mutable state has traded a compile error for a runtime race.

**Since** – Swift 6.2 (matters most with `MainActor` default isolation).

**Detection signals** – `nonisolated` applied to whole classes/structs holding `var` state; `nonisolated` on a member whose body touches `static var`, a singleton, `UserDefaults`, a cache, or a `@MainActor` property; `nonisolated` + `@unchecked Sendable` on the same declaration; a type where "everything is nonisolated" except a couple of `@MainActor` members (see split isolation); `nonisolated` methods that then call `MainActor.assumeIsolated` to get their state back.

**Severity hint** – High — real races hidden behind an annotation.

**Refactor direction** – Restore type-level isolation and move the genuinely non-isolated slice out: pure formatting/parsing functions into a `nonisolated` helper type, state stays `@MainActor` (or in an actor). If a nonisolated caller needs state, return a `Sendable` snapshot instead of opening the object up.

**Counter-signals** – `nonisolated` on `static` pure helpers, `Codable`/`Hashable` implementations over immutable stored properties, and types conforming to a `Sendable` protocol (Swift 6.2 stops inferring `MainActor` for those) that legitimately stay nonisolated.

**Sources** – [WWDC25-268](https://developer.apple.com/videos/play/wwdc2025/268/) (nonisolated code section, 13:10) [official, 2025]; [Donny Wals, "Solving actor-isolated protocol conformance related errors in Swift 6.2"](https://www.donnywals.com/solving-actor-isolated-protocol-conformance-related-errors-in-swift-6-2/) [power-user, 2025].

### Resolve conformance-isolation errors with isolated conformances, not `@preconcurrency`

**Rule** – When a `@MainActor` type cannot satisfy a nonisolated protocol requirement, either isolate the conformance (`extension Model: @MainActor P`) or make the requirement `nonisolated`; `@preconcurrency` on the conformance keeps compiling but turns a compile-time guarantee into a runtime crash.

**Since** – Swift 6.2 (SE-0470 `InferIsolatedConformances`, isolated conformances); diagnostic `#ConformanceIsolation` exists since Swift 6.0.

**Detection signals** – Compiler note `conformance of 'X' to protocol 'Y' crosses into main actor-isolated code and can cause data races [#ConformanceIsolation]`; `@preconcurrency` written on a conformance or type in first-party code; `SWIFT_UPCOMING_FEATURE_INFER_ISOLATED_CONFORMANCES = NO` while the module defaults to `MainActor`; a protocol requirement marked `nonisolated` purely to satisfy a Sendable-constrained protocol.

**Severity hint** – High — `@preconcurrency` conformance makes the mismatch a runtime trap instead of a build error.

**Refactor direction** –
```swift
// before
@MainActor final class Model: @preconcurrency Identifiable { … }

// after (Swift 6.2): isolate the conformance
@MainActor final class Model: @MainActor Identifiable { … }
```
Isolated conformances are only usable from that actor; if a nonisolated framework calls the requirement (WidgetKit, delegates), mark the specific member `nonisolated` and return `Sendable` values instead.

**Counter-signals** – `@preconcurrency` on a conformance whose protocol comes from an Objective-C framework that calls the requirement on the main thread by contract (documented, not assumed).

**Sources** – [SE-0470 Global-actor isolated conformances](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0470-isolated-conformances.md) [official, 2025]; [Swift compiler diagnostics: ConformanceIsolation](https://docs.swift.org/compiler/documentation/diagnostics/) [official].

### `@unchecked Sendable` needs a written invariant; prefer actors, `Mutex`, or value types

**Rule** – Every `@unchecked Sendable` must name the mechanism that makes it safe (an internal lock, immutable storage, main-actor-only access); otherwise model the state as an actor, a `Mutex`, or a value type.

**Since** – Swift 5.5 (`@unchecked Sendable`); Swift 6.3 adds `weak let` (SE-0481) and Swift 6.4 adds `~Sendable` (SE-0518) to retire common excuses.

**Detection signals** – `@unchecked Sendable` on a `class` with mutable `var` properties and no `Mutex`/`NSLock`/`DispatchQueue` in the type; `@unchecked Sendable` combined with `static var`, `nonisolated(unsafe)`, or `@preconcurrency`; `@unchecked Sendable` on a type used from more than one isolation domain; a `weak var` forcing `@unchecked Sendable` (fix: `weak let`); `final class X: @unchecked Sendable` whose only reason is "the compiler complained".

**Severity hint** – High — the compiler's only data-race guarantee for that type is removed.

**Refactor direction** – Replace the escape hatch with an owning primitive: `final class Cache: Sendable { private let state = Mutex<[Key: Value]>([:]) }`; for a weak back-reference use `weak let` (Swift 6.3, upcoming feature `ImmutableWeakCaptures`); to state that a type must never be `Sendable`, write `class Mission: ~Sendable` (Swift 6.4) instead of pretending.

**Counter-signals** – Types that are truly immutable after `init` and only conform because a stored property's type is non-`Sendable` but never mutated; `@unchecked Sendable` on a wrapper whose entire API is `withLock`-scoped.

**Sources** – [Apple docs: Sendable](https://developer.apple.com/documentation/swift/sendable) ("you are responsible for the correctness of unchecked sendable types") [official]; [SE-0481 `weak let`](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0481-weak-let.md) [official, 2025]; [SE-0518 `~Sendable`](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0518-tilde-sendable.md) [official, 2026]; [WWDC26-262](https://developer.apple.com/videos/play/wwdc2026/262/) [official, 2026].

### `nonisolated(unsafe)` on global or static state only behind an enforced lock

**Rule** – Treat `nonisolated(unsafe)` as a claim that a specific lock serialises every access; if that lock is not visible in the same type, the declaration is a data race.

**Since** – Swift 5.10 (SE-0412); an error in Swift 6 mode without the attribute.

**Detection signals** – `nonisolated(unsafe) var|let` at file/type scope; `nonisolated(unsafe)` on a declaration whose type contains no `Mutex`, `NSLock`, `OSAllocatedUnfairLock`, or actor; `static var` + `nonisolated(unsafe)` used as a cache or `UserDefaults` mirror; `nonisolated(unsafe)` applied to a `let` of a non-`Sendable` type (a `let` binding does not make the object safe).

**Severity hint** – High.

**Refactor direction** – Wrap the storage: `private let cache = Mutex<[String: Value]>([:])` and expose `withLock`; for read-only-after-init data prefer `let` of a `Sendable` value; for "set once at launch, read everywhere" use `@MainActor` or an actor with a single `configure` call.

**Counter-signals** – Interop with a C global that is documented immutable; a `let` initialized once in `init` of a `@MainActor` type and read off-actor through a snapshot.

**Sources** – [SE-0412 Strict concurrency for global variables](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0412-strict-concurrency-for-global-variables.md) [official, 2023]; [Swift migration guide, "Unsafe Global and Static Variables"](https://www.swift.org/migration/documentation/swift-6-concurrency-migration-guide/commonproblems/) [official].

### Retire blanket `@preconcurrency import` once the dependency is Swift-6 ready

**Rule** – `@preconcurrency import` downgrades every Sendable violation from that modul to a runtime check; keep it only for a dependency that still lacks `Sendable` annotations, and delete it when the dependency ships concurrency annotations.

**Since** – Swift 5.6 (SE-0337); behavior unchanged through Swift 6.4.

**Detection signals** – `@preconcurrency import` on system modules that have been annotated for years (`Foundation`, `UIKit`, `SwiftUI`, `Combine`, `CoreData`, `UserNotifications`); more than a handful of such imports in one target; `@preconcurrency` on first-party declarations as a substitute for `nonisolated`/isolated conformances; a comment-free `@preconcurrency` block at the top of a file.

**Severity hint** – Medium.

**Refactor direction** – Remove the attribute, rebuild, and fix the (usually few) real diagnostics with `Sendable` conformances, `sending` parameters, or an actor hop; if the dependency genuinely lacks annotations, isolate the import in one small adapter file rather than sprinkling it.

**Counter-signals** – A third-party or closed-source framework whose types are non-`Sendable` by design and are only touched on one actor; an Objective-C API that documents main-thread-only callbacks.

**Sources** – [SE-0337 Incremental migration to concurrency checking](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0337-support-incremental-migration-to-concurrency-checking.md) [official, 2022]; [Swift migration guide, "Preconcurrency Import"](https://www.swift.org/migration/documentation/swift-6-concurrency-migration-guide/commonproblems/) [official]; [Matt Massicotte, "Problematic Swift Concurrency Patterns"](https://massicotte.org/problematic-patterns/) [power-user, updated 2026].

### `MainActor.assumeIsolated` only where the API contract guarantees the main thread

**Rule** – `MainActor.assumeIsolated` traps when the current executor is not the main actor's; use it for callbacks whose documentation guarantees main-thread delivery, never to make a compiler error disappear.

**Since** – Swift 5.9 (back-deployed to iOS 13).

**Detection signals** – `MainActor.assumeIsolated` inside `Task {}`, `Task.detached`, `DispatchQueue.global().async`, `URLSession` completion handlers, background `NotificationCenter` observers, or `deinit`; the call wrapping a large body of work instead of one value read; `assumeIsolated` used in code paths that also run under unit tests off the main actor (crash message: `Incorrect actor executor assumption; Expected same executor as MainActor.`); a `nonisolated` function whose first statement is `MainActor.assumeIsolated`.

**Severity hint** – High — deterministic crash in production, invisible to the compiler.

**Refactor direction** – Make the boundary async: `let value = await MainActor.run { model.value }`, or annotate the API `@MainActor` (delegate protocol, closure parameter) so the compiler proves it. If the call comes from an Objective-C callback documented as main-thread, keep `assumeIsolated` for the single property read and add the contract as a comment.

**Counter-signals** – `MainActor.assumeIsolated` in a `CADisplayLink`/`UIScrollViewDelegate`-style callback that Apple documents as main-thread, or inside a `@MainActor`-inheriting override where the compiler cannot express it.

**Sources** – [Apple docs: `MainActor.assumeIsolated`](https://developer.apple.com/documentation/swift/mainactor/assumeisolated(_:file:line:)-swift.method) ("or stop program execution") [official]; [Swift Forums: "MainActor.assumeIsolated crashes on main thread"](https://forums.swift.org/t/mainactor-assumeisolated-crashes-on-main-thread/80624) [official-forum, 2025]; [Matt Massicotte, "Is Dynamic Isolation Bad?"](https://www.massicotte.org/dynamic-isolation/) [power-user, 2024].

### One type, one isolation domain: no split isolation in view models and stores

**Rule** – Apply `@MainActor` to the whole type (or none of it); a class with some `@MainActor` members and some nonisolated mutable members is neither sendable nor safely usable from either side.

**Since** – all (Swift 5.5+ actor model).

**Detection signals** – `@MainActor` on individual properties/methods of an otherwise nonisolated class; `@MainActor` members mixed with `nonisolated var` mutable state; `nonisolated` pure accessors on a `@MainActor` view model returning mutable references; `ObservableObject`/`@Observable` models where `objectWillChange`/observation plumbing forced partial `nonisolated`; a class passed between actors that is not `Sendable` because of the mixed members.

**Severity hint** – Medium.

**Refactor direction** – Whole-type `@MainActor` on the view model; move genuinely off-main computation into `@concurrent` free functions or a separate actor that returns `Sendable` snapshots; keep `nonisolated` only on `static` pure helpers.

```swift
@MainActor @Observable final class FeedModel {
    private(set) var items: [Item] = []
    func load() async throws { items = try await FeedLoader.load() } // @concurrent inside
}
```

**Counter-signals** – A class whose `@MainActor` members exist only to expose a snapshot and whose nonisolated part is fully immutable (`let` of `Sendable` values).

**Sources** – [Matt Massicotte, "Problematic Swift Concurrency Patterns" → "Split Isolation"](https://massicotte.org/problematic-patterns/) [power-user, updated 2026]; [WWDC25-268](https://developer.apple.com/videos/play/wwdc2025/268/) (actor-isolated types, 17:16) [official, 2025].

### Never block the main actor waiting for async work

**Rule** – No synchronous waits on the main actor: semaphores, `DispatchGroup.wait`, `DispatchQueue.main.sync`, run-loop spinning, or `.result`-style blocking on a `Task` — each one deadlocks or freezes the UI.

**Since** – all.

**Detection signals** – `DispatchSemaphore.wait()` / `DispatchGroup.wait()` / `.wait(timeout:)` reachable from a `@MainActor` or `View` context; `DispatchQueue.main.sync`; `Task { }.result` / `.wait()`; `while !done { RunLoop.current.run(…) }`; `await` inside a `withCheckedContinuation` closure that itself blocks; a `@MainActor` function calling a `sync` API that hops back to main.

**Severity hint** – High — hang, watchdog kill, or priority inversion.

**Refactor direction** – Make the caller `async` and `await` the work; if an API forces synchronous access (initializer, `body`), return a placeholder and fill it from a `.task`/`Task`; bridge callbacks with continuations instead of semaphores.

**Counter-signals** – Blocking waits in a non-main background queue where blocking is the intended design and no main-actor work is awaited inside.

**Sources** – [Matt Massicotte, "Problematic Swift Concurrency Patterns" → blocking for async work](https://massicotte.org/problematic-patterns/) [power-user, updated 2026]; [WWDC25-268](https://developer.apple.com/videos/play/wwdc2025/268/) [official, 2025].

### Re-validate actor state after every `await` (actor reentrancy)

**Rule** – An actor method that reads state, awaits, then writes must re-check its preconditions after the `await`; interleaving at suspension points is guaranteed, not hypothetical.

**Since** – Swift 5.5.

**Detection signals** – Actor methods with `await` between a guard/`if` on actor state and the mutation; `if items.isEmpty { … }` followed by `await` then `items.append(…)`; in-flight bookkeeping (`isLoading`, `inFlightIDs`) set before an `await` and read after; two actor methods mutating the same dictionary around awaits; `withCheckedContinuation` inside an actor method mutating state before resuming.

**Severity hint** – High — double work, duplicated records, lost updates, crashes from stale indices.

**Refactor direction** – Record intent before the await and re-check after:
```swift
func load(_ id: ID) async throws -> Item {
    if let cached = cache[id] { return cached }
    let item = try await client.fetch(id)   // suspension: other calls interleave
    if let cached = cache[id] { return cached } // re-check
    cache[id] = item
    return item
}
```
For "exactly once" semantics use an in-flight `[ID: Task<Item, Error>]` map so the second caller awaits the first task.

**Counter-signals** – Actor methods with no `await` between read and write (synchronous sections are atomic); methods operating on a value captured before the await.

**Sources** – [Donny Wals, "Actor reentrancy in Swift explained"](https://www.donnywals.com/actor-reentrancy-in-swift-explained/) [power-user, 2023]; [WWDC21-10134 "Explore structured concurrency in Swift"](https://developer.apple.com/videos/play/wwdc2021/10134/) [official, 2021].

### Unstructured `Task {}` needs an owner, a cancellation path and an error path

**Rule** – Prefer structured concurrency (`.task`, `async let`, task groups); an unstructured `Task` is acceptable only when a view/model owns it, stores the handle and cancels it, or when the work must outlive the caller.

**Since** – Swift 5.5.

**Detection signals** – `Task {` inside `body`, `init`, `onAppear`, button actions or `View` methods with no stored handle; `Task { }` in `deinit`; a `Task` created per row/render pass; `Task` inside `Task`; view models without `deinit { task?.cancel() }` and without `.task {}`; `Task { }` wrapping work whose failure is logged nowhere; `Task` used where a `didSet`/`onChange` should re-run a `.task(id:)`.

**Severity hint** – Medium (High when the result mutates shared state after the owner is gone).

**Refactor direction** – SwiftUI: `.task(id:)` for lifecycle-bound work; imperative: store `private var task: Task<Void, Never>?`, cancel before replacing and in `deinit`; if it must run detached from the caller, keep the `Task` handle and expose `await task.value`.

**Counter-signals** – Fire-and-forget analytics/logging that is intentionally untracked and cannot fail meaningfully; a `Task` created once by a singleton that lives for the process.

**Sources** – [WWDC21-10134](https://developer.apple.com/videos/play/wwdc2021/10134/) [official, 2021]; [WWDC25-268](https://developer.apple.com/videos/play/wwdc2025/268/) (9:15 ordered operations) [official, 2025]; [Swift Group Lab, WWDC26-8001](https://developer.apple.com/videos/play/wwdc2026/8001/) (structured concurrency Q&A, 06:05) [official, 2026].

### Do not ignore the result of a throwing `Task`

**Rule** – An unstructured `Task` whose closure throws must be either handled inside or stored so `task.value` is awaited; discarding it swallows the error.

**Since** – Swift 6.4 (SE-0520); warning name `#NoUseUnstructuredThrowingTask`.

**Detection signals** – Compiler warning `Unstructured throwing task was not used, which may accidentally ignore errors thrown inside the task [#NoUseUnstructuredThrowingTask]`; `Task { try … }` as a statement; `Task { try await … }` whose `catch` only prints in debug; typed throwing initializers `Task<Int, any Error> { … }` with no consumer.

**Severity hint** – Medium.

**Refactor direction** – Either handle inside (`Task { do { try … } catch { logger.error(error) } }`) or keep the handle (`let task = Task { try … }; try await task.value`), and mark deliberate discards `_ = Task { … }` at the call site so the intent is visible.

**Counter-signals** – `Task` closures that cannot throw; test helpers that intentionally start work.

**Sources** – [SE-0520 Discardable result use in Task initializers](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0520-discardableresult-task-initializers.md) [official, 2026]; [WWDC26-262](https://developer.apple.com/videos/play/wwdc2026/262/) (1:12 diagnostics) [official, 2026].

### `Task.detached` is a last resort; use `@concurrent` to leave the main actor

**Rule** – `Task.detached` drops actor isolation *and* priority, task-local values and cancellation linkage; to run heavy work off the main actor, call a `@concurrent` async function from a normal `Task`.

**Since** – Swift 5.5 (`Task.detached`); `@concurrent` alternative since Swift 6.2.

**Detection signals** – `Task.detached` anywhere in app code; `Task.detached(priority: .background)` used as a substitute for priority propagation; `Task.detached` bodies reading `@MainActor` state via `MainActor.run`; `Task.detached` inside actors or view models that then mutate state (`await MainActor.run { self.x = … }`); detached tasks with no stored handle.

**Severity hint** – Medium (High when the detached task mutates UI state after the view disappeared).

**Refactor direction** –
```swift
// before
Task.detached { let image = decode(data); await MainActor.run { self.image = image } }
// after
Task { let image = await decodeImage(data); self.image = image } // decodeImage is @concurrent
```
Task-local values (`@TaskLocal` tracing/context) and cancellation then keep working.

**Counter-signals** – A deliberate "background job that must not be cancelled with the caller" (upload queue, telemetry flush) where losing inheritance is the point — then keep the handle and document it.

**Sources** – [Matt Massicotte, "Problematic Swift Concurrency Patterns" → Task.detached](https://massicotte.org/problematic-patterns/) [power-user, updated 2026]; [SE-0461](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0461-async-function-isolation.md) [official, 2025]; [WWDC25-268](https://developer.apple.com/videos/play/wwdc2025/268/) [official, 2025].

### Cooperative cancellation must be checked, and cleanup must survive it

**Rule** – Long loops and multi-step async work need `try Task.checkCancellation()` / `Task.isCancelled` at natural boundaries; cleanup that must run after cancellation belongs in `withTaskCancellationShield` (Swift 6.4), not in an unconditioned `defer`.

**Since** – Swift 5.5 (cancellation, `withTaskCancellationHandler`); Swift 6.4 adds `withTaskCancellationShield` (SE-0504) and async `defer` bodies (SE-0493).

**Detection signals** – Loops/`for await` over large collections with no cancellation check; `URLSession`/`FileHandle` work whose result is applied after cancellation without a check; `defer` blocks that call `await` cleanup and bail out because `Task.isCancelled` is true; completion handlers that resume a continuation with success after cancellation; `Task.checkCancellation()` absent in recursive download/upload code; `withTaskCancellationHandler` present but its `onCancel` does not resume the continuation.

**Severity hint** – Medium (High when cancelled work still writes to storage or the server).

**Refactor direction** –
```swift
for chunk in chunks {
    try Task.checkCancellation()
    try await upload(chunk)
}
// cleanup that must finish even after cancellation:
await withTaskCancellationShield { await connection.close() }
```
Inside the shield `Task.isCancelled` is `false`; the outer state is restored afterwards. `defer { await cleanup() }` in an async function (Swift 6.4) runs before the caller resumes and keeps errors visible.

**Counter-signals** – Short, bounded work (a single request, a handful of items) where the latency of a check exceeds the benefit; cleanup that is already cancellation-safe and idempotent.

**Sources** – [SE-0504 Task cancellation shields](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0504-task-cancellation-shields.md) [official, 2026]; [SE-0493 async defer](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0493-defer-async.md) [official, 2026]; [WWDC26-262](https://developer.apple.com/videos/play/wwdc2026/262/) (6:26 task cancellation) [official, 2026]; [Antoine van der Lee, "Swift 6.4: What's New in Concurrency"](https://www.avanderlee.com/concurrency/swift-6-4-whats-new-in-concurrency/) [power-user, 2026].

### Bridge callbacks with checked continuations; `withUnsafeContinuation` needs proof of a single resume

**Rule** – Default to `withCheckedContinuation` / `withCheckedThrowingContinuation`; `withUnsafeContinuation` is only acceptable in a measured hot path where resume-exactly-once is structurally guaranteed.

**Since** – Swift 5.5 (checked variants diagnose misuse at runtime).

**Detection signals** – `withUnsafeContinuation` / `withUnsafeThrowingContinuation` in app code; continuation captured in an escaping closure with several `resume` call sites; `resume` calls in `if`/`guard` branches without an early return; no `resume` on some path (checked continuations log `SWIFT TASK CONTINUATION MISUSE: … leaked its continuation without resuming it`); resuming from both a success and an error callback (`… tried to resume its continuation more than once`); the deprecated `isolation:` overload (`withCheckedContinuation(isolation:function:_:)`, replaced by the `nonisolated(nonsending)` overload in Swift 6.2).

**Severity hint** – High — a leaked continuation hangs the task forever; a double resume crashes.

**Refactor direction** – One resume point per call:
```swift
func fetch() async throws -> Data {
    try await withCheckedThrowingContinuation { cont in
        api.fetch { result in
            cont.resume(with: result)   // the only resume
        }
    }
}
```
If several callbacks can fire, funnel them through an actor or a `Mutex<Bool>` one-shot guard instead of branching on `resume`.

**Counter-signals** – `withUnsafeContinuation` in a framework's internal hot loop with a single unconditional resume (and a comment saying so).

**Sources** – [Donny Wals, "The difference between checked and unsafe continuations in Swift"](https://www.donnywals.com/the-difference-between-checked-and-unsafe-continuation-in-swift/) [power-user, 2023]; [Swift stdlib `CheckedContinuation.swift` runtime diagnostics](https://github.com/swiftlang/swift/blob/main/stdlib/public/Concurrency/CheckedContinuation.swift) [official]; [Apple docs: `withCheckedContinuation`](https://developer.apple.com/documentation/swift/withcheckedcontinuation(function:_:)) [official].

### Model completion-handler APIs that can call back twice, instead of resuming twice

**Rule** – Before bridging a callback API, establish whether the completion can fire more than once (progress handlers, delegate pairs, retries); if it can, guard the continuation with a one-shot state, not with `if resumed`.

**Since** – Swift 5.5.

**Detection signals** – Continuation resumed from `didCompleteWithError` *and* a success handler; `URLSession` delegate `didReceive data:`/`didCompleteWithError` pairs feeding one continuation; old APIs whose completion is documented "may be called multiple times"; `@escaping` completion stored and invoked from two places; `var hasResumed = false` captured by an escaping closure without synchronization (itself a race); `withCheckedContinuation` around `AVAssetExportSession`, `PHPhotoLibrary.performChanges`, `CKModifyRecordsOperation` callbacks that retry.

**Severity hint** – High.

**Refactor direction** – Make the one-shot state a `Mutex<Bool>` (or an actor) and resume through `withLock`:
```swift
let once = Mutex(false)
api.start { result in
    let first = once.withLock { if $0 { return false }; $0 = true; return true }
    guard first else { return }
    cont.resume(with: result)
}
```
Better: pick the single terminal callback the API documents as authoritative.

**Counter-signals** – APIs whose completion is documented exactly-once and called from one code path (most `async` wrappers around `URLSession.dataTask`).

**Sources** – [Donny Wals, "Migrating callback based code to Swift Concurrency with continuations"](https://www.donnywals.com/migrating-callback-based-code-to-swift-concurrency-with-continuations/) [power-user, 2023]; [Swift stdlib `CheckedContinuation.swift`](https://github.com/swiftlang/swift/blob/main/stdlib/public/Concurrency/CheckedContinuation.swift) [official].

### Cancellation-aware bridging: `withTaskCancellationHandler` must resume the continuation

**Rule** – A continuation-based wrapper over a cancellable operation must resume with `CancellationError` from `onCancel`, or the awaiting task hangs after cancellation.

**Since** – Swift 5.5.

**Detection signals** – `withCheckedContinuation` wrapping `URLSessionTask`/`CKOperation`/`AVAssetExportSession` with no `withTaskCancellationHandler`; `withTaskCancellationHandler(operation:onCancel:)` whose `onCancel` only sets a flag or calls `cancel()` without resuming; task handle captured but never cancelled in `onCancel`; `onCancel` resuming while the operation also resumes (double resume); `try Task.checkCancellation()` after the continuation returns instead of before.

**Severity hint** – High — a cancelled download leaves the caller suspended forever; also a leak.

**Refactor direction** –
```swift
try await withTaskCancellationHandler {
    try await withCheckedThrowingContinuation { cont in
        let task = api.start { cont.resume(with: $0) }
        onCancelHook = { task.cancel(); cont.resume(throwing: CancellationError()) } // guarded once
    }
} onCancel: { onCancelHook?() }
```
Keep the resume-once guard from the previous entry so `cancel()` racing a late callback cannot double-resume.

**Counter-signals** – Operations that are cheap and atomic (a single `UserDefaults` read, a Keychain query) where cancellation latency does not matter.

**Sources** – [Apple docs: `withTaskCancellationHandler(operation:onCancel:)`](https://developer.apple.com/documentation/swift/withtaskcancellationhandler(operation:oncancel:)) [official]; [Swift migration guide](https://www.swift.org/migration/documentation/migrationguide/) [official].

### Fan out with a task group when the count is dynamic; `async let` only for a fixed set

**Rule** – Use `withThrowingTaskGroup` for a runtime-sized fan-out, `async let` for a compile-time-fixed number of siblings; never share mutable non-`Sendable` state between concurrently running children.

**Since** – Swift 5.5.

**Detection signals** – `async let` repeated inside a loop or generated per element (compile error or unrolled copy-paste); manual index bookkeeping to reassemble results out of a group (`results[i] = …`) instead of returning values from `addTask`; `group.addTask` closures capturing and mutating a `var` array/`URLSession`-free state; `group.waitForAll()` followed by `next()` (results lost or misordered); `TaskGroup` children that never check cancellation after the parent throws; child tasks capturing `self` from a non-`Sendable` type.

**Severity hint** – Medium.

**Refactor direction** –
```swift
try await withThrowingTaskGroup(of: (Int, Item).self) { group in
    for (i, url) in urls.enumerated() {
        group.addTask { (i, try await fetch(url)) }   // return, don't mutate
    }
    var items = [Item?](repeating: nil, count: urls.count)
    for try await (i, item) in group { items[i] = item }
}
```
A thrown child cancels siblings automatically; awaiting `group.next()` inside the loop keeps memory bounded compared with collecting all results after `waitForAll`.

**Counter-signals** – Two or three independent awaits where `async let` reads better; `withDiscardingTaskGroup` (iOS 17+) for long-lived, never-ending child tasks.

**Sources** – [WWDC21-10134 "Explore structured concurrency in Swift"](https://developer.apple.com/videos/play/wwdc2021/10134/) [official, 2021]; [Swift Group Lab, WWDC26-8001](https://developer.apple.com/videos/play/wwdc2026/8001/) (06:05) [official, 2026].

### Do not mix `DispatchQueue` and locks with actors

**Rule** – Pick one model per piece of state: inside actors and `@MainActor` types there is no place for `DispatchQueue.main.async`, `DispatchQueue.sync` or a lock that spans an `await`.

**Since** – all (Swift 5.5+ actors).

**Detection signals** – `DispatchQueue.main.async` (or `.asyncAfter`) inside `@MainActor` code or `Task { @MainActor in … }` — redundant hop that reorders work; `DispatchQueue.global().sync` / `queue.sync { }` called from an actor method (deadlock risk when the queue block hops back); `NSLock.lock()` held across `await` (lock/unlock unbalanced across suspension); `os_unfair_lock` stored in a struct copied around; `DispatchQueue` used as the isolation for state that also has an actor; `@MainActor` class that also creates a serial `DispatchQueue` "for safety".

**Severity hint** – High (deadlock) / Medium (reordering, priority inversion).

**Refactor direction** – Replace the queue with an actor (`actor Store`) or `@MainActor`; replace lock-protected synchronous state with `Mutex`; for "run after the current main-actor turn" use `Task { @MainActor in … }` or `MainActor.run`, not `DispatchQueue.main.async`.

**Counter-signals** – Legacy callbacks delivered on a specific queue that must be preserved (documented third-party contract) — wrap once at the boundary and convert to `async` there.

**Sources** – [Matt Massicotte, "Problematic Swift Concurrency Patterns"](https://massicotte.org/problematic-patterns/) [power-user, updated 2026]; [WWDC25-268](https://developer.apple.com/videos/play/wwdc2025/268/) (17:16 actor-isolated types) [official, 2025].

### Protect small shared state with `Mutex` (Synchronization), not `NSLock`

**Rule** – For synchronous state shared across isolation domains, use `Mutex`/`Atomic` from the `Synchronization` module; `NSLock` and `os_unfair_lock` have no `Sendable` story and invite unbalanced locking across `await`.

**Since** – Swift 6.0 / iOS 18, macOS 15 (`Synchronization`); `Mutex` is `~Copyable` and conforms to `Sendable`.

**Detection signals** – `NSLock`, `NSRecursiveLock`, `os_unfair_lock`, `pthread_mutex_t` guarding a property that is also touched from `async` code; a class made `@unchecked Sendable` solely because of an internal `NSLock`; `lock()`/`unlock()` pairs split by `return` or `throw` paths (missing `defer`); `Mutex` available but state guarded by `DispatchQueue`; actor used for a two-field counter where a hop costs more than the lock.

**Severity hint** – Medium (High when the lock spans an `await`).

**Refactor direction** –
```swift
import Synchronization
final class Counters: Sendable {
    private let state = Mutex<(sent: Int, failed: Int)>((0, 0))
    func record(success: Bool) {
        state.withLock { $0.sent += 1; if !success { $0.failed += 1 } }
    }
}
```
`withLock` is non-async and cannot suspend, so the critical section cannot interleave; keep actor methods synchronous where possible for the same reason.

**Counter-signals** – Locks owned by third-party code you cannot change; state that must be mutated across `await` (then it belongs in an actor, not a lock).

**Sources** – [Apple docs: `Mutex`](https://developer.apple.com/documentation/synchronization/mutex) (iOS 18+, conforms to `Sendable`) [official]; [SE-0433 Synchronous mutual exclusion lock](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0433-mutex.md) [official, 2024].

### Eliminate global and static mutable state

**Rule** – No `static var`, file-scope `var`, or singleton with mutable properties reachable from more than one isolation domain; make it `let`, isolate it (`@MainActor`, actor), or move it into an injected store.

**Since** – Swift 6.0 (error: "global variable 'x' is not concurrency-safe because it is non-isolated global shared mutable state"; warning with complete checking in Swift 5).

**Detection signals** – `static var` / `static let shared` whose type has `var` properties; file-scope `var` used as a cache, formatter or flag; singletons (`static let shared = …`) with mutable dictionaries and no isolation; `UserDefaults` values cached in `static var`; `@MainActor static var` read from a `nonisolated` context through `assumeIsolated`; global `DateFormatter`/`NumberFormatter` used from concurrent code (not thread-safe in practice for mutation).

**Severity hint** – High.

**Refactor direction** – Convert leaf state to `let` of a `Sendable` value; move mutable state behind an actor or `@MainActor` type injected through the environment/initializer; for process-wide caches expose `async` accessors (`func value(for:) async -> T`) backed by an actor; `nonisolated(unsafe)` is only acceptable with an enforced lock (see that entry).

**Counter-signals** – `static let` of a `Sendable` immutable value (constants, `Logger`, `Notification.Name`); `@MainActor static var` in a UI-only type where every access is on the main actor.

**Sources** – [Swift migration guide, "Unsafe Global and Static Variables"](https://www.swift.org/migration/documentation/swift-6-concurrency-migration-guide/commonproblems/) [official]; [WWDC24-10169](https://developer.apple.com/videos/play/wwdc2024/10169/) (9:26 logger options) [official, 2024]; [Swift Group Lab, WWDC26-8001](https://developer.apple.com/videos/play/wwdc2026/8001/) (14:29 `@MainActor` contagion) [official, 2026].

### App extensions: nonisolated entry points meet a MainActor-default target

**Rule** – Extension entry points are nonisolated (WidgetKit providers, `UNNotificationServiceExtension.didReceive`, `DeviceActivityMonitor` events, `AppIntent.perform`), so an extension target that defaults to `MainActor` must mark those members `nonisolated` — and shared files must not be compiled under two different isolation defaults.

**Since** – Swift 6.2 / Xcode 26 (default isolation per target); iOS 26 SDK for current WidgetKit/DeviceActivity shapes.

**Detection signals** – Extension target with `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor` and a `TimelineProvider`/`AppIntentTimelineProvider` whose `placeholder(in:)`/`getSnapshot`/`getTimeline` are not `nonisolated`; compiler note "main actor isolation inferred from conformance to protocol 'TimelineProvider'" followed by `#ActorIsolatedCall` where WidgetKit calls it; `#ConformanceIsolation` on `AppIntent`, `DeviceActivityMonitor`, `UNNotificationServiceExtension` subclasses; `Task { @MainActor in … }` sprinkled through a widget timeline provider; the same source file listed in both an app target (`MainActor`) and an extension target (`nonisolated`); `NotificationService` doing network work on the main actor because default isolation leaked into it.

**Severity hint** – High — the extension either fails to build in one target or silently hops to the main actor for work that must finish before the extension is killed.

**Refactor direction** – Keep extension targets at `nonisolated` default and mark only the UI/persistence-facing helpers `@MainActor`; in the app, mark extension-implemented conformances `nonisolated` explicitly:
```swift
struct Provider: TimelineProvider {
    nonisolated func placeholder(in context: Context) -> Entry { Entry(date: .now) }
    nonisolated func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) { … }
}
```
and give shared files a single owning module (a package) instead of compiling them into several targets with different defaults.

**Counter-signals** – Extensions whose only work is UI-adjacent and short (a widget that renders precomputed App Group state) — `MainActor` default is then correct, provided the provider methods are `nonisolated`.

**Sources** – [Apple docs: `TimelineProvider`](https://developer.apple.com/documentation/widgetkit/timelineprovider) (`getTimeline` declared `@preconcurrency`, nonisolated) [official]; [Apple docs: `UNNotificationServiceExtension.didReceive(_:withContentHandler:)`](https://developer.apple.com/documentation/usernotifications/unnotificationserviceextension/didreceive(_:withcontenthandler:)) [official]; [Apple docs: `DeviceActivityMonitor`](https://developer.apple.com/documentation/deviceactivity/deviceactivitymonitor) (`@objc`, nonisolated) [official]; [SE-0466](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0466-control-default-actor-isolation.md) [official, 2025]; [SSE amendment: disable `@MainActor` inference for `SendableMetatype` protocols](https://forums.swift.org/t/amendment-se-0466-control-default-actor-isolation-inference/80994) [official-forum, 2025].

## Tools

- `xcodebuild -showBuildSettings -json -project X.xcodeproj -scheme App | jq '.[0].buildSettings | {SWIFT_VERSION, SWIFT_STRICT_CONCURRENCY, SWIFT_DEFAULT_ACTOR_ISOLATION, SWIFT_APPROACHABLE_CONCURRENCY, SWIFT_UPCOMING_FEATURE_NONISOLATED_NONSENDING_BY_DEFAULT, SWIFT_UPCOMING_FEATURE_INFER_ISOLATED_CONFORMANCES}'` — per-target isolation/checking configuration; run once per scheme (app + every extension) and diff.
- `swift package dump-package | jq '.targets[] | {name, settings}'` — SwiftPM `swiftLanguageMode`, `.defaultIsolation`, `.enableUpcomingFeature`.
- `swiftc -swift-version 6 -typecheck File.swift` and `swiftc -swift-version 5 -strict-concurrency=complete -warn-concurrency -typecheck File.swift` — data-race diagnostics without a full build; add `-default-isolation MainActor` to reproduce an app target's isolation.
- `swiftc -debug-diagnostic-names …` — prints the machine-readable IDs (`#ConformanceIsolation`, `#ActorIsolatedCall`, `#NoUseUnstructuredThrowingTask`, `#SendableMetatype`), which are the stable grep targets for findings.
- `swift build -Xswiftc -strict-concurrency=complete -Xswiftc -warn-concurrency` (or `xcodebuild build … SWIFT_STRICT_CONCURRENCY=complete SWIFT_TREAT_WARNINGS_AS_ERRORS=YES`) — turns every concurrency diagnostic into a failure so counts are trustworthy.
- `xcodebuild test -enableThreadSanitizer YES` — Thread Sanitizer catches the races that `@unchecked Sendable`, `nonisolated(unsafe)` and `DispatchQueue` bridging hide from the compiler. The Main Thread Checker (scheme → Diagnostics) is the only check that still flags UI access from a background thread once `@preconcurrency` imports have downgraded main-actor violations to runtime checks.
- `SWIFT_BACKTRACE=enable=yes` in the scheme environment — symbolized crash for `SWIFT TASK CONTINUATION MISUSE` and `Incorrect actor executor assumption` (`MainActor.assumeIsolated`), both of which abort without a useful stack otherwise.
- `xcrun xctrace record --template 'Swift Concurrency' --launch -- ./App.app/App --output concurrency.trace` then `xcrun xctrace export --input concurrency.trace --toc` — Swift Tasks/Swift Actors instruments: shows tasks created and never awaited, actor hops, and main-actor occupancy (evidence for missing `@concurrent`, `Task.detached` and blocking-the-main-actor findings).
- Source greps (run per target, since isolation differs): `rg -n '@unchecked Sendable|nonisolated\(unsafe\)|@preconcurrency|Task\.detached|withUnsafeContinuation|assumeIsolated|DispatchQueue\.main\.(async|sync)|\.sync \{|NSLock|os_unfair_lock|static var|nonisolated func .*async|withCheckedContinuation|withTaskCancellationHandler|Task \{'`.
