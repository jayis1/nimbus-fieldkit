#!/usr/bin/env python3
"""Prepare an inactive native coordinator from reviewed restoration source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STAGE = '/tmp/nimbus-root-capture-v1'
STREAM_HASH = 'a3bede887069b5542af485988e561ed570427f317714d71742b1a8cf033065dd'
TEMPLATE_HASH = 'ed7b3ce606c5bf43f63d9dd610d0022cbcf8422462c811ab92e49fb14a333cfc'
IDENTITY_HASH = '11025a9fd9a86a3dcc25a7ea64c85a3e44506dda8887b6906781c2285fe6cf60'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Reviewed restoration layout changed; inspect before generation.')
    return text.replace(old, new)


SUPPORT = r'''
capture_pid=''; capture_stamp=''; capture_active=no; capture_completed=no; capture_abnormal=no
capture_binary="$trial_stage/streamer"
capture_hash=a3bede887069b5542af485988e561ed570427f317714d71742b1a8cf033065dd
capture_geometry() {
    [ -b /dev/mmcblk0p2 ] &&
    [ "$(cat /sys/class/block/mmcblk0p2/start)" = 38912 ] &&
    [ "$(cat /sys/class/block/mmcblk0p2/size)" = 524288 ]
}
capture_input() {
    verify_file "$capture_binary" "$capture_hash" &&
    [ "$(stat -c '%a' "$capture_binary")" = 700 ] &&
    verify_file /usr/bin/sha256sum c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2 &&
    [ "$(stat -c '%u:%g:%a:%s' /usr/bin/sha256sum)" = '0:0:755:116878' ] &&
    verify_file /bin/busybox aad1bd291b7a23098b11a0ee6e9f0526a98ba82a84a1e4ae6a933fd74f5d153c
}
capture_child_ok() {
    [ -n "$capture_pid" ] && [ -n "$capture_stamp" ] &&
    process_valid "$capture_pid" "$capture_binary" "$capture_stamp" "$capture_hash"
}
child_drain_ok() {
    capture_drain="$trial_stage/CHILD-DRAIN"
    private_file "$capture_drain" &&
    [ "$(stat -c '%s' "$capture_drain")" = "$(printf 'NIMBUS-CHILD-DRAIN %s reader-closed hasher-drained\n' "$capture_session" | wc -c | tr -d ' ')" ] &&
    [ "$(cat "$capture_drain")" = "NIMBUS-CHILD-DRAIN $capture_session reader-closed hasher-drained" ]
}
no_raw_readers() {
    # Metadata only, never opens block contents. A race is still possible.
    for capture_process in /proc/[0-9]*; do
        [ -d "$capture_process/fd" ] || continue
        for capture_fd in "$capture_process"/fd/[0-9]*; do
            [ -L "$capture_fd" ] && [ -b "$capture_fd" ] || continue
            capture_device=$(stat -L -c '%t:%T' "$capture_fd") || return 1
            [ "$capture_device" != b3:2 ] || return 1
        done
    done
}
drain_capture() {
    [ "$capture_active" = yes ] || {
        [ "$capture_abnormal" = no ] || return 1
        [ -z "$capture_pid" ] || child_drain_ok
        return $?
    }
    # Signal only a freshly matched instance of our own component; no escalation.
    if capture_child_ok; then
        kill -TERM "$capture_pid" || :
    fi
    # wait refers to this shell's child even if /proc raced. Unknown identity is
    # not permission to kill another process or restore before the child ends.
    capture_wait_status=0
    wait "$capture_pid" || capture_wait_status=$?
    capture_active=no
    [ "$capture_wait_status" -le 1 ] && child_drain_ok && no_raw_readers
}
'''


def generate(template):
    if hashlib.sha256(template.encode()).hexdigest() != TEMPLATE_HASH:
        raise ValueError('Restoration template changed; review and repin explicitly.')
    text = replace_once(template, '# Preparation only until separately approved. No capture, force, freeze or reboot.',
                        '# Inactive capture coordinator. Separate live approval required; no force/freeze/reboot.')
    text = replace_once(text, 'trial_stage=/tmp/nimbus-root-restoration-trial-v1', 'trial_stage=' + STAGE)
    text = replace_once(text, '[ "$#" -le 1 ] || fail \'Use --check or --start\'\nmode=${1:---check}\ncase "$mode" in --check|--start|--worker) :;; *) fail \'Use --check or --start\';; esac',
                        '''[ "$#" -le 2 ] || fail 'Use --check; --worker requires separate approved transport'
mode=${1:---check}
case "$mode" in
    --check) [ "$#" -le 1 ] || fail 'No check arguments'; capture_session='';;
    --worker)
        [ "$#" = 2 ] || fail 'Missing session'
        capture_session=$2
        case "$capture_session" in ''|*[!0-9a-f]*) fail 'Invalid session';; esac
        [ "${#capture_session}" = 64 ] || fail 'Invalid session length'
        # Binary/protocol stdout alone uses fd3. All ordinary diagnostics go to stderr.
        exec 3>&1
        exec 1>&2;;
    *) fail 'No launch mode supplied; use --check';;
esac
readonly capture_session''')
    text = replace_once(text, 'private_file started && private_file worker.log && [ ! -e RESULT ] && [ ! -L RESULT ]',
                        'private_file started && [ "$(cat started)" = "$capture_session" ] && private_file worker.log && [ ! -e RESULT ] && [ ! -L RESULT ]')
    start = text.index('if [ "$mode" = --start ]; then\n')
    end = text.index('old_requested=no; vendor_requested=no;', start)
    text = text[:start] + text[end:]
    text = replace_once(text, 'root_rw && replacement_ok && old_ok && vendor_ok && no_children "$trial_old" && no_children "$trial_vendor" && writer_check before || fail \'Identity/children/writers changed; no action\'',
                        SUPPORT + '\nroot_rw && replacement_ok && old_ok && vendor_ok && no_children "$trial_old" && no_children "$trial_vendor" && writer_check before && capture_geometry && capture_input || fail \'Identity/children/writers/capture inputs changed; no action\'')
    text = replace_once(text, '    recovered=yes\n    if restore_rw && root_rw && usb_tmp_safe && replacement_ok; then',
                         '    recovered=yes\n    if drain_capture && no_raw_readers && restore_rw && root_rw && usb_tmp_safe && replacement_ok; then')
    text = replace_once(text, '    trap - EXIT HUP INT TERM',
                        "    trap - EXIT\n    trap '' HUP INT TERM  # Never interrupt already-running checked cleanup")
    # Do not leak cleanup's ignored TERM/INT into the restored services.
    text = replace_once(text, '    sh "$service" start </dev/null >/dev/null 2>&1 &',
                        '    (trap - HUP INT TERM; exec sh "$service" start) </dev/null >/dev/null 2>&1 &')
    text = replace_once(text, '    nohup setsid sh "$launcher" </dev/null >>"$base/boot.log" 2>&1 &',
                        '    (trap - HUP INT TERM; exec nohup setsid sh "$launcher") </dev/null >>"$base/boot.log" 2>&1 &')
    text = replace_once(text, "trap 'exit 1' HUP INT TERM",
                        "trap 'finish_result=FAIL; capture_completed=no; exit 1' HUP INT TERM")
    text = replace_once(text, '    (set -C; printf \'%s\\n\' "$finish_result" > "$trial_stage/RESULT") || :',
                        '''    (set -C; printf '%s %s\\n' "$capture_session" "$finish_result" > "$trial_stage/RESULT") || {
        finish_result=FAIL
        echo 'Private result recording failed; capture success withheld'
    }
    if [ "$finish_result" = PASS ] && [ "$capture_completed" = yes ]; then
        printf 'NIMBUS-ROOT-RESULT %s ro-until-ack rw-restored ssh-restored vendor-restored\\n' "$capture_session" >&3
    fi
    [ "$finish_result" = PASS ] || exit 1''')
    text = replace_once(text, "echo 'Requesting one non-forced read-only remount; no capture'",
                        "echo 'Requesting one non-forced read-only remount for separately approved capture'")
    text = replace_once(text, "echo 'Expected root read-only configuration observed; restoring immediately'", r'''echo 'Expected root ro observed; stream component waits for host readback ACK'
capture_geometry && capture_input && usb_tmp_safe && no_raw_readers || fail 'Capture preconditions changed'
set -C
exec 4> "$trial_stage/CHILD-DRAIN"
set +C
"$capture_binary" --stream-evidence "$capture_session" <&0 >&3 4>&4 &
capture_pid=$!
capture_active=yes
exec 4>&-
capture_stamp=$(start_time "$capture_pid" 2>/dev/null || :)
capture_status=0
wait "$capture_pid" || capture_status=$?
capture_active=no
if [ "$capture_status" -gt 1 ]; then capture_abnormal=yes; fi
[ "$capture_status" = 0 ] && child_drain_ok && no_raw_readers || fail 'Capture/ACK/reader completion failed'
root_state && [ "$state" = ro ] && usb_tmp_safe && replacement_ok || fail 'Read-only epoch/fallback not observed after ACK'
capture_completed=yes''')
    text = replace_once(text, "echo 'Root restoration process/state trial completed; fresh pinned login/browser checks still required'",
                        "echo 'Capture protocol/restoration observed; offline fsck and fresh pinned service checks still required'")
    return text


def prepare(component_dir, output):
    component_dir = Path(component_dir).absolute()
    output = Path(output).absolute()
    for path in (component_dir, output):
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError('Symlink input/output paths refused.')
    if any(parent in (Path('/dev'), Path('/proc'), Path('/sys')) for parent in output.parents):
        raise ValueError('Pseudo-filesystem output refused.')
    binary = component_dir / 'root-capture-stream.arm'
    if binary.is_symlink() or not binary.is_file() or binary.stat().st_size > 1048576:
        raise ValueError('Expected bounded regular ARM component.')
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != STREAM_HASH:
        raise ValueError('Pinned component mismatch.')
    template = (ROOT / 'device/root-restoration-trial.sh').read_text()
    worker = generate(template).encode()
    identity = (ROOT / 'device/handover-identity-preflight.sh').read_bytes()
    if hashlib.sha256(identity).hexdigest() != IDENTITY_HASH:
        raise ValueError('Identity source changed; review and repin explicitly.')
    output.mkdir(mode=0o700)
    files = {'worker.sh': worker, 'identity.sh': identity, 'streamer': data}
    for name, payload in files.items():
        with (output / name).open('xb') as stream:
            (output / name).chmod(0o600)
            stream.write(payload)
    for name in ('worker.sh', 'identity.sh'):
        subprocess.run(['sh', '-n', str(output / name)], check=True, capture_output=True)
    sums = {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()}
    (output / 'SHA256SUMS').write_text(''.join(digest + '  ' + name + '\n' for name, digest in sorted(sums.items())))
    manifest = {'schema': 'nimbus-root-capture-coordinator/v1',
                'template_sha256': hashlib.sha256(template.encode()).hexdigest(),
                'identity_sha256': IDENTITY_HASH,
                'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'stage': STAGE, 'files': sums, 'hardware_validated': False,
                'installable': False, 'flash_authorized': False,
                'limitations': ['Inactive coordinator only; reviewed transport/launcher not supplied.',
                                'Native remount/capture/child-drain failures and autonomous actors unqualified.',
                                'No guarantee against kernel IO stalls, SIGKILL or power loss.']}
    (output / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'NOT-RUN-ON-DEVICE.txt').write_text('Offline coordinator prototype. No deployment or live capture approval. Do not manually start it.\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        prepare(args.component_directory, args.output)
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.error('Offline preparation failed; retain evidence. No device changed.')
    print('Inactive capture coordinator prepared; transport/native gates remain pending.')
