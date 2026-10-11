# v0.6 enhancement candidate delivery

2026-10-11: user reported successful v0.5 installation; read-only HTTP homepage hash subsequently matched the shipped v0.5 page exactly.

v0.6 adds global theme control, keyboard/search navigation, security-readiness guidance, hidden-view polling pause and load-retry handling. See `UNIFIED-ENHANCEMENTS.md` and `SECURITY-PLAN.md`.

Regression suite passed 70 tests. The targeted browser suite then passed against the generated **v0.6** page/assets served locally with device APIs unavailable. This checks interface behavior, not live media playback, SSH configuration or Wi-Fi security.

Archive: `build/nimbus-unified-v06.tar`.

SHA-256: `869a61cf3bbb1c6170efb2a32e9d6cd63537fd7b779a324d43f8b7f3469cfdfd`.

Uploaded to a previously unused filename via normal stock upload API and verified by HTTP readback:

`/mnt/storage/Scotti Upload/nimbus-unified-v06-c8f8f2c6c61f.tar`.

Candidate only, not installed by the agent. Stage into a new `/mnt/storage/nimbus-unified-v06` directory after archive verification and explicitly run `sh install.sh install` in the authorized root session. Installer checks the exact current v0.5 homepage, stores it for rollback and adds versioned v0.6 assets. `sh install.sh rollback` restores v0.5.

Native v0.5 runtime/settings/vault/publisher are retained unchanged. No root session was opened by the agent; no Telnet/SSH/Wi-Fi/firewall/firmware changes were performed. Security hardening is a subsequent gated task, not part of the UI installer.
