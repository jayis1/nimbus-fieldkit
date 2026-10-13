# Coordinated GameHack / SanDisk opt-in network lab

Status: architecture proposal, not an installed proxy or interception service.
User-selected scope: passive monitoring only on GameHack's second (MONITOR)
radio. The optional proxy design below is not selected and must remain inactive.
Scope: owner-controlled test clients and destinations with explicit permission.
No client redirection, firmware flash, vendor firewall rewrite or TLS certificate
installation is authorized by this document. Existing private work is preserved.

## Topology

User-confirmed intended path: SanDisk uplink WLAN provides Internet to the
little local network. Existing documentation names uplink wlan1 and local AP
wlan0; revalidate actual interfaces before any future configuration. Retain the
stock forwarding/DHCP/DNS behavior rather than replacing it on GameHack.

```text
Internet / verified hotspot uplink
                 |
       SanDisk stock AP + gateway (192.168.11.1)
                 |
          consented test clients
                 |
       same AP: GameHack INTERNET radio (managed)
                 +-- optional explicit test proxy, OFF by default
       GameHack MONITOR radio: bounded passive observation only
       Pi USB worker: separate 192.168.77.0/24, no gateway/DNS changes
```

Clients normally route through SanDisk, not GameHack. Monitor mode cannot
redirect traffic or insert GameHack into that path. Encrypted Wi-Fi/TLS traffic
does not become readable application content just because frames are captured.

## Two distinct operating modes

1. Passive lab: retain stock routing. GameHack's MONITOR radio observes only the
   authorized channel/BSSID using existing bounded capture. This is not MITM.
2. Explicit proxy lab: a consenting test client explicitly configures a proxy
   on GameHack's INTERNET address. Ordinary non-participating clients keep their
   normal SanDisk path. No ARP/DNS spoofing, DHCP takeover, deauthentication,
   transparent redirect or credential collection is part of this proposal.
   HTTPS uses an opaque CONNECT tunnel; no installed CA or TLS decryption.

Proxy implementation/deployment is gated on selected mode and approved clients,
destinations, duration and data retention. No proxy code/listener added yet.

## Responsibility boundaries

- SanDisk: retain working stock AP/uplink/NAT and media services. Do not add
  monitor mode; no such capability is established. No modern nftables candidate
  may be applied to the legacy stock kernel. No forwarding to management ports.
- GameHack: UI/session owner, managed Internet radio, separate monitor radio,
  local bounded proxy only if explicitly approved, private mounted debug storage.
- Test clients: intentional enrollment, removable proxy configuration and clear
  indication that the test is active. WLAN client isolation may prevent access
  to GameHack; check reachability without silently disabling isolation.
- Phone companion: status/explicit approved controls only through pinned SSH;
  no public unauthenticated control endpoint or proprietary hardware emulation.
- Pi: existing pinned worker, never silently repurposed as gateway/interceptor.

## Implementation contract after scope selection

- Validate saved, distinct INTERNET/MONITOR MAC roles against live identities.
  Do not infer roles from insertion order, device-model ID or DHCP activation.
- Monitor preparation requires explicit consent to disconnect only MONITOR.
  Preserve INTERNET and verify live state after AP selection. Role labels alone
  do not disable NetworkManager autoconnect; this remains a workflow gap.
- Optional proxy binds only the approved managed-LAN address, never 0.0.0.0;
  refuses new/missing identities, destination outside scope and unknown clients.
  Client admission must be authenticated, not solely inferred from source IP.
- Before any listener: review firewall and recovery; no global rules flush,
  saved-network edits, management-interface rebinding or permanent startup.
- Session expires and is manually stoppable; bounded concurrency/storage,
  metadata-minimal logs, no request bodies, auth headers, cookies or secrets.
  Captures remain private, reviewed and deletable; never automatically publish.
- Settings UI shows OFF / PREFLIGHT BLOCKED / READY / ACTIVE / STOPPED / ERROR,
  enrolled scope, duration and stop control. READY is not native success proof.

## Known deployment gates, 2026-10-11

- GameHack roles now save natively, but MONITOR still autoconnects. A capture
  attempt on the connected MONITOR radio returned immediately with no PCAP.
- Dual-radio hub has recovered USB -71/disconnect events. Latest observed boot
  settled afterward; stability under capture/proxy load remains unverified.
- SanDisk README documents pinned custom SSH TCP 2224 bound to uplink wlan1;
  downstream GameHack management pairing/access policy is separately unverified.
- Stock AP Internet transit is recorded in LIVE-TEST-2026-10-11.md. Validate
  current uplink, client-to-GameHack reachability and address reservation anew.
- No live Sandisk login, listener, routing change or deployment performed here.

Coordination copy: the owner's local `OPT-IN-NETWORK-LAB-ARCHITECTURE.md`.
Resolve scope first, then implement/test one bounded mode before deployment.
