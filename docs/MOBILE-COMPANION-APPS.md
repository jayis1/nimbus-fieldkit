# GameHack Zero + SanDisk companion — Android and iOS release track

User requirement: **one two-part companion app for both GameHack Zero and the customized SanDisk**, available on Android and iOS. It is not two unrelated apps or a SanDisk-only client. This is an independent project, not a claimed official SanDisk app update. No mobile implementation, APK, iOS build, signing identity or store listing exists yet. Vendor app source/assets and trademarks are not assumed reusable.

The original enhanced device homepage remains available and preserves vendor functions. Installing an app is optional; the apps do not introduce a second device-hosted dashboard or change the Pi's independent USB-worker role.

## Two-part application structure

Use two primary sections within the same app, backed by shared connection, transfer and permission handling:

### GameHack Zero

- Pair with the handheld independently of SanDisk; clearly show handheld status and supported capabilities.
- Manage supported handheld media/library, favorites, notes and backup/restore workflows where the deployed GameHack API supports them. Staged handheld features must not be presented as already installed.
- Show approved Pi job/worker status through GameHack's existing integration where available. Do not reroute or replace the independent Pi USB link or introduce arbitrary remote command execution.
- Keep this section functional when SanDisk is absent, powered off or disconnected. Operations that specifically need the drive must say so rather than blocking the entire handheld client.

### SanDisk / FieldKit

- Pair with the drive separately; browse internal/SD storage, transfer files, play supported media and show network/battery/storage status.
- Manage supported FieldKit switches through the scoped authenticated device API.
- Offer optional storage/gateway integration with the paired GameHack. No new mandatory SanDisk dependency for the handheld or Pi.

### Shared workflows and boundaries

When both devices are paired, expose compatible media handoff, handheld backup-to-drive/restore and transfer status. Check capabilities, available storage, explicit destination and authorization on both devices. Do not claim direct device-to-device transfer unless that authenticated transport is implemented and tested; otherwise show the actual phone-mediated path and its limitations.

Keep each device's identity and revocable credentials separate. Pairing with one must not silently authorize the other. Version and test the GameHack and SanDisk API contracts independently, with a combined compatibility matrix and separate connected/disconnected states. The app must never imply that the current wlan1-only drive SSH listener provides a working downstream GameHack API.

## First-release scope

- Pair with explicitly selected GameHack and/or SanDisk devices, display each verified identity and firmware/API compatibility.
- Browse internal storage and SD separately, with accurate free space and writable/read-only state.
- Upload/download with bounded requests, safe filenames, progress, cancellation, checksum verification and explicit overwrite confirmation. Resume support requires a verified server protocol; do not claim it based on client UI alone.
- Browse/play supported media, with native-device codec and streaming tests on each platform.
- Show real battery/charging, SD, AP/uplink and toolkit status; identify stale/unavailable data rather than inventing values.
- Manage supported persistent feature switches through scoped allowlisted API actions. Existing browser command preparation is **not** an already available remote execution API.
- Expose optional GameHack storage/backup workflows only when the deployed handheld and authenticated transfer capability actually support them. Keep SanDisk optional and Pi USB networking unchanged.
- Offer diagnostics with redaction and informed export. No automatic upload of media, keys, settings backups or hotspot credentials.

Firmware flashing, arbitrary shell commands, filesystem repair and destructive reset/format are excluded from initial app automation. Existing vendor functionality remains preserved on the drive; any later app exposure requires explicit authorization and reviewed safety gates.

## Required device contract

Define versioned GameHack and SanDisk APIs and capability schemas before building production mobile clients. Both device contracts require their own authentication and scope review. The current vendor HTTP/FTP endpoints and root SSH listener are not sufficient evidence of a secure mobile API.

- Authenticated encrypted transport with modern TLS, verified device identity and a reviewed out-of-band pairing flow. Do not bypass certificate validation, ship a universal secret, rely on plaintext first-contact trust, or place tokens in URLs.
- Per-client revocable credentials, bounded retries, least-privilege scopes, request/body limits, path containment, conflict detection and audit/log retention. No arbitrary command-execution endpoint or client root password.
- Credentials stored in Android Keystore-backed storage and iOS Keychain; device-side token/key storage and reset/revocation must be defined and tested.
- Explicit LAN/interface policy, independent of the current `wlan1`-only SSH administration listener. Do not expose root SSH globally to make the apps or GameHack work.
- Treat network changes as disconnect-prone transactions, with confirmed settings, visible failure status and a tested recovery path.
- Measure CPU/RAM/battery/transfer impact of a compatible backend on the retained ARMv7/legacy-kernel platform. Do not assume current vendor TLS is adequate or replace charging/network services blindly.

## Platform and topology tests

Test GameHack-only operation, SanDisk-only operation and both-device workflows. Support direct connection to the drive AP and the intended phone-hotspot topology only after real-device routing tests. A hotspot phone's access to attached clients varies by OS/network; no seamless reachability is promised. Verify loss of SanDisk does not break independent GameHack functions and loss of either device cancels/transitions shared operations safely.

Android requires current networking/media/storage permissions and lifecycle handling. iOS requires local-network permission handling, relevant discovery declarations and constrained background-task behavior. Manual address selection is required if discovery is unavailable. Do not assume background transfers, automatic Wi-Fi joining or hotspot controls work identically on both systems.

Use a shared client/domain layer where practical, with native platform integrations. Framework selection is pending; Flutter or React Native are candidates, not existing dependencies. Include a fake-device backend for client tests plus real Android/iPhone tests for pairing, disconnects, media, uploads, sleep/resume, permission denial and credential revocation.

## Delivery and release gates

1. Finish the firmware's provisioning, safe storage/USB policy, native boot and recovery gates.
2. Specify and security-test both versioned paired device APIs and optional shared transfers without weakening vendor/SSH access boundaries or changing Pi USB networking.
3. Implement the shared client and platform adapters; test minimum supported OS versions on hardware.
4. Produce signed Android builds with a protected, stable signing identity. Define distribution/store policy and update compatibility.
5. Produce iOS builds using macOS/Xcode and Apple signing; TestFlight/App Store distribution requires the applicable Apple developer account and review. This Linux workspace alone cannot sign and validate the iOS release.
6. Publish a firmware/API/app compatibility matrix, privacy disclosure, source/license review and rollback/update policy. The mobile apps must not label an untested image production-ready.

The firmware and companion apps are coordinated release tracks, not evidence that either is ready today. There is no promised store approval or release date.
