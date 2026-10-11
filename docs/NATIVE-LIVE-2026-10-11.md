# Native toolkit installed and capability inventory received

The user ran the native agent on the physical drive as `admin` (uid/gid 1002), firmware 3.04, ARMv7 Linux 2.6.35.3-899-g9b1a262. This is user-provided live terminal evidence, not an agent-authenticated shell session.

## Installation

- Native script/doc bundle uploaded via the stock `/NimbusAPI/upload` endpoint, without firmware files or credentials.
- Vendor upload destination was `/mnt/storage/Scotti Upload/nimbus-kit-6d8a758826df.tar`, also visible through the FTP storage bind mount.
- Readback through `/storage/Scotti%20Upload/...` matched the prepared archive SHA-256.
- User independently ran `sha256sum -c` on the drive and received `OK` for hash `7c68b71482f02d15d1108824cd87f365910e9d789208051179b7b77298202834`.
- User extracted into **`/mnt/storage/nimbus-fieldkit-v02/native`** and successfully ran `sh nimbus-agent.sh capabilities`.
- No firmware, bootloader, startup files, rootfs services or radio modes were changed. The agent has not obtained the user's password or shell session.

The archive was deliberately timestamped at epoch zero for reproducibility. Old tar warned about implausibly old timestamps, but extraction and execution succeeded. Future packages use fixed 2026-01-01 timestamps to avoid this warning; the already installed archive remains valid and does not need reinstalling. Future packages have a different checksum and must be verified independently.

## Runtime and permissions

Previous live output established approximately 128 MB RAM, ~27 MB free rootfs space, a writable media directory, a read-only tmpfs home `/var/ftp`, and no `sudo`. `/tmp` is a small 4 MB filesystem. Do not fill rootfs or rely on tmpfs for persistent tools.

Available binaries reported:

- BusyBox, iw, hostapd_cli
- tcpdump, sha256sum, wget, netcat (`nc`)
- stock sshd (old firmware binary; not an enabled/verified secure SSH service)

No `timeout`, Dropbear, iperf, curl or Nmap executable appeared in the agent's PATH checks. Whether BusyBox includes a timeout applet remains unknown. Presence of tcpdump does not prove admin has packet-capture privileges.

## Live radio evidence

Loaded Wi-Fi modules include `wl12xx_sdio`, `wl12xx`, mac80211 and cfg80211. NAT modules, including MASQUERADE, are also loaded.

`iw list` reports:

- 2.4 GHz channels 1–13; channel 14 disabled. Actual use must obey regulatory settings, not just this listing.
- AP, managed, AP/VLAN, IBSS, monitor and P2P interface modes.
- Monitor and AP/VLAN listed as software interface modes.
- `interface combinations are not supported`.
- CCMP cipher support, alongside obsolete WEP/TKIP modes which must not be selected.

**Monitor mode is now advertised by the live driver.** It has not been created or used, and no packet capture, injection, deauthentication or channel change was performed. This legacy driver does not expose usable general interface-combination guarantees. That listing does not undo the successful earlier stock AP/client Internet transit test, but it is not proof of simultaneous AP/client/monitor operation.

The listing has a second band heading with no frequencies. This is **not evidence of usable 5 GHz operation**; do not enable or promise it.

## Safe next checks

On the drive, manually read `sh nimbus-agent.sh status`, `iw dev`, and `busybox timeout --help`. Review output before sharing. These can establish current interfaces/roles, routing, power telemetry if present, and whether the required bounded-capture timer exists, without changing radio state.

Root/approved capture capabilities, supported timer behavior and a recovery path remain prerequisites for packet capture/radio changes. Stock SSH must not be presented as hardened merely because its executable exists. Keep working Telnet until a maintained, pinned-key administration path is tested, while restricting the trusted management link and avoiding plaintext credential exposure.
