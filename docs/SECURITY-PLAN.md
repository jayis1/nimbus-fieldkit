# SanDisk security transition — plan only

No security settings are changed by reading this plan or installing the enhanced UI.

## Present evidence

- Direct root Telnet login works; factory root credentials are publicly known.
- Private off-device copies of the boot area, system partitions, calibration and web assets passed SHA-256 checks. Restore and recovery boot remain untested.
- Earlier probing found FTP/Telnet/HTTP listeners and SSH/HTTPS refused connections. Recheck current status before making decisions; historical observations are not live guarantees.
- Legacy firmware includes old SSH/OpenSSL components. Merely starting these binaries is not a maintained secure administration solution.
- The active Wi-Fi encryption mode/passphrase has not been verified. A template supporting WPA2 does not establish actual configuration.

## Sequence, with rollback at each step

1. Keep two authorized management sessions on an isolated trusted network. Keep private backups off the device, never in source control. Backups on stock media shares can disclose credentials; removal from the device is a separate explicit operation after backup verification.
2. Inventory SSH implementation/version, configuration, host-key location, writable persistence and available disk/RAM. Inspect only necessary metadata; do not display private keys or whole credential/configuration files in chat.
3. Identify a maintained SSH build compatible with ARM EABI, the old kernel and libc. Verify provenance/build reproducibility and runtime compatibility. If none works, use a trusted external management gateway rather than pretending an obsolete SSH daemon is modern.
4. Generate a unique client key on the management computer. Install only its public key on the device. Store server private keys outside world-readable media shares. Pin the server host key through a trusted channel. Disable password login only after key login is verified.
5. Test a second independent SSH session, explicit privilege access, reboot persistence and a recovery/rollback route. Do not disable the working Telnet service before these checks pass.
6. Use WPA2-Personal with AES/CCMP, not open Wi-Fi, WEP or TKIP; select WPA3 only if genuinely supported (not established here). Use a long unique passphrase. Verify both the downstream AP and phone-hotspot uplink configuration, avoid revealing their credentials in logs, and reconnect/test before further changes. Radio changes can disconnect management clients.
7. Restrict administration to the intended management side/subnet, considering both wlan0/AP and wlan1/uplink exposure. Review current firewall rules before editing; do not flush the vendor routing/NAT tables or break Internet transit.
8. After SSH and recovery validation, explicitly disable Telnet at its startup/service source and stop its listener. Disable unused FTP/other legacy services only after checking which stock features depend on them. Verify ports from both network sides and again after reboot.
9. HTTP stock administration remains a separate confidentiality risk even with SSH and WPA2. Evaluate a maintained TLS proxy/backend before calling the entire dashboard secure. Do not publish management ports to the Internet.

## Limits

This is not an automated hardening switch. Root access is not a secure web API; toolkit browser actions remain terminal-confirmed. The current legacy kernel, vendor libraries and browser dependencies are not repaired by a theme or firewall. No firmware flashing, password guessing, service stopping, SSH installation, Wi-Fi change or reboot is performed by the dashboard enhancement.
