# Per-payload learnings

What the schema does not say. Each item is cited to Apple (schema file under
`mdm/profiles/`, a developer.apple.com page, or a support.apple.com/guide/deployment
page id), to the vendor, or marked **measured** (observed on a real Mac) or
**[INFERENCE]**. Schema facts that `mobileconfig.py schema` prints are not repeated.

## Contents

- [Container](#container)
- [FileVault and escrow](#filevault-and-escrow)
- [Certificates](#certificates)
- [Wi-Fi](#wi-fi)
- [VPN and network extensions](#vpn-and-network-extensions)
- [System and kernel extensions](#system-and-kernel-extensions)
- [PPPC / TCC](#pppc--tcc)
- [Firewall](#firewall)
- [Gatekeeper](#gatekeeper)
- [Passcode](#passcode)
- [Restrictions and Activation Lock](#restrictions-and-activation-lock)
- [Managed preferences](#managed-preferences)
- [Deprecated in macOS 26–27](#deprecated-in-macos-2627)
- [Reading a profile back](#reading-a-profile-back)

## Container

- DOCTYPE: Apple's own profile examples use `-//Apple//DTD PLIST 1.0//EN`, some pages
  `-//Apple Inc//DTD PLIST 1.0//EN`. Both appear from Apple; neither is known to be rejected.
  `plistlib` / `plutil -convert xml1` output is fine.
- `PayloadVersion` is `1` at both levels; it is the format version, not a revision counter.
  Nothing in the profile says "this is revision 7" — the top-level `PayloadUUID` may change per
  revision (Apple: its content is "unimportant") and is what `ProfileList` reports back, but payload
  UUIDs must not.
- `IsEncrypted` is **not** a key you author; it appears only in `ProfileList` responses. Encryption
  means removing `PayloadContent`, CMS-enveloping it (an array-rooted plist) to a certificate already
  installed on that one Mac, and setting `EncryptedPayloadContent`. Per-device only; a server without
  a device identity cannot use it.
- `PayloadEnabled` is not in `TopLevel.yaml` or `CommonPayloadKeys.yaml`, though vendor examples set
  it. Omit it.
- A signed profile is CMS SignedData over the XML. MicroMDM's `PUT /v1/profiles` store verifies the
  signature and rejects a self-signed signer it cannot verify; its `InstallProfile` command path
  passes bytes through untouched.

## FileVault and escrow

Payloads: `com.apple.security.pkcs1` (escrow certificate, DER, no private key) +
`com.apple.security.FDERecoveryKeyEscrow` + `com.apple.MCX.FileVault2`.

- `EncryptCertPayloadUUID` must name a `com.apple.security.pkcs1` payload **in the same profile**.
  Whether `com.apple.security.root` (documented as an alias) satisfies it: no primary source.
- The escrow payload must be installed **before** FileVault is enabled; a key generated with no
  escrow payload present is never escrowed, and nothing re-escrows it except a key rotation.
  Escrow payload and FileVault payload may live in separate profiles; ordering is the constraint.
  Shipping all three together is simplest and is what Apple's example does.
- `FDERecoveryKeyEscrow` must be in a **System**-scoped profile.
- MDM cannot enable FileVault silently: `Enable: On` sent over MDM needs either the user's
  credentials in the payload or `Defer: true`. With `Defer`, encryption starts at the user's next
  logout/login ("deferred enablement", `dep0a2cb7686`). Never report a Mac as encrypted until
  `SecurityInfo` → `FDE_Enabled` says so.
- `DeferForceAtUserLoginMaxBypassAttempts` (`0` = mandatory at next login, `-1` = never forced) and
  `DeferDontAskAtUserLogout` only mean something while `Defer` is true.
- `ForceEnableInSetupAssistant` (macOS 14+): ADE only, refused in a manual install, needs
  `await_device_configured` and must land before `DeviceConfigured`; when set, **every key except
  `ShowRecoveryKey` is ignored** (`dep32bf53500`). An admin SecureToken user is required or the
  FileVault pane does not appear.
- Do not emit `Certificate`, `UseKeychain` or `PayloadCertificateUUID` on `MCX.FileVault2`: that is
  the institutional recovery key, which Apple calls of "no functional value" on Apple silicon.
- `MCX.FileVault2` needs user-approved MDM (macOS 10.15+). Removing the payload does **not** turn
  FileVault off.
- The escrow key's private half decrypts every key ever escrowed under that certificate. Rotating the
  certificate does not re-encrypt old envelopes, so keep every private key ever deployed.
- The escrowed envelope comes back in `SecurityInfo` → `FDE_PersonalRecoveryKeyCMS`, indexed by
  `FDE_PersonalRecoveryKeyDeviceKey` (serial). `FDE_HasPersonalRecoveryKey: true` means the Mac has a
  key, not that the server holds it.
- A certificate payload whose `PayloadContent` is not a certificate makes the whole profile fail to
  install — the only placeholder that fails loudly (**measured** in this workspace).

## Certificates

- `pkcs1`, `pem`, `root` carry public certificates; `pkcs12` carries a private key and a password —
  the file is then a secret.
- Every certificate reference (`PayloadCertificateUUID`, `PayloadCertificateAnchorUUID`,
  `EncryptCertPayloadUUID`, `IdentityCertificateUUID`, `SMIME*CertificateUUID`, …) resolves to a
  `PayloadUUID` in the same profile. `com.apple.sso.yaml`: "The configuration file needs to contain
  both the SSO payload and the identity certificate payload."
- A new certificate payload UUID on an existing profile = the old keychain item removed, a new one
  added; anything pinned to the old item breaks.

## Wi-Fi

`com.apple.wifi.managed`.

- `EncryptionType`: from macOS 13, `WPA` and `WPA2` are floors ("allows joining WPA2 or WPA3
  networks"); `WPA3` is exact — "allows joining WPA3 networks only" — so a WPA2-only access point is
  silently unreachable. Before macOS 13 every value had to match the network exactly. `Any` also
  admits WEP.
- A placeholder `Password` installs cleanly and reports success; the Mac just never joins
  (**measured**). An install is never evidence that the network works.
- `SetupModes` `System` / `Loginwindow`: the schema defines neither; every Apple mention is beside
  802.1X. Joining at the login window with a PSK network is **[INFERENCE]**; test it.
- Enterprise: `EAPClientConfiguration.AcceptEAPTypes` (13 = EAP-TLS, 25 = PEAP, 21 = TTLS),
  `PayloadCertificateAnchorUUID` for the server's CA, `PayloadCertificateUUID` for the client
  identity. `TLSTrustedServerNames` pins the RADIUS server name.
- **The two references differ, and requests often confuse them.** Server trust may live elsewhere:
  Apple, "It's not necessary to establish a chain of certificate trust in the same profile that
  contains the 802.1X configuration" (`depabc994b84`); anchors are optional when
  `TLSTrustedServerNames` is set. The **client identity for EAP-TLS may not**:
  `PayloadCertificateUUID` is "the UUID of the certificate payload within the same profile to use
  for the client credential" (`com.apple.wifi.managed.yaml:124-130`), and Apple's 802.1X guide says
  to "select the configuration that contains the certificate identity" — SCEP, ACME, PKCS #12 or AD
  Certificate. So "the identity comes from our separate SCEP profile, don't put one in this Wi-Fi
  profile" is a request to push back on: no Apple source documents a system-mode EAP-TLS network
  picking an identity from another profile. The fix is to move the SCEP (or ACME) payload into the
  Wi-Fi profile and reference it. If the user insists on two profiles, say plainly that it is
  undocumented — **[INFERENCE]** expect a certificate prompt or no pre-login join — and that it must
  be tested on a real Mac before rollout.
- `DisableAssociationMACRandomization` (macOS 15+) pins the hardware MAC; only for networks that
  require it.

## VPN and network extensions

`com.apple.vpn.managed` for a third-party NetworkExtension client:

- `VPNType: VPN`, `VPNSubType` = the **app's** bundle ID, `VPN.ProviderBundleIdentifier` = the
  **extension's** bundle ID. `UserDefinedName` and `VPN.RemoteAddress` are required even when
  cosmetic.
- Apple: if the provider uses a system extension, `VPN.ProviderDesignatedRequirement` is required.
  Some vendors' own examples omit it; if you follow the vendor, say so and name it as the first
  suspect when the extension fails to start.
- Pair it with a `com.apple.system-extension-policy` payload for the vendor's Team ID in the same
  profile, or the user sees *System Extension Blocked*.
- Vendor bug (Tailscale's docs): a VPN profile landing before the app is registered in
  LaunchServices logs `The VPN app used by the VPN configuration is not installed`. Mitigate by
  installing the app first, then a reboot or
  `lsregister -kill -r -domain local -domain system -domain user`, then the profile.
- Never embed a long-lived, reusable auth key in a profile: it lands in the MDM database as base64
  and multiplies profiles by headcount. The vendor's policy page is the source for its keys, and old
  key names (e.g. Tailscale's `ControlURL`, now `LoginURL`) linger in third-party templates.
- `com.apple.dnsSettings.managed`, `com.apple.dnsProxy.managed`, `com.apple.relay.managed` are
  deprecated in macOS 27.0 with no replacement named in their schema files; the same release adds
  DDM `network.dns-settings`, `network.dns-proxy`, `network.relay` configurations — the functional
  successors, **[INFERENCE]**.

## System and kernel extensions

- `com.apple.system-extension-policy` and `com.apple.syspolicy.kernel-extension-policy`: MDM only
  (manual install refused), user-approved MDM required.
- A Team ID must not be both in `AllowedTeamIdentifiers` and a key of `AllowedSystemExtensions` —
  Apple calls it an error. Same Team ID → bundle mapping in both `RemovableSystemExtensions` and
  `NonRemovableSystemExtensions` is an error.
- `AllowUserOverrides` defaults `true` for system extensions and `false` for kernel extensions.
- Installing an allowing payload completes a pending extension's activation; **removing it
  deactivates an active extension** (macOS 11.3+). Unassigning the profile breaks the product.
- Verify a vendor's Team ID from the installed app, not from a web page:
  `codesign -dv --verbose=4 /Applications/X.app 2>&1 | grep TeamIdentifier`.

## PPPC / TCC

`com.apple.TCC.configuration-profile-policy` — MDM only, UAMDM.

- Each entry needs `Identifier`, `IdentifierType` (`bundleID` for apps, `path` for bare binaries)
  and `CodeRequirement` = the output of `codesign -dr - /path/to/App.app` (the `designated =>` part).
  A wrong requirement fails closed, silently.
- `Allowed` **or** `Authorization`, never both. `AllowStandardUserToSetSystemService` only for
  `ListenEvent` and `ScreenCapture`.
- `Camera`, `Microphone`, `ListenEvent`, `ScreenCapture`: a profile can only **deny**.
- `AppleEvents` needs the three `AEReceiver*` keys; they are invalid anywhere else.
- Conflicts resolve to deny across profiles.
- macOS 27.0 deprecates `Accessibility`, `BluetoothAlways`, `Camera`, `Microphone`,
  `SpeechRecognition` here; Apple: "use the `Privacy` key in the declarative management
  `com.apple.configuration.app.settings` configuration", and on 27.0 an Accessibility grant becomes a
  non-blocking notification the user can undo.

## Firewall

`com.apple.security.firewall` — System scope, device channel.

- Multiple profiles merge as "the most restrictive union", so a baseline can be layered on later.
- `AllowSigned`/`AllowSignedApp` default `true` and the system sets them if absent.
- `EnableLogging`/`LoggingOption` were removed in macOS 15 and are gone from the 27.0 schema.
- Read back through `SecurityInfo` → `FirewallSettings` (`FirewallEnabled`, `BlockAllIncoming`).
- Whether the user can still toggle the firewall off, and what happens when the profile is
  removed: no primary source.

## Gatekeeper

`com.apple.systempolicy.control` (`EnableAssessment`, `AllowIdentifiedDevelopers`).

- Deployment allows one Security payload group per device; ship one.
- Blocking the Finder "Open anyway" override is a **separate** payload,
  `com.apple.systempolicy.managed` → `DisableOverride`.
- No MDM command reads Gatekeeper state; only an agent on the Mac (`spctl --status`, osquery's
  `gatekeeper` table) can confirm it.

## Passcode

`com.apple.mobiledevice.passwordpolicy` — deprecated in macOS 27.0 (the schema names no
replacement; the DDM `com.apple.configuration.passcode.settings` is the functional analogue,
**[INFERENCE]**). Still installs.

- Schema says `multiple: true`; Deployment says "Duplicates allowed: False". Ship exactly one
  passcode-bearing profile.
- `maxInactivity` / `maxGracePeriod` map onto screen-saver behaviour; `maxInactivity` has
  `range.max: 15` while the macOS prose says 60 — Apple does not reconcile them.
- `changeAtNextAuth` forces a reset at the next login for every user: never in a baseline.
- Whether an existing password is re-checked at install or only at the next change: no primary
  source.

## Restrictions and Activation Lock

`com.apple.applicationaccess` — several Restrictions payloads may coexist.

- `allowFindMyDevice: false` removes the user's only route to a user-linked Activation Lock; it
  locks nothing by itself. The organization-linked lock is an Apple Business Manager call, never a
  profile. `ActivationLockAllowedWhileSupervised` on the `Settings` command is the supervised-only
  alternative; "Unsupervised devices ignore this value".
- No MDM query reads Find My state on macOS: verify by the install, not a status read.
- `allowAssistant`, `allowDictation`, `allowDefinitionLookup` and several AI keys are deprecated at
  macOS 26.4 in favour of DDM `siri.settings` / `intelligence.settings` /
  `keyboard.settings` configurations.

## Managed preferences

Two ways to force an app's preferences:

1. **Payload per domain** — `PayloadType` = the app's preference domain (usually its bundle ID),
   keys flat beside `PayloadType`. This is what most vendors document.
2. **`com.apple.ManagedClient.preferences`** — `PayloadContent` is a *dictionary* from domain to
   `{Forced: [{mcx_preference_settings: {…}}]}` (or `Set-Once`). Apple's errata (macOS 15) records
   that this was once misdocumented.

Either way no Apple schema checks the keys: cite the vendor for each one, and check which domain
the app actually reads (`defaults read <domain>` on a Mac with the app).

## Deprecated in macOS 26–27

From the 27.0 schema (`CHANGES.md`), payload level on macOS:
`com.apple.SoftwareUpdate` (removed 27.0 → DDM `softwareupdate.settings`),
`com.apple.mobiledevice.passwordpolicy`, `com.apple.dnsSettings.managed`,
`com.apple.dnsProxy.managed`, `com.apple.relay.managed`, `com.apple.AssetCache.managed`,
`com.apple.applicationaccess.new` (27.0). `com.apple.systempreferences` (13.0: use
`DisabledSystemSettings`), `com.apple.configurationprofile.identification` (15.4).
`com.apple.SetupAssistant.managed` `Skip*` keys (15.0). Deprecated is not removed: the profile still
installs; say so and name the successor.

## Reading a profile back

- `ProfileList` returns identifiers, UUIDs and payload types — never settings values. It cannot
  prove a setting took effect. Send `ManagedOnly: true`; `IsManaged` is not returned on macOS.
- On the Mac: `sudo profiles show -type configuration` lists installed profiles and payloads;
  `profiles status -type enrollment` shows "(User Approved)".
- `profiles install` does not work from macOS 11; a manual install goes through System Settings →
  General → Device Management.
