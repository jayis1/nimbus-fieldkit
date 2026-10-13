import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('go_session_model',ROOT/'scripts/wardrive-go-session.py')
go=importlib.util.module_from_spec(spec);sys.modules[spec.name]=go;spec.loader.exec_module(go)
SESSION='a'*32
OWNER='b'*32
UTC=1800000000000


class PocketGoTests(unittest.TestCase):
    def setUp(self):
        self.gates={gate:True for gate in go.GATES}
        self.session=go.PocketSession(SESSION,OWNER,900000,1000,self.gates,True)
        self.session.bind_clock(OWNER,go.ClockBinding(UTC,1000,100),1000)

    def wire(self,**changes):
        data={'schema':go.SCHEMA,'session_id':SESSION,'sequence':1,
              'permission':'granted','fix_status':'fix','provider':'native_gps',
              'acquired_at_ms':UTC,'latitude':12.5,'longitude':-45.25,'accuracy_m':10}
        data.update(changes);return json.dumps(data).encode()

    def ingest(self,now=1100,**changes):self.session.location(OWNER,self.wire(**changes),now)

    def test_all_independent_gates_must_be_verified(self):
        for gate in go.GATES:
            for bad in (False,None,'verified',1):
                with self.subTest(gate=gate,bad=bad),self.assertRaises(go.Refused):
                    go.PocketSession(SESSION,OWNER,1000,1000,{**self.gates,gate:bad},True)
        with self.assertRaises(go.Refused):go.PocketSession(SESSION,OWNER,1000,1000,{},True)

    def test_start_requires_consent_bounded_duration_and_identity(self):
        for duration in (0,999,900001,True,1.5):
            with self.subTest(duration=duration),self.assertRaises(go.Refused):go.PocketSession(SESSION,OWNER,duration,1000,self.gates,True)
        for consent in (False,None,1):
            with self.assertRaises(go.Refused):go.PocketSession(SESSION,OWNER,1000,1000,self.gates,consent)
        with self.assertRaises(go.Refused):go.PocketSession('bad',OWNER,1000,1000,self.gates,True)

    def test_valid_fix_zero_coordinates_and_coordinate_free_status(self):
        self.ingest(latitude=0,longitude=0)
        self.assertEqual(self.session.fix['latitude'],0)
        status=self.session.status(OWNER,1100)
        self.assertEqual(status['location'],'fresh')
        self.assertNotIn('latitude',status);self.assertNotIn('longitude',status)
        self.assertFalse(status['native_verified']);self.assertFalse(status['radio_started'])

    def test_permission_denial_and_revocation_clear_fix_and_cannot_resume_silently(self):
        for permission in ('denied','revoked'):
            self.setUp();self.ingest()
            self.ingest(now=1200,sequence=2,permission=permission,fix_status='unavailable',provider='none',
                        acquired_at_ms=None,latitude=None,longitude=None,accuracy_m=None)
            self.assertIsNone(self.session.fix);self.assertFalse(self.session.consent)
            with self.assertRaises(go.Refused):self.ingest(now=1300,sequence=3,acquired_at_ms=UTC+200)
            with self.assertRaises(go.Refused):self.session.bind_clock(OWNER,go.ClockBinding(UTC+200,1300,100),1300)

    def test_unavailable_and_suspended_do_not_reuse_old_coordinates(self):
        for state in ('unavailable','suspended'):
            self.setUp();self.ingest()
            self.ingest(now=1200,sequence=2,fix_status=state,provider='none',acquired_at_ms=None,
                        latitude=None,longitude=None,accuracy_m=None)
            self.assertIsNone(self.session.fix);self.assertEqual(self.session.location_state,state)

    def test_status_ages_out_fix_without_new_phone_samples(self):
        self.ingest()
        self.assertEqual(self.session.status(OWNER,5900)['location'],'fresh')
        self.assertEqual(self.session.status(OWNER,5901)['location'],'stale')
        self.assertIsNone(self.session.fix)

    def test_stale_future_inaccurate_and_expired_clock_are_unknown(self):
        for now,changes,state in ((7000,{},'stale'),(1100,{'acquired_at_ms':UTC+1000},'clock_mismatch'),
                                 (1100,{'accuracy_m':101},'inaccurate'),(61001,{'acquired_at_ms':UTC+60000},'clock_unqualified')):
            self.setUp();self.ingest(now=now,**changes)
            self.assertIsNone(self.session.fix);self.assertEqual(self.session.location_state,state)

    def test_clock_uncertainty_counts_towards_freshness(self):
        self.session.bind_clock(OWNER,go.ClockBinding(UTC,1000,1000),1000)
        self.ingest(now=5001)
        self.assertEqual(self.session.location_state,'stale')

    def test_unqualified_clock_and_binding_reset_do_not_retag_old_fix(self):
        self.session.clock=None;self.ingest()
        self.assertEqual(self.session.location_state,'clock_unqualified')
        self.session.bind_clock(OWNER,go.ClockBinding(UTC+100,1100,100),1100)
        self.assertIsNone(self.session.fix)
        for uncertainty in (-1,1001,True):
            with self.assertRaises(go.Refused):self.session.bind_clock(OWNER,go.ClockBinding(UTC,1100,uncertainty),1100)

    def test_sequence_and_acquisition_replay_clear_current_fix(self):
        self.ingest()
        with self.assertRaises(go.Refused):self.ingest(now=1200)
        self.assertIsNone(self.session.fix)
        with self.assertRaises(go.Refused):self.ingest(now=1300,sequence=2)
        self.assertIsNone(self.session.fix)

    def test_cross_session_and_wrong_owner_are_refused(self):
        self.ingest()
        with self.assertRaises(go.Refused):self.session.location('c'*32,self.wire(sequence=2),1200)
        self.assertIsNotNone(self.session.fix)  # Wrong peer cannot mutate owner state.
        with self.assertRaises(go.Refused):self.ingest(now=1200,sequence=2,session_id='d'*32)
        self.assertIsNone(self.session.fix)
        for operation in (lambda:self.session.status('c'*32,1300),lambda:self.session.stop('c'*32,1300)):
            with self.assertRaises(go.Refused):operation()

    def test_malformed_messages_clear_fix_without_echoing_private_input(self):
        for wire in (b'',b'x'*1025,b'[]',b'{',b'\xff',b'{"schema":"private","schema":"private"}',
                     self.wire(latitude=float('nan')),self.wire(latitude=10**300),self.wire(latitude=91),
                     self.wire(longitude=-181),self.wire(accuracy_m=-1),self.wire(sequence=True),
                     self.wire(acquired_at_ms=True),self.wire(extra='PRIVATE_FIX'),self.wire(provider='browser_http')):
            self.setUp();self.ingest()
            with self.subTest(length=len(wire)),self.assertRaises(go.Refused) as caught:
                self.session.location(OWNER,wire,1200)
            self.assertNotIn('PRIVATE',str(caught.exception));self.assertIsNone(self.session.fix)

    def test_permission_messages_cannot_smuggle_coordinates(self):
        with self.assertRaises(go.Refused):go.decode_location(self.wire(permission='revoked'))
        with self.assertRaises(go.Refused):go.decode_location(self.wire(fix_status='unavailable'))

    def test_session_expiry_is_not_success_or_restoration(self):
        self.ingest()
        status=self.session.status(OWNER,901000)
        self.assertEqual(status['state'],'stopping');self.assertEqual(status['remaining_ms'],0)
        self.assertIsNone(self.session.fix)
        with self.assertRaises(go.Refused):self.ingest(now=901000,sequence=2,acquired_at_ms=UTC+900000)

    def test_backwards_clock_stops_session(self):
        self.ingest()
        with self.assertRaises(go.Refused):self.session.status(OWNER,1099)
        self.assertEqual(self.session.state,'stopping');self.assertIsNone(self.session.fix)

    def test_stop_is_idempotent_and_completion_requires_drain_and_restoration(self):
        self.ingest();self.session.stop(OWNER,1200);self.session.stop(OWNER,1200)
        self.assertIsNone(self.session.fix);self.assertFalse(self.session.consent)
        self.session.finish(OWNER,1300,True,True)
        self.assertEqual(self.session.state,'complete')
        self.assertFalse(self.session.status(OWNER,1300)['native_verified'])

    def test_failed_drain_or_restoration_never_becomes_complete(self):
        for drained,restored in ((False,True),(True,False),(None,True),(1,True)):
            self.setUp();self.session.stop(OWNER,1100)
            self.session.finish(OWNER,1200,drained,restored)
            self.assertEqual(self.session.state,'restoration_unconfirmed')

    def test_cannot_finish_active_session(self):
        with self.assertRaises(go.Refused):self.session.finish(OWNER,1100,True,True)

    def test_capability_loss_stops_without_fallback_or_radio_action(self):
        self.ingest();self.session.capability_lost(OWNER,1200)
        status=self.session.status(OWNER,1200)
        self.assertEqual(status['state'],'stopping');self.assertFalse(status['radio_started'])
        self.assertFalse(self.session.consent)

    def test_model_representation_never_exposes_fixes_or_identity(self):
        self.ingest()
        for private in (SESSION,OWNER,'12.5','-45.25',str(UTC)):
            self.assertNotIn(private,repr(self.session));self.assertNotIn(private,repr(self.session.clock))

    def test_observation_attribution_does_not_backfill_future_or_stale_fixes(self):
        self.ingest()
        self.assertIsNone(self.session.observation_location(OWNER,999,1100))
        self.assertIsNone(self.session.observation_location(OWNER,1050,1100))
        self.assertIsNone(self.session.observation_location(OWNER,1101,1100))
        self.assertEqual(self.session.observation_location(OWNER,1100,1100)['latitude'],12.5)
        self.assertIsNone(self.session.observation_location(OWNER,6000,6000))

    def test_invalid_clock_rebinding_invalidates_old_binding(self):
        self.ingest()
        with self.assertRaises(go.Refused):self.session.bind_clock(OWNER,go.ClockBinding(UTC,1100,1001),1100)
        self.assertIsNone(self.session.clock);self.assertIsNone(self.session.fix)
        self.ingest(now=1200,sequence=2,acquired_at_ms=UTC+100)
        self.assertEqual(self.session.location_state,'clock_unqualified')


class GoInventorySourceTests(unittest.TestCase):
    def test_collector_has_no_scan_service_or_private_config_command(self):
        text=(ROOT/'device/wardrive-go-capability-preflight.sh').read_text()
        for forbidden in ('iw dev','iwlist wlan','iwconfig wlan','ifconfig ',
                          'modprobe ','insmod ','rmmod ','kill ','killall ',
                          '/etc/shadow','wpa_supplicant.conf','/address','fw_server'):
            self.assertNotIn(forbidden,text)
        self.assertIn('radio_actions=none credential_reads=none',text)
        self.assertIn('scan=unqualified coexistence=unqualified monitor=unqualified',text)


if __name__=='__main__':unittest.main()
