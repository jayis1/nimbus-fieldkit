# Native ON/OFF feature settings — v0.3

No monitor mode. No radio/firmware/system-service changes. All feature settings default **OFF** and persist as strictly validated plain files in `.settings` beside the installed scripts, on user-selected writable storage. Config files are never evaluated as shell code.

## Controller-independent native settings

From the new native installation directory:

```sh
sh nimbus-agent.sh settings menu
sh nimbus-agent.sh settings show
sh nimbus-agent.sh settings set network_health on
sh nimbus-agent.sh settings set watchdog on
sh nimbus-agent.sh settings run network_health
sh nimbus-agent.sh settings run watchdog 12 10
```

The numbered menu toggles each feature ON/OFF and explains missing dependencies. A toggle grants permission for our feature's explicit `run` command; it does **not** start a daemon, change Wi-Fi, install dependencies, create a network listener, mount media or execute arbitrary tasks. Basic agent inventory/help remain read-only maintenance functions outside these optional switches.

OFF blocks new actions. Already-running finite copies/speed tests finish rather than being killed mid-write; the watchdog is the exception and checks OFF continuously between reports. No feature silently restarts after reboot.

Watchdog runs in the foreground, max 120 samples, interval 5–300 seconds. Default is 12 checks every 10 seconds. It reports local interfaces/routes and optionally storage; it is **not a test proving phone Internet availability** and never reconnects or resets radios. Ctrl+C stops it. In another authorized session, switching watchdog OFF stops it within about one second between reports. Switching network_health OFF also switches watchdog OFF. No PID-based kill or vendor-service shutdown is used.

## Switches and actual behavior

| Switch | Enabled behavior | Dependency/boundary |
| --- | --- | --- |
| `network_health` | Read routes and interface counters | No active scan, no Internet-success claim |
| `watchdog` | Bounded foreground repeated reports | Requires network_health ON |
| `speed_tests` | Explicit 10-second iperf client | Requires iperf/iperf3 and an authorized numeric IP; no server is started |
| `backup_vault` | Copy one selected file into local vault and verify SHA-256 | Max 64 MiB; no overwrite; no recursive or automatic backup |
| `offline_toolbox` | List/read bundled docs | Requires bundled docs directory |
| `storage_alerts` | Read free space; warn below 64 MiB | Requires df/awk; no cleanup or file deletion |
| `file_sync` | Explicit single-file copy into existing local/mounted directory | No insecure FTP/SFTP automation or mounts; verify SHA-256 |
| `pi_jobs` | Native ON refused until secure pairing exists | Existing GameHack pinned Pi queue controls remain separate |
| `local_git` | Create a new named bare local repository | Requires git; no network fetch, hook execution or existing-repo overwrite |
| `encrypted_archives` | Store a pre-encrypted .age/.gpg file with checksum | Does not encrypt or verify ciphertext; encrypt/authenticate on GameHack |

Unsupported switches are shown but enabling them is refused. OFF is always allowed. Dependencies are rechecked at execution. None of these switches control the stock SanDisk AP, NAT, FTP, Telnet or SSH daemons. A user-level settings file is not a security boundary against someone with direct shell/storage access. FAT/exFAT does not enforce ordinary POSIX permissions in the same way as a Linux filesystem.

## Manual examples

```sh
sh nimbus-agent.sh settings set storage_alerts on
sh nimbus-agent.sh settings run storage_alerts
sh nimbus-agent.sh settings set offline_toolbox on
sh nimbus-agent.sh settings run offline_toolbox TOGGLES.md
sh nimbus-agent.sh settings set backup_vault on
sh nimbus-agent.sh settings run backup_vault /path/to/reviewed-report.txt
sh nimbus-agent.sh settings set file_sync on
sh nimbus-agent.sh settings run file_sync /path/to/reviewed-report.txt /existing/mounted/directory
sh nimbus-agent.sh settings set watchdog off
```

Copies require simple basenames (letters/digits/dot/underscore/hyphen), refuse source/destination symlinks and existing outputs, and checksum both input/output. A interrupted or failed copy can leave a partial **new** file; inspect it manually rather than treating it as a successful backup. Do not include passwords, keys or private captures accidentally.

This update is installed in a fresh v0.3 directory after archive checksum verification; it does not overwrite the working v0.2 installation. No boot/autostart integration is included. Persisting ON across reboot does not automatically execute a feature.
