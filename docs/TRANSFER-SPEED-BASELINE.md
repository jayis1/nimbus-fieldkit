# Upload/download baseline — approved, local payload prepared

The user explicitly approved a 16MiB synthetic-file upload/download test on
internal storage and SD, without overwriting existing files. Use the existing
dashboard upload endpoint, one destination at a time; no SSH transfer or new
upload endpoint masquerading as browser-performance measurement.

## Prepared non-sensitive payload

- PC directory: `/tmp/opencode/nimbus-speed-20261011-112449-10cc8a06fdf8/`, 0700.
- File: `payload-16MiB.bin`, 0600, **16777216 bytes** of host-generated random
  data (64 chunks of 262144 bytes), flushed/fsynced locally.
- SHA-256: **`60d9ac46a47650b15ccd860e0309c5db9ec68f99ae3c245bc2d9f16997187599`**.
- Private local metadata: same directory's `MANIFEST.json`, 0600.
- New folder on each storage: **`nimbus-speed-20261011-112449-10cc8a06fdf8`**.
  If that folder already exists, stop rather than merge/overwrite anything.

The agent created only the PC payload/metadata. No benchmark media directory,
upload, download verification or cleanup has yet been performed. No user files,
credentials, vendor firmware or private images are used as test payloads.

## Procedure and measurement boundary

Keep stable external power, USB data disconnected, music/other transfers paused
and the same PC/Wi-Fi topology during each measurement. Hard-refresh to load the
verified UI performance update. Create the exact fresh folder through the
original Files view, enter it and upload the prepared file: internal first, SD
second, never in parallel. Do not format, repair or remount to overcome refusal.

For upload timing, preferably record only the POST `/NimbusAPI/upload` request's
elapsed duration from the browser Network list. Do not share request headers,
cookies, form data, tokens or a full HAR. A stopwatch from upload start to device
confirmation is an approximate fallback; label it accordingly. `100% sent` is
not completion. Unknown/unconfirmed response is not a successful baseline;
retain destination evidence and do not blindly retry an existing filename.

After the user confirms uploads, separately read only the exact test objects via
`/storage/nimbus-speed-20261011-112449-10cc8a06fdf8/payload-16MiB.bin` and
`/sdcard/nimbus-speed-20261011-112449-10cc8a06fdf8/payload-16MiB.bin` on the known
device. Read one at a time with bounded expected-size validation, no redirects,
no compression and a streamed SHA-256. Measure elapsed request/read/hash time
and label it as host HTTP read throughput, not browser Save-dialog time or raw
flash/SD speed. No-cache request directives do not clear the device's OS cache;
do not drop caches or reboot to create a 'cold' result.

Both downloads must have exact expected size/hash. MB/s is decimal and MiB/s is
binary; report units explicitly. Treat a single 16MiB sample as a diagnostic
baseline, not a sustained-speed guarantee or proof of cache-independent storage
throughput. Configuration changes need evidence and separate scope review.

| Destination | Upload seconds / timing method | HTTP read seconds / MiB/s | Size/hash |
| --- | --- | --- | --- |
| Internal | Pending | Pending | Pending |
| SD | Pending | Pending | Pending |

Retain test files until integrity results and exact cleanup are reviewed. No
automatic deletion, arbitrary filename cleanup, concurrent upload, retries,
Wi-Fi security downgrade, mount-policy change, reboot or capture is authorized
by this benchmark.

## Follow-up: confirmation and missing expected URLs

The user replied that the uploads were good, without upload durations or exact
destination paths. Sequential bounded readback attempts to the two exact URLs
above returned HTTP errors before any payload bytes; status-only follow-up
confirmed **404 on both**. These are not successful downloads and do not provide
a throughput sample or integrity result. A browser-visible object may be in a
different folder or have a different name; do not assume data loss or upload
failure solely from these URLs. Do not probe arbitrary user paths, repeat
uploads blindly, or change export/mount policy to bypass the discrepancy.

Next request is exact test-file location confirmation, restricted to the
approved benchmark paths. No benchmark cleanup or device configuration change
has occurred. The local payload/manifest remain intact.
