# GameHack Zero + SanDisk main Wi-Fi unit

## v0.2 integration update

The native menu now includes dedicated Pi queue controls, explicit diagnostics, verified single-file mounted-storage transfers, vault manifests, offline docs, and a secure-administration checklist. See `FEATURES.md` for precise scope. To upgrade the known unchanged v0.1 staged module:

```sh
python3 scripts/stage-gamehack.py --staging ../GameHack-Zero/hackeros-v3/staging --upgrade
```

This preserves a `.pre-v02` module backup and refuses unknown modified modules. Extra tools and offline docs are copied alongside the launcher; no card-update/deployment script is run. The original design notes below describe the proposed replacement AP; stock SanDisk AP/client Internet sharing has since passed a live test with its existing 192.168.11.1 LAN. After reset it must be configured and checked again.

## Roles (user-selected)

```text
GameHack Zero / R36XX       controller-first UI, L2 back / R2 select
  ├── Wi-Fi ── SanDisk      MAIN Wi-Fi AP + planned network/file service
  │             192.168.78.1/24 (proposed, not deployed)
  └── USB ──── Pi Zero W    existing key-pinned SSH worker
                192.168.77.1/24 (existing project configuration)
```

SanDisk is not merely an optional storage accessory. It is the main wireless control node; the Pi is not its replacement. The handheld's own Wi-Fi radio is still needed to join the SanDisk AP. No changes to the Pi USB profile, default Internet route, boot configuration, or handheld USB role are made.

With a single unverified 2.4 GHz radio, do not assume SanDisk can simultaneously provide an AP, use a Wi-Fi uplink, and capture on another channel. Initial design is a local control LAN without Internet/DNS routing. Internet gateway mode needs verified AP/client concurrency or a separate supported uplink, firewall/NAT, DNS, and explicit configuration. If the SanDisk firmware uses this proposed subnet already for another purpose, select a non-conflicting subnet before deployment.

## Implemented controller integration

`fieldkit/nimbus_fieldkit.py` uses the real launcher API (`select`, `text_view`, `confirm`, `browse`, `busy`) and its existing Pi client. The menu includes:

- Roles and main-Wi-Fi plan.
- Local host/link inventory, explicitly not remote SanDisk telemetry.
- Review/confirm a private local diagnostic snapshot, SHA-256 included.
- Browse the handheld's local Nimbus vault.
- Existing Pi USB link diagnostics and worker status, through `pi_worker.py` with its unchanged pinned SSH policy.

No raw shell, power control, or radio action is added. Snapshot collection reads only filtered Pi connection metadata, not private keys, queue commands/results, credentials, or captures. Review the preview before saving; host/interface names and diagnostic reasons can be private. Nothing syncs automatically.

Staging integration (not installation onto a card):

```sh
python3 scripts/stage-gamehack.py --staging ../GameHack-Zero/hackeros-v3/staging
```

The script adds **CONNECT > SanDisk / main Wi-Fi unit**, copies the standalone module beside the launcher, and saves `launcher.py.pre-nimbus` before editing. It validates the expected launcher anchors and Python syntax, is idempotent, and refuses conflicting modules/backups. To deploy later, use GameHack's reviewed card-update workflow; this project does not invoke it. Review any later changes before using the backup as a rollback—do not overwrite unrelated edits.

The browser prototype can display handheld snapshots by running on that host:

```sh
python3 fieldkit/server.py --vault /data/gamehack-zero/nimbus-vault
```

It still binds localhost; controller operation uses the native menu, not a required web browser. Browser access from a different computer would require a separately reviewed secure tunnel/deployment.

## SanDisk main-Wi-Fi candidate configuration

After checking the actual interface and local regulatory jurisdiction, generate candidates on this computer:

```sh
python3 fieldkit/wifi_plan.py --interface wlan0 --country DK --output ./private-wifi-plan
```

`wlan0` and `DK` are examples, not detected device values. Enter a new WPA2 password at the hidden prompt. The output directory is mode 0700, files mode 0600; it contains a plaintext AP password, so never publish it. Existing directories are refused. Configuration candidates use WPA2-AES, client isolation, and a separate 192.168.78.0/24 control LAN. DHCP does not advertise a router or DNS server; dnsmasq DNS is disabled. No WEP, WPS, open fallback, forwarding, NAT, startup services, address assignment, or installation is generated.

**These files are inactive, not an AP implementation tested on the SanDisk.** `nl80211` support is an explicit prerequisite; a vendor driver may require a different backend. Before activation, verify recovery, chipset/AP support, installed hostapd/dnsmasq versions, country/channel legality, static addressing, firewall, and secured file/API services. The prototype HTTP server is not that production service.

Once a secured SanDisk AP actually works, use GameHack's existing Wi-Fi menu to join it. Keep the Pi's no-gateway USB link unchanged. The currently observed USB -71 and SD2 controller problems are not fixed by this integration; local vault snapshots do not depend on SD2 mounting.

## Phone-hotspot Internet mode

The target is **phone hotspot → SanDisk Wi-Fi client/uplink → SanDisk AP → GameHack**. Only after verifying concurrent AP+client interface support, generate inactive candidates:

```sh
python3 fieldkit/wifi_plan.py --interface ap0 --uplink wlan0 --country DK --output ./private-wifi-plan
```

`ap0` and `wlan0` are illustrative. The generator does not create virtual interfaces or join the phone hotspot. On a single radio, AP and uplink generally must share a channel; the generated channel must match the verified hotspot channel. Use the phone's 2.4 GHz/compatibility hotspot mode where available, since the drive specs list only 2.4 GHz. The phone hotspot subnet must not overlap 192.168.78.0/24 or the Pi USB subnet.

Gateway mode generates DHCP router/DNS advertisements and an isolated IPv4 NAT/firewall candidate. The nftables file targets a **future modern-kernel port**, not stock Linux 2.6.35. It is not applied and does not flush existing rules. Its input policy is restrictive (AP DHCP/DNS/HTTPS and uplink DHCP); review administration/recovery access before ever loading it. Existing firewall interaction, DNS privacy, forwarding, uplink DHCP/default route, authenticated HTTPS service, and reboot rollback all need validation. No phone SSID/password is collected or stored by the generator. Internet speed and availability depend on the phone signal, carrier tethering policy, battery and radio.

If AP+client concurrency is unavailable, every device can join the phone hotspot directly, but that is **not** SanDisk acting as the main Wi-Fi router. USB phone tethering is another possibility only if SanDisk USB host support is proven; its charging/data connector is not evidence of host support.

Getting the Pi online through GameHack's USB connection requires another reviewed forwarding/route configuration on GameHack and Pi. It is not implemented here: the current Pi link intentionally advertises no gateway, and that existing policy is preserved.

## Source alignment

Read from the existing `GameHack-Zero` project: root README, handheld launcher and Pi client, Pi worker/radio notes, and SD2 diagnostics. Pairing `access/`, card images/backups, credentials, and captures were not read or copied. No radio capabilities are invented: SanDisk does not add NFC, Sub-GHz, IR, or confirmed monitor mode.
