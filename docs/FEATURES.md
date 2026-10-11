# Nimbus FieldKit v0.2 — tools and deployment boundaries

**Live update:** the user installed and ran the native shell agent successfully on the drive. The live TI driver advertises monitor mode; this is not a working capture or concurrency test. See `NATIVE-LIVE-2026-10-11.md`. Earlier deployment boundaries below still apply to the host Python tools and privileged actions.

GameHack controls, SanDisk is the main Wi-Fi hub, and Pi is the USB worker. Stock SanDisk AP/client Internet sharing passed a live test before the user's reset. It must be checked again after configuring WPA2 and the upstream hotspot.

## Delivered software

| Feature | Available now | Important boundary |
| --- | --- | --- |
| Controller dashboard | GameHack-native menu, local inventory, bounded SanDisk service probes | Remote battery/client/storage metrics need authenticated telemetry; not fabricated |
| Pi queue | Dedicated list, submit, result and cancel menu actions | Uses existing pinned SSH/USB client and worker; not a new unauthenticated API |
| Field vault | Local snapshots, SHA-256 manifests, read-only web download | No automatic capture/credential collection |
| Diagnostics | Single-IP TCP, ping, DNS query, local routes | Web active diagnostics require explicit CIDR and permission confirmation |
| Watchdog | Bounded repeated node checks, changes observable in JSON output | Detects service reachability, not phone uplink health; never changes networks |
| Offline toolbox | Bundled docs in browser and controller menu | No Internet or CDN required |
| File sync | Explicit single-file local/mounted transfers with SHA-256 verification | No overwrite, no automatic mounting, no insecure FTP sync; remote SFTP not implemented |
| Privacy | Local prototype blocks sharing/probes/active diagnostics | Does not turn off SanDisk FTP/Telnet/AP; device hardening is gated |
| Passive capture | Controller can queue existing bounded Pi radio capture | Pi helper rejects connected/unsupported radios; SanDisk monitor mode still unverified |

These are host/controller tools. They are not flashed or installed on SanDisk. Its stock archive has no Python executable identified. Device-native binaries require a verified ARM/libc toolchain and authorized shell access.

There is also a **device-native POSIX shell agent candidate**, `device/nimbus-agent.sh`, for manually reading status/capabilities, hashing an explicitly selected file, and optional bounded ordinary-interface capture when tcpdump and a supported timeout command are present. It does not install tools, change radio modes, disable services, or flash firmware. Its syntax/help can be checked on the host, but its native execution has not been tested on SanDisk. Do not interpret host execution as device telemetry.

Once secure authorized access is established, review the script and run `sh nimbus-agent.sh capabilities` on the drive first. Capture requires explicit permission, an existing interface and a new output file; it is capped at 15 seconds/250 packets/128 bytes per packet without promiscuous or monitor mode. Output can contain private traffic, and timeout can leave a partial capture. There is no automatic capture on startup.

## Browser

```sh
python3 fieldkit/server.py --vault ./vault --device 172.16.10.178 --allow-network 192.168.11.0/24
```

Use the device's actual post-reset IP. `--device` authorizes read-only probes of that single address; it does not authorize scanning a subnet or logging in. The server stays localhost-only. Privacy mode is in-memory and resets to disabled on restart; it is not a firewall or a defense against other local programs. Lock clears the browser token, not the server token.

## CLI (no packages required)

```sh
python3 fieldkit/tools.py status 192.168.11.1
python3 fieldkit/tools.py watch 192.168.11.1 --count 6 --interval 10
python3 fieldkit/tools.py dns 192.168.11.1 example.com --source 192.168.11.100
python3 fieldkit/tools.py ping 192.168.11.1
python3 fieldkit/tools.py routes
python3 fieldkit/tools.py manifest ./vault
python3 fieldkit/tools.py sync ./vault/REVIEWED_FILE.json /path/to/already-mounted/storage
python3 fieldkit/tools.py privacy-plan
```

Watch count is 1–120 and interval 5–300 seconds. Transfers are limited to one regular file up to 64 MiB; directories, source symlinks, and destination collisions are refused. Each newly created output is flushed and rehashed; failed outputs created by this operation are removed. This is not a recursive/mirroring backup. Mount media yourself through an established safe workflow. On FAT/exFAT, POSIX file modes may not enforce privacy; protect the physical media and mount permissions.

Manifests cover up to 500 regular supported files and record hashes, sizes and names. A checksum detects changes, but does not authenticate a file's author. Snapshots and manifests can contain private identifiers; review before sharing.

## Tools that can eventually run ON SanDisk

The practical target is lightweight **ARM Linux** tools, cross-built against the device's actual ABI/libc and kernel APIs. Storage capacity is not evidence of RAM capacity.

| Tool | Purpose | Status |
| --- | --- | --- |
| BusyBox ping, DHCP, shell, network/process tools | Basic diagnostics | BusyBox is present in the firmware archive; individual applets/live paths need checking |
| iw / hostapd / wpa_supplicant / iptables | AP/client networking and inspection | Present in archive; stock AP/client transit tested pre-reset |
| Dropbear/OpenSSH | Key-only pinned administration | Service material exists; usable authenticated access not yet established |
| tcpdump/libpcap | Bounded interface traffic captures for owned/permitted traffic | Build/runtime and RAM/storage limits need validation; no monitor-mode promise |
| iperf | Client/server LAN throughput tests | Candidate cross-build, not installed; expose only temporarily on trusted LAN |
| curl/wget | HTTP/TLS/DNS connectivity tests | Candidate runtime; modern TLS/library compatibility must be validated |
| netcat/socat | Explicit TCP checks and authorized lab serial/network workflows | Candidate; no automatic listening shell or relay |
| Nmap (small build) | Explicit scoped host/service checks | Optional feasibility test; expensive scripts/full distro are not a baseline |
| sha256sum and bounded log collector | File integrity and system diagnostics | Applet/runtime verification required |

No Kali rootfs, modern Python runtime, mass scan, credential attack, deauthentication, injection, or exploit bundle is supplied. Packet capture remains subject to driver capabilities and authorization. NFC/Sub-GHz/IR require real external hardware; none is created in software.

## Device security and recovery gates

1. After reset, configure WPA2-AES and a new admin password locally; never send passwords or private keys in chat.
2. Verify authorized shell access on the trusted management link. Open Telnet is evidence of a listener, not permission/authentication or a secure channel. Do not brute-force passwords or expose it to untrusted clients.
3. Read live inventory, exact partition map, ABI/libc, RAM, daemon startup methods and Wi-Fi capabilities. Preserve original firmware and device-specific NVS/calibration with a verified recovery method.
4. Establish and test key-only SSH with a pinned host key, including a second session and reboot/recovery test.
5. Only then disable Telnet/FTP and unnecessary HTTP/discovery/port forwarding. Keep a rollback path. No shutdown script is supplied because current administrative access has not been proven.
6. Validate power loss, radio coexistence, battery/charging, hotspot reconnection and security before calling this a device release.

The reset does not by itself upgrade the legacy kernel or harden exposed services. Post-reset recheck found HTTP/Telnet reachable at the previous upstream IP but SSH/HTTPS unavailable; no login or device changes were attempted.
