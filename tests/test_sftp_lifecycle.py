import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sftp_lifecycle',ROOT/'scripts/sftp-service-lifecycle.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)


class SFTPLifecycleTests(unittest.TestCase):
    def running(self):
        lifecycle=model.Lifecycle()
        lifecycle.begin({name:True for name in model.PREREQUISITES})
        lifecycle.listener_ready(identity_bound=True,policy_matches=True,views_readonly=True,usb_inactive=True)
        return lifecycle

    def test_unknown_false_and_truthy_prerequisites_never_start(self):
        for name in model.PREREQUISITES:
            for value in (None,False,1,'yes'):
                with self.subTest(name=name,value=value):
                    lifecycle=model.Lifecycle();facts={key:True for key in model.PREREQUISITES};facts[name]=value
                    with self.assertRaises(ValueError):lifecycle.begin(facts)
                    self.assertEqual(lifecycle.state,'new')

    def test_shutdown_order_requires_listener_then_descendants_then_views(self):
        lifecycle=self.running()
        self.assertEqual(lifecycle.stop(),'stop-only-identity-bound-listener')
        self.assertEqual(lifecycle.listener_stopped(identity_bound=True,absent=True),'cancel-and-drain-all-enrolled-sessions')
        self.assertEqual(lifecycle.sessions_drained(complete_inventory=True,no_live_descendants=True,no_media_handles=True,usb_state='inactive'),
                         'detach-only-exact-reviewed-readonly-views')
        self.assertFalse(lifecycle.receipt()['vendor_transition_reviewable'])
        lifecycle.views_detached(complete_inventory=True,exact_views_absent=True,usb_state='inactive')
        receipt=lifecycle.receipt();self.assertTrue(receipt['shutdown_observed'])
        for flag in ('native_verified','usb_handoff_verified','listener_authorized','production_ready','flash_authorized'):
            self.assertFalse(receipt[flag])

    def test_no_detach_before_listener_or_session_drain(self):
        lifecycle=self.running()
        with self.assertRaises(ValueError):lifecycle.views_detached(complete_inventory=True,exact_views_absent=True,usb_state='inactive')
        lifecycle.stop()
        with self.assertRaises(ValueError):lifecycle.sessions_drained(complete_inventory=True,no_live_descendants=True,no_media_handles=True,usb_state='inactive')

    def test_incomplete_descendants_or_open_handles_prevent_unmount(self):
        for field in ('complete_inventory','no_live_descendants','no_media_handles'):
            lifecycle=self.running();lifecycle.stop();lifecycle.listener_stopped(identity_bound=True,absent=True)
            facts={'complete_inventory':True,'no_live_descendants':True,'no_media_handles':True,'usb_state':'inactive'};facts[field]=False
            self.assertEqual(lifecycle.sessions_drained(**facts),'retain-draining-no-unmount-no-usb-release')
            self.assertEqual(lifecycle.state,'draining');self.assertFalse(lifecycle.receipt()['vendor_transition_reviewable'])

    def test_export_or_unknown_ownership_is_irreversible_even_if_later_inactive(self):
        for state in ('active','unknown',None):
            lifecycle=self.running()
            lifecycle.observe(usb_state=state,views_readonly=True,fallback_verified=True,session_count=1)
            lifecycle.listener_stopped(identity_bound=True,absent=True)
            self.assertEqual(lifecycle.sessions_drained(complete_inventory=True,no_live_descendants=True,no_media_handles=True,usb_state='inactive'),
                             'ownership-lost-preserve-views-for-explicit-review')
            self.assertTrue(lifecycle.receipt()['ownership_lost']);self.assertFalse(lifecycle.receipt()['vendor_transition_reviewable'])

    def test_owner_stop_during_export_drain_cannot_clear_invalidation(self):
        lifecycle=self.running();lifecycle.stop(reason='usb-export',ownership_lost=True)
        self.assertEqual(lifecycle.stop(),'retain-shutdown-in-progress')
        self.assertTrue(lifecycle.invalidated);self.assertTrue(lifecycle.ownership_lost)

    def test_listener_replacement_or_stop_refusal_blocks_all_media_actions(self):
        for field in ('identity_bound','absent'):
            lifecycle=self.running();lifecycle.stop()
            facts={'identity_bound':True,'absent':True};facts[field]=False
            self.assertEqual(lifecycle.listener_stopped(**facts),'refuse-unknown-or-replacement-listener-no-media-action')
            self.assertEqual(lifecycle.state,'blocked')
            with self.assertRaises(ValueError):lifecycle.sessions_drained(complete_inventory=True,no_live_descendants=True,no_media_handles=True,usb_state='inactive')

    def test_view_detach_failure_or_new_export_withholds_usb_release(self):
        for failure in ('inventory','view','export'):
            lifecycle=self.running();lifecycle.stop();lifecycle.listener_stopped(identity_bound=True,absent=True)
            lifecycle.sessions_drained(complete_inventory=True,no_live_descendants=True,no_media_handles=True,usb_state='inactive')
            result=lifecycle.views_detached(complete_inventory=failure!='inventory',exact_views_absent=failure!='view',usb_state='active' if failure=='export' else 'inactive')
            self.assertEqual(result,'detach-unconfirmed-no-usb-release')
            self.assertFalse(lifecycle.receipt()['vendor_transition_reviewable'])

    def test_deadline_extra_sessions_or_lost_fallback_trigger_ordered_stop(self):
        for change in ({'session_count':2},{'session_count':True},{'fallback_verified':False},
                       {'views_readonly':False},{'deadline_expired':True}):
            lifecycle=self.running()
            facts={'usb_state':'inactive','views_readonly':True,'fallback_verified':True,'session_count':1}
            facts.update(change)
            self.assertEqual(lifecycle.observe(**facts),'stop-only-identity-bound-listener')
            self.assertEqual(lifecycle.state,'stopping');self.assertTrue(lifecycle.invalidated)

    def test_finished_or_blocked_attempt_cannot_be_reused(self):
        lifecycle=self.running();lifecycle.stop();lifecycle.listener_stopped(identity_bound=False,absent=False)
        with self.assertRaises(ValueError):lifecycle.begin({name:True for name in model.PREREQUISITES})
        with self.assertRaises(ValueError):lifecycle.stop()
