# iOS platform correctness and App Store risk — reference catalog

Scope: Swift/SwiftUI/UIKit code plus the project files that decide what ships (Info.plist, entitlements, privacy manifests, build settings, extension targets). Generic code smells are out of scope.

## Contents

- [Version baseline (verified 2026-10-25)](#version-baseline-verified-2026-10-25)
- [Rules](#rules)
- [Tools](#tools)

## Version baseline (verified 2026-10-25)

| Fact | Value | Source |
|---|---|---|
| Xcode 27 requires | macOS Tahoe 26.6 or later; ships Swift 6.4 and the iOS 27 SDK | [official] Xcode 27 Release Notes |
| App Store upload gate | Since **2026-04-28**, apps must be built with Xcode 26 or later against the iOS 26 SDK or later | [official] Upcoming Requirements |
| Minimum deployment target | Since **2026-09-09**, iOS/iPadOS apps must target iOS 13 or later | [official] Upcoming Requirements |
| Next gate | iOS 27 SDK uploads will be required around spring 2027 — `[INFERENCE]` from Apple's annual April/May SDK deadline, no announcement yet. Already true today: the iOS 27 SDK hard-fails apps without scene lifecycle, and App Store Connect rejects 27.0-SDK builds without a launch screen | [official] iOS 27 Release Notes, WWDC26-278 |

WWDC26 sessions used below: 222 (MetricKit), 258 (Xcode 27), 268 (Instruments responsiveness), 277 (WidgetKit), 278 (Modernize your UIKit app), 220 (accessibility for custom controls).

## Rules

### Ship a `PrivacyInfo.xcprivacy` in every target and declare each required-reason API in use

**Rule** – For each target (app + every extension), include a `PrivacyInfo.xcprivacy` that lists every required-reason API category the target's code touches, with the reason codes Apple publishes; no manifest means the upload is refused.

**Since** – iOS 17 manifest format; rooted in App Store Connect enforcement from 2024-05-01. Apple's documentation still lists the same five categories under the iOS 27 SDK, and the iOS 27 release notes announce none.

**Detection signals**
- `find . -name PrivacyInfo.xcprivacy` returns fewer files than there are targets in `project.yml` (`targets:`) — each extension bundles its own copy.
- Code uses an API with no matching `NSPrivacyAccessedAPITypes` dict in that target's manifest: `UserDefaults` / `NSUserDefaults` / `@AppStorage` → `NSPrivacyAccessedAPICategoryUserDefaults` (verified code `CA92.1`); `FileManager.attributesOfItem`, `URL.resourceValues(forKeys: [.contentModificationDateKey])`, `stat` → `NSPrivacyAccessedAPICategoryFileTimestamp`; `ProcessInfo.processInfo.systemUptime`, `mach_absolute_time`, `clock_gettime` → `NSPrivacyAccessedAPICategorySystemBootTime`; `volumeAvailableCapacityForImportantUsageKey`, `attributesOfFileSystem` → `NSPrivacyAccessedAPICategoryDiskSpace` (verified codes `E174.1`, `B728.1`); `UITextInputMode.activeInputModes` → `NSPrivacyAccessedAPICategoryActiveKeyboards`.
- Reverse leak: manifest declares a category no code path can reach (grep the category's APIs) — over-declaration is a fingerprinting-policy mismatch, not a harmless default.
- Reason code copied from a blog rather than from Apple's table, or a made-up code.
- `plutil -p PrivacyInfo.xcprivacy` shows an empty `NSPrivacyAccessedAPITypeReasons` array or a reason string with a trailing space.

**Severity hint** – High (upload rejection; also a policy violation independent of tracking consent).

**Refactor direction** – One manifest per target, generated/kept in the target's source folder so it lands in `Copy Bundle Resources`; declare only what the target's own code uses. Reason strings must come verbatim from Apple's per-category table.

```xml
<key>NSPrivacyAccessedAPITypes</key>
<array>
  <dict>
    <key>NSPrivacyAccessedAPIType</key>
    <string>NSPrivacyAccessedAPICategoryUserDefaults</string>
    <key>NSPrivacyAccessedAPITypeReasons</key>
    <array><string>CA92.1</string></array>
  </dict>
</array>
```

**Counter-signals** – `UserDefaults` reached only through a third-party SDK: the SDK declares it in its own manifest, so the app does not repeat it.

**Sources** – https://developer.apple.com/documentation/bundleresources/privacy-manifest-files [official 2026]; https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api [official 2026]; https://developer.apple.com/documentation/technotes/tn3183-adding-required-reason-api-entries-to-your-privacy-manifest [official 2026]

---

### Audit third-party SDK manifests and signatures, not just your own

**Rule** – Every SDK on Apple's "SDKs that require a privacy manifest and signature" list must arrive as a signed XCFramework/binary with its own `PrivacyInfo.xcprivacy`; an SDK that ships a manifest but never declares `NSPrivacyTracking`/`NSPrivacyCollectedDataTypes` hides data collection from the privacy label.

**Since** – 2024 signature requirement; the SDK list and the Xcode-combined privacy report are stable through Xcode 27.

**Detection signals**
- `Package.resolved` / `Podfile.lock` / `Cartfile.resolved` names intersecting Apple's list (Alamofire, Firebase*, Facebook, Adjust, AppsFlyer, Braze, OneSignal, Sentry, Realm, Unity Ads, …) where the resolved version predates that SDK's manifest-bearing release.
- `find . -name PrivacyInfo.xcprivacy -path "*SourcePackages*"` — an SDK binary with no manifest inside its bundle.
- `codesign -d --entitlements :- <SDK>.framework` or `codesign -dv --verbose=4` reporting `Signature=adhoc` (stripped) for a listed SDK.
- `NSPrivacyCollectedDataTypes` absent in an SDK manifest that also links a tracking framework (grep the binary for `ASIdentifierManager`, `ATTrackingManager`, `SKAdNetwork`).
- A vendored binary framework committed into the repo (`*.xcframework` under version control) — signatures break when re-zipped or re-signed by hand.

**Severity hint** – High (upload rejection for missing signature; App Review 5.1.2 for undisclosed sharing).

**Refactor direction** – Upgrade to a version that ships the manifest; if none exists, vendor the source and add a manifest that matches actual behaviour, then document the audit in the PR. Produce Xcode's combined privacy report from the Organizer archive before every submission and diff it against the App Store Connect privacy answers.

**Counter-signals** – Apple first-party frameworks; SDKs used only in a test target (not bundled).

**Sources** – https://developer.apple.com/support/third-party-SDK-requirements/ [official 2026]; https://developer.apple.com/documentation/bundleresources/privacy-manifest-files [official 2026]

---

### Keep credentials out of `UserDefaults` and source; store them in the Keychain with the right accessibility class

**Rule** – Tokens, passwords, API keys and licence keys go in the Keychain (or Secure Enclave-backed keys), never in `UserDefaults`, `@AppStorage`, plists, `Info.plist` or a Swift literal; and the Keychain item's `kSecAttrAccessible` must match when the app actually reads it.

**Since** – All; Keychain accessibility constants are iOS 4+.

**Detection signals**
- `grep -rn "UserDefaults.standard.set" --include=*.swift` where the value type is a token/session/credential (`token`, `secret`, `password`, `apiKey`, `bearer`, `refresh`, `license`, `pin`), or `@AppStorage("token")`.
- Secret-shaped literals: `sk_live_`, `AKIA`, `-----BEGIN`, `AIza`, `ghp_`, base64 blobs > 40 chars assigned to a `let`, hardcoded `client_secret` in an OAuth flow.
- Secrets in `Info.plist` / `.xcconfig` committed to git (`git check-ignore` says tracked), or `$(SECRET)` build settings with a default value in the repo.
- Keychain writes that omit `kSecAttrAccessible` (defaults to `kSecAttrAccessibleWhenUnlocked`) while a background task, notification extension, widget or `BGTaskScheduler` handler reads the same item — the read fails silently with `errSecInteractionNotAllowed` on a locked device.
- `kSecAttrAccessibleAlways` (deprecated iOS 12) or `…AlwaysThisDeviceOnly`.
- A "remember me" flag in `UserDefaults` next to the token: the flag survives restore while the token sits in a plist that is readable after first unlock, so the credential is exposed before the user unlocks the device.

**Severity hint** – High (credential theft; App Review 5.1.1 / 5.1.2).

**Refactor direction** – One small Keychain wrapper (`SecItemAdd`/`SecItemCopyMatching` with `kSecClassGenericPassword`, `kSecAttrService`, `kSecAttrAccount`), defaulting to `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`; migrate existing `UserDefaults` values by writing then deleting the key.

```swift
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: "com.example.session",
    kSecAttrAccount as String: "refreshToken",
    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
    kSecValueData as String: data
]
SecItemAdd(query as CFDictionary, nil)
```

**Counter-signals** – Non-sensitive preferences (theme, last tab) belong in `UserDefaults`; test-only fixtures in a `#if DEBUG` file that is excluded from Release.

**Sources** – https://developer.apple.com/documentation/security/restricting-keychain-item-accessibility [official 2026]; https://developer.apple.com/documentation/security/ksecattraccessibleafterfirstunlock [official 2026]

---

### Set an explicit file-protection class on user data written to disk

**Rule** – Files containing personal data must carry the narrowest `FileProtectionType` the feature can survive, instead of relying on the default (`.completeUntilFirstUserAuthentication`, readable after first unlock).

**Since** – iOS 4 (`FileAttributeKey.protectionKey`, `FileProtectionType`); `NSFileProtectionComplete` also settable per file in the Data Protection capability.

**Detection signals**
- `try data.write(to: url, options: .atomic)` on Documents/Application Support without `.completeFileProtection` / `.completeFileProtectionUnlessOpen` in the options.
- `FileManager.default.createFile(atPath:contents:attributes:)` with `attributes: nil` for anything user-generated.
- Core Data/SQLite store holding personal data added without `NSPersistentStoreFileProtectionKey: NSFileProtectionComplete` in the store's `options` dictionary (the default leaves it readable after first unlock).
- Caches/`tmp` used for tokens or full-resolution photos that outlive the session.
- Entitlement `com.apple.developer.default-data-protection` missing while the project claims data protection (it is required for `NSFileProtectionComplete` to apply to all files by default).
- Widget or extension reading a `.complete`-protected file while the device is locked — the read throws and the extension shows a placeholder.

**Severity hint** – High (data exposure on a locked/stolen device; security review finding).

**Refactor direction** – Pass the protection option at write time, and keep files an extension must read behind `.completeUntilFirstUserAuthentication` in a shared container.

```swift
try data.write(to: url, options: [.atomic, .completeFileProtection])
```

**Counter-signals** – Non-sensitive caches, thumbnails and logs; files that must be read from a notification extension while locked.

**Sources** – https://developer.apple.com/documentation/foundation/fileprotectiontype [official 2026]; https://developer.apple.com/documentation/foundation/fileattributekey/protectionkey [official 2026]

---

### Wire App Groups on every target and never force-unwrap the shared container or suite

**Rule** – The `com.apple.security.application-groups` entitlement must be identical on app and every extension that shares data, and the shared `UserDefaults`/container URL must be handled as optional with a fallback, not `!`.

**Since** – All.

**Detection signals**
- `project.yml` (`entitlements.properties.com.apple.security.application-groups`) or `*.entitlements` differs between targets, or an extension target lists none while its code reads shared state.
- `UserDefaults(suiteName: "group.…")!` (failable init force-unwrapped) or `FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: …)!`.
- `UserDefaults(suiteName:)` given a bundle identifier instead of the `group.` identifier.
- Group identifier not team-prefixed where Apple requires it (`group.<TeamID>.<name>`) — provisioning fails at archive time.
- Data written before the group was enabled: no migration path from `UserDefaults.standard` to the suite, so existing users silently lose their state.
- Reads that mutate through `UserDefaults.standard` in one process and through the suite in another (two sources of truth).

**Severity hint** – High (crash on a configuration mistake; silent data loss on upgrade).

**Refactor direction** – One `AppGroup` enum owning the identifier, returning a non-optional `UserDefaults` backed by `UserDefaults.standard` when the suite is unavailable, plus a one-shot migration keyed by a version marker.

```swift
enum AppGroup {
    static let id = "group.team.example.app"
    static var defaults: UserDefaults {
        UserDefaults(suiteName: id) ?? .standard
    }
}
```

**Counter-signals** – Extensions that only read data passed in the notification payload and never touch the container.

**Sources** – https://developer.apple.com/documentation/xcode/configuring-app-groups [official 2026]; https://developer.apple.com/documentation/foundation/userdefaults/init(suitename:) [official 2026]

---

### Keep the widget extension inside its ~30 MB budget and out of the network

**Rule** – Widget timelines must render from cheap, precomputed data: no full-resolution image decoding, no network calls, no database scan per entry; the view declares its background with `containerBackground(for: .widget)` and the target declares data protection.

**Since** – Budget undocumented and unchanged through the iOS 27 SDK (observed jetsam `EXC_RESOURCE … limit=30 MB`); `containerBackground` since iOS 17.

**Detection signals**
- `UIImage(contentsOfFile:)`, `UIImage(named:)` or `AsyncImage` on camera/photo assets inside the widget target; decoding a 1024×1024 asset costs ~4 MB (w×h×4 bytes) — three of those exhaust the budget.
- `URLSession` / `await client.fetch()` anywhere in the widget target (timeline provider, intent, view).
- `NSManagedObjectContext` fetch or `FileManager` enumeration inside `getTimeline` without a fetch limit.
- `.containerBackground(for: .widget)` absent on the widget's root view — a hand-built `ZStack { Color… ; content }` background instead; the modifier is what lets the system place the widget in the newer contexts (StandBy, Lock Screen, tinted appearance, Mac/iPad) and strip the background where needed.
- Widget entitlements missing `com.apple.developer.default-data-protection` while the widget shows user content.
- `WidgetCenter.shared.reloadAllTimelines()` called from app launch or a loop instead of `reloadTimelines(ofKind:)` after a real data change.

**Severity hint** – High (jetsam kills the extension; the widget silently goes stale) / Medium for budget-adjacent waste.

**Refactor direction** – Downsample at the source with ImageIO (`kCGImageSourceThumbnailMaxPixelSize`), cache a rendered thumbnail keyed by size, and let the app push fresh entries through the shared container.

```swift
let opts = [kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceThumbnailMaxPixelSize: 300,
            kCGImageSourceShouldCacheImmediately: true] as CFDictionary
```

**Counter-signals** – A one-off `URLSession` inside a `TimelineProvider` only when the widget's whole purpose is live data (e.g. transit), with a cached fallback entry.

**Sources** – https://developer.apple.com/videos/play/wwdc2026/277/ [official WWDC26-277]; https://developer.apple.com/documentation/widgetkit/creating-a-widget-extension [official 2026]; https://developer.apple.com/videos/play/wwdc2023/10028/ [official WWDC23-10028, `containerBackground` for the additional widget locations]; https://developer.apple.com/forums/thread/713561 [official forum, jetsam log showing `limit=30 MB`]; https://ariabolour.dev/writing/widgetkit-memory-budget.html [power-user 2025]

---

### Notification service extension: finish in ~30 s, inside ~24 MB, always call the content handler

**Rule** – `didReceive(_:withContentHandler:)` must do bounded work, hand back content on every path (including `serviceExtensionTimeWillExpire()`), and never run migrations, big writes or image pipelines.

**Since** – iOS 10.

**Detection signals**
- No `serviceExtensionTimeWillExpire()` override, or an override that does not call `contentHandler`.
- `contentHandler` called inside a `Task`/callback that can also be reached twice (double-call crashes with "completion handler called more than once").
- Work that is unbounded in the handler: `FileManager` copy of a media file, `NSPersistentContainer.loadPersistentStores`, `try await client.syncAll()`, `UIImage(data:)` on a full-size attachment.
- Push payload lacks `"mutable-content": 1` in the `aps` dictionary while relying on the extension (extension never runs).
- Crash logs in Organizer / MetricKit `MemoryExceptionDiagnostic` naming the extension with `EXC_RESOURCE … high watermark memory limit exceeded (limit=24 MB)`.
- Extension target embeds a database framework (Realm/Core Data + migration) and writes on first launch.

**Severity hint** – High (notification lost and app appears broken; possible repeated jetsam).

**Refactor direction** – Guard the handler once, do the minimum transform, fall back to original content on timeout.

```swift
private var handler: ((UNNotificationContent) -> Void)?
private var fallback: UNNotificationContent?

override func didReceive(_ request: UNNotificationRequest,
                         withContentHandler contentHandler: @escaping (UNNotificationContent) -> Void) {
    handler = contentHandler
    fallback = request.content.mutableCopy() as? UNMutableNotificationContent
}

private func finish(_ content: UNNotificationContent?) {
    guard let handler, let content = content ?? fallback else { return }
    self.handler = nil            // makes a second call a no-op instead of a crash
    handler(content)
}

override func serviceExtensionTimeWillExpire() { finish(partialContent()) }
```

**Counter-signals** – Extensions that only decrypt a small payload or attach a pre-sized thumbnail. A missing `serviceExtensionTimeWillExpire()` override is acceptable when the push's own `alert` already carries usable text: the system then shows the original content on timeout. Flag the missing override only when the original alert would be wrong, empty or a placeholder.

**Sources** – https://developer.apple.com/documentation/usernotifications/unnotificationserviceextension [official 2026]; https://developer.apple.com/documentation/usernotifications/modifying-content-in-newly-delivered-notifications [official 2026, "about 30 seconds"]; https://github.com/realm/realm-swift/issues/8693 [power-user repro, `limit=24 MB`]

---

### Screen Time / DeviceActivity extensions: entitlement, shared container, and almost no work in the monitor

**Rule** – `DeviceActivityMonitor` and `DeviceActivityReport` targets need the Family Controls entitlement, an App Group shared with the app, and a monitor implementation that persists a threshold event and returns — the system gives it a short window and kills it on overrun.

**Since** – iOS 15 (Family Controls / Device Activity); `AuthorizationCenter` shared instance.

**Detection signals**
- `*.entitlements` for the monitor/report target missing `com.apple.developer.family-controls` (must also be granted on the App ID; App Review rejects unauthorised use outright).
- Monitor extension without `com.apple.security.application-groups`, or with a group the app target does not list.
- `intervalDidStart`/`intervalDidEnd`/`eventDidReachThreshold` doing network requests, UI work, or `Task { await … }` that outlives the callback.
- `AuthorizationCenter.shared.requestAuthorization(for:)` called without awaiting/handling the result (`.approved`/`.denied`/`.notDetermined`), or the app side never calling `AuthorizationCenter.shared.revokeAuthorization()` when the user disables Screen Time access.
- Activity/schedule built with a `DeviceActivityName` string literal duplicated across targets instead of a shared constant.
- Report extension rendering with unbounded `DeviceActivityResults` iteration or retaining the results collection past the view's lifetime.

**Severity hint** – High (App Review rejection; the monitor silently stops firing).

**Refactor direction** – Keep the extension dumb: write a marker into the shared store and let the app react on next foreground. Share identifiers through a small package both targets link.

```swift
override func eventDidReachThreshold(_ event: DeviceActivityEvent.Name, activity: DeviceActivityName) {
    AppGroup.defaults.set(Date.now, forKey: "threshold.\(event.rawValue)")
}
```

**Counter-signals** – A report extension that only maps `DeviceActivityResults` into a SwiftUI view and performs no persistence.

**Sources** – https://developer.apple.com/documentation/familycontrols [official 2026]; https://developer.apple.com/documentation/deviceactivity [official 2026]; https://developer.apple.com/documentation/xcode/configuring-app-groups [official 2026]

---

### `BGTaskScheduler`: register before launch returns, declare permitted identifiers, keep one pending request per identifier

**Rule** – `register(forTaskWithIdentifier:)` must run before `application(_:didFinishLaunchingWithOptions:)` returns, every identifier must be listed in `BGTaskSchedulerPermittedIdentifiers`, each request must have an expiration handler, and only one pending request per identifier can exist.

**Since** – iOS 13.

**Detection signals**
- `BGTaskScheduler.shared.register` called from a view controller, a SwiftUI `.task`, or after an `await` — launch handler never runs.
- `Info.plist` / `project.yml` lacking `BGTaskSchedulerPermittedIdentifiers`, or listing an identifier the code never registers — registering an undeclared identifier is a launch-time failure, not a no-op.
- `BGAppRefreshTaskRequest` submitted twice without cancelling/settling the previous one → `BGTaskScheduler.Error.Code.tooManyPendingTaskRequests`.
- No `task.expirationHandler = { task.setTaskCompleted(success: false) }` — the system kills the app and counts a watchdog termination.
- `task.setTaskCompleted(success:)` called on some paths only, or called twice.
- `UIBackgroundModes` present but `fetch`/`processing` missing while using `BGAppRefreshTask`/`BGProcessingTask`.
- `beginBackgroundTask(withName:expirationHandler:)` never ended (leaks a background assertion; app is killed after ~30 s).

**Severity hint** – High (silent loss of background work, watchdog crashes).

**Refactor direction** – Register all handlers in one function called from the app/scene delegate init, submit with a single helper that cancels the existing request first, and always pair `setTaskCompleted` with an expiration handler.

```swift
BGTaskScheduler.shared.register(forTaskWithIdentifier: id, using: nil) { task in
    task.expirationHandler = { task.setTaskCompleted(success: false) }
    Task { let ok = await refresh(); task.setTaskCompleted(success: ok) }
}
```

**Counter-signals** – Apps with no background-refresh feature at all (then delete the identifier, the background mode and the capability).

**Sources** – https://developer.apple.com/documentation/backgroundtasks/bgtaskscheduler [official 2026]; https://developer.apple.com/documentation/uikit/using-background-tasks-to-update-your-app [official 2026]; https://developer.apple.com/documentation/bundleresources/information-property-list/bgtaskschedulerpermittedidentifiers [official 2026]

---

### Declare only background modes the app really uses; prefer `BGContinuedProcessingTask` over keep-alive hacks

**Rule** – Each `UIBackgroundModes` value must map to a feature that genuinely needs it; silent-audio loops, dummy location updates or empty `fetch` handlers are App Review 2.5.4 rejections and battery bugs. Long user-initiated work belongs in the iOS 26 continued-processing task, not in a background-mode workaround.

**Since** – iOS 13 for `BGTaskScheduler`; iOS 26 for `BGContinuedProcessingTaskRequest`.

**Detection signals**
- `UIBackgroundModes` contains `audio` while `AVAudioSession` is only used for playback of user-chosen media (no `MPNowPlayingInfoCenter`/`MPRemoteCommandCenter`), or `location` with `allowsBackgroundLocationUpdates = true` for anything other than navigation/fitness.
- `fetch` mode with a registered handler that returns immediately or does nothing.
- `voip` mode (only legitimate for `PKPushRegistry` VoIP pushes), `remote-notification` without a `UNNotificationServiceExtension` or silent-push handler, `processing` without a `BGProcessingTask`.
- `UIApplication.beginBackgroundTask` used to keep a timer or socket alive indefinitely.
- Long export/processing implemented as a `BGProcessingTask` that the user started by tapping a button — that is the case `BGContinuedProcessingTaskRequest(identifier:title:subtitle:)` exists for, and it shows progress in the system UI.
- `project.yml` `info.properties.UIBackgroundModes` listing a mode no code path references (grep the mode's API, e.g. `CLLocationManager`, `AVAudioSession`, `PKPushRegistry`).

**Severity hint** – High (2.5.4 rejection + battery/energy regressions).

**Refactor direction** – Delete the unused mode from both the capability and `Info.plist`; replace keep-alive loops with `BGContinuedProcessingTaskRequest` submitted on the user's tap, with `task.progress` updated.

**Counter-signals** – Music/podcast players, navigation apps, and VoIP clients where the mode matches the product.

**Sources** – https://developer.apple.com/documentation/backgroundtasks/performing-long-running-tasks-on-ios-and-ipad [official 2026]; https://developer.apple.com/documentation/bundleresources/information-property-list/uibackgroundmodes [official 2026]; https://developer.apple.com/app-store/review/guidelines/ §2.5.4 [official 2026]

---

### Building with the iOS 27 SDK: adopt the UIScene lifecycle or the app will not launch

**Rule** – Migrate off the app-delegate-only lifecycle to `UISceneDelegate`/`UIWindowScene`; with the iOS 27 SDK, an app without scene lifecycle does not launch at all.

**Since** – Required for apps built with the iOS 27 SDK (Xcode 27).

**Detection signals**
- `Info.plist` without `UIApplicationSceneManifest`, or `AppDelegate` creating its own `UIWindow` in `application(_:didFinishLaunchingWithOptions:)`.
- `@UIApplicationMain` / `@main class AppDelegate` with no `SceneDelegate`, or SwiftUI `App` with `UIApplicationDelegateAdaptor` that still builds a window manually.
- `UIApplication.shared.delegate?.window` reads, `applicationDidEnterBackground` as the only lifecycle hook.
- `UIApplicationSupportsMultipleScenes` missing on an iPad-capable target.

**Severity hint** – High (app fails to launch after the SDK bump — a 1-star-review incident, not a warning).

**Refactor direction** – Add the scene manifest, move window setup into `scene(_:willConnectTo:options:)`, and move background/foreground work from the app delegate to the scene delegate. Apple's "Transitioning to the UIKit scene-based life cycle" article is the reference, and WWDC26-278 points at an agent skill that performs the migration.

**Counter-signals** – Share/action extensions and watchOS apps do not use scenes.

**Sources** – https://developer.apple.com/videos/play/wwdc2026/278/ [official WWDC26-278, "UIScene lifecycle is now required when building with the latest SDKs. Without it, your application will no longer launch"]; https://developer.apple.com/documentation/ios-ipados-release-notes/ios-ipados-27-release-notes [official 2026]

---

### Build with a supported SDK and declare a launch screen, or App Store Connect refuses the build

**Rule** – The project must build with Xcode 26+/iOS 26 SDK (mandatory since 2026-04-28) and, once it moves to the iOS 27 SDK, `Info.plist` must contain one of `UILaunchStoryboardName`, `UILaunchStoryboards`, `UILaunchScreen`, `UILaunchScreens`.

**Since** – iOS 27.0 SDK for the launch-screen key; 2026-04-28 for the SDK floor.

**Detection signals**
- `project.yml` / pbxproj `SDKROOT` or CI workflow pinned to Xcode 25 or earlier; `LastUpgradeCheck` far behind.
- `IPHONEOS_DEPLOYMENT_TARGET` below 13.0 (rejected since 2026-09-09) or above the SDK the CI uses.
- Info.plist with none of the four launch-screen keys (XcodeGen: `info.properties.UILaunchScreen` absent). An empty `UILaunchScreen: {}` is sufficient and is the modern default — a deleted `LaunchScreen.storyboard` with no replacement is the usual regression.
- Legacy `UILaunchImages` / `UILaunchImageFile` usage on iPhone.

**Severity hint** – High (upload rejected; TN3208 documents the requirement).

**Refactor direction** – Keep `UILaunchScreen` in the target's Info.plist and let it derive from the asset catalog; bump the CI Xcode before the next submission window.

**Counter-signals** – None for App Store apps; a launch screen is mandatory.

**Sources** – https://developer.apple.com/documentation/ios-ipados-release-notes/ios-ipados-27-release-notes [official 2026]; https://developer.apple.com/news/upcoming-requirements/ [official 2026]; https://developer.apple.com/videos/play/wwdc2026/278/ [official WWDC26-278, TN3208 reference]

---

### Remove main-screen, key-window and screen-bounds references; lay out with size classes and effective geometry

**Rule** – No `UIScreen.main`, `UIApplication.shared.keyWindow`, `UIApplication.shared.windows`, screen bounds or interface-orientation checks for layout: under iPhone Mirroring and iPad windowing (mandatory adaptivity in iOS 27) the scene's screen and size change at runtime, and the main screen reports the wrong one.

**Since** – `keyWindow` deprecated iOS 13, `windows` iOS 15, `UIScreen.main` deprecated iOS 26; layout must follow the scene from the iOS 27 SDK. `UIRequiresFullScreen` no longer opts an app out of resizing on iPhone in iOS 27 — it now enables discrete resizing that honours the supported orientations.

**Detection signals**
- `grep -rn "UIScreen.main\|\.keyWindow\|UIApplication.shared.windows\|UIScreen.bounds" --include=*.swift` — all four are compile warnings under the 26/27 SDK and produce wrong values under mirroring.
- `UIScreen.main.scale` driving image sizes → replace with `traitCollection.displayScale`.
- `UIDevice.current.userInterfaceIdiom == .pad` / `== .phone` branching on layout, `UIDevice.current.orientation` or `interfaceOrientation` in `viewWillTransition`.
- `UIRequiresFullScreen` = `true`, `TARGETED_DEVICE_FAMILY = 1` with fixed-width layouts, `UISupportedInterfaceOrientations` used to force a layout.
- Fixed `frame`/`NSLayoutConstraint` constants derived from `UIScreen.main.bounds.width`.
- Scene delegate not implementing `windowScene(_:didUpdateEffectiveGeometry:)` while geometry-dependent layout exists.

**Severity hint** – High (broken layout on every resizable environment; deprecated API use falls under 2.5.1).

**Refactor direction** – Read the size from the nearest view (`view.bounds`, `GeometryReader`, `containerRelativeFrame`) or from `windowScene.effectiveGeometry`; branch on `traitCollection.horizontalSizeClass`/`verticalSizeClass` and `dynamicTypeSize`, never on idiom.

```swift
// before
let width = UIScreen.main.bounds.width
// after
let width = view.window?.windowScene?.effectiveGeometry.coordinateSpace.bounds.width
    ?? view.bounds.width
```

**Counter-signals** – A game that intentionally opts into discrete resizing via `UIRequiresFullscreen` (iOS 27 semantics); screenshot/test helpers may read the screen.

**Sources** – https://developer.apple.com/videos/play/wwdc2026/278/ [official WWDC26-278]; https://developer.apple.com/documentation/uikit/uiscreen/main [official, availability 2.0–26.0]; https://developer.apple.com/documentation/uikit/uiapplication/keywindow [official, deprecated iOS 13]

---

### Liquid Glass is compulsory in the iOS 27 SDK: delete `UIDesignRequiresCompatibility` and stop overriding system chrome

**Rule** – Remove the compatibility opt-out and custom bar/blur styling; when built for iOS 27+, the system ignores `UIDesignRequiresCompatibility` and renders Liquid Glass over assumptions written for the old chrome.

**Since** – iOS 26 introduced the design and the key; the key is ignored when building for iOS 27 or later.

**Detection signals**
- `UIDesignRequiresCompatibility` present in `Info.plist`/`project.yml` at all — the warning in Apple's docs is explicit that it is temporary.
- `UINavigationBar.appearance()`, `UITabBar.appearance()`, `UIToolbar.appearance()` setting `standardAppearance`, `scrollEdgeAppearance`, `backgroundColor`, `isTranslucent`, or a custom `UIVisualEffectView` behind bars.
- `scrollEdgeAppearance` explicitly set to `.soft` (no longer the default look in iOS 27; `.automatic` changed visuals).
- Hard-coded `.white`/`.black` foreground colours on bars or `Color(uiColor: .systemBackground)` behind glass surfaces — contrast breaks in dark mode and under tinted rendering.
- Navigation items that rely on `barMinimizationBehavior` defaults changing: code that assumes the bar always stays visible (`additionalSafeAreaInsets` math), or that fights minimization instead of setting `.never`.
- Menu items that depend on their images being displayed: in the iOS 27 SDK, images on menu elements may not be shown by default in some contexts (menu bars on iPadOS/macOS, context menus); `preferredImageVisibility` is the explicit override.

**Severity hint** – Medium (visual breakage and contrast failures once the SDK stops honouring the compatibility mode; touch handling in hand-rolled chrome is the usual casualty).

**Refactor direction** – Delete the key, delete appearance proxies, let system materials do the work; express intent with the new properties (`barMinimizationBehavior`, `preferredImageVisibility`, `sidebar.preferredPlacement`) instead of re-implementing chrome.

**Counter-signals** – A genuine brand surface (custom camera UI, game HUD) that is not using system bars at all.

**Sources** – https://developer.apple.com/documentation/bundleresources/information-property-list/uidesignrequirescompatibility [official 2026, "ignored when you build for iOS 27 or later"]; https://developer.apple.com/videos/play/wwdc2026/278/ [official WWDC26-278]

---

### Replace `canOpenURL` and keep `LSApplicationQueriesSchemes` at 25 entries or fewer

**Rule** – `UIApplication.canOpenURL(_:)` is deprecated in the iOS 27 SDK; and the `LSApplicationQueriesSchemes` cap drops from 50 entries (apps linked on iOS 15+) to 25 entries for apps linked on iOS 27+.

**Since** – iOS 27.

**Detection signals**
- `canOpenURL(` anywhere in Swift/ObjC sources (compiler deprecation warning under the 27 SDK).
- `LSApplicationQueriesSchemes` array with more than 25 strings — the cap is 25 for apps linked on iOS 27 (it was 50 from iOS 15), and entries past the cap always return `false`, so deep-link detection that used to work silently stops.
- Deep-link detection used to fingerprint installed apps (a store of dozens of schemes) — also a 5.1.1/2.5.1 problem, not just a deprecation.

**Severity hint** – Medium (feature silently stops working after the SDK bump).

**Refactor direction** – Prefer universal links and attempt the open, reading the completion flag, instead of probing with `canOpenURL`; where scheme probing is unavoidable, prune the list to the schemes the feature actually needs.

```swift
UIApplication.shared.open(url, options: [:]) { opened in
    if !opened { showInstallPrompt() }
}
```

**Counter-signals** – `Info.plist` `CFBundleURLSchemes` (incoming links) is unrelated and uncapped.

**Sources** – https://developer.apple.com/documentation/uikit/uiapplication/canopenurl(_:) [official, availability 3.0–27.0]; https://developer.apple.com/app-store/review/guidelines/ §2.5.1 [official 2026]

---

### Sweep the APIs deprecated by the 26/27 SDK wave before the next submission

**Rule** – Replace `NavigationView`, `FileDocument`, On Demand Resources and other surfaces deprecated in the iOS 26/27 SDKs; 2.5.1 requires apps to phase out deprecated technologies, and each one is a future launch-time break.

**Since** – `NavigationView` availability ends at 27.2; `FileDocument` deprecated in the iOS 27 SDK (`Document`/`ReadableDocument` replace it); On Demand Resources + `NSBundleResourceRequest` deprecated in iOS 27 (use Background Assets).

**Detection signals**
- `NavigationView {` in SwiftUI (replacement `NavigationStack`, iOS 16+), `NavigationViewStyle`, `.navigationViewStyle(.stack)`.
- `: FileDocument` / `ReferenceFileDocument` conformances.
- `NSBundleResourceRequest`, `beginAccessingResources`, tags in `On Demand Resources` build settings.
- `project.yml`/pbxproj `ENABLE_ON_DEMAND_RESOURCES`.
- Release-time deprecation warnings: `xcodebuild build -scheme <scheme> 2>&1 | grep -c "deprecated"` — triage every unique API, not the count.
- `@available(iOS, deprecated: …)` annotations the team added itself but never migrated.

**Severity hint** – Medium (works today, breaks on the next SDK; review risk under 2.5.1).

**Refactor direction** – One mechanical migration per PR: `NavigationView` → `NavigationStack` with `NavigationPath`, `FileDocument` → `Document`, ODR → Background Assets.

**Counter-signals** – Deprecated APIs used inside a `#available` fallback for a deployment target that genuinely needs them (still flag for removal planning).

**Sources** – https://developer.apple.com/documentation/ios-ipados-release-notes/ios-ipados-27-release-notes [official 2026]; https://developer.apple.com/documentation/swiftui/navigationview [official, availability 13.0–27.2]; https://developer.apple.com/app-store/review/guidelines/ §2.5.1 [official 2026]

---

### Keep the main thread free: no synchronous I/O, sleeps or large decodes; a 100 ms block is a hang

**Rule** – Anything on the main actor that can take more than ~100 ms (file/network I/O, JSON decode of a large payload, image resize, `Thread.sleep`, semaphore waits, keychain queries in a loop) must move off it.

**Since** – All; the 100 ms perceptibility threshold is Apple's current published guidance, and WWDC26-268 is the workflow for finding these.

**Detection signals**
- `Data(contentsOf:)`, `String(contentsOf:)`, `try Data(contentsOf: url, options: .mappedIfSafe)` in a `View`/`body`, `viewDidLoad`, `init` of a view model, or any `@MainActor` type.
- `Thread.sleep`, `usleep`, `DispatchSemaphore.wait()`, `.waitUntilExit()`, `NSLock.lock()` held across a call.
- `JSONDecoder().decode` of a multi-MB payload during first render; `UIImage(data:)` + resize on the main actor.
- Keychain/SQLite/`UserDefaults.synchronize()` in a `for` loop inside a view update.
- `Bundle.main.loadNibNamed`, `NSAttributedString(data:options:)`, `DateFormatter` construction per row.
- Evidence: MetricKit `MXHangDiagnostic` / Organizer Hangs report (`hangDuration`), Instruments Time Profiler showing a main-thread stack above 100 ms, the Swift Concurrency instrument showing main-actor contention.

**Severity hint** – High (visible freeze, watchdog terminations during launch, 2.1 completeness rejections).

**Refactor direction** – Move the work to a nonisolated/background function and return only the finished value; a single `Task.detached`/actor hop per unit of work, not per row.

```swift
// before: blocks the first frame
let data = try Data(contentsOf: url)
// after
let data = try await Task.detached(priority: .userInitiated) {
    try Data(contentsOf: url)
}.value
```

**Counter-signals** – Sub-millisecond work; a deliberate `await Task.yield()` loop; `Data(contentsOf:)` for a local, tiny, cached file on a background actor.

**Sources** – https://developer.apple.com/documentation/xcode/understanding-hangs-in-your-app [official 2026, "less than 100 ms … rarely noticeable"]; https://developer.apple.com/videos/play/wwdc2026/268/ [official WWDC26-268]

---

### Adopt MetricKit for production evidence, and recompile to survive the iOS 27 hitch-type change

**Rule** – Use the iOS 27 Swift-first `MetricManager` (`MetricReport` / `DiagnosticReport` delivered through `AsyncStream`) rather than the legacy `MXMetricManager`, and recompile everything that touches hitch metrics, because `ScrollHitchTimeMetric` and the `scrollHitchTime` case of `MetricResult` no longer exist in the 27 SDK.

**Since** – iOS 27 for `MetricManager`, `MemoryExceptionDiagnostic`, `MetalFrameRateMetric`, `CrashDiagnostic.terminationCategory`, the `HitchTimeRatio` type; iOS 14 for the legacy MX family, now "no longer recommended for new adoption".

**Detection signals**
- No `MetricManager`/`MXMetricManager` subscriber at all — zero production evidence for hangs, memory kills and crashes.
- Any reference to `ScrollHitchTimeMetric` or `MetricResult.scrollHitchTime(_:)`: a missing symbol at launch once the app is recompiled against the iOS 27 SDK (Apple: "recompile your app with the latest SDK to pick up this type change and avoid any crashes on launch").
- `HitchTimeMetric.ratio` / `SignpostIntervalMetric.hitchTimeRatio` compared against `Double` — they now return `HitchTimeRatio`, a `Dimension` subclass; arithmetic written for `Double` silently changes meaning or fails to compile.
- Legacy-only integration that never reads `MXHangDiagnostic`, `MXAppExitMetric`, `MXMemoryMetric` or `MXDiskWriteExceptionDiagnostic`.
- Extension targets with no diagnostics path: a jetsammed widget or NSE leaves no `MemoryExceptionDiagnostic` trail unless the containing app subscribes.
- Reports collected but never correlated with app state — the iOS 27 `StateReporting` framework exists to attribute metrics to a screen or task.

**Severity hint** – Medium (telemetry blind spots); High where a removed symbol crashes on launch.

**Refactor direction** – Rebuild against the 27 SDK before shipping, migrate the subscriber to `MetricManager`, and record the `HitchTimeRatio` values with their unit rather than coercing to `Double`.

**Counter-signals** – Apps using a third-party crash/performance SDK that already collects hang and memory data, where MetricKit duplication is noise.

**Sources** – https://developer.apple.com/documentation/ios-ipados-release-notes/ios-ipados-27-release-notes [official 2026, MetricKit section]; https://developer.apple.com/videos/play/wwdc2026/222/ [official WWDC26-222]; https://developer.apple.com/documentation/metrickit/mxhangdiagnostic [official 2026]

---

### Break retain cycles in timers, notification observers and escaping closures

**Rule** – `Timer.scheduledTimer(target:selector:)` retains its target, a closure-based `NotificationCenter.addObserver(forName:)` retains what the closure captures until the token is removed, and any long-lived owner (view model, singleton, coordinator) capturing `self` strongly in an escaping closure leaks the whole object graph.

**Since** – All. Selector-based observers registered with `addObserver(_:selector:name:object:)` no longer need removal on iOS 9+, which is exactly why the closure-based variant is the one that leaks.

**Detection signals**
- `Timer.scheduledTimer(timeInterval:target:selector:userInfo:repeats: true)` in a view controller or view model, with no `invalidate()` on disappear/deinit — the timer keeps the controller alive forever.
- `Timer.scheduledTimer(withTimeInterval:repeats:) { _ in self.… }` capturing `self` strongly.
- `NotificationCenter.default.addObserver(forName:object:queue:using:)` whose returned `NSObjectProtocol` token is discarded (not stored in a property) — observer lives for the process lifetime.
- `addObserver(forName:)` with `[weak self]` but the token never removed, so the closure still fires after the object is dead.
- `DispatchQueue.main.asyncAfter(deadline:) { self.… }` on a long delay (splash timers, debounce) retaining a controller.
- `CADisplayLink` with a strong target, `URLSession` delegate cycles, `deinit` that is never called (add a log and check).
- Instruments "Leaks"/"Allocations" showing monotonically growing counts of a view controller class across navigation.

**Severity hint** – Medium (memory growth, duplicated timers causing double work) / High when the leak keeps a camera session or location updates alive.

**Refactor direction** – Store the observer token and remove it in `deinit`; use the block-based timer with `[weak self]` and invalidate in `deinit`; where available, prefer `Task`/`AsyncSequence` with cancellation over timers.

```swift
// before
Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in self.tick() }
// after
let t = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.tick() }
deinit { t.invalidate() }
```

**Counter-signals** – Timers whose owner is meant to live for the app's lifetime (a singleton clock) — then make the capture explicit and documented.

**Sources** – https://developer.apple.com/documentation/foundation/notificationcenter/addobserver(_:selector:name:object:) [official 2026, "you do not need to unregister … iOS 9.0 and later"]; https://www.donnywals.com/when-to-use-weak-self-and-why/ [power-user 2019, updated 2025]

---

### Dynamic Type, VoiceOver, contrast and hit regions are review-visible requirements, not polish

**Rule** – Every text element must scale with Dynamic Type, every custom control must expose a label/value/action to VoiceOver, colour must meet contrast in both appearances, and every tappable element must have a ≥44×44 pt hit region.

**Since** – All; `UIFontMetrics` iOS 11+, SwiftUI text styles iOS 13+, `performAccessibilityAudit` Xcode 15+ (iOS 17).

**Detection signals**
- `Font.system(size:)`, `.font(.system(size: 13))`, `UIFont.systemFont(ofSize:)`, `UIFont(name:size:)` without `relativeTo:` / `UIFontMetrics(forTextStyle:).scaledFont(for:)`; `Font.custom(_:fixedSize:)`.
- `UILabel`/`UITextView` without `adjustsFontForContentSizeCategory = true`.
- Fixed heights/`frame(height:)`/`lineLimit(1)` around text, or `.minimumScaleFactor` used to defeat large text — clips at AX sizes.
- Icon-only `Button` with no `.accessibilityLabel`/`accessibilityLabel`; `Image(systemName:)` used as a control without a label; decorative images missing `.accessibilityHidden(true)`.
- Custom `UIView` controls: no `isAccessibilityElement`, no `accessibilityTraits` (`.adjustable` + `accessibilityIncrement`/`accessibilityDecrement` for sliders/steppers), no `accessibilityValue`, no `accessibilityActivationPoint`.
- Contrast: `.foregroundStyle(.secondary)`/`.tertiary` on a custom background, hard-coded `Color(hex: "#999999")` on white, white text on a brand colour that fails 4.5:1 (3:1 for ≥18 pt bold).
- Hit regions: `.contentShape(Rectangle())` missing on a small tappable label; button frames under 44 pt.
- Any `accessibilityAudit` failure in UI tests: `XCUIApplication().performAccessibilityAudit(for: [.contrast, .dynamicType])`.

**Severity hint** – High (excludes VoiceOver/Dynamic Type users outright; contrast and hit-region failures are release blockers, not polish).

**Refactor direction** – Semantic styles everywhere (`Font.body`, `@ScaledMetric` for spacing), one custom control conforming properly, and an audit in CI that fails the build.

```swift
// before
Text(title).font(.system(size: 13)).frame(height: 20)
// after
Text(title).font(.footnote)            // scales with Dynamic Type
```

**Counter-signals** – Canvas/game surfaces drawn at a fixed scale with an alternative accessible representation; charts with `accessibilityChartDescriptor`.

**Sources** – https://developer.apple.com/documentation/uikit/scaling-fonts-automatically [official 2026]; https://developer.apple.com/videos/play/wwdc2026/220/ [official WWDC26-220]; https://developer.apple.com/videos/play/wwdc2023/10035/ [official WWDC23-10035, `performAccessibilityAudit`]; https://developer.apple.com/design/human-interface-guidelines/accessibility [official]

---

### Localise through localised APIs, with a String Catalog, plurals and `FormatStyle` — never concatenation or hand formatting

**Rule** – User-facing text must be produced by `Text("…")` / `String(localized:)` / `LocalizedStringResource` with the String Catalog as the single source of translations; sentences must not be built by concatenation, plurals must use catalog variants, and dates/numbers/units must go through `FormatStyle`.

**Since** – `String(localized:)` and `FormatStyle` iOS 15; String Catalogs Xcode 15; Xcode 26/27 add agent-assisted translation and catalog-wide generation — the catalog is now the default format (`LOCALIZATION_PREFERS_STRING_CATALOGS`).

**Detection signals**
- `Text(someString)` where `someString` is a `String` variable (non-localised overload) instead of `Text(verbatim:)` for intentional literals or `String(localized:)` for user-facing text.
- Concatenation with `+` or interpolation of already-localised fragments: `Text("You have " + "\(count)" + " items")`, `label.text = NSLocalizedString("Hello", nil) + ", " + name`.
- Manual formatting: `DateFormatter` with `dateFormat: "dd/MM/yyyy"`, `NumberFormatter` instances created per cell, `String(format: "%d", n)`, `"\(price) €"`, `measurement.description`.
- `NSLocalizedString(_:comment:)` with an empty or generic comment ("") — extraction context lost; or `tableName:` pointing at a catalog that does not exist.
- Pluralisation done with `count == 1 ? "item" : "items"` or `%lld items` without an inflection/variation in the catalog.
- `Localizable.xcstrings` missing keys that exist in code: `xcrun xcstringstool extract` output vs `xcrun xcstringstool print Localizable.xcstrings` (diff the key sets).
- `knownRegions` in pbxproj or `CFBundleLocalizations` disagreeing with the catalogs actually present; `developmentLanguage` set but no catalog in the bundle.
- Build settings missing `SWIFT_EMIT_LOC_STRINGS = YES` / `LOCALIZATION_PREFERS_STRING_CATALOGS = YES` (XcodeGen `settings.base`).

**Severity hint** – Medium (broken UI in non-English locales, App Review "localisation" friction) / High when a formatted date is parsed back and produces wrong data.

**Refactor direction** – Replace concatenation with a single interpolated localised string and let the catalog hold the plural variants; replace formatters with `Date.FormatStyle`/`IntegerFormatStyle` so the locale decides the pattern.

```swift
// before
let text = "\(count) items — " + dateFormatter.string(from: date)
// after
Text("^[\(count) item](inflect: true) — \(date, format: .dateTime.day().month())")
```

**Counter-signals** – Machine-readable strings (API keys, log messages, `debugDescription`) must not be localised; developer-facing text in a `#if DEBUG` menu.

**Sources** – https://developer.apple.com/documentation/xcode/preparing-your-apps-text-for-translation [official 2026]; https://developer.apple.com/documentation/xcode/localizing-and-varying-text-with-a-string-catalog [official 2026]; https://developer.apple.com/documentation/foundation/formatstyle [official, iOS 15+]; https://developer.apple.com/videos/play/wwdc2026/258/ [official WWDC26-258, localization chapter]

---

### Lay out for right-to-left: semantic leading/trailing, no hard-coded left/right, no baked-in directional glyphs

**Rule** – Use leading/trailing and semantic alignment so the interface mirrors in Arabic/Hebrew; anything that must not mirror (media controls, progress direction, clocks) must say so explicitly.

**Since** – All; `semanticContentAttribute` / `.environment(\.layoutDirection, …)`.

**Detection signals**
- `Edge.Set.left` / `.right` passed to `padding`/`safeAreaInset` instead of `.leading`/`.trailing`; `NSLayoutConstraint` mixing `leftAnchor`/`rightAnchor` with `leadingAnchor`/`trailingAnchor`; `frame(alignment: .topLeft)`.
- `NSTextAlignment.left`/`.right` for body text instead of `.natural`.
- Chevrons and arrows as fixed images (`chevron.right`, `arrow.left`) for navigation affordances — should be `.forward`/`.backward` or flipped via `imageFlippedForRightToLeftLayoutDirection()`.
- `UIView.appearance().semanticContentAttribute = .forceLeftToRight` on a container that holds text.
- Custom drawing (Core Graphics, Canvas) computing positions from `bounds.width - x` without consulting `layoutDirection`.

**Severity hint** – Medium (unusable mirrored UI; visible in review screenshots for RTL locales).

**Refactor direction** – Switch to leading/trailing constants and `.natural` alignment; for arrows use the direction-aware symbols or `imageFlippedForRightToLeftLayoutDirection()`.

**Counter-signals** – Media transport controls, timelines and numeric keypads where LTR is semantically correct (mark them explicitly).

**Sources** – https://developer.apple.com/design/human-interface-guidelines/right-to-left [official 2026]; https://developer.apple.com/documentation/uikit/uiimage/imageflippedforrighttoleftlayoutdirection() [official 2026]

---

### Info.plist and entitlement hygiene: no unused usage strings, declare export compliance, keep `aps-environment` honest

**Rule** – Every `NS*UsageDescription` must correspond to a permission the app actually requests and reads, `ITSAppUsesNonExemptEncryption` must be set, and `aps-environment`/`remote-notification` must match real push usage.

**Since** – `ITSAppUsesNonExemptEncryption` since 2019 submission flow; usage strings since the protected resource shipped; `aps-environment` is injected by the Push Notifications capability.

**Detection signals**
- `NS*UsageDescription` keys in Info.plist with no matching API in the binary: `NSCameraUsageDescription` without `AVCaptureSession`, `NSLocationWhenInUseUsageDescription` without `CLLocationManager`, `NSMicrophoneUsageDescription` without `AVAudioRecorder/AVAudioSession.record`, `NSContactsUsageDescription` without `CNContactStore`, `NSPhotoLibraryUsageDescription` when the app only uses `PhotosPicker` (no permission needed).
- Usage strings that are placeholder text (`" "`, `"TODO"`, `"We need this"`) or do not state the purpose — 5.1.1(ii) rejection.
- `NSUserTrackingUsageDescription` present but no `ATTrackingManager.requestTrackingAuthorization` call, or `NSPrivacyTracking` absent/false in the manifest while `ASIdentifierManager`/IDFA is used.
- `ITSAppUsesNonExemptEncryption` missing entirely (every submission is asked again; a wrong `true` invites an export-compliance questionnaire).
- `aps-environment` in entitlements but no `remote-notification`/push registration, or the reverse: `registerForRemoteNotifications()` with no `aps-environment` → `didFailToRegisterForRemoteNotificationsWithError`.
- `CFBundleURLTypes` schemes declared but never handled in `onOpenURL`/`application(_:open:)`.
- `NSSupportsLiveActivities` / `NSSupportsLiveActivitiesFrequentUpdates` present with no ActivityKit code.

**Severity hint** – Medium (review questions, delayed submissions, privacy-label mismatch) / High where a missing `NS*UsageDescription` crashes the app at first permission request.

**Refactor direction** – Delete unused keys, write purpose strings that name the feature ("<App> compares photos you pick…"), set `ITSAppUsesNonExemptEncryption=false` when only Apple-provided crypto is used, and pair `aps-environment` with the push capability on the App ID.

**Counter-signals** – Usage strings required by an extension target's own Info.plist (each bundle needs its own); `ITSAppUsesNonExemptEncryption=true` for apps that implement their own crypto.

**Sources** – https://developer.apple.com/documentation/security/complying-with-encryption-export-regulations [official 2026]; https://developer.apple.com/app-store/review/guidelines/ §5.1.1 [official 2026]; https://developer.apple.com/documentation/bundleresources/information-property-list/ITSAppUsesNonExemptEncryption [official 2026]

---

### Handle the age-assurance APIs when shipping in regulated regions

**Rule** – Apps built against the iOS 26.2+ SDK that distribute in age-assurance jurisdictions must ask for the system-declared age range (`AgeRangeService`) and check the regulatory feature set, instead of collecting a birth date themselves.

**Since** – `AgeRangeService` / `DeclaredAgeRange` iOS 26.0; `requiredRegulatoryFeatures` and `showSignificantUpdateAcknowledgment(in:updateDescription:)` iOS 26.4; the full set requires building against the iOS 26.2 SDK with Xcode 26.2 (17C52) or later.

**Detection signals**
- No `import DeclaredAgeRange` / `AgeRangeService` usage in an app that gates content by age (grep `birthYear`, `birthdate`, `isAdult`, `dateOfBirth` pickers in onboarding).
- `try await AgeRangeService.shared.requiredRegulatoryFeatures` never called before showing age-gated content, or its `throws` (`Error.notAvailable`) swallowed into a silent "allow".
- The `.sharing(ageRange)` result not handled — code that assumes a range always comes back, and no path for "declined" or `lowerBound == nil` (under 13).
- Custom DOB entry stored server-side where the declared-range API is the required path.
- App Store Connect age-rating questions still answered under the old 4+/9+/12+/17+ scheme (the 13+/16+/18+ system applies, with responses required since 2026-01-31).

**Severity hint** – High (regulatory exposure in the affected regions; review rejection for missing age assurance).

**Refactor direction** – Replace DOB collection with the system sheet, branch UI on the returned range, and keep the server side able to accept "unknown/declined".

**Counter-signals** – Apps with no age-restricted content and no distribution in the regulated regions.

**Sources** – https://developer.apple.com/support/age-assurance/ [official 2026]; https://developer.apple.com/news/upcoming-requirements/?id=07242025a [official 2025, deadline 2026-01-31]

---

### Close the code-level App Review traps: UGC moderation, account deletion, remote code, hidden features

**Rule** – Apps with user-generated content must ship report + block + filter; apps with account creation must offer in-app account deletion; no code may be downloaded to add or change features; no hidden or debug-only feature may be reachable in the release build.

**Since** – All; account deletion since 2022, remote-code prohibition is longstanding 2.5.2.

**Detection signals**
- UGC surface (feed, comments, profiles) with no `report`/`block` action in the code path, no `filter`/moderation call in the client.
- Sign-up flow (`createAccount`, `signUp`, `ASAuthorizationController` for SIWA) with no `deleteAccount` request anywhere in the networking layer, or deletion only via a web link — 5.1.1(v).
- Digital goods sold outside IAP: `Stripe`, `PayPal`, `checkout` URLs for unlocking features/credits/subscriptions (3.1.1), or "restore purchases" missing.
- Downloaded executable content: bundled JS engines evaluating remote scripts, `.jsbundle`/`.lua`/DEX from the network, `WKWebView` used to render app UI that changes behaviour remotely (2.5.2 / 4.7 rules).
- Debug surfaces reachable in Release: `#if DEBUG` menus, hidden gestures (`tapCount == 5`), remote-config flags that reveal unreleased features, a `-UITest` launch argument branch compiled into Release.
- Third-party login without Sign in with Apple (4.8), or SIWA present but `ASAuthorizationAppleIDProvider` results not handled.
- Placeholder content or a "coming soon" screen in the shipping build (2.1/4.2).

**Severity hint** – High (rejection or removal).

**Refactor direction** – Add the missing moderation/deletion/IAP path behind the existing service layer; move every debug affordance behind `#if DEBUG` and a non-Release build configuration.

**Counter-signals** – Apps with no accounts and no UGC; a `WKWebView` used to display third-party web content the app does not control (still subject to 5.2).

**Sources** – https://developer.apple.com/app-store/review/guidelines/ §1.2, §2.5.2, §3.1.1, §4.8, §5.1.1 [official 2026]

---

## Tools

Availability of the CLI tools below was checked on the Xcode 27.1 toolchain that ships with this machine; the Organizer rows are UI flows, and the privacy-report row depends on an archive existing.

| Command | Detects |
|---|---|
| `xcodebuild -version`; `xcrun --sdk iphoneos --show-sdk-version`; `swift --version` | Whether the toolchain meets the 2026 submission floor (Xcode 26+/iOS 26 SDK) and which SDK deprecations will fire. |
| `xcodebuild -showBuildSettings -scheme <scheme> \| grep -E 'SDKROOT\|IPHONEOS_DEPLOYMENT_TARGET\|SWIFT_EMIT_LOC_STRINGS\|LOCALIZATION_PREFERS_STRING_CATALOGS\|ENABLE_ON_DEMAND_RESOURCES\|TARGETED_DEVICE_FAMILY'` | SDK/deployment floor, localisation settings, ODR leftovers, device-family assumptions. |
| `find . -name PrivacyInfo.xcprivacy -not -path "*/.build/*"` | Missing privacy manifest per target (compare with `targets:` in `project.yml`). |
| `plutil -p <target>/PrivacyInfo.xcprivacy` | Declared `NSPrivacyAccessedAPITypes`/`NSPrivacyCollectedDataTypes`/`NSPrivacyTracking` — diff against greps for `UserDefaults`, `attributesOfItem`, `systemUptime`, `activeInputModes`. |
| `plutil -p <path>/Info.plist`; `plutil -p <path>.entitlements`; `plutil -lint <path>/PrivacyInfo.xcprivacy` | Unused usage strings, launch-screen keys, `ITSAppUsesNonExemptEncryption`, `UIBackgroundModes`, `LSApplicationQueriesSchemes` count, `aps-environment`, App Group parity across targets, malformed manifest. |
| `codesign -d --entitlements :- Payload/<App>.app` | Entitlements actually embedded in the built product (App Group, family-controls, `aps-environment`), not just the source plist. |
| `git ls-files -z \| xargs -0 grep -nE 'sk_live_\|AKIA\|BEGIN (RSA\|EC) PRIVATE\|ghp_'` | Secrets committed in source or config. |
| `grep -rn "UIScreen.main\|\.keyWindow\|UIApplication.shared.windows\|UIScreen.bounds" --include=*.swift .` | Main-screen/key-window references (deprecated iOS 13/15/26; wrong values under iPhone Mirroring). |
| `grep -rn "NavigationView\|FileDocument\|NSBundleResourceRequest\|canOpenURL(" --include=*.swift .` | Deprecated-in-26/27 surfaces. |
| `grep -rn "Timer.scheduledTimer\|addObserver(forName\|asyncAfter" --include=*.swift .` | Retain-cycle candidates (target-retained timers, unstored observer tokens, delayed strong-self captures). |
| `grep -rn "Font.system(size:\|systemFont(ofSize:\|fixedSize:" --include=*.swift .` | Fixed font sizes that ignore Dynamic Type. |
| `xcodebuild build -scheme <scheme> 2>&1 \| grep -i "deprecated" \| sort -u` | Every API the current SDK flags, one line per unique warning. |
| `xcodebuild test -scheme <ui-test-scheme> -destination 'platform=iOS Simulator,name=<simulator>'` with `try app.performAccessibilityAudit(for: [.contrast, .dynamicType])` in a UI test | Contrast, Dynamic Type, element-description and hit-region failures as test failures (Xcode 15+/iOS 17+). |
| `xcrun xcstringstool print <path>/Localizable.xcstrings`; `xcrun xcstringstool extract <source-files…> --output-directory /tmp/strdata` | Localisable string keys present in the catalog versus keys a lightweight parse finds in source — the missing-translation set. |
| `xcodebuild -exportLocalizations -project <x>.xcodeproj -localizationPath ./loc` | XLIFF export of every project localisation — the definitive list of what is translatable and which languages are actually wired into the project. |
| `xcrun xctrace list templates`; `xcrun xctrace record --template 'Time Profiler' --attach <pid> --time-limit 30s` | Available instruments on the machine (`Swift Concurrency`, `Leaks`, `Allocations`, `Animation Hitches`, `App Launch`, `Time Profiler`, `System Trace`); Time Profiler on the main thread is how a >100 ms block is proven. |
| Xcode Organizer archive → **Generate Privacy Report** (Xcode 15+) | The combined privacy-manifest report for the app plus every embedded SDK; diff it against App Store Connect privacy answers. |
| Xcode Organizer → Hangs / Disk Writes / Battery reports; MetricKit `MXHangDiagnostic.hangDuration`, iOS 27 `MemoryExceptionDiagnostic` | Field evidence of hangs, extension memory kills and disk-write exceptions that unit tests cannot reproduce. |
| Device Hub (Xcode 27) and Xcode Previews drag-to-resize | Resizable-layout regressions (iPhone Mirroring, iPad windowing) without extra devices. |
