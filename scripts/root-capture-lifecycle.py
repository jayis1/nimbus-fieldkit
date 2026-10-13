#!/usr/bin/env python3
"""Executable offline lifecycle model, not a device coordinator or launcher."""
from dataclasses import dataclass
import re

ROOT_BYTES = 268435456


@dataclass
class CaptureLifecycle:
    session: str
    state: str = 'preflight'
    invalid: bool = False
    old_requested: bool = False
    vendor_requested: bool = False
    ro_requested: bool = False
    rw_requested: bool = False
    readers_open: bool = False
    source_digest: str = ''
    acknowledged: bool = False
    root: str = 'rw'
    vendor_start_requested: bool = False
    ssh_start_requested: bool = False
    failed: bool = False
    fallback_valid: bool = True

    def __post_init__(self):
        if not isinstance(self.session, str) or not re.fullmatch('[a-f0-9]{64}', self.session):
            raise ValueError('Expected a fresh controller-generated session token.')

    def next_action(self):
        # Returned labels are model decisions, never shell commands or execution.
        return {
            'preflight': 'verify_fresh_dependencies_and_identities',
            'stop_old': 'request_one_fresh_old_listener_term',
            'stop_vendor': 'request_one_fresh_vendor_term',
            'request_ro': 'request_one_nonforced_ro',
            'read': 'open_exact_partition_readonly',
            'streaming': 'stream_and_monitor_epoch',
            'wait_ack': 'wait_for_exact_host_readback_ack',
            'drain': 'stop_and_observe_all_owned_capture_children',
            'restore_rw': 'request_one_guarded_explicit_rw',
            'restore_vendor': 'restore_interrupted_vendor_once_if_absent',
            'restore_ssh': 'restore_interrupted_ssh_once_if_absent',
            'verify': 'verify_original_rw_and_services_and_fallback',
            'complete': 'report_protocol_candidate_not_certified',
            'failed': 'retain_evidence_no_success',
            'blocked': 'retain_fallback_no_blind_action',
        }[self.state]

    def abort(self, root=None, fallback=None):
        self.invalid = True
        if fallback is not None:
            if not isinstance(fallback, bool):
                raise ValueError('Fallback observation must be boolean.')
            self.fallback_valid = fallback
        if root is not None:
            if root not in ('rw', 'ro', 'unknown'):
                raise ValueError('Unsupported observed root state.')
            self.root = root
        if self.readers_open:
            self.state = 'drain'
        elif not self.fallback_valid or self.root == 'unknown':
            self.state = 'blocked'
        elif self.root == 'ro':
            self.state = 'restore_rw' if self.ro_requested and not self.rw_requested else 'blocked'
        else:
            self.state = 'restore_vendor' if self.vendor_requested else 'restore_ssh' if self.old_requested else 'failed'

    def event(self, name, **facts):
        if self.state in ('complete', 'failed', 'blocked'):
            raise ValueError('Terminal attempt cannot be resumed or reused.')
        if name == 'abort':
            self.abort(**facts)
            return
        if name == 'root_changed':
            self.abort(root=facts['root'], fallback=facts.get('fallback'))
            return
        if name == 'preflight_pass' and self.state == 'preflight':
            self.state = 'stop_old'
        elif name == 'old_term_requested' and self.state == 'stop_old' and not self.old_requested:
            self.old_requested = True
        elif name == 'old_exit_verified' and self.state == 'stop_old' and self.old_requested:
            self.state = 'stop_vendor'
        elif name == 'vendor_term_requested' and self.state == 'stop_vendor' and not self.vendor_requested:
            self.vendor_requested = True
        elif name == 'vendor_exit_and_no_writers' and self.state == 'stop_vendor' and self.vendor_requested:
            self.state = 'request_ro'
        elif name == 'ro_requested' and self.state == 'request_ro' and not self.ro_requested:
            self.ro_requested = True
        elif name == 'ro_verified' and self.state == 'request_ro' and self.ro_requested:
            self.root = 'ro'
            self.state = 'read'
        elif name == 'reader_opened' and self.state == 'read' and self.root == 'ro':
            self.readers_open = True
            self.state = 'streaming'
        elif name == 'stream_verified_readers_closed' and self.state == 'streaming':
            digest = facts.get('sha256')
            if facts.get('bytes') != ROOT_BYTES or not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
                self.abort()
                return
            self.readers_open = False
            self.source_digest = digest
            self.state = 'wait_ack'
        elif name == 'host_ack' and self.state == 'wait_ack':
            if self.invalid or self.root != 'ro' or facts.get('session') != self.session or facts.get('sha256') != self.source_digest:
                self.abort()
                return
            self.acknowledged = True
            self.state = 'restore_rw'
        elif name == 'readers_closed' and self.state == 'drain':
            self.readers_open = False
            self.abort(root=facts.get('root', self.root), fallback=facts.get('fallback'))
        elif name == 'rw_requested' and self.state == 'restore_rw' and self.root == 'ro' and not self.readers_open and not self.rw_requested:
            self.rw_requested = True
        elif name == 'rw_verified' and self.state == 'restore_rw' and self.rw_requested:
            self.root = 'rw'
            self.state = 'restore_vendor'
        elif name == 'vendor_start_requested' and self.state == 'restore_vendor' and self.root == 'rw' and self.vendor_requested and not self.vendor_start_requested:
            self.vendor_start_requested = True
        elif name in ('vendor_verified', 'vendor_restore_failed') and self.state == 'restore_vendor' and self.root == 'rw':
            if name == 'vendor_restore_failed':
                self.invalid = True
                self.failed = True
            self.state = 'restore_ssh'  # SSH recovery is independent of vendor outcome.
        elif name == 'ssh_start_requested' and self.state == 'restore_ssh' and self.root == 'rw' and self.old_requested and not self.ssh_start_requested:
            self.ssh_start_requested = True
        elif name in ('ssh_verified', 'ssh_restore_failed') and self.state == 'restore_ssh' and self.root == 'rw':
            if name == 'ssh_restore_failed':
                self.invalid = True
                self.failed = True
            self.state = 'verify'
        elif name == 'final_verified' and self.state == 'verify' and self.root == 'rw' and not self.readers_open:
            self.state = 'complete' if not self.invalid and self.acknowledged and not self.failed else 'failed'
        else:
            raise ValueError('Unexpected/out-of-order lifecycle event.')

    def receipt_flags(self):
        return {'protocol_candidate': self.state == 'complete',
                'attempt_invalidated': self.invalid,
                'filesystem_consistency_verified': False,
                'restore_tested': False, 'flash_authorized': False}


if __name__ == '__main__':
    raise SystemExit('Offline lifecycle model only. No device actions or live capture supplied.')
