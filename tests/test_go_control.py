import base64
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('go_control',ROOT/'scripts/wardrive-go-control.py')
control=importlib.util.module_from_spec(spec);sys.modules[spec.name]=control;spec.loader.exec_module(control)


def key(seed):
    # Structural public-key fixture, not a cryptographic possession test.
    raw=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32)+bytes([seed])*32
    return 'ssh-ed25519 '+base64.b64encode(raw).decode()+'\n'


def framed(data):return len(data).to_bytes(4,'big')+data


class GoControlTests(unittest.TestCase):
    def setUp(self):
        self.registry=control.Registry([key(1),key(2)])
        self.pin=self.registry.enroll(key(3),True)
        self.evidence=control.TransportEvidence(self.pin,'a'*32,True,True)
        self.gates={name:True for name in control.session_model.GATES}
        self.channel=self.registry.open_channel(self.evidence,1000,self.gates)
        self.counter=0

    def wire(self,op,body=None,**changes):
        self.counter+=1
        data={'schema':control.SCHEMA,'channel_id':self.channel.channel_id,'request_id':self.counter,
              'operation':op,'body':{} if body is None else body}
        data.update(changes);return framed(json.dumps(data,separators=(',',':')).encode())

    def send(self,op,body=None,now=1000,**changes):
        return self.channel.feed(self.wire(op,body,**changes),now)[0]

    def start(self):
        return self.send('start',{'duration_ms':900000,'consent':True,'tier':'pocket','location_mode':'foreground'})

    def bind_clock(self):
        reply=self.send('clock_begin',now=1000)
        return self.send('clock_reply',{'nonce':reply['nonce'],'phone_utc_ms':1800000000000},now=1100)

    def location(self):
        sample={'schema':control.session_model.SCHEMA,'session_id':self.channel.session.session_id,
                'sequence':1,'permission':'granted','fix_status':'fix','provider':'native_gps',
                'acquired_at_ms':1800000000100,'latitude':12.5,'longitude':-45.25,'accuracy_m':10}
        return self.send('location',{'sample':sample},now=1200)

    def test_management_file_and_duplicate_keys_cannot_enroll_for_go(self):
        for public in (key(1),key(2),key(3)):
            with self.assertRaises(control.Refused):self.registry.enroll(public,True)
        with self.assertRaises(control.Refused):self.registry.enroll(key(4),False)

    def test_key_shape_options_and_private_material_refused(self):
        for public in ('PRIVATE KEY','command="sh" '+key(4),key(4)+key(5)):
            with self.assertRaises(control.Refused) as caught:self.registry.enroll(public,True)
            self.assertNotIn('PRIVATE',str(caught.exception))

    def test_registry_bound_and_distinct_identity_requirement(self):
        for seed in range(4,11):self.registry.enroll(key(seed),True)
        with self.assertRaises(control.Refused):self.registry.enroll(key(11),True)
        with self.assertRaises(control.Refused):control.Registry([key(1),key(1)])

    def test_verified_transport_cannot_be_replaced_by_wire_dictionary(self):
        with self.assertRaises(control.Refused):self.registry.open_channel({'client_proof_verified':True},1000,self.gates)
        for evidence in (control.TransportEvidence(self.pin,'a'*32,False,True),
                         control.TransportEvidence(self.pin,'a'*32,True,False),
                         control.TransportEvidence('unknown','a'*32,True,True)):
            with self.assertRaises(control.Refused):self.registry.open_channel(evidence,1000,self.gates)

    def test_one_channel_per_enrolled_identity(self):
        with self.assertRaises(control.Refused):self.registry.open_channel(self.evidence,1000,self.gates)
        old=self.channel.channel_id;self.channel.close(1000)
        newer=self.registry.open_channel(self.evidence,1000,self.gates)
        self.assertNotEqual(newer.channel_id,old)

    def test_foreground_pocket_start_and_status_do_not_start_a_radio(self):
        response=self.start();self.assertFalse(response['native_verified'])
        status=self.send('status');self.assertFalse(status['radio_started']);self.assertFalse(status['records_persisted'])
        self.assertEqual(status['state'],'active')

    def test_start_scope_background_or_wire_capability_override_refuses(self):
        for changed in ({'tier':'pi-b'},{'location_mode':'background'},{'consent':False},{'scan_qualified':True}):
            self.setUp()
            body={'duration_ms':1000,'consent':True,'tier':'pocket','location_mode':'foreground'};body.update(changed)
            with self.assertRaises(control.Refused):self.send('start',body)
            self.assertTrue(self.channel.closed)

    def test_server_gates_cannot_be_overridden_by_client(self):
        self.channel.gates['scan_qualified']=False
        with self.assertRaises(control.Refused):self.start()
        self.assertIsNone(self.channel.session)

    def test_request_replay_and_cross_channel_close_and_clear_fix(self):
        for changes in ({'request_id':1},{'channel_id':'b'*32}):
            self.setUp();self.start();self.bind_clock();self.location()
            with self.assertRaises(control.Refused):self.send('status',now=1300,**changes)
            self.assertTrue(self.channel.closed);self.assertIsNone(self.channel.session.fix)
            self.assertEqual(self.channel.session.state,'stopping')

    def test_revocation_stops_session_without_waiting_for_next_location(self):
        self.start();self.bind_clock();self.location()
        self.registry.revoke(self.pin,1300,True)
        self.assertTrue(self.channel.closed);self.assertIsNone(self.channel.session.fix)
        with self.assertRaises(control.Refused):self.registry.open_channel(self.evidence,1400,self.gates)

    def test_revocation_requires_explicit_owner_approval(self):
        with self.assertRaises(control.Refused):self.registry.revoke(self.pin,1000,False)
        self.assertFalse(self.channel.closed)

    def test_clock_exchange_uncertainty_and_private_location_flow(self):
        self.start();response=self.bind_clock()
        self.assertEqual(response['uncertainty_ms'],100)
        status=self.location();self.assertEqual(status['location'],'fresh')
        self.assertNotIn('latitude',status);self.assertNotIn('longitude',status)
        self.assertEqual(self.channel.session.clock.server_mono_ms,1050)

    def test_clock_nonce_replay_expiry_and_mismatch_refuse(self):
        for mode in ('replay','expired','mismatch'):
            self.setUp();self.start();response=self.send('clock_begin')
            body={'nonce':response['nonce'],'phone_utc_ms':1800000000000}
            if mode=='replay':self.send('clock_reply',body,now=1100)
            if mode=='mismatch':body['nonce']='f'*32
            with self.assertRaises(control.Refused):self.send('clock_reply',body,now=3000 if mode=='expired' else 1200)
            self.assertIsNone(self.channel.session.clock);self.assertTrue(self.channel.closed)

    def test_phone_clock_discontinuity_is_not_silently_rebound(self):
        self.start();self.bind_clock();self.location()
        response=self.send('clock_begin',now=2100)
        self.assertIsNone(self.channel.session.fix)
        with self.assertRaises(control.Refused):self.send('clock_reply',{'nonce':response['nonce'],'phone_utc_ms':1800000000000},now=2200)
        self.assertTrue(self.channel.closed)

    def test_phone_clock_continuity_can_refresh_binding(self):
        self.start();self.bind_clock()
        response=self.send('clock_begin',now=2100)
        result=self.send('clock_reply',{'nonce':response['nonce'],'phone_utc_ms':1800000001100},now=2200)
        self.assertTrue(result['clock_bound']);self.assertIsNone(self.channel.session.fix)

    def test_control_eof_truncation_and_backward_clock_stop_model(self):
        for mode in ('eof','truncated','clock'):
            self.setUp();self.start()
            if mode=='eof':self.channel.eof(1100)
            elif mode=='truncated':
                self.channel.feed(b'\0',1100)
                with self.assertRaises(control.Refused):self.channel.eof(1200)
            else:
                with self.assertRaises(control.Refused):self.send('status',now=999)
            self.assertTrue(self.channel.closed);self.assertEqual(self.channel.session.state,'stopping')

    def test_unknown_command_duplicate_keys_and_auth_claims_refuse(self):
        for wire in (b'{"schema":"PRIVATE","schema":"PRIVATE"}',b'[]',b'{',
                     json.dumps({'schema':control.SCHEMA,'channel_id':'a'*32,'request_id':1,
                                 'operation':'status','body':{},'authenticated':True}).encode()):
            self.setUp();self.start()
            with self.assertRaises(control.Refused) as caught:self.channel.feed(framed(wire),1100)
            self.assertNotIn('PRIVATE',str(caught.exception));self.assertTrue(self.channel.closed)
        self.setUp();self.start()
        with self.assertRaises(control.Refused):self.send('shell',{'command':'PRIVATE'})

    def test_fragmented_requests_and_no_payload_debug_representation(self):
        wire=self.wire('start',{'duration_ms':1000,'consent':True,'tier':'pocket','location_mode':'foreground'})
        self.assertEqual(self.channel.feed(wire[:7],1000),[])
        self.assertEqual(len(self.channel.feed(wire[7:],1000)),1)
        for value in (self.channel,self.channel.frames,self.registry,self.evidence):
            self.assertNotIn(self.pin,repr(value));self.assertNotIn(self.channel.channel_id,repr(value))

    def test_overflowing_json_exponent_closes_channel_and_clears_prior_fix(self):
        self.start();self.bind_clock();self.location()
        wire=self.wire('location',{'sample':{'latitude':0.5}}).replace(b'0.5',b'1e309')
        # Replacement changes the body length; supply a newly framed payload.
        with self.assertRaises(control.Refused):self.channel.feed(framed(wire[4:]),1300)
        self.assertTrue(self.channel.closed);self.assertIsNone(self.channel.session.fix)


class FrameTests(unittest.TestCase):
    def test_length_chunk_and_batch_bounds(self):
        for data in (b'\0\0\0\0',(2049).to_bytes(4,'big'),b'x'*2053,framed(b'x')*9):
            parser=control.Frames()
            with self.assertRaises(control.Refused):parser.feed(data)
            self.assertTrue(parser.failed);self.assertFalse(parser.pending)

    def test_fragmentation_coalescing_and_maximum_frame(self):
        parser=control.Frames();data=framed(b'x'*2048)
        self.assertEqual(parser.feed(data[:1000]),[])
        self.assertEqual(parser.feed(data[1000:]),[b'x'*2048]);parser.finish()
        self.assertEqual(parser.feed(framed(b'a')+framed(b'b')),[b'a',b'b'])

    def test_direct_decoder_bounds_and_nonfinite_numbers(self):
        for data in (b'x'*2049,'not bytes',b'{"value":NaN}'):
            with self.assertRaises(control.Refused):control.decode(data)
