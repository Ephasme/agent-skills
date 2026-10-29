# Swift language, API design, modularity, tests — review catalog

Scope: Swift/iOS language-level quality rules. Baseline: **Swift 6.4** (released 2026-09-15), on top of 6.3 (2026-03-24) and 6.2 (2025-09). Rules below note the version a pattern or its fix first applies to. Generic smells (god objects, long methods, naming taste) are out of scope.

## Contents

- [Rules](#rules)
- [Tools](#tools)

## Rules

### 1. Name methods after their side effects, and keep mutating / non-mutating pairs grammatical
- **Rule** — A mutating method takes the imperative verb; its value-returning twin takes the participle (`sort()` / `sorted()`). Non-mutating `Bool` uses read as assertions about the receiver.
- **Since** — all (Swift 3 guidelines).
- **Detection signals** — `func getX()` / `func setX(_:)` accessors; a non-mutating `func sort() -> [T]` or `func sortedArray()`; pairs whose names do not share a base (`append` vs `adding`, `insert` vs `inserted`); `func isValid() -> Bool` vs `var isValid: Bool` used inconsistently; `func check...()` returning `Bool`; mutating methods with noun-only names (`func cache()` that writes).
- **Severity hint** — Low.
- **Refactor direction** — Rename to the imperative/participle pair; convert `getX()` to a property, `setX(_:)` to a `mutating` setter or `x = value`. `func reversed() -> Self` over `func reverseCopy()`.
- **Counter-signals** — Names fixed by Objective-C selectors or a wire protocol; established domain verbs (`print`, `map`, `filter`); mutating-only APIs with no value-returning twin (`Array.removeAll()`).
- **Sources** — [API Design Guidelines — Naming, Strive for Fluent Usage](https://www.swift.org/documentation/api-design-guidelines/) [official].

### 2. Label arguments so the call site reads as a phrase; never leave a `Bool` or closure parameter bare
- **Rule** — Omit the first label only when the base name plus argument forms one grammatical phrase; label everything else, and label Boolean and closure parameters.
- **Since** — all (Swift 3 guidelines).
- **Detection signals** — `set(true)`, `configure(false)`, `flag:`, `value:` for booleans; `func animate(_ duration:)` where `_` does not continue a phrase; unlabeled closure parameters in public APIs; initializers with `_` on a parameter that is not a value-preserving conversion (`init(_ value: Int16)` is fine, `init(_ name: String)` is not).
- **Severity hint** — Low.
- **Refactor direction** — `view.setHidden(true)` → `view.isHidden = true`; `func save(_ force: Bool)` → `func save(forcefully: Bool)`; `func on(_ event: Event, _ handler: @escaping () -> Void)` → `func on(_ event: Event, handler: @escaping () -> Void)`.
- **Counter-signals** — Operators and operator-like functions (`+`, `==`), value-preserving conversions, `print`-style domain notation, XCTest/Swift Testing APIs.
- **Sources** — [API Design Guidelines — Argument Labels, Special Instructions](https://www.swift.org/documentation/api-design-guidelines/) [official].

### 3. Model data with structs and enums; reserve `class` for identity, Obj-C, or shared mutable lifecycle — and mark such classes `final`
- **Rule** — Default to value types. A class must earn itself with reference identity, inheritance from an Apple framework, `deinit`-managed resources, or Objective-C interop. Any class that is not designed for subclassing is `final`.
- **Since** — all; whole-module optimization can infer `final` for non-`public` declarations.
- **Detection signals** — `class` with only stored properties + a memberwise-like init, no `deinit`, no `override`, no `===` comparison, not `NSObject`/`@objc`, never shared across owners; `class` used as a `Codable` DTO; `var` reference properties mutated from several places (aliasing bugs); non-`final` classes in an app target; `open` in a module with no external subclass; Periphery `redundant public accessibility` findings also unlock `final` inference under WMO.
- **Severity hint** — Medium (unintended sharing, and vtable dispatch / retain-release on hot paths).
- **Refactor direction** — `class` → `struct` when copies are cheap and identity is irrelevant; otherwise add `final`. Check `Equatable`/`Hashable`/`Sendable` conformance while converting.
- **Counter-signals** — Reference semantics required (caches, observer registries, delegates, observable models, where `@Observable` is applied to classes); subclassing a framework type (`UIViewController`, `NSObject`); identity compared with `===`; Objective-C runtime needs (`@objc dynamic`, KVO).
- **Sources** — [Choosing Between Structures and Classes](https://developer.apple.com/documentation/swift/choosing-between-structures-and-classes) [official]; [Swift Optimization Tips — use `final`](https://github.com/swiftlang/swift/blob/main/docs/OptimizationTips.rst) [official].

### 4. Delete protocols that exist for a single conformer unless a second implementation is already planned
- **Rule** — A protocol with one conformer and no default implementations is indirection with no seam. Introduce it when the second implementation (including a test double that is actually used) exists.
- **Since** — all.
- **Detection signals** — `protocol X` where repo-wide the only `: X` conformance is the type it mirrors; protocol members that are 1:1 forwarding calls; the only other conformance is an unused mock in test targets; `any X` stored as a property with one possible assignment; protocol + factory + `init(default:)` trio wrapping a concrete type.
- **Severity hint** — Low (Medium when it forces an existential on a hot path — see rule 5).
- **Refactor direction** — Replace the protocol with the concrete type at the call site; if a test double is the reason, keep the protocol only for that seam and keep it internal. If a seam is genuinely needed, prefer a closure or a small struct of closures over a one-method protocol.
- **Counter-signals** — A public package API where conformers are expected outside the module; generic algorithms constrained on the protocol; multiple real conformances (e.g. `Preview` vs `Live`); associated-type protocols (`Iterable`, `Collection`).
- **Sources** — [John Sundell, Alternatives to protocols in Swift](https://www.swiftbysundell.com/articles/alternatives-to-protocols-in-swift) [power-user, 2019]; [API Design Guidelines — protocols read as nouns](https://www.swift.org/documentation/api-design-guidelines/) [official].

### 5. Use `any` only at real type-erasure boundaries; prefer generics or `some` inside algorithms
- **Rule** — `any P` boxes the value (inline 3-word buffer, heap allocation beyond that), adds a value-witness-table word and a protocol-witness-table word, and forces dynamic dispatch. Use a generic parameter or `some P` wherever the concrete type can stay known.
- **Since** — `any` spelling: Swift 5.6 (SE-0335). Still a **warning** under the Swift 6 language mode in 6.4 (`#ExistentialAny`), so absence of `any` is itself a signal of undeclared existential use.
- **Detection signals** — `any P` properties, parameters, or locals inside loops, render paths, parsers, or numeric code; `[any P]` whose elements are all one concrete type; existential passed straight into a generic function; `let x: any P = Concrete()` immediately followed by member calls; `some P` return whose body has a single `return Concrete()` (fine, but a sign the type could be concrete); Instruments allocation/ARC traces pointing at existential boxes in a hot loop.
- **Severity hint** — Medium (allocation and dispatch cost; Low outside hot paths).
- **Refactor direction** — `func draw(_ shapes: [any Shape])` → `func draw<S: Shape>(_ shapes: [S])` when homogeneous; `func make() -> any Shape` → `some Shape`; keep `any` for heterogeneous storage.
- **Counter-signals** — Heterogeneous collections, plugin/DI registries, values stored across a boundary where the concrete type is unknowable, `any Error` in `throws`. Note: class-constrained existentials cost 2 words vs 1 for a bare class reference, and the existential path is only marginally worse than a class hierarchy — measure before rewriting.
- **Sources** — [SE-0335 Existential `any`](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0335-existential-any.md) [official]; [Swift Forums: Relative Performance of Existential `any` (Jordan Rose, Slava Pestov)](https://forums.swift.org/t/relative-performance-of-existential-any/77299) [power-user, 2025]; [TSPL — Opaque and Boxed Protocol Types](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/opaquetypes/) [official].

### 6. Remove `!`, `try!`, `as!`, implicitly unwrapped optionals and `fatalError` from production paths
- **Rule** — A trap on user-, network-, or disk-derived data is a crash. Force unwrap only where a proof exists in the same function; `fatalError`/`preconditionFailure` only for programmer errors, never for inputs.
- **Since** — all (IUO semantics refined in SE-0054, Swift 4.2).
- **Detection signals** — `try!`, `as!`, postfix `!` on calls/subscripts/`as`; declarations `var x: T!` outside `@IBOutlet`; `fatalError(` / `preconditionFailure(` reachable from decoding, URL handling, `init?(rawValue:)`, dictionary lookups, `first`, `last`, `URL(string:)`, `Int(_:)`, `FileManager` calls; `assert` used to validate external input (removed in optimized builds, so the check silently disappears) or `precondition` on external input (traps in release); `-Ounchecked` in a Release configuration; `@unchecked Sendable` masking the same unsafe access.
- **Severity hint** — High (crash or data loss on a path reachable with real data).
- **Refactor direction** — `guard let` / `if let` with a thrown domain error; `as?` plus a `DecodingError`/`typeMismatch`; `do/catch` around `try!`; `switch` over a known set with `@unknown default` instead of `fatalError`. Keep `precondition` only for invariants the type itself establishes (e.g. non-empty name in `init`).
- **Counter-signals** — `@IBOutlet` (Xcode's own template uses IUO), test code, `fatalError` in `switch` over a compiler-enforced exhaustive enum with genuinely no valid other case, `try!` on a literal that cannot throw (still prefer `try`).
- **Sources** — [TSPL — Implicitly Unwrapped Optionals](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/thebasics/) [official]; [TSPL — Converting Errors to Optional Values / Disabling Error Propagation](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/errorhandling/) [official]; [TSPL — Assertions and Preconditions](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/thebasics/) [official].

### 7. Keep `throws` untyped except in narrow, fully-handled, non-public boundaries (typed throws)
- **Rule** — Typed throws (`throws(E)`) is for code that exhaustively handles its own errors, generic pass-through, or allocation-free environments. Untyped `throws` remains the default because it does not constrain future error cases.
- **Since** — Swift 6.0 (SE-0413). Note: `FullTypedThrows` inference was **not** implemented, so every `throws(E)` must be written explicitly and every inner throwing call wrapped in `do/catch` to map into `E`.
- **Detection signals** — `throws(SomeError)` on a `public`/`package` API or a protocol requirement; typed throws on a function whose body wraps three or more calls in `do/catch` just to preserve `E`; `throws(E)` where `E` is a single-case enum wrapping an underlying error; `Result`-returning APIs converted to typed throws for "precision"; overloads distinguished only by thrown type.
- **Severity hint** — Low (API evolution risk; Medium when it causes error re-mapping noise).
- **Refactor direction** — Drop to `throws`; keep typed throws for internal parsers/validators whose caller switches exhaustively over the cases, and for generic functions that only forward a caller-provided error type.
- **Counter-signals** — Single-module implementation detail where the caller must handle every case; `Never` for non-throwing generic closures; `rethrows` replacement; Embedded Swift / no-allocation code; `Task`'s `Failure` type.
- **Sources** — [SE-0413 Typed throws, "When to use typed throws"](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0413-typed-throws.md) [official].

### 8. Never discard errors: no bare `try?` on meaningful work, no unobserved throwing `Task`
- **Rule** — `try?` converts any error into `nil` and destroys the reason. Handle, map, or at minimum record the error. Since 6.4 the compiler warns when a `Task` initializer's thrown error is ignored — treat that warning as a defect, not noise.
- **Since** — `try?` all versions; the `Task` warning: Swift 6.4 (SE-0520).
- **Detection signals** — `try?` on a call whose result is then `?? default` or discarded; `try? await`; `catch {}` or `catch { print(error) }` with no propagation/telemetry; `Task { try ... }` with the task handle unused (new warning in 6.4); `Task.detached { try ... }`; `Result` values created and dropped; `#if DEBUG`-only logging in a catch.
- **Severity hint** — High (silent data loss, state divergence).
- **Refactor direction** — `do { try save() } catch { logger.error(...); state = .failed(error) }`; when ignoring is intentional, say so: `try? cache.flush()` on a best-effort path with a comment, or `_ = try? ...`. For fire-and-forget work, keep the `Task` handle and `await`/inspect it later, or use a `TaskGroup` so failures surface.
- **Counter-signals** — Best-effort cleanup in `defer`; optional cache reads where "absent" and "failed" are the same outcome for the caller; deliberately ignored errors in tests.
- **Sources** — [TSPL — Converting Errors to Optional Values](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/errorhandling/) [official]; [SE-0520 Discardable result use in Task initializers](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0520-discardable-result-task-initializers.md) [official]; [WWDC26-262 What's new in Swift](https://developer.apple.com/videos/play/wwdc2026/262/) [official].

### 9. Use `Result` for stored or deferred outcomes, not as the return type of async code
- **Rule** — `async throws` is the return channel for asynchronous work. `Result` is a value: use it when the outcome must be stored, serialized, memoized, or passed through a callback.
- **Since** — `Result`: all; async `Result.init(catching:)`: Swift 6.4.
- **Detection signals** — `func load() async -> Result<T, Error>`; `switch` over a `Result` that only rethrows or unwraps right after `await`; completion-handler API plus a parallel async wrapper that both survive; `Result` used as a `ViewState` instead of an enum with explicit `loading/failed` cases; `Result` mapped through `flatMap` chains in async code.
- **Severity hint** — Medium (call-site noise and double error modelling; Low if the value is genuinely stored).
- **Refactor direction** — `func load() async throws -> T`; at the storage boundary convert once: `let result: Result<T, Error> = await Result { try await load() }` (new 6.4 initializer, removes the manual do/catch).
- **Counter-signals** — Result stored in model/state and rendered; callback-based APIs that cannot be made async yet; memoizing outcomes for later replay; the `Failure` type captured by `Task`/`TaskGroup`.
- **Sources** — [Preserving the Results of a Throwing Expression](https://developer.apple.com/documentation/swift/preserving-the-results-of-a-throwing-expression) [official]; [SE-0413 — communicates less error information than `Result` or `Task`](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0413-typed-throws.md) [official]; [Result — `init(catching:)` async overload](https://developer.apple.com/documentation/swift/result) [official].

### 10. Keep access as narrow as possible; use `package` between targets of one package instead of `public`
- **Rule** — Default is `internal`; `private` beats `fileprivate`; `package` is the cross-target, in-package level; `public` is only for a module's real external surface. In an app target `public` buys nothing; in a library it also blocks WMO's automatic `final` inference and enlarges the ABI surface.
- **Since** — `package`: Swift 5.9 (SE-0386); `private` members visible to same-file extensions: Swift 4.
- **Detection signals** — `public` declarations in an app/executable target; `public` types never referenced from another module (Periphery's redundant-public analysis); `fileprivate` where no other declaration in the file uses the symbol; `@testable import` replaced by widening API to `public` "for tests"; missing `package` on symbols shared by sibling targets of one package; `open` outside a framework.
- **Severity hint** — Medium (public surface blocks WMO's automatic `final` inference and hides dead code).
- **Refactor direction** — Delete `public`; introduce `package` when a sibling target in the same package needs the symbol; keep `@testable import` for tests instead of widening access.
- **Counter-signals** — Framework/package products with real external consumers; `@_spi` for staged API; Objective-C headers that must see the declaration.
- **Sources** — [SE-0386 New access modifier: `package`](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0386-package-access-modifier.md) [official]; [Periphery — Redundant Public Accessibility](https://periphery.pro/docs/analysis/redundant-public/) [power-user tool docs]; [Swift Optimization Tips — `private`/`fileprivate`](https://github.com/swiftlang/swift/blob/main/docs/OptimizationTips.rst) [official].

### 11. Don't put `@discardableResult` on functions whose return value signals failure
- **Rule** — The attribute deletes the compiler's unused-result warning. Keep that warning where the result carries information (success flag, `Result`, count, created object); add the attribute only where ignoring the result is the normal, safe use.
- **Since** — all. Reinforced by SE-0520 (6.4), which deliberately removed `@discardableResult` from throwing `Task` initializers for exactly this reason.
- **Detection signals** — `@discardableResult` on `-> Bool`, `-> Result`, `-> Int` (count), `-> T?` (created/found object), or on `throws` APIs; several `@discardableResult` declarations per module; attribute added in the same commit that introduced call sites ignoring the result; an existing `_ = try?`/`_ =` at many call sites.
- **Severity hint** — Low (Medium when the ignored value is a failure signal).
- **Refactor direction** — Remove the attribute and handle the result at the call site; if ignoring is legitimate, make it explicit at each call (`_ = cache.purge()`), which documents intent without disabling the check module-wide.
- **Counter-signals** — Fluent/DSL builders where chaining is optional; convenience methods whose result duplicates state the caller already has; `mutating` collection APIs where the result is a bonus (`Set.insert(_:)` returns `(inserted:memberAfterInsert:)` and is `@discardableResult`).
- **Sources** — [SE-0520 — Motivation](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0520-discardable-result-task-initializers.md) [official].

### 12. Replace stringly-typed identifiers with enums, `RawRepresentable` wrappers, or typed constants
- **Rule** — Any string that names something in your own program (defaults key, notification name, route, cell identifier, analytic event, image name) belongs in a type, not a literal repeated at call sites.
- **Since** — all.
- **Detection signals** — `UserDefaults.standard.string(forKey: "…")` with the same literal in more than one file; `NotificationCenter.default.post(name: Notification.Name("…"))` or `NSNotification.Name("…")` inline; `func track(_ event: String)`; `switch` over `String` with a `default:`; identifiers typed `String` where the valid set is finite (`func open(_ screen: String)`); `[String: Any]` config dictionaries; cell reuse identifiers as literals (`"UserCell"`); `Selector("…")` built from string literals (compile-time checked `#selector` is the fix).
- **Severity hint** — Medium (silent typos, no exhaustive switch, rename fragility).
- **Refactor direction** — `enum DefaultsKey: String { case hasSeenOnboarding }`; `extension Notification.Name { static let didSync = Self("app.didSync") }`; `struct Route: RawRepresentable { let rawValue: String; static let settings = Route(rawValue: "settings") }` with `ExpressibleByStringLiteral` **not** conformed.
- **Counter-signals** — Wire-format keys (JSON/CodingKeys) which must stay strings — confine them to the `Codable` layer; localized user-facing strings (`LocalizedStringKey`); URLs/paths received from outside.
- **Sources** — [Adam Wulf, Type-safe notifications in Swift](https://adamwulf.me/2022/02/type-safe-notifications-in-swift/) [power-user, 2022]; [Daniel Tull, Type-safe User Defaults](https://danieltull.co.uk/blog/2019/10/09/type-safe-user-defaults/) [power-user, 2019].

### 13. Treat `Codable` as a wire contract: explicit keys, no swallowed decode errors, unknown cases preserved
- **Rule** — Decoding is a schema boundary. Never let a missing/changed field silently become a default, never let an unknown enum raw value fail the whole payload, and never decode dates without an explicit strategy.
- **Since** — all (Codable since Swift 4).
- **Detection signals** — `init(from:)` containing `try?` or `decodeIfPresent(...) ?? <default>` for fields that are required by the server; a new non-optional `let` added to a type that decodes persisted data (old payloads now fail with `keyNotFound`); enums decoded via `RawRepresentable` where a new server value would throw (`dataCorrupted`); `JSONDecoder()` without `dateDecodingStrategy` (defaults to `.deferredToDate`, i.e. Double since 2001); encoder and decoder configured with different `keyEncodingStrategy`/`keyDecodingStrategy`; hand-written `CodingKeys` duplicating `snake_case` conversion; a hand-rolled `[String: Any]` parse sitting next to (or replacing) a `Codable` model; `encode`/`init(from:)` asymmetry (field encoded but never decoded or vice versa).
- **Severity hint** — High (data loss, migration breakage).
- **Refactor direction** — Keep key mapping in `CodingKeys` and use one strategy consistently; use `decodeIfPresent` only for fields the contract marks optional; make extensible enums decode unknown values into a `.unknown(String)` case with a custom `init(from:)`; set `dateDecodingStrategy = .iso8601` (or a custom formatter) next to the decoder's construction; add a fixture test per payload version.
- **Counter-signals** — Internal persistence you fully control and version; genuinely optional fields; lossy analytics payloads where dropping a bad record is the desired behaviour (log it).
- **Sources** — [Donny Wals, JSON parsing in Swift explained using Codable](https://www.donnywals.com/json-parsing-in-swift-explained-using-codable/) [power-user, 2021/updated 2025].

### 14. Use property wrappers to encapsulate reusable storage semantics, not to hide I/O or shrink a property
- **Rule** — A wrapper earns itself when the same get/set transformation is reused and testable. A wrapper that performs disk/network access hides side effects behind property syntax and breaks value-type reasoning.
- **Since** — Swift 5.1 (SE-0258).
- **Detection signals** — `@propertyWrapper` types whose `wrappedValue` touches `UserDefaults`, `FileManager`, Keychain, or the network; `@UserDefault("key")` style wrappers used across the app; a wrapper whose backing `_value` breaks synthesised `Codable`/`Equatable`/`Hashable`/`Sendable` on the enclosing type because the wrapper itself does not conform; a wrapper used on exactly one property with a one-line get/set; `@Published` on a model that is not observed by SwiftUI (pre-Observation pattern); wrapper applied to `let`; wrapper whose `projectedValue` is never used.
- **Severity hint** — Medium (hidden I/O, broken conformances, untestable state).
- **Refactor direction** — Replace with a plain stored property plus an explicit `SettingsStore`/service call at the boundary; for observable models on iOS 17+, `@Observable` on the class instead of `@Published` per property.
- **Counter-signals** — SwiftUI's `@State`/`@Binding`/`@Environment`/`@FocusState`; `@Published` inside an `ObservableObject` view model (pre-Observation, still valid); wrappers that encode a reusable, tested invariant (clamping, validation) used on several properties.
- **Sources** — [SE-0258 Property Wrappers](https://github.com/swiftlang/swift-evolution/blob/master/proposals/0258-property-wrappers.md) [official]; [Christian Tietze, UserDefaults Access via Property Wrappers Is Worse Than You Might Think](https://christiantietze.de/posts/2019/12/userdefaults-property-wrappers/) [power-user, 2019]; [Apple — Observable()](https://developer.apple.com/documentation/observation/observable()) [official].

### 15. Don't write a macro where a function, protocol extension, or plain code would do
- **Rule** — Macros are for boilerplate that must be generated at compile time and cannot be expressed otherwise. A macro used once, expanding to a few lines, is a build-time tax and an invisible control-flow hop.
- **Since** — Swift 5.9 (SE-0382/SE-0389/SE-0397).
- **Detection signals** — `macro` declarations whose expansion is shorter than the call site; macro used in a single file; a macro duplicating a compiler feature (memberwise init, `CaseIterable`, `Equatable` synthesis); macro targets in `Package.swift` pulling `swift-syntax`; CI build times dominated by macro-plugin compilation (prebuilt SwiftSyntax landed in Xcode 16.4, older toolchains build it from source: ~20 s debug, >4 min release); no expansion tests; reviewers cannot see the generated members without `-Xfrontend -dump-macro-expansions`.
- **Severity hint** — Low (Medium for build time in large projects).
- **Refactor direction** — Replace with a free function or a protocol extension; if the macro stays, add expansion tests and pin a toolchain with prebuilt SwiftSyntax.
- **Counter-signals** — Framework macros (`@Observable`, `#Preview`, `@Model`); `#expect`/`#require`; macros replacing dozens of repetitive conformances; compile-time-checked DSLs.
- **Sources** — [Point-Free, Mitigating SwiftSyntax build times](https://www.pointfree.co/blog/posts/171-mitigating-swiftsyntax-build-times) [power-user, 2025]; [SE-0382 Expression macros](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0382-expression-macros.md) [official].

### 16. Use ownership modifiers deliberately: `borrowing` for read-only parameters, `consuming` only when ownership transfers
- **Rule** — `borrowing` and `consuming` document and enforce what a function does with its argument. Do not make business models `~Copyable`; do use `borrowing` to avoid retain/release on class parameters and copies on large structs.
- **Since** — Swift 5.9 (SE-0377, SE-0390); 6.4 extends conformance support (Equatable/Comparable/Hashable on noncopyable types, noncopyable associated types, `Iterable`, `borrow`/`mutate` accessors).
- **Detection signals** — `consuming` on a parameter the body only reads (or reads before storing); missing `borrowing` on hot-path class parameters; `~Copyable` struct with no `deinit` and no `consuming` method (ownership machinery for nothing); noncopyable type used in public model/API surface; `let x = value` followed by use of both (forces a copy that `borrowing` would avoid); a noncopyable element type forced into `UniqueArray`/`InlineArray` when a plain copyable model would have been simpler (`Array` still requires `Copyable` elements).
- **Severity hint** — Low (Medium on measured hot paths).
- **Refactor direction** — Add `borrowing` to read-only parameters; keep `consuming` for types that release a resource or explicitly transfer a buffer; keep `~Copyable` for resource handles, and leave models `Copyable`.
- **Counter-signals** — Small structs where copying is a couple of words; `consuming` factory methods that intentionally transfer ownership; compiler-synthesised conformances that require `Copyable`.
- **Sources** — [SE-0377 Parameter ownership modifiers](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0377-parameter-ownership-modifiers.md) [official]; [SE-0390 Noncopyable structs and enums](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0390-noncopyable-structs-and-enums.md) [official]; [WWDC26-262 — Ownership System & Noncopyable Types](https://developer.apple.com/videos/play/wwdc2026/262/) [official].

### 17. Keep `Array` as the default; reach for `InlineArray` and `Span` only where allocation is measured
- **Rule** — `InlineArray` is a fixed-size array stored inline in its container (no heap allocation, no COW); `Span` is a non-escapable view over contiguous storage with no copy. Both are performance tools with lifetime and API-shape costs, not general replacements for `Array`.
- **Since** — Swift 6.2 (SE-0453 `InlineArray`, SE-0447 `Span`); 6.4 adds `Iterable` for `for`-in over noncopyable collections.
- **Detection signals** — `InlineArray<N, T>` in a public API, model, or `Codable` type; fixed-size tuple used as an array (`let x = (a, b, c)` indexed manually); `Span` stored in a property or returned from a computed property (lifetime errors force `@lifetime`/closure plumbing); `withSpan`/`withUnsafe...` closures doing escaping work; conversion to `Array` immediately after obtaining a `Span` (defeats the purpose); `[N of T]` sugar in code that never profiles.
- **Severity hint** — Low.
- **Refactor direction** — Keep `[T]` until a profile shows allocation/COW cost; use `Span` at parsing/serialization boundaries where the buffer is borrowed for the duration of a call; use `InlineArray` for small fixed-size numeric buffers.
- **Counter-signals** — Crypto/audio/graphics fixed-size buffers; embedded targets; APIs that already traffic in `UnsafeBufferPointer` and can be made safe with `Span`.
- **Sources** — [SE-0453 InlineArray](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0453-vector.md) [official]; [SE-0447 Span](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0447-span-access-shared-contiguous-storage.md) [official]; [WWDC26-262 — New standard library types](https://developer.apple.com/videos/play/wwdc2026/262/) [official].

### 18. Split the app into local SwiftPM packages along a dependency DAG
- **Rule** — Modularise by dependency direction (models/utilities at the leaves, features above, app shell on top), not by file type. A package must not need to know about the app or about a sibling feature.
- **Since** — all (SwiftPM); `package` access for cross-target internals: Swift 5.9.
- **Detection signals** — one app target with hundreds of files and no `Package.swift`; local package whose `dependencies:` include a feature package it should not know about; `import` graph with cycles (SwiftPM rejects them, so the symptom is duplicated types instead); a package importing the app module or `@testable import`ing it; a single target containing both UI and networking; every symbol in the package `public` (see rule 10); build log showing most files recompiling for a one-line change (no module boundary).
- **Severity hint** — Medium (build times, ownership, testability).
- **Refactor direction** — Extract a leaf package (models, API client protocol), depend inward only, expose cross-target internals with `package`, keep UI composition in the app target.
- **Counter-signals** — Small apps where the package boundary costs more than it saves; heavy `@_spi`/Objective-C coupling; single-developer prototypes.
- **Sources** — [Organizing your code with local packages](https://developer.apple.com/documentation/xcode/organizing-your-code-with-local-packages) [official]; [SE-0386 `package`](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0386-package-access-modifier.md) [official].

### 19. Break up expressions and functions the type checker chokes on; measure with the frontend flags
- **Rule** — Long expressions with overloaded operators and mixed numeric types cost seconds of compile time per file. Split them, annotate types, and put the measurement in CI.
- **Since** — all (flags available across versions; verified on 6.4).
- **Detection signals** — `-Xfrontend -warn-long-expression-type-checking=100` output (e.g. "expression took 1200ms to type-check"); one expression spanning dozens of lines; `+`/`??`/ternary chains mixing `Double`, `CGFloat`, `Int`; large array/dictionary literals with heterogeneous element types; nested closures with inferred parameter/return types; a function body > 100 lines; one file taking > 1 s in the Xcode build log while its neighbours take 50 ms.
- **Severity hint** — Medium (developer throughput).
- **Refactor direction** — Annotate `let x: CGFloat = ...`, split `let` steps, replace long `+` chains with interpolation or an array `joined()`, move subexpressions into small typed functions/properties.
- **Counter-signals** — SwiftUI `View` bodies are the usual offender but are owned by the SwiftUI checklist; generated code; one-off scripts.
- **Sources** — [Swift Forums — Debugging long compile times (Jon Shier)](https://forums.swift.org/t/debugging-long-compile-times/52447) [power-user, 2021]; flag list verified against `swiftc -frontend -help-hidden` on Swift 6.4 [official].

### 20. Write new tests with Swift Testing; migrate assertions, not frameworks, incrementally
- **Rule** — New tests use `@Test`/`#expect`/`#require` and suites. Keep XCTest where it is still the only option (UI tests, performance tests), and use 6.4's interoperability instead of a big-bang rewrite.
- **Since** — Swift 6.0 / Xcode 16; XCTest↔Swift Testing interoperability: Swift 6.4 (ST-0021).
- **Detection signals** — new files with `import XCTest` + `XCTAssert*`; `XCTestCase` subclass holding a single test; `XCTestExpectation` + `wait(for:timeout:)`; `@Test` functions containing zero `#expect`/`#require` (assert-free tests); `#expect` inside a `Task {}` that is never awaited (assertion can never fail the test); nested `for` loops over inputs instead of `@Test(arguments:)`; tests that only assert "does not crash"; `XCTUnwrap`/`XCTAssert*` in new Swift Testing code (interop makes them report, but `try #require` / `#expect` is the native idiom).
- **Severity hint** — Low (Medium when assert-free tests hide regressions).
- **Refactor direction** — `@Test func \`parses empty payload\`() throws { let model = try #require(decode(fixture)); #expect(model.items.isEmpty) }`; parameterize with `@Test(arguments: cases)`; gate with `.enabled(if:)` rather than an early `return`.
- **Counter-signals** — XCUITest, `measure {}` performance tests, APIs only reachable through XCTest (delegate expectations with run-loop pumping); files mid-migration.
- **Sources** — [Swift Testing](https://developer.apple.com/documentation/testing) [official]; [Migrating a test from XCTest](https://developer.apple.com/documentation/testing/migratingfromxctest) [official]; [WWDC26-267 Migrate to Swift Testing](https://developer.apple.com/videos/play/wwdc2026/267/) [official].

### 21. Keep tests isolated: no shared mutable global state, no sleeps, no blanket `.serialized`
- **Rule** — Swift Testing runs test functions in parallel on arbitrary tasks (XCTest ran synchronous tests on the main actor). Shared `UserDefaults`, singletons, temp files and clocks must be injected, and `.serialized` is a last resort, not a default.
- **Since** — Swift 6.0.
- **Detection signals** — `@Suite(.serialized)` on suites that only touch local state; `static var` in a suite or a global fixture; tests reading/writing `UserDefaults.standard`, `FileManager.default` shared paths, Keychain, or a singleton; `Task.sleep`/`Thread.sleep`/`RunLoop.run` as synchronisation; date/locale/timezone-dependent assertions; tests relying on execution order; a test calling `@MainActor` code without `@MainActor` on the test (compile error under the Swift 6 language mode unless the module opts into default main-actor isolation).
- **Severity hint** — Medium (flaky CI, false greens).
- **Refactor direction** — Inject fakes (protocol or closure) per test; mark UI-touching tests `@MainActor`; use `confirmation` for callback APIs; freeze time with an injected clock; reserve `.serialized` for a genuinely shared resource and clean it up in the test.
- **Counter-signals** — One shared simulator/device resource with explicit setup/teardown; tests that mutate a real app group container by design.
- **Sources** — [Migrating a test from XCTest — parallelism and main-actor notes](https://developer.apple.com/documentation/testing/migratingfromxctest) [official]; [WWDC26-267](https://developer.apple.com/videos/play/wwdc2026/267/) [official].

### 22. Remove dead code with Periphery in CI; don't keep "just in case" declarations
- **Rule** — Unused declarations are a maintenance and compile-time cost. Run an index-store-based scan, baseline the existing findings, and fail on new ones.
- **Since** — all (index-based unused-code analysis); current tooling is Periphery 3.x, commercial with sign-in and `.periphery.yml` config.
- **Detection signals** — `periphery scan --strict` findings; assign-only properties (written, never read); unused imports; `redundant public accessibility`; `#if DEBUG` helpers referenced only from previews; commented-out code blocks; `@objc`/`dynamic` code reachable only via selectors (mark retained rather than deleting); unused `Codable` fields that no payload uses.
- **Severity hint** — Low (Medium on large codebases: compile time and reviewer confusion).
- **Refactor direction** — Delete; rely on version control. For public library API, run with `--retain-public` so only genuinely dead internals surface, and delete only after checking SPI/selector entry points.
- **Counter-signals** — Public API of a shipped library; Objective-C runtime/selector/KVC entry points; SwiftUI preview-only helpers; test-only helpers in test targets.
- **Sources** — [Periphery — Running a Scan](https://periphery.pro/docs/running-a-scan/) and [Configuration](https://periphery.pro/docs/configuration/) [power-user tool docs, 2026]; [Redundant Public Accessibility](https://periphery.pro/docs/analysis/redundant-public/) [power-user tool docs].

### 23. Confine unsafe code behind a safe wrapper, and enable strict memory safety on new targets
- **Rule** — `Unsafe*` pointers, `unsafeBitCast`, `nonisolated(unsafe)` and `@unchecked Sendable` are audit points. Wrap them in one type with a safe API and tests; opt in to `-strict-memory-safety` so new unsafe expressions are flagged.
- **Since** — Swift 6.2 (SE-0458, opt-in).
- **Detection signals** — `UnsafeMutablePointer`, `UnsafeRawBufferPointer`, `withUnsafeBytes`, `withUnsafeMutableBufferPointer`, `unsafeBitCast`, `Unmanaged`, `nonisolated(unsafe)`, `@unchecked Sendable` outside a wrapper; unsafe calls spread across features rather than one file; missing `-strict-memory-safety` in the target's Swift flags; `-Ounchecked`; `unsafe` expressions whose bounds are derived from remote input.
- **Severity hint** — High when reachable from untrusted input; Medium otherwise.
- **Refactor direction** — Collapse into one `struct` that validates lengths/alignment, exposes `Span`/`Array` APIs, and owns the only `unsafe` expressions; add the flag per target and fix the diagnostics it produces.
- **Counter-signals** — Thin C/C++ interop layer with fuzz tests; performance-critical parser already covered by sanitizers.
- **Sources** — [SE-0458 Opt-in Strict Memory Safety Checking](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0458-strict-memory-safety.md) [official].

### 24. Don't add `@inline(always)` or `@specialized` speculatively
- **Rule** — Forced inlining and forced specialization are last-mile tuning after measurement. Applied broadly they bloat binaries and can slow builds without moving runtime numbers.
- **Since** — `@specialized`: Swift 6.3; `@inline(always)`: Swift 6.4; `@inlinable`/`@usableFromInline`: Swift 5.
- **Detection signals** — `@inline(always)` on non-trivial or non-`final` methods, or applied module-wide; `@specialized(where:)` on helpers used with many types; `@inlinable` exposing internals without `@usableFromInline` hygiene; `-Ounchecked` used to "make it fast"; no benchmark or Instruments trace backing the attribute.
- **Severity hint** — Low.
- **Refactor direction** — Remove; rely on WMO, `final`, and `@inlinable` at real module boundaries; re-add only with a trace showing the call site is hot.
- **Counter-signals** — Tiny arithmetic/byte helpers proven hot; generic code in a library where the concrete type is only known to the client (the documented `@specialized` use case); `@inline(always)` on a `final` method the optimizer refuses to inline.
- **Sources** — [WWDC26-262 — tuning performance-sensitive code](https://developer.apple.com/videos/play/wwdc2026/262/) [official]; [Swift Optimization Tips](https://github.com/swiftlang/swift/blob/main/docs/OptimizationTips.rst) [official].

## Tools

Commands verified against Swift 6.4 on macOS unless noted.

**Type-checker and build time**
- `swift build -Xswiftc -Xfrontend -Xswiftc -warn-long-expression-type-checking=100 -Xswiftc -Xfrontend -Xswiftc -warn-long-function-bodies=100` — warns per expression/body over the threshold; the fastest way to find type-checker hot spots.
- `swiftc -typecheck -Xfrontend -debug-time-expression-type-checking File.swift` — prints `ms<TAB>file:line:col` per expression.
- `swiftc -typecheck -Xfrontend -debug-time-function-bodies File.swift` — per-body type-check times.
- Xcode: add the same `-Xfrontend -warn-long-…` pairs under *Other Swift Flags*, one per line.

**Warnings as evidence**
- `swiftc -swift-version 6 -Werror <Group>` / `-Wwarning <Group>` — promote or demote a warning group (e.g. `ExistentialAny`, `DeprecatedDeclaration`); groups are shown in the diagnostic as `[#Group]`.
- `@diagnose(Group, as: ignored|warning|error)` (Swift 6.4, SE-0522) — same control at declaration scope; useful to silence one migration hotspot without disabling the group module-wide.
- `-strict-memory-safety` (Swift 6.2+, SE-0458) — diagnoses unsafe constructs; `-strict-memory-safety:migrate` for staged adoption.
- `-Xfrontend -dump-macro-expansions` — prints each macro expansion, the only practical way to review what a custom macro generates.

**Style and dead code**
- `swift format lint -r -s .` — swift-format ships in the toolchain as `swift format`; `-s/--strict` makes findings fail the run.
- `swiftlint lint --strict` — SwiftLint 0.65.1 (2026-08); relevant rules: `force_cast`, `force_try`, `force_unwrapping` (opt-in), `redundant_type_annotation`, `empty_count`.
- `periphery scan --strict` — index-store based unused-code scan; configure once in `.periphery.yml` (e.g. `project`, `schemes`, `exclude_tests`, `retain_public`), or run `periphery scan --setup`. Detects unused declarations, assign-only properties, unused imports, redundant `public`, unused `Codable` members, unused XCTest cases. Periphery 3.x is commercial and requires sign-in; the open-source repo is archived.

**Tests**
- `swift test` — runs Swift Testing and XCTest side by side; Swift Testing tests run in parallel on arbitrary tasks.
- Xcode test plan → *Test Execution* → interoperability mode: `limited` (default; cross-framework issues downgraded) or `complete` (issues promoted to failures) — the switch for the 6.4 XCTest↔Swift Testing interop.
- `swift test --enable-code-coverage` — coverage for suites; combine with `#expect`/`#require` to spot assert-free tests.
