# GameHack integration: native capability report

## Refreshed handheld baseline

October 12 source review: `GameHack-Zero/FIRST-BOOT-SETUP-STATUS.md` records
227 passing PC tests. The earlier controller/setup batch is installed on the
256GB development card; its media runtime and Nimbus library module were already
present. Consolidated password/SSH sandbox fix, live setup status, region changes,
Pi direct-USB route validation and interactive Wi-Fi secret handling remain
staged. The old images do not include these updates. Native acceptance is separate.

These handheld Python/systemd actions must not be copied onto the legacy SanDisk
runtime. The drive remains optional; Pi pairing and USB networking stay independent.

## Implemented on the SanDisk source side

`device/nimbus-companion-status.sh` produces bounded, allowlisted JSON on stdout:

- Main internal/SD and SD FTP mount state, separately.
- Observed `g_file_storage` module state, or unknown if unreadable.
- Observed TCP 2224 listening state from IPv4/IPv6 kernel tables.
- Explicit unqualified remote browsing/SFTP/backup-transfer states.
- No implied network, mount or remote-write permissions.

It accepts no arguments, reads no keys/passwords, filenames, profiles or user
content, starts no process/service beyond shell/awk, and creates no files. It does
not publish a public web endpoint or install a background service. It is intended
for an already authenticated, pinned management session. A caller must establish
and record that authentication independently; JSON cannot authenticate itself.
Ordinary metadata reads are not a guarantee of zero kernel atime activity.

From a reviewed directory containing the source helper:

```sh
sh nimbus-companion-status.sh
# Or, with the updated agent beside it:
sh nimbus-agent.sh companion-status
```

The output schema is `nimbus-companion-status/v1`. Missing tables produce unknown
states, not false readiness. Duplicate mount records produce unknown. No raw
mount source, IP, MAC, process arguments, host identity or arbitrary options are
returned. Observations are non-atomic and not an action-time safety gate.

For a minimal source-only bundle, without dashboard assets or installer:

```sh
python3 scripts/package-companion-status.py --output build/nimbus-gamehack-companion-status-v1.tar
```

The builder refuses existing destinations and symlinks. The archive contains only
the helper, this document and a size/SHA-256 manifest; archive/member permissions
are 0600. Source tests cover mount ambiguity, missing observations, export state,
IPv4/IPv6 listener detection, argument refusal, unchanged fixtures, agent dispatch
and reproducible/no-overwrite packaging. No native execution has occurred.

The generic native source-kit builder includes this helper and document. That kit
also contains existing dashboard candidates; it is **not** a live upgrade
installer. Do not overwrite an installed toolkit with it. The helper can be
reviewed and streamed to `sh -s` through existing strict-pinned SSH without device
file installation, once the current address/key/pin configuration is confirmed.

## Not enabled by this change

SFTP remains disabled in the reviewed management build. A root SFTP listener is
not an acceptable production file-sharing shortcut; client path filters cannot
provide server confinement. No listener replacement, downstream SSH exposure,
mount policy, media upload, firmware change or radio operation is performed.

Next native step: run this helper over existing pinned management and compare
the output with the current browser/storage checks. Then separately review a
restricted authenticated transport and downstream pairing policy. Remote
browsing/transfer must stay blocked until that path is qualified. No GameHack
card, release manifest or app was changed in this SanDisk source implementation.
