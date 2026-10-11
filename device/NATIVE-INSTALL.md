# Native toolkit: prepared, not installed

This bundle contains **scripts and documentation only**. It contains no firmware image, replacement bootloader, credentials, executable downloads, or service-start/stop commands. It does not grant shell access.

## Firmware runtime evidence

Read-only archive inspection found 32-bit little-endian ARM ELF binaries (ELF machine 40), EABI5 flags, `/lib/ld-linux.so.3`, and glibc 2.11.1. That is not an ARM64 or ordinary modern armhf rootfs. Do not copy desktop binaries or install distribution packages blindly.

The firmware archive already includes:

- `/usr/sbin/tcpdump`
- `/usr/sbin/sshd`, `/usr/bin/ssh`, `/usr/libexec/sftp-server`
- `/usr/bin/wget`
- BusyBox, iw, hostapd, wpa_supplicant, and legacy iptables tooling

Dropbear has startup script material, but a Dropbear executable was not found in this inspected archive. iperf, curl and Nmap were not found under their usual executable names. Live availability and versions still need checking.

The SSH binary contains old OpenSSH version strings, including 4.3/4.3p2, and old OpenSSL material. This is **not a verified modern secure SSH server**. Merely starting stock sshd does not resolve its age/security or compatibility problems. No legacy-crypto exception or host-key-check bypass is supplied. A maintained replacement needs a compatible cross-build and live tests; this host currently has no ARM cross-compiler or ARM emulator available.

## Establish access first

Live login is now verified: `admin`, uid/gid 1002, ARMv7. The user reports ~128 MB physical RAM and ~27 MB free rootfs space, no sudo, read-only tmpfs home `/var/ftp`, and storage mounted at `/mnt/storage` and `/mnt/sdcard`. Storage writability for admin remains to be checked. Do not install into the small rootfs, tmpfs home, firmware pool, or settings/calibration partition. User-level installation must use a newly created directory on writable storage; it does not grant capture/root/daemon privileges.

The post-reset upstream IP was reachable at `172.16.10.178`, but port 22 refused connections. FTP/Telnet/HTTP were open. The user successfully logged in via Telnet; the agent has not authenticated or issued privileged commands on the device.

Use only the device's documented/known shell credentials through an existing authorized access method. The web admin password is not necessarily the Linux shell password. Do not brute-force credentials or expose plaintext Telnet to an untrusted network. Keep any initial administration on an isolated trusted link. Never paste passwords/private keys into chat.

Before installing, record the live runtime inventory, rootfs/mount layout, free RAM, and verified recovery method. The filesystem might be read-only or have vendor-generated startup/configuration files; do not assume persistence.

## First manual run, after verified access

1. Transfer only this toolkit archive using a reviewed method, to user-selected storage. Do **not** copy the project's `.img` firmware file to an upgrade-monitored location.
2. Inspect archive paths/content and its `MANIFEST.json`, verify hashes, then unpack into a new disposable directory. No rootfs replacement, startup edits, or flash writes are needed.
3. Run these commands **on the drive**, not on the desktop:

   ```sh
   sh nimbus-agent.sh help
   sh nimbus-agent.sh status
   sh nimbus-agent.sh capabilities
   ```

4. Review output before sharing. Status includes network/storage identifiers. It deliberately does not read passwords, keys, shell history, or vendor configuration databases.
5. Do not enable capture until tcpdump, timeout syntax, filesystem capacity and authorization have been verified. The agent refuses absent tools and unsupported timeout syntax. It never changes monitor/promiscuous mode or radio channel.

## Remaining installation gates

- Maintained key-only SSH server, dedicated key and verified pinned host identity, including reboot and second-session checks.
- Configuration/calibration backups and tested rollback before stopping vendor services.
- Only then disabling unnecessary Telnet/FTP/HTTP exposure.
- Compatible builds/runtime tests for iperf, modern curl/TLS and optional small Nmap; pinned source/checksums/licenses.
- Native memory, capture, battery/charging and hotspot stability tests.

No installation or hardening is claimed until these gates have passed on the physical drive.
