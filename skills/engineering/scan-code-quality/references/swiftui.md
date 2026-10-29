# SwiftUI state, architecture and rendering performance

Scope: SwiftUI only. Baseline today is Swift 6.4 / Xcode 27.1 / iOS 27. SwiftUI built with Xcode 27 is the "2027 releases" SDK; several rules below changed shape there and are marked.

## Contents

- [Rules](#rules)
- [Tools](#tools)

## Rules

### 1. Give every screen exactly one owner of its state; pass everything else
**Rule** – Declare the model once, with `@State`, in the narrowest view (or `App`/`Scene`) that must outlive its children; pass it down as `let` and read shared app-wide models from `@Environment`.
**Since** – iOS 17 (`@Observable`); generic to SwiftUI.
**Detection signals** –
- Two `@State` variables in different views holding the same `@Observable` instance, or a `@State` in a child re-wrapping an argument: `_model = State(initialValue: model)`, `@State var model: Model` plus an `init(model:)` that assigns it.
- A model constructed in a `body` (`MyView(model: Model())`) — new instance every body evaluation, all state lost.
- `@State` inside `ForEach` rows to mirror row data (`@State var title: String` seeded from `item.title`): the mirror goes stale on data change and is never reset when SwiftUI recycles the row.
**Severity hint** – High (silent data loss / stale UI).
**Refactor direction** – Delete the mirrored `@State`, take a `@Binding` or a `let` model. If a child genuinely needs local editing state, seed it once in `init` and omit the inline default (see #5).
```swift
// before: child owns a copy, drops updates
struct Row: View { @State var item: Item; var body: some View { Text(item.title) } }
// after
struct Row: View { @Binding var item: Item; var body: some View { Text(item.title) } }
```
**Counter-signals** – A per-row `@State` for ephemeral, non-model UI (expanded/collapsed, hover, focus) is correct; do not promote it.
**Sources** – https://developer.apple.com/documentation/swiftui/managing-model-data-in-your-app [official]; WWDC23 10149 "Discover Observation in SwiftUI" [official]; WWDC21 10022 "Demystify SwiftUI" (identity drives state lifetime) [official].

### 2. Migrate `ObservableObject` to `@Observable`, and drop `@Published` when you do
**Rule** – Replace `ObservableObject` + `@Published` + `@StateObject`/`@ObservedObject`/`@EnvironmentObject` with `@Observable` + `@State`/`@Bindable`/`@Environment(Type.self)`; never leave `@Published` in a class that is also `@Observable`.
**Since** – iOS 17 / macOS 14 / Xcode 15.
**Detection signals** –
- `: ObservableObject`, `objectWillChange`, `@Published`, `@StateObject`, `@ObservedObject`, `@EnvironmentObject`, `AnyCancellable` stored for observation.
- **Highest-value signal:** a class annotated `@Observable` that still has `@Published` properties. Compiles; SwiftUI does not track them; those rows silently stop updating (only the Combine publisher fires, and nothing subscribes). Severity High.
- `@Observable` class that still calls `objectWillChange.send()` — dead code that looks like it matters.
**Severity hint** – Medium for the mechanical migration; High for the `@Published`-inside-`@Observable` hybrid.
**Refactor direction** – Delete `ObservableObject` conformance and every `@Published`; keep plain `var`. At the call site swap `@StateObject`→`@State`, `@ObservedObject`→`let` (or `@Bindable` if it needs `$`), `@EnvironmentObject`→`@Environment(Model.self)`.
**Counter-signals** – Keep `ObservableObject` when you need Combine semantics SwiftUI cannot express — `objectWillChange` coalescing with an operator pipeline, a class shared with UIKit/AppKit code that observes it, or a deployment target below iOS 17 with no `@Observable` back-deploy. Observation also cannot be adopted on a type you don't own; wrap it.
**Sources** – https://developer.apple.com/documentation/swiftui/migrating-from-the-observable-object-protocol-to-the-observable-macro [official]; WWDC23 10149 [official].

### 3. Track at property granularity — a view must not depend on a whole model
**Rule** – Read only the properties a view needs; when a collection is large and mutates per element, make each element an `@Observable` class instead of a field in an array on one big model.
**Since** – iOS 17.
**Detection signals** –
- A view that takes `model: AppModel` but reads one property, so every write anywhere on the model re-runs that `body`. Use `Self._printChanges()` to prove it.
- `@Observable` class holding `var items: [struct Item]` rendered in a long `List`, where flipping one item's `isFavorite` reassigns the array. Array identity is not observed per element — Observation tracks the `items` property, so the whole list re-evaluates.
- An `@Observable` model whose only mutation path is `items[i].x = y` / `items = items.map { … }`.
**Severity hint** – Medium (measurable per-frame cost on scroll).
**Refactor direction** – Split into `@Observable final class Item` elements (`Identifiable`) inside the parent; each row then depends on its own instance.
**Counter-signals** – Small collections (< ~50 rows), or views that legitimately read the whole collection each time. Do not shatter a model into 30 observable classes for a settings screen.
**Sources** – WWDC25 306 "Optimize SwiftUI performance with Instruments" (per-item observable model for the Landmarks list) [official]; WWDC23 10160 "Demystify SwiftUI performance" (dependency scoping) [official]; WWDC23 10149 [official].

### 4. Use `@Bindable` for bindings into an `@Observable` you do not own
**Rule** – `@State` owns, `let`/parameter reads, `@Bindable` writes-through. Add `@Bindable` only where a `$` projection into someone else's model is required.
**Since** – iOS 17.
**Detection signals** –
- `TextField(text: $model.name)` on a plain `let model` or on an `@Environment(Model.self) var model` — with Observation this does not compile, so the code that does compile often shows the workaround smell: `@Bindable var model = model` declared at the top of `body`, or `Binding(get:set:)` wrappers where `@Bindable` would do.
- Manual `Binding(get: { model.x }, set: { model.x = $0 })` for a simple property.
- `@StateObject` retained purely to obtain `$`.
**Severity hint** – Low (friction), Medium when hand-rolled `Binding` copies a value instead of writing through (data loss).
**Refactor direction** – `struct DonutView: View { @Bindable var donut: Donut; var body: some View { TextField("Name", text: $donut.name) } }`.
**Counter-signals** – A view that only ever sets a value to a constant, or one that needs a transformed binding (clamping, formatting) — a real `Binding(get:set:)` is right there.
**Sources** – WWDC23 10149 (chapters "Using @Bindable") [official]; https://developer.apple.com/documentation/swiftui/bindable [official].

### 5. Never assign a `@State` that already has an inline default; never rely on `@State` init ordering
**Rule** – If the initial value must come from the initializer, declare `@State` **without** an inline default and assign it in `init` after all other stored properties; if it has an inline default, never assign it in `init`.
**Since** – Xcode 27 makes these hard errors and documents the silent case; the runtime trap (inline default wins, `init` assignment discarded) exists on every version.
**Detection signals** –
- `@State private var x = <default>` **and** an `init` containing `self.x = …` or `_x = State(initialValue:)` — silently ignored, view renders the default. High.
- In an `init`, assigning to a `@State` before other stored properties are initialized — Xcode 27 error `'self' used in property access '_x' before 'super.init' call` / `variable 'self.x' used before being initialized`.
- A view whose `@State` properties are all `private`, initialized from an extension `init` that calls `self.init(...)`: no memberwise initializer is synthesized under the macro (SE-0400 init accessors).
- Two property wrappers stacked on one property (`@State @Something var`).
**Severity hint** – High (silent wrong-value bugs; hard build breaks on upgrade).
**Refactor direction** – Remove the inline default when `init` supplies the value; reorder `init` so non-`@State` stored properties are assigned first.
```swift
struct StickerPageView: View {
    @State private var page: StickerPage   // no inline default
    let title: String
    init(title: String) { self.page = StickerPage(title: title); self.title = title }
}
```
**Counter-signals** – `@StateObject` keeps its `init(wrappedValue:)` autoclosure; the "assign in `init`" prohibition applies to `@State`, not `@StateObject`, and `StateObject(wrappedValue:)` must be called *inside* the closure/thunk or you lose the laziness the wrapper exists for.
**Sources** – TN3211 "Resolving SwiftUI source incompatibilities for State and ContentBuilder" [official]; WWDC26 269 "What's new in SwiftUI" 23:48–24:02 [official]; Jared Sinclair, "Be Careful When You Initialize a State Object", 2024 [power-user].

### 6. Know that `@State` initialization became lazy in Xcode 27 — and don't build on side effects either way
**Rule** – Treat `@Observable` initializers as pure and cheap: no network, no disk, no `Task {}`, no analytics. Laziness is now guaranteed, but the initializer still runs on a background-free path in the middle of view creation.
**Since** – Xcode 27 (Swift 6.4): `@State` is a macro, the value is created once for the view's lifetime; behaviour back-ported to iOS 17 / macOS 14 deployment targets. Before Xcode 27 the initial-value expression ran on **every** view init and the result was discarded.
**Detection signals** –
- `@Observable` class whose `init` calls `fetch()`, `URLSession.shared.data(...)`, `FileManager`, `UserDefaults.standard.set`, or `Task { }`.
- `@State private var model = Model()` where `Model.init` is O(n) over persisted data.
- Migration evidence of the old cost: `@StateObject` used *solely* for its autoclosure, or `@State private var model: Model?` + `.task { model = Model() }` workarounds — the manual fix for this exact problem, now obsolete.
**Severity hint** – Medium (startup/main-thread cost, duplicate side effects when views are re-created), High when the initializer performs I/O.
**Refactor direction** – Move loading to `.task` on the view; keep `init` to stored-property assignment.
**Counter-signals** – Cheap value computation, or `@State` of a value type (`Bool`, `String`, enum) where evaluation cost is irrelevant.
**Sources** – WWDC26 269 19:58–23:08 [official]; https://developer.apple.com/documentation/swiftui/state() ("When you build with Xcode 26 or earlier, the system uses the State property wrapper instead") [official]; WWDC23 10160 (expensive dynamic-property instantiation as a top cause of slow updates) [official].

### 7. Mark non-UI stored properties `@ObservationIgnored`
**Rule** – Anything a view must not be invalidated by — caches, services, delegates, Combine cancellables, `let` dependencies captured for later — gets `@ObservationIgnored`.
**Since** – iOS 17.
**Detection signals** –
- `@Observable` class with stored `var cache: [ID: Image]`, `var searchTask: Task<Void, Never>?`, `var cancellables`, `let apiClient`, `weak var delegate` and no `@ObservationIgnored`.
- An `@Observable` model whose `body` re-runs during a cache fill (`_printChanges` shows the view updating for a write no view reads).
- `@ObservationIgnored` on a *computed* property's only dependency — this makes the computed property never fire (opposite bug, High).
**Severity hint** – Low/Medium (spurious invalidation), High for the computed-property case (frozen UI).
**Refactor direction** – Annotate the property; keep observation on anything a view reads for display.
**Counter-signals** – A view genuinely displays the cached value's freshness; then it should observe it deliberately, via a tracked property.
**Sources** – https://developer.apple.com/documentation/Observation/ObservationIgnored() [official]; WWDC23 10149 [official].

### 8. Keep `body` free of formatting, sorting, filtering and allocation
**Rule** – `body` may compose views and read state; it may not format dates/numbers, localize, sort, filter, or build new collections on every pass. Precompute on the model, or format once at the boundary.
**Since** – all; measured by the SwiftUI instrument from Xcode 26.
**Detection signals** –
- In `body` or a computed `some View`: `DateFormatter()`, `NumberFormatter()`, `Date.FormatStyle` constructed inline, `String(format:)`, `String(localized:)`, `Bundle.main.localizedString(...)`, `…formatted(...)` over a freshly built style, `.sorted`, `.filter`, `.map`, `Set(...)`, `Dictionary(uniqueKeysWithValues:)`.
- A `DateFormatter`/`NumberFormatter` stored in a view (`let formatter = DateFormatter()`) — re-allocated on every view init, which is every parent body pass.
- Measured: Long View Body Updates > 500 µs (orange) / > 1000 µs (red) in the SwiftUI instrument.
**Severity hint** – High when it is per-row in a scroll view; Medium otherwise.
**Refactor direction** – Do the transform once where the data is written or in a `let` on the model; cache the formatter in a `static`/`enum` constant or in the model, not in the view.
```swift
// before
Text(DateFormatter.relative.localizedString(for: event.date, relativeTo: .now))   // new formatter-ish work per pass
// after
private static let relative = RelativeDateTimeFormatter()
Text(Self.relative.localizedString(for: event.date, relativeTo: .now))
```
**Counter-signals** – Hot-path string interpolation of already-formatted values (`"\(count) items"`) is cheap; the cost is in the formatter, the locale lookup and the bundle lookup, not the interpolation operator.
**Sources** – https://developer.apple.com/documentation/xcode/understanding-and-improving-swiftui-performance [official]; WWDC25 306 [official]; WWDC23 10160 (string interpolation, bundle, image lookup named as update costs) [official].

### 9. Never store an escaping closure in a view; call the builder closure in `init`
**Rule** – A view initializer that accepts a closure producing a child view must invoke it during initialization and store the resulting view, and the parameter must not be `@escaping`.
**Since** – all.
**Detection signals** –
- `struct Wrapper<Content: View>: View { let content: () -> Content; init(@ViewBuilder content: @escaping () -> Content) { self.content = content } }` — the closure is retained, deferred past layout/identity, and re-invoked at arbitrary times.
- Stored closures used as callbacks (`let onTap: () -> Void`) where a button/binding modifier would do.
- `@escaping` on any view-initializer parameter.
**Severity hint** – Medium (lost identity, layout churn, retain cycles through `self` capture).
**Refactor direction** – `init(@ContentBuilder content: () -> Content) { self.content = content() }`.
**Counter-signals** – Genuine action closures handed to a control (`Button(action:)`), which are ephemeral, not stored view content.
**Sources** – "Understanding and improving SwiftUI performance", section on storing closures [official].

### 10. Use `ForEach` identities that are stable, unique and derived from the model
**Rule** – Every `ForEach` element needs an `id` that survives reordering, insertion and updates, and never collides.
**Since** – all.
**Detection signals** –
- `ForEach(items.indices, id: \.self)`, `ForEach(0..<items.count)`, `ForEach(Array(items.enumerated()), id: \.offset)` — identity is position: inserting at the top reassigns every row's identity, so all state and animations shift one row down.
- `id: \.self` on a struct whose content changes (name, title) — identity changes on every edit.
- `var id = UUID()` on a value type that is re-created from the network/disk on refresh — every reload creates a new identity.
- Duplicate ids (ids derived from a non-unique field like `category`): SwiftUI warns "ID occurs multiple times within the collection".
- `ForEach` over filtered/derived collections whose count changes inside a lazy stack (see #12).
**Severity hint** – High (state loss, flashing content, scroll jumps).
**Refactor direction** – `Identifiable` with a server/DB-derived id; otherwise a stable key (`item.uuid` persisted with the value).
```swift
// before: id is the row position
ForEach(model.pets.indices, id: \.self) { i in PetRow(model.pets[i]) }
// after
ForEach(model.pets) { pet in PetRow(pet) }   // Pet: Identifiable with a persisted id
```
**Counter-signals** – Static literal ranges (`ForEach(0..<7)` over fixed card slots) are fine — the collection never mutates.
**Sources** – WWDC21 10022 (identifier stability, index ids, uniqueness) [official]; WWDC23 10160 "Identity in List and Table" [official].

### 11. Do not use `.id()` to force a refresh
**Rule** – `.id()` changes a view's identity and therefore destroys and rebuilds it; use it only when you intend a full reset, and never generate the value per render.
**Since** – all.
**Detection signals** –
- `.id(UUID())`, `.id(Date())`, `.id(UUID().uuidString)` — a new identity on every body pass: infinite view churn, animations never run.
- `.id(item.id)` applied inside a `List`/`ForEach` row (row already has identity) — measured slow; benchmarks put this among the worst offenders.
- `.id(someCounter)` used as an "invalidate" trick, often alongside state that is then lost.
- `.id()` combined with `.transition`/`.animation` on the same view — the transition never fires because the view is replaced, not animated.
**Severity hint** – High (state loss, hangs during scroll).
**Refactor direction** – Remove it; if you wanted new *data*, fix the model or the view's dependency. If you wanted a new *animation*, key the animation on the value with `.animation(_:value:)`.
**Counter-signals** – Deliberate resets: `.id(document.id)` on an editor so switching documents discards the old editor's state; `.id(selection)` to reset a `ScrollView`'s offset. Both are legitimate when the value is stable per logical document.
**Sources** – https://forums.swift.org/t/swiftui-and-anyview-performance-benchmarks/65717 (Michael Long, 2023, `.id()` inside rows measured) [power-user]; WWDC21 10022 (identity defines lifetime) [official].

### 12. Do not branch on visibility inside lazy-stack children — filter at the data level
**Rule** – A child of `LazyVStack`/`LazyHStack`/`LazyVGrid` must resolve to a constant number of views; conditional rendering inside the child makes the count dynamic, forcing size re-estimation and layout thrash.
**Since** – iOS 27 SDK guidance; the underlying mechanism applies from iOS 14 lazy stacks.
**Detection signals** –
- `if condition { Content() }` or `if condition { Content() } else { EmptyView() }` as the top level of a view used inside `ForEach` in a lazy container. (`EmptyView()` is still a branch.)
- `if let x = optional { … }` inside a lazy child — optional unwrapping is a `_ConditionalContent`.
- An `@Environment` value read only to decide whether to render (`detailLevel`, `writingStyle`, feature flags) inside a lazy row.
- Child `body` returning more than one view at top level (multiple statements, `VStack` of ungrouped siblings) where a single resolved subview would do.
**Severity hint** – Medium (scroll hitches, estimated-size drift, wrong scroll offsets).
**Refactor direction** – Keep the branch in the view but make the child's view count constant, or filter before the `ForEach`: `ForEach(steps.filter(\.isVisible))`, or a `@Query`/`#Predicate` at the data layer. Unwrap optionals before the child; pass a non-optional.
```swift
// before — dynamic view count per lazy row
struct StepView: View { let step: Step; @Environment(\.detailLevel) var lvl
  var body: some View { if step.isVisible(in: lvl) { StepBody(step) } } }
// after — filter at the data level
init(detailLevel: DetailLevel) { _steps = Query(filter: #Predicate { $0.detailLevel >= detailLevel }) }
```
**Counter-signals** – Conditional content in a non-lazy `VStack`/`List` row is normal and idiomatic; `List` virtualises but does not estimate sizes the same way.
**Sources** – WWDC26 321 "Dive into lazy stacks and scrolling with SwiftUI", chapters "Subview loading" 9:13–13:15 and "Prefetching" 13:15–17:40 [official].

### 13. Configure a lazy cell in its initializer, not in `onAppear`; load asynchronously with `.task`
**Rule** – Lazy children are created before they appear and can be created, discarded and re-created while scrolling; configuration belongs in `init`, asynchronous work in `.task`, and the result in a model the cell does not own.
**Since** – iOS 27 SDK guidance; `.task` from iOS 15.
**Detection signals** –
- `onAppear { viewModel.configure() }` / `onAppear { load() }` on a row inside a lazy container — appears-too-late flashes, or repeated work as rows are recycled.
- `@State var viewModel = StepViewModel()` inside a lazy row, with the id passed in `onAppear` — the state belongs to the row's identity, not the item.
- `onAppear { Task { await fetch() } }` anywhere: uncancellable, fires again on every appearance.
- `.task` on a lazy row without `id:` for work that depends on the row's item.
**Severity hint** – Medium.
**Refactor direction** – Synchronous setup in `init`; `let id: Step.ID` + `.task(id: id) { await model.load(id) }`; hold per-item data in a model outside the cell.
**Counter-signals** – `.task` on a screen-level view is correct; `.onAppear` remains right for non-idempotent, view-instance-scoped triggers such as starting an analytics timer for the screen.
**Sources** – WWDC26 321 15:53–17:40 ("Setting up lazy stack subview in onAppear") [official]; WWDC21 10034 "Discover concurrency in SwiftUI" [official].

### 14. Prefer `.task` over `onAppear` + `Task`, and `.task(id:)` for parameterised work
**Rule** – Use `.task` for anything async: it starts before the view appears and SwiftUI cancels it when the view disappears or its identity changes. Use `.task(id:)` when the work depends on a value; the old task is cancelled and a new one starts when that value changes.
**Since** – iOS 15 (`task(priority:_:)` / `task(id:priority:_:)`); since iOS 26.4 / Xcode 26 the modifiers accept `name:`/`file:`/`line:` for task naming in Instruments (no-ops on earlier releases).
**Detection signals** –
- `onAppear { Task { … } }` or `onAppear { Task.detached { … } }` — never cancelled, outlives the view, writes to dead state.
- `.task { await load(query) }` where `query` is read from state but not passed as `id:` — stale results after the query changes.
- `.onChange(of: query) { Task { … } }` — the same problem hand-rolled, without cancellation of the previous task.
- `.task` on a view that is conditionally replaced (`if`) instead of the same view with changing `id:` — the task is torn down with the identity, which may be right or may be a bug depending on intent.
**Severity hint** – High for `onAppear`+`Task` (leaked work, data races, writes after teardown); Medium for the missing `id:`.
**Refactor direction** –
```swift
// before
.onAppear { Task { results = await search(query) } }
// after
.task(id: query) { results = await search(query) }
```
**Counter-signals** – Fire-and-forget work that must survive the view (upload, sync) belongs in a model/service, not in `.task`; `.task` is tied to the view's lifetime by design.
**Sources** – https://developer.apple.com/documentation/swiftui/view/task(id:name:priority:file:line:_:) [official]; https://developer.apple.com/documentation/swiftui/view/task(name:priority:file:line:_:) [official]; WWDC21 10034 [official].

### 15. Do not create a view-model layer per screen; let the view read the model
**Rule** – Default architecture is model + view: an `@Observable` model (or plain values) that the view reads directly. A per-screen view model that only forwards properties and rebuilds them as `@Published`/computed state adds a synchronisation layer SwiftUI does not need.
**Since** – all; the `@Observable` form from iOS 17.
**Detection signals** –
- A `ViewModel` type that owns no logic beyond `func didTapX() { model.y = … }` and mirrors model fields (`var title: String { model.title }`), with the view holding both the model and the view model.
- Duplicated derived state: `@Published var isEnabled` in the view model recomputed from `canSubmit`, plus the view also computing `canSubmit`.
- `ObservableObject` view models introduced where the only reason was to get `objectWillChange` — superseded by #2/#3.
- One view model per view *file*, named after the view, with no test that uses it (the layer pays for itself only through tests).
**Severity hint** – Medium (duplicate state, stale copies, extra invalidation).
**Refactor direction** – Delete the pass-through; keep the logic as methods on the `@Observable` model and let the view call them. Keep a view model where it holds genuinely view-scoped state machines (multi-step wizard, gesture-driven editing session).
**Counter-signals** – Legitimate: a view model that adapts a legacy/UIKit/backend type, holds a non-trivial async state machine with retries, or is the unit under test. Apple's own WWDC25 sample introduces a small per-item `@Observable` model for list rows — fine-grained, not a screen-level MVVM layer. Note also that MVVM is not a SwiftUI concept at all: Apple's guidance and its Landmarks sample use `@Observable class ModelData`, `@State private var modelData = ModelData()` in the `App`, `.environment(modelData)`, and views that read it — no view-model layer anywhere.
**Sources** – https://developer.apple.com/documentation/swiftui/managing-model-data-in-your-app [official]; https://developer.apple.com/tutorials/swiftui/handling-user-input (Landmarks: `@Observable`, `@State private var modelData = ModelData()`, `.environment(modelData)`) [official]; WWDC25 306 [official]; Paul Hudson, "Introducing MVVM into your SwiftUI project" (MVVM as one option, not a requirement) [power-user]; Fatbobman, "Single Source of Truth in SwiftUI", 2020 (why `ObservableObject` forced coarse models) [power-user].

### 16. Avoid `AnyView`; use `@ContentBuilder` branches, `AnyLayout` or inert modifiers
**Rule** – Type-erasing a view destroys structural identity: when the erased type changes, the old hierarchy is torn down and a new one built, losing state and animations. Express variation with builder branches, `AnyLayout`, or modifiers that stay inert.
**Since** – all; `AnyLayout` from iOS 16.
**Detection signals** –
- `AnyView(` anywhere; especially `-> AnyView` helper functions and `[AnyView]` arrays, which exist only to satisfy a single return type.
- A `@ViewBuilder` function that returns `AnyView` in each branch — the builder already solved the type problem.
- Switching layout by branching (`if horizontal { HStack{…} } else { VStack{…} }`) instead of `AnyLayout(HStackLayout())` / `AnyLayout(VStackLayout())` — the branch changes identity and resets child state.
- Toggling *presence* by branching (`if isEnabled { Label() }`) instead of `.opacity`/`.disabled`, when the branch sits inside an animated container.
**Severity hint** – Medium (state loss, animation glitches, extra work per update).
**Refactor direction** –
```swift
// before
func icon() -> AnyView { isOn ? AnyView(BellOn()) : AnyView(BellOff()) }
// after — same type both branches, identity preserved
Bell().symbolVariant(isOn ? .fill : .none)
// layout switch without identity change
let layout = horizontal ? AnyLayout(HStackLayout()) : AnyLayout(VStackLayout())
layout { Content() }
```
**Counter-signals** – One `AnyView` around a single opaque view in a non-hot path is measurably near-free; the real cost is per-row in a large collection, or where the erased type actually changes. Erasing a `some View` you cannot name (third-party builder output stored in a property) is an acceptable use.
**Sources** – https://developer.apple.com/documentation/swiftui/anyview ("the old hierarchy is destroyed and a new hierarchy is created for the new type") [official]; WWDC21 10022 ("structural identity… its evil nemesis, AnyView") [official]; https://forums.swift.org/t/swiftui-and-anyview-performance-benchmarks/65717 (2023) [power-user].

### 17. Extract a `View` struct instead of a computed `some View` property
**Rule** – A computed property inside a view has no identity and no dependency scope of its own: it re-evaluates whenever the enclosing `body` does. A separate `View` struct gets its own dependency tracking and re-evaluates only when its own inputs change.
**Since** – all.
**Detection signals** –
- `var header: some View { … }`, `var rows: some View { … }`, `@ViewBuilder var content: some View` inside a view struct — properties of type `some View`, not nested types.
- `body` longer than ~40–60 lines, or a view file over ~250 lines with several such properties, where each one reads a different slice of the model.
- `Self._printChanges()` inside a large view showing it re-runs for a change that only one section consumes.
- Functions returning `some View` that take arguments (`func row(for item: Item) -> some View`) — same problem, plus a closure-free escape hatch that hides the cost.
**Severity hint** – Medium (measurable: every parent-driven update redoes all sections).
**Refactor direction** – Promote each property to `private struct Section: View { let slice: Slice }`, passing only the values it reads (not the whole model — see #3).
**Counter-signals** – A one-line computed property used once (`var body: some View { content }`), or a property that is pure layout with no dependencies; extracting it buys nothing.
**Sources** – WWDC23 10160 ("extract views to reduce dependencies", 8:46–8:48 before/after) [official]; https://developer.apple.com/documentation/xcode/understanding-and-improving-swiftui-performance [official]; WWDC21 10022 [official].

### 18. Confine `GeometryReader` to the smallest possible scope, and prefer `onGeometryChange`
**Rule** – `GeometryReader` is greedy (it takes all offered space and reports zero intrinsic size), so it must never wrap a row, a cell, or the root of a screen whose layout depends on its own content. To react to geometry changes, use `onGeometryChange(for:of:action:)`, which reports only when the transformed value changes, instead of rebuilding a subtree from a proxy.
**Since** – `GeometryReader` all; `onGeometryChange(for:of:action:)` iOS 18 SDK (Apple's availability metadata lists iOS 16+, so it back-deploys); `containerRelativeFrame` iOS 17; `ScrollPosition` / `onScrollGeometryChange` iOS 18.
**Detection signals** –
- `GeometryReader` as the outermost view of a screen (intended replacement for `Color.clear` backgrounds or for `Spacer`-based layout) — everything inside is now sized against the reader, not the content.
- `GeometryReader` inside `ForEach` rows or inside a lazy stack child — each row measures the full container and defeats size estimation.
- `GeometryReader { geo in … }` used solely to read `geo.size.width` for a width/height/padding calculation, where `.frame(maxWidth:)`, `.containerRelativeFrame`, `ViewThatFits`, or a custom `Layout` would express it.
- `GeometryReader` used to detect scroll offset (classic `GeometryReader`-in-background + preference-key plumbing) — replaced by `onScrollGeometryChange(for:of:action:)`.
- `GeometryReader` wrapping a whole scroll view, so every scroll tick rebuilds the reader's subtree (named in Apple's own guidance as a cause of updates that change nothing).
- `ScrollViewReader` + `scrollTo` plumbing where `ScrollPosition` / `scrollTargetLayout` would do.
**Severity hint** – Medium (layout cost, hitches); High when per-row in a long list.
**Refactor direction** –
```swift
// before: whole subtree rebuilt on scroll
GeometryReader { geo in Content(offset: geo.frame(in: .global).minY) }
// after: only fires when the transformed value changes
.onGeometryChange(for: Bool.self) { $0.frame(in: .global).minY > 0 } action: { _, above in self.above = above }
```
**Counter-signals** – Legitimate: a card/board layout that genuinely divides the *available* space into a grid (Apple's own WWDC26 card-game sample does exactly this), and geometry-dependent drawing/canvas work inside a `Canvas`. Even then, scope it to the smallest subtree.
**Sources** – https://developer.apple.com/documentation/xcode/understanding-and-improving-swiftui-performance (GeometryReader/ScrollViewReader scope, 125–156) [official]; https://developer.apple.com/documentation/swiftui/view/ongeometrychange(for:of:action:) [official]; WWDC26 271 "A guide to layout in SwiftUI" [official].

### 19. Use `NavigationStack` with a typed path; `NavigationView` is gone
**Rule** – Build navigation on `NavigationStack`/`NavigationSplitView` with `navigationDestination(for:)` and a `NavigationPath` or homogeneous array held in state or in the model; never `NavigationView`.
**Since** – `NavigationStack` iOS 16 / macOS 13; `NavigationView` deprecated in iOS 16 and its availability in Apple's current documentation now ends at 27.2.
**Detection signals** –
- `NavigationView { }`, `.navigationViewStyle(...)`, `NavigationLink(destination:isActive:)`, `NavigationLink(tag:selection:)` — the path-less forms deprecated alongside `NavigationView`.
- `NavigationLink(destination:)` inside a `List`/`ForEach` — still compiles, but builds every destination eagerly and cannot be driven from a path; the value-based `NavigationLink(_:value:)` plus `navigationDestination(for:)` replaces it.
- Navigation state kept in ad-hoc booleans (`@State var showDetail = false` + `.sheet`/`isActive`) instead of a path, so deep links and state restoration cannot be expressed.
- `navigationDestination` declared *inside* the lazily loaded content of the stack — inside a `List`/`LazyVStack` row or inside `ForEach` — where Apple's docs say not to put it: destinations must be inside the stack but outside the lazy container.
- `NavigationStack` nested inside another `NavigationStack`/`TabView` column.
- A `NavigationPath` reset by reassigning `path = NavigationPath()` when the user should be able to pop one level.
**Severity hint** – Medium (unbuildable deep links, broken state restoration). High if the app still targets a UI where `NavigationView` behaviour differs per platform.
**Refactor direction** – `@State private var path: [Park] = []`, `NavigationStack(path: $path) { List(parks) { NavigationLink($0.name, value: $0) }.navigationDestination(for: Park.self) { ParkDetails(park: $0) } }`; mutate `path` for programmatic navigation.
**Counter-signals** – A single-level modal-ish flow with no programmatic navigation can legitimately use a plain sheet instead of a stack.
**Sources** – https://developer.apple.com/documentation/swiftui/navigationstack [official]; https://developer.apple.com/documentation/swiftui/navigationview (availability ends 27.2) [official]; https://developer.apple.com/documentation/swiftui/navigationpath [official]; WWDC22 10054 "The SwiftUI cookbook for navigation" [official].

### 20. Do not put fast-changing values in the environment
**Rule** – An environment change invalidates every view that reads that key, even when its `body` would produce the same result; keep the environment for stable dependencies (models, services, locale, colour scheme) and pass per-frame values as parameters.
**Since** – all.
**Detection signals** –
- Custom `EnvironmentKey`/`EnvironmentValues` extension holding something written on every scroll/gesture/tick (offset, drag translation, playback progress, published search text).
- `.environment(\.x, value)` applied at a view that wraps a large subtree, where `value` changes per frame.
- `@Observable` model put in the environment via `.environmentObject`/`.environment(_:)` at the *root* while hundreds of leaf views read it for one field (see #3 — environment registration is fine, coarse reads are not).
- Custom `EnvironmentKey` used to pass an `@Observable` model where `.environment(model)` + `@Environment(Model.self)` now exists.
**Severity hint** – Medium (update storm), High when it drives a scroll-linked effect.
**Refactor direction** – Pass the changing value as an initializer parameter to the few views that need it; keep the environment entry for the stable model.
**Counter-signals** – Values that change rarely (theme, dynamic type, authentication state) are exactly what the environment is for.
**Sources** – WWDC25 306 (environment changes invalidate readers; avoid storing frequently changing values in the environment) [official]; WWDC23 10160 (environment as a dependency) [official].

### 21. Previews: `#Preview` + `@Previewable`, driven by the same environment the app injects
**Rule** – Replace `PreviewProvider` structs with `#Preview`; declare inline `@State`/`@Bindable` in the preview body with `@Previewable`; inject the same model and environment the real app injects rather than a parallelism of fakes that can drift.
**Since** – `#Preview` Xcode 15+ (compile-time only, so it works at any deployment target); `@Previewable` Xcode 16+; in Xcode 27 the `#Preview` body parameter is typed `@ContentBuilder` instead of `@ViewBuilder`.
**Detection signals** –
- `struct …_Previews: PreviewProvider { static var previews: some View { … } }`.
- `PreviewProvider` kept only because the view needs state at preview time: `@State private var x = …` in a wrapper struct — now expressible inline.
- `@Previewable` used outside a `#Preview` body (compile error) or applied to a property-wrapper composition.
- Previews constructing a second, hand-built mock model per view (`PreviewModel()`) while the app uses `.environment(model)` — the two drift and previews stop being evidence.
- No preview for a view that has heavy state; or a preview that requires a live network/persisted store to render.
**Severity hint** – Low (friction), Medium when previews diverge from the injected environment (they stop catching crashes).
**Refactor direction** –
```swift
#Preview("toggle") {
    @Previewable @State var toggled = true
    Toggle("Loud Noises", isOn: $toggled)
}
#Preview { LibraryView().environment(ModelData.preview) }
```
**Counter-signals** – Separate fixture values for previews are fine; duplicated *wiring* (a second environment setup path) is the smell.
**Sources** – https://developer.apple.com/documentation/swiftui/previewable() [official]; https://developer.apple.com/documentation/swiftui/preview(_:body:) [official]; WWDC24 10144 "What's new in SwiftUI" [official].

### 22. Budget for `@ContentBuilder` when upgrading to Xcode 27
**Rule** – SwiftUI's result builders are unified under `@ContentBuilder` in Xcode 27; type-checking improves dramatically, but a few patterns stop compiling and the diagnostic is not always local to the real cause.
**Since** – Xcode 27 (Swift 6.4).
**Detection signals** –
- `error: ambiguous use of 'opacity'` / `'blendMode'` on `background(_:alignment:)`/`overlay(_:alignment:)` with a composed `ShapeStyle` — replace with the closure forms `background(alignment:content:)`/`overlay(alignment:content:)`.
- `error: return type of property 'body' requires that 'EmptyMapContent' conform to 'View'` when an empty builder block (or a `#if` whose only branch is excluded) exists in a file where MapKit is in scope, even without `import MapKit` when member import visibility is off — fix with an explicit `EmptyContent()`/`EmptyView()` or an `#else` branch.
- Constraint-dependent overloads: code that relied on builder contents conforming to `View` to disambiguate (`TupleView` appearing as a nested generic argument).
- Swift 5.10+/6 expression type-check warnings on long `body` bodies; Xcode's build timing summary.
**Severity hint** – Low (mechanical fixes), Medium if it lands as a blocking upgrade.
**Refactor direction** – Prefer the closure-based modifier overloads; supply explicit `EmptyContent()`; do not fight the builders with generic constraints — restructure into a named subview.
**Counter-signals** – None notable; the unification is strictly a win once migrated.
**Sources** – TN3211 [official]; WWDC26 269 26:07 (`@ContentBuilder`) [official].

### 23. Measure before refactoring — the framework moved under you
**Rule** – SwiftUI's own cost model changes every release; a refactor justified by a 2022 profile may be pointless now. Profile with the SwiftUI instrument, then change the view, then re-profile.
**Since** – Xcode 26 ships the SwiftUI instrument; iOS 26 brought list updates up to 16× faster and improved update scheduling on iOS/macOS.
**Detection signals** –
- Long View Body Updates lane: orange > 500 µs, red > 1000 µs per body evaluation.
- View Body Count / cause-effect graph showing one interaction producing N body evaluations of the same view.
- Refactors present without a profile: `AnyView` elimination, `equatable()`, manual `EquatableView`, memoisation caches, `@State`-cached formatters introduced "for performance" with no measurement and no test.
- Hand-rolled virtualisation or view recycling that duplicates what `List`/`LazyVStack` now do.
**Severity hint** – Medium (misplaced complexity), High when a hand-rolled workaround is now slower than the framework path.
**Refactor direction** – Profile → identify the specific long/frequent update → apply the smallest fix from #3/#8/#17/#18 → re-profile. Delete speculative optimisations that no profile justifies.
**Counter-signals** – Obvious O(n²) or per-row formatter allocation needs no profile; fix it and move on.
**Sources** – WWDC25 306 [official]; WWDC25 256 "What's new in SwiftUI" (lists up to 16× faster, improved update scheduling) [official]; https://developer.apple.com/documentation/xcode/understanding-and-improving-swiftui-performance [official].

## Tools

- **SwiftUI instrument** (Instruments, Xcode 26+): `xcodebuild`-built app + Product ▸ Profile ▸ SwiftUI template. Lanes give Long View Body Updates (>500 µs orange, >1000 µs red), View Body Count, and a cause-and-effect graph linking a state mutation to the bodies it invalidated. This is the only tool that shows *why* a body ran.
- **`Self._printChanges()`** as the first line of `body` (or `let _ = Self._printChanges()`), then run and read the console; it prints which dynamic property/environment/observable property triggered the update. Debug only — underscore-prefixed, not API-guaranteed. In LLDB: `expression Self._printChanges()`.
- **`_printChanges` on a whole view tree via the SwiftUI instrument's cause graph** is preferable for anything larger than one view.
- **Type-check cost**: build setting `OTHER_SWIFT_FLAGS = $(inherited) -Xfrontend -warn-long-expression-type-checking=200 -Xfrontend -warn-long-function-bodies=100` (milliseconds); `xcodebuild -showBuildTimingSummary` / Product ▸ Perform Action ▸ Build with Timing Summary. Evidence for `body` complexity and for the `ContentBuilder` migration payoff.
- **`_ = Self._printChanges()` plus grep** is how you confirm #3 (coarse model reads) without Instruments.
- **Structural greps for a reviewer** (source-level, no build required): `AnyView(`, `\.id\(UUID\(\)\)`, `\.id\(`, `ForEach\(.*\.indices`, `ForEach\(Array\(.*enumerated\(\)\)`, `GeometryReader`, `NavigationView`, `PreviewProvider`, `ObservableObject`, `@Published`, `@StateObject`, `onAppear \{ *Task`, `DateFormatter\(\)` inside `body`, `: ObservableObject` combined with `@Observable`, `background\(\.\w+\.opacity`, `@State private var .* = .*` plus `init(` in the same struct.
- **`swift-format` / SwiftLint custom rules** are the right home for the stable greps above (`AnyView(`, `.id(UUID())`, `NavigationView`); keep the list short — every rule that fires on legitimate code gets disabled and takes the useful ones with it.
- **Instruments "Hangs" and "Animation Hitches" templates** to attribute a symptom to SwiftUI before touching view code at all; the SwiftUI instrument session explicitly defers non-SwiftUI causes to them.
