# Security inventory supplied by user — 2026-10-11

Root session observations (no passwords, key contents or SSIDs retained):

- ARMv7 Linux 2.6.35.3-899-g9b1a262; rootfs approximately 27 MiB free.
- `ssh -V`: OpenSSH_4.3p2, OpenSSL 0.9.8g (2007-era client). `/usr/sbin/sshd` is installed; server implementation/version still requires confirmation rather than assuming the client version proves it.
- `/usr/sbin/dropbear` absent at that path. Other paths were not yet checked.
- Three SSH private host-key files in `/etc/ssh` are mode 0744 (world-readable); timestamps are from 2012. Uniqueness is not established. Restricting permissions does not erase prior exposure or replace/rotate keys.
- No active directives matched the limited SSH configuration grep. This does not establish safe defaults or exclude additional directives/configuration sources.
- `/etc/inetd.conf` line 27 launches BusyBox Telnet via inetd.
- AP hostapd reports `key_mgmt=WPA-PSK`, group cipher TKIP, RSN pairwise CCMP and TKIP. The precise WPA protocol setting was not shown by `get_config`; inspect only non-secret active fields to establish it.
- Hotspot uplink wpa_supplicant reports WPA2-PSK, pairwise/group CCMP, COMPLETED.

Offline vendor source/script review identifies persistent `CFG_WIFI_AP_MODE`, and the Wi-Fi startup script maps `wpa2aes` to the WPA2-AES template. Active hostapd config is generated in `/tmp/hostapd.conf`. Do not edit that temporary file as the persistent fix or blindly invoke the Wi-Fi restart/routing scripts: they can disconnect management and alter NAT/firewall state.

Next: restrict exposed private host-key permissions (without starting SSH), check only the active AP protocol/cipher fields and persistent AP mode, and identify compatible maintained SSH build options. No Telnet disabling, Wi-Fi change, service restart, key rotation or reboot has yet been performed by the agent. Keep working management access until the replacement is verified.

## Follow-up

User ran chmod 0600 on the three old private host keys; command reported no error (subsequent permission listing not yet supplied). This is containment only, not host-key rotation or proof keys were never exposed.

Persistent AP mode is `CFG_WIFI_AP_MODE:anywpa2`. Active filtered hostapd fields are `wpa=2`, `wpa_key_mgmt=WPA-PSK`, `wpa_pairwise=TKIP CCMP`, `auth_algs=3`. WPA2 is confirmed; mixed TKIP/CCMP remains the issue. Vendor persistent `wpa2aes` mode is the intended candidate after access/rollback checks. No Wi-Fi mode change/restart was made.

Dropbear was also absent at `/usr/bin/dropbear` and `/usr/local/sbin/dropbear`. The existing `/usr/bin/ssh-keygen` dates to 2012; it is not selected for new credentials.

## Maintained SSH source review

Official upstream identifies Dropbear 2026.94 as latest (23 July 2026). The primary archive request returned HTTP 403; the mirror explicitly linked by upstream supplied the release, detached signature and signing key. Isolated GPG verification succeeded against that downloaded key; fingerprint `F7347EF2EE2E07A267628CA944931494F29C6773`. This verifies signature consistency, not an independently established out-of-band signer identity.

Archive SHA-256: `e098034a843699200c8c977a991fff73159735bf795d5f72ef672c41a6b1ae81`. Review artifacts: `/tmp/opencode/nimbus-ssh-review/`. No source configure/build scripts were executed and no candidate binary was uploaded or installed yet.

Source supports Ed25519 and public-key authentication and includes a runtime password-disable option. Build policy should disable password/PAM authentication and unused forwarding, use a unique securely stored host key, and initially listen only on a verified management address/test port with Telnet retained. Runtime compatibility, entropy handling on kernel 2.6.35 and reboot persistence are not established.

Host has clang/LLVM linker and native GCC, but no ARM GCC cross-compiler was found in PATH. A compatible cross sysroot/runtime is still required. An unpatched stock musl 1.2.6 runtime is **not** an acceptable shortcut: upstream's current release page lists 32-bit qsort and iconv security advisories requiring patches. Any static build must pin/verify the fixes as well as the SSH source. No claim of a secure built replacement is made.

References: `https://matt.ucc.asn.au/dropbear/dropbear.html`, its linked `https://mirror.dropbear.nl/mirror/`, and `https://musl.libc.org/releases.html`.
