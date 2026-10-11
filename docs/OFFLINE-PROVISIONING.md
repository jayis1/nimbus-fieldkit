# Private offline SSH provisioning — development candidate

This addresses the generic image's missing SSH identity without shipping shared private keys. It does **not** establish secure first boot, Wi-Fi onboarding/reset safety, native boot or recovery. No image may leave preview based on this tool alone.

## Model

- One fresh Ed25519 host key per device, generated on a trusted Linux host by a trusted native `dropbearkey` tool. Do not reuse the current installed device's private host key.
- One explicitly selected plain Ed25519 client public key; no client private keys imported, no password fallback, no key options or forced commands accepted.
- Output must live in ignored `.private-provisioning/`, directory 0700, files 0600. A checksum/identity manifest pins both host/client fingerprints. Validation asks Dropbear to read the host key; mode, ownership, symlink, checksum and identity failures block import.
- The provisioned rootfs is a **private per-device artifact containing a private key**. Never attach its image, tar, tree, manifest or provisioning bundle to a public release. Only generic source/overlay artifacts remain publishable.
- Existing settings partition, Wi-Fi credentials and calibration remain external and unchanged. WPA2 defaults alone do not validate existing credentials, reset behavior or management reachability.

## Generate privately

Use a locally built/reviewed Dropbear 2026.94 host key tool or a trusted distribution package. It is a host utility, not the ARM daemon, and is not shipped in the source release.

```sh
python3 scripts/provision-image.py \
  --output .private-provisioning/drive-a \
  --authorized-key /path/to/admin-ed25519.pub \
  --dropbearkey /path/to/trusted/native/dropbearkey \
  --device-id drive-a
```

No output overwrite is permitted. Preserve failed staging for local inspection rather than rerunning blindly. The tool prints fingerprints, not private key material. Generation requires a trustworthy host RNG. Keys are unencrypted for unattended daemon use; host disk encryption and physical control of the drive are required. Filesystem root access can extract its host identity.

## Build privately

Use the documented hash-pinned rootfs/ARM inputs and staged companion prerequisites from `CUSTOM-ROOTFS-CANDIDATE.md`, adding:

```sh
fakeroot python3 scripts/build-custom-image.py \
  --stock-rootfs /path/to/reviewed/rootfs_nimbus_v3.04.tar \
  --ssh-binary /path/to/reviewed/dropbearmulti \
  --provisioning-dir .private-provisioning/drive-a \
  --dropbearkey /path/to/trusted/native/dropbearkey \
  --output .private-provisioning/drive-a-rootfs-candidate
```

Do not run this as host root. No filesystem mounting, block writes, updater wrapping or flashing is performed. The private keys are placed only in `/etc/nimbus`, root-owned 0600 in the rootfs with a 0700 directory. Startup retains the existing wlan1-only, key-only port-2224 policy. The manifest still says `secure_provisioning_verified: false`, because offline file checks do not prove native access/reset behavior.

## Required before hardware deployment

1. Match the intended client's fingerprint and record the newly generated host pin privately.
2. Inspect rootfs tar/image keys, ownership and directory permissions offline; validate image geometry and read-only fsck.
3. Establish and test matching recovery independently before replacing the working rootfs.
4. Validate native boot, authorized login, rejected wrong keys, interface binding and reboot persistence on recoverable hardware.
5. Validate AP/uplink settings and credential/reset handling without publishing device secrets.

Do not reuse a generated per-device image as a generic downloadable firmware release. A public production installer will need a reviewed local personalization/onboarding process and independently established redistribution rights.
