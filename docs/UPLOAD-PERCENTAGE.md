# Genuine upload percentage: guarded browser transport candidate

The user requested a numerical upload percentage. The vendor AjaxUpload implementation submits a multipart form to a hidden iframe; that path does not expose bytes transmitted. `device/unified/upload-progress.js` intercepts **only the dashboard Upload button's** submission and cancellation methods to use XMLHttpRequest/FormData with `xhr.upload` events. Other AjaxUpload instances retain their original methods.

## Behavior

- Existing vendor `onSubmit` still selects the destination and opens the busy card. The same same-origin `/NimbusAPI/upload?rn&dest=...` endpoint, `userfile` field, multiple-file selection, additional form fields and browser session cookies are used. The browser constructs the multipart boundary; no file is pre-read into a custom memory buffer.
- The displayed percentage is `loaded / total` for the **whole multipart request**, including small framing overhead. It is not a per-file counter, a timer estimate or proof of durable storage.
- At 100% the label explicitly says **waiting for device confirmation**. If the browser cannot compute the request length, the UI stays indeterminate and says the percentage is unavailable.
- Recognized Nimbus XML/JSON numeric `errcode=0` invokes the existing completion callback; nonzero codes, HTTP errors and network failures invoke the existing failure callback. An unrecognized/empty/HTML response does **not** produce a success message: it asks the user to check the destination before retrying and refreshes the folder listing. Native endpoint response compatibility remains unverified.
- Cancel aborts the active XHR, closes the busy card, re-enables selection and ignores late events. It does not promise to remove partial/already-written files on the drive. No automatic retry or cleanup occurs. Only one request per uploader instance is active at a time.
- Missing File/FormData/XHR-upload support retains the legacy transport, without an invented percentage.

The CSS adds a numerical status line and native progress meter to the existing card while retaining the corrected stacking layer, Cancel, theme and reduced-motion styles. No new server API, shell execution, credentials, binary, service or radio configuration is introduced. This is nevertheless a **browser upload-transport change**, not merely decorative CSS, and requires native testing on a small disposable file before relying on it for large/private uploads.

## Package and guard scope

Prepared local-only artifact: `build/nimbus-upload-progress-ui-r1.tar`, SHA-256 **`e280a1bc7ab2ca99f4996bcf57985510af9e151e599d542c4c5bb620e0211748`**.

Read-only live checks before packaging confirmed the existing HTML5 homepage (`457f1244a7f017b080da0d475ef2c67752509f39b52f604fd34c6da98523b50b`) and **r2** loader stylesheet (`8fda6af14c301ffae5146afa4be8f9bda1164598c00637e92c10afe7651abf98`). This also establishes that the earlier overlap correction is served, though the user has not separately confirmed its visuals.

The package guards those exact baselines, requires fresh root-owned mode-0700 `/root/nimbus-upload-progress-r1` staging, backs up homepage/CSS privately, installs additive `/nimbus/data/fieldkit-upload-progress-r1/upload-progress.js`, and replaces only the homepage script reference and stylesheet. Patched hashes:

| Asset | SHA-256 |
| --- | --- |
| Homepage | `cef815fab959980289889a2fb99a0bb9619617d1052bdbd860850699f0491410` |
| CSS | `ab67dee0dbf51360cc1593699ccb60ded6a4f277a32233a08f8bf567ac05820b` |
| Progress adapter | `792fe880137c12880f75ae8dc2d7068b5149b3e4c04e8025ce1e1c2271818a4b` |

`scripts/package-upload-progress.py` reuses the reviewed homepage policy and extends it with exact CSS backup/replace/rollback guards. Rollback verifies installed homepage, CSS and adapter hashes before restoring both original UI assets; it refuses later edits and retains the unreferenced additive asset/backups. A partial install requires review, not blind rerunning. The installed Flash-warning controller, HTML5 Music adapter, Settings bridge, SSH listeners/hooks, services, mounts and firmware are not changed. Generated archive includes a vendor-derived homepage: **keep it local; do not publish it**. First-party sources are public.

Future unified/image builds now include the adapter, but existing v4 image artifacts were not rebuilt. The live drive still uses its existing upload transport until explicit UI installation and browser refresh; no progress installation is confirmed yet.

## Validation

**141 tests run: 139 pass, 2 Node-dependent skips.** The offline Chromium fixture exercises the adapter with deterministic byte events (50%, unknown length, 100% awaiting response), two-file FormData, cancellation/ignored late events, HTTP failure and XML success/error/unknown response classification. It also performs a real native XHR multipart request with two generated fixture files to a localhost-only test endpoint. No request is proxied to the drive. Existing navigation/Settings/music, overlap hit-testing, light theme and narrow/reduced-motion tests pass.

Installer fixtures test backup/replace/restoration of both homepage and CSS, refusal of later stylesheet edits and preservation of original backups during rollback. These are not native backend, large-file or storage durability tests.

After a guarded installation, hard-refresh and choose a small disposable file first. Verify percentage transitions, server-confirmation/error behavior and that the expected file appears with the right contents. For an unknown response, inspect the destination **before** retrying; do not assume failure or re-upload blindly. Do not share credentials, private filenames/files or full captured network traces. Native success/failure/cancel, media ownership and backend response evidence remain pending. No upload, remount or firmware flash was performed by the agent.
