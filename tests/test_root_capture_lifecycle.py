import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture_lifecycle', ROOT / 'scripts/root-capture-lifecycle.py')
# dataclasses requires the module to be registered during exec_module.
import sys
lifecycle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lifecycle
spec.loader.exec_module(lifecycle)
TOKEN = 'a' * 64
DIGEST = 'b' * 64


class LifecycleTests(unittest.TestCase):
    def ready(self, until='streaming'):
        model = lifecycle.CaptureLifecycle(TOKEN)
        for event in ('preflight_pass', 'old_term_requested', 'old_exit_verified',
                      'vendor_term_requested', 'vendor_exit_and_no_writers',
                      'ro_requested', 'ro_verified', 'reader_opened'):
            model.event(event)
            if model.state == until:
                return model
        return model

    def wait_ack(self):
        model = self.ready()
        model.event('stream_verified_readers_closed', bytes=lifecycle.ROOT_BYTES, sha256=DIGEST)
        return model

    def restore(self, model):
        if model.state == 'restore_rw':
            model.event('rw_requested'); model.event('rw_verified')
        if model.state == 'restore_vendor':
            model.event('vendor_start_requested'); model.event('vendor_verified')
        if model.state == 'restore_ssh':
            model.event('ssh_start_requested'); model.event('ssh_verified')
        model.event('final_verified')

    def test_success_requires_ack_and_never_certifies_recovery(self):
        model = self.wait_ack()
        model.event('host_ack', session=TOKEN, sha256=DIGEST)
        self.restore(model)
        self.assertEqual(model.state, 'complete')
        self.assertTrue(model.receipt_flags()['protocol_candidate'])
        for flag in ('filesystem_consistency_verified', 'restore_tested', 'flash_authorized'):
            self.assertFalse(model.receipt_flags()[flag])

    def test_disconnect_and_abort_drain_readers_before_rw(self):
        model = self.ready()
        model.event('abort')
        self.assertEqual(model.state, 'drain')
        with self.assertRaises(ValueError):
            model.event('rw_requested')
        model.event('readers_closed')
        self.restore(model)
        self.assertEqual(model.state, 'failed')

    def test_premature_rw_invalidates_even_if_restoration_later_succeeds(self):
        model = self.ready()
        model.event('root_changed', root='rw')
        self.assertTrue(model.readers_open)
        model.event('readers_closed', root='rw')
        self.assertFalse(model.rw_requested)
        self.restore(model)
        self.assertEqual(model.state, 'failed')

    def test_late_ack_cannot_revive_aborted_attempt(self):
        model = self.wait_ack()
        model.event('abort')
        with self.assertRaises(ValueError):
            model.event('host_ack', session=TOKEN, sha256=DIGEST)
        self.restore(model)
        self.assertFalse(model.receipt_flags()['protocol_candidate'])

    def test_wrong_token_digest_and_short_stream_invalidate(self):
        for facts in ({'session': 'c'*64, 'sha256': DIGEST}, {'session': TOKEN, 'sha256': 'c'*64}):
            model = self.wait_ack()
            model.event('host_ack', **facts)
            self.assertTrue(model.invalid)
            self.assertFalse(model.acknowledged)
        model = self.ready()
        model.event('stream_verified_readers_closed', bytes=1, sha256=DIGEST)
        self.assertEqual(model.state, 'drain')
        self.assertTrue(model.invalid)

    def test_unknown_root_or_lost_fallback_blocks_blind_restoration(self):
        for facts in ({'root': 'unknown'}, {'root': 'ro', 'fallback': False}):
            model = self.wait_ack()
            model.event('abort', **facts)
            self.assertEqual(model.state, 'blocked')
            with self.assertRaises(ValueError):
                model.event('rw_requested')

    def test_lost_fallback_persists_while_readers_are_draining(self):
        model = self.ready()
        model.event('abort', fallback=False)
        self.assertEqual(model.state, 'drain')
        model.event('readers_closed')
        self.assertEqual(model.state, 'blocked')
        self.assertFalse(model.fallback_valid)

    def test_rw_failure_not_retried_but_actual_rw_can_restore_services(self):
        for actual in ('ro', 'rw'):
            model = self.wait_ack()
            model.event('host_ack', session=TOKEN, sha256=DIGEST)
            model.event('rw_requested')
            model.event('abort', root=actual)
            if actual == 'ro':
                self.assertEqual(model.state, 'blocked')
            else:
                self.restore(model)
                self.assertEqual(model.state, 'failed')
            with self.assertRaises(ValueError):
                model.event('rw_requested')

    def test_one_request_each_no_repeat_terms_mounts_or_starts(self):
        model = lifecycle.CaptureLifecycle(TOKEN)
        model.event('preflight_pass'); model.event('old_term_requested')
        with self.assertRaises(ValueError):
            model.event('old_term_requested')
        model.event('old_exit_verified'); model.event('vendor_term_requested')
        with self.assertRaises(ValueError):
            model.event('vendor_term_requested')
        model.event('vendor_exit_and_no_writers'); model.event('ro_requested')
        with self.assertRaises(ValueError):
            model.event('ro_requested')
        model.event('ro_verified'); model.event('reader_opened')
        model.event('stream_verified_readers_closed', bytes=lifecycle.ROOT_BYTES, sha256=DIGEST)
        model.event('host_ack', session=TOKEN, sha256=DIGEST)
        model.event('rw_requested')
        with self.assertRaises(ValueError):
            model.event('rw_requested')
        model.event('rw_verified'); model.event('vendor_start_requested')
        with self.assertRaises(ValueError):
            model.event('vendor_start_requested')
        model.event('vendor_verified'); model.event('ssh_start_requested')
        with self.assertRaises(ValueError):
            model.event('ssh_start_requested')

    def test_vendor_restore_failure_does_not_suppress_ssh_attempt(self):
        model = self.wait_ack()
        model.event('host_ack', session=TOKEN, sha256=DIGEST)
        model.event('rw_requested'); model.event('rw_verified')
        model.event('vendor_start_requested'); model.event('vendor_restore_failed')
        self.assertEqual(model.state, 'restore_ssh')
        model.event('ssh_start_requested'); model.event('ssh_verified'); model.event('final_verified')
        self.assertEqual(model.state, 'failed')

    def test_ro_error_after_state_change_allows_one_recovery_not_success(self):
        model = self.ready(until='request_ro')
        model.event('ro_requested'); model.event('abort', root='ro')
        self.restore(model)
        self.assertEqual(model.state, 'failed')
        self.assertTrue(model.rw_requested)

    def test_no_stream_or_ack_without_verified_ro_and_completed_read(self):
        model = lifecycle.CaptureLifecycle(TOKEN)
        for event, facts in (('reader_opened', {}), ('ro_verified', {}),
                             ('host_ack', {'session': TOKEN, 'sha256': DIGEST})):
            with self.assertRaises(ValueError):
                model.event(event, **facts)
