#!/usr/bin/env python3
"""Host executable specification for enrolled GO control/framing/clock exchange.

No TLS/SSH implementation, listener, native account, radio or storage writer.
Transport evidence is supplied by a future reviewed adapter, NEVER wire JSON.
Fixture evidence is not proof of authentication or native support.
"""
from dataclasses import dataclass
import importlib.util
import json
import math
from pathlib import Path
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('go_control_session',ROOT/'scripts/wardrive-go-session.py')
session_model=importlib.util.module_from_spec(spec);sys.modules[spec.name]=session_model;spec.loader.exec_module(session_model)
spec=importlib.util.spec_from_file_location('go_control_key_policy',ROOT/'scripts/sftp-confinement.py')
key_policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(key_policy)
MAX_FRAME=2048
MAX_REQUESTS=4096
MAX_CLIENTS=8
MAX_CLOCK_RTT_MS=1900
CLOCK_MARGIN_MS=50
SCHEMA='nimbus-go-control/v1'


class Refused(ValueError):pass


def decode(data):
    if not isinstance(data,bytes) or not 1<=len(data)<=MAX_FRAME:raise Refused('Control frame refused')
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise Refused('Control frame refused')
            value[key]=item
        return value
    def nonfinite(_):raise Refused('Control frame refused')
    def finite_float(text):
        value=float(text)
        if not math.isfinite(value):raise Refused('Control frame refused')
        return value
    try:
        value=json.loads(data.decode('utf-8'),object_pairs_hook=unique,parse_constant=nonfinite,parse_float=finite_float)
    except (UnicodeError,ValueError,RecursionError):raise Refused('Control frame refused') from None
    if not isinstance(value,dict) or set(value)!={'schema','channel_id','request_id','operation','body'}:
        raise Refused('Control frame refused')
    if value['schema']!=SCHEMA or not session_model.identifier(value['channel_id']) or not session_model.integer(value['request_id'],1,MAX_REQUESTS):
        raise Refused('Control frame refused')
    if not isinstance(value['operation'],str) or not isinstance(value['body'],dict):raise Refused('Control frame refused')
    return value


class Frames:
    def __init__(self):self.pending=bytearray();self.failed=False
    def __repr__(self):return '<GO frames private; payload redacted>'

    def feed(self,data):
        if self.failed or not isinstance(data,bytes) or len(data)>MAX_FRAME+4:
            self.failed=True;self.pending.clear();raise Refused('Control framing refused')
        output=[]
        # Consume incrementally: an unfinished maximum-size frame plus a new
        # chunk never requires an unbounded persistent buffer.
        for byte in data:
            self.pending.append(byte)
            if len(self.pending)<4:continue
            length=int.from_bytes(self.pending[:4],'big')
            if not 1<=length<=MAX_FRAME:
                self.failed=True;self.pending.clear();raise Refused('Control framing refused')
            if len(self.pending)==4+length:
                if len(output)>=8:
                    self.failed=True;self.pending.clear();raise Refused('Control framing refused')
                output.append(bytes(self.pending[4:]));self.pending.clear()
        return output

    def finish(self):
        if self.failed or self.pending:
            self.failed=True;self.pending.clear();raise Refused('Truncated control framing')


@dataclass(frozen=True,repr=False)
class TransportEvidence:
    # Out-of-band verified context supplied by SSH/TLS adapter; this class
    # performs no cryptography and is not a certificate/key-possession proof.
    client_fingerprint:str
    transport_binding:str
    server_pin_verified:bool
    client_proof_verified:bool


class Registry:
    def __init__(self,blocked_public_keys):
        if not isinstance(blocked_public_keys,(tuple,list)) or not 2<=len(blocked_public_keys)<=16:
            raise Refused('Distinct management and file identities required')
        self.blocked=set()
        for key in blocked_public_keys:
            try:_,pin=key_policy.public_key(key)
            except ValueError:raise Refused('Enrollment identity refused') from None
            self.blocked.add(pin)
        if len(self.blocked)<2:raise Refused('Distinct management and file identities required')
        self.clients={};self.channels={}

    def __repr__(self):return '<GO registry private; identities redacted>'

    def enroll(self,public_key,explicit_approval):
        if explicit_approval is not True or len(self.clients)>=MAX_CLIENTS:raise Refused('Enrollment refused')
        try:_,pin=key_policy.public_key(public_key)
        except ValueError:raise Refused('Enrollment identity refused') from None
        if pin in self.blocked or pin in self.clients:raise Refused('Dedicated GO identity required')
        principal=secrets.token_hex(16)
        self.clients[pin]={'principal':principal,'revoked':False}
        return pin

    def open_channel(self,evidence,now,gates):
        if (not isinstance(evidence,TransportEvidence) or evidence.server_pin_verified is not True or
                evidence.client_proof_verified is not True or not session_model.identifier(evidence.transport_binding)):
            raise Refused('Verified transport required')
        try:client=self.clients.get(evidence.client_fingerprint)
        except TypeError:raise Refused('Verified transport required') from None
        if client is None or client['revoked'] or evidence.client_fingerprint in self.channels:
            raise Refused('Enrollment unavailable or channel busy')
        if not session_model.integer(now,0,2**53-1) or not isinstance(gates,dict) or set(gates)!=set(session_model.GATES):
            raise Refused('Control context refused')
        channel=Channel(self,evidence,client['principal'],now,dict(gates))
        self.channels[evidence.client_fingerprint]=channel
        return channel

    def revoke(self,pin,now,explicit_approval):
        if explicit_approval is not True or not isinstance(pin,str) or pin not in self.clients:raise Refused('Revocation refused')
        self.clients[pin]['revoked']=True
        channel=self.channels.get(pin)
        if channel is not None:channel.close(now)


class Channel:
    def __init__(self,registry,evidence,principal,now,gates):
        self.registry=registry;self.evidence=evidence;self.principal=principal
        self.channel_id=secrets.token_hex(16);self.last_request=0;self.last_now=now
        self.gates=gates;self.frames=Frames();self.session=None;self.clock_pending=None;self.closed=False
        self.last_binding=None

    def __repr__(self):return '<GO control source-model-only; private state redacted>'

    def close(self,now):
        self.closed=True;self.clock_pending=None;self.frames.pending.clear();self.frames.failed=True
        if self.session is not None:
            try:self.session.stop(self.principal,now)
            except session_model.Refused:pass  # Clock refusal already clears/stops.
        if self.registry.channels.get(self.evidence.client_fingerprint) is self:
            del self.registry.channels[self.evidence.client_fingerprint]

    def guard(self,now):
        client=self.registry.clients[self.evidence.client_fingerprint]
        if self.closed or client['revoked'] or not session_model.integer(now,0,2**53-1) or now<self.last_now:
            self.close(now);raise Refused('Control channel unavailable')
        self.last_now=now

    def feed(self,data,now):
        self.guard(now)
        try:return [self._request(payload,now) for payload in self.frames.feed(data)]
        except (Refused,session_model.Refused):
            self.close(now);raise Refused('Control request refused') from None

    def eof(self,now):
        try:self.frames.finish()
        finally:self.close(now)

    def _request(self,data,now):
        self.guard(now)
        request=decode(data)
        if request['channel_id']!=self.channel_id or request['request_id']<=self.last_request:
            raise Refused('Control replay or channel mismatch')
        self.last_request=request['request_id']
        op=request['operation'];body=request['body']
        if op=='start':
            if self.session is not None or set(body)!={'duration_ms','consent','tier','location_mode'} or body['tier']!='pocket' or body['location_mode']!='foreground':
                raise Refused('Pocket session start refused')
            self.session=session_model.PocketSession(secrets.token_hex(16),self.principal,body['duration_ms'],now,self.gates,body['consent'])
            return {'session_id':self.session.session_id,'source_model_only':True,'native_verified':False}
        if self.session is None:raise Refused('Pocket session not started')
        if op=='status' and not body:return self.session.status(self.principal,now)
        if op=='stop' and not body:
            self.session.stop(self.principal,now);self.clock_pending=None
            return self.session.status(self.principal,now)
        if op=='clock_begin' and not body:
            self.session.tick(now)
            if self.session.state!='active' or not self.session.consent:raise Refused('Clock session inactive')
            self.session.clock=None;self.session.clear_fix('clock_unqualified')
            self.clock_pending={'nonce':secrets.token_hex(16),'sent_ms':now}
            return {'nonce':self.clock_pending['nonce'],'source_model_only':True}
        if op=='clock_reply' and set(body)=={'nonce','phone_utc_ms'}:
            pending=self.clock_pending;self.clock_pending=None
            if (pending is None or body['nonce']!=pending['nonce'] or
                    not session_model.integer(body['phone_utc_ms'],1,2**53-1) or
                    not 0<=now-pending['sent_ms']<=MAX_CLOCK_RTT_MS):
                raise Refused('Clock exchange refused')
            elapsed=now-pending['sent_ms'];anchor=pending['sent_ms']+elapsed//2
            uncertainty=(elapsed+1)//2+CLOCK_MARGIN_MS
            previous=self.last_binding
            if previous is not None:
                expected_utc=previous.phone_utc_ms+anchor-previous.server_mono_ms
                if abs(body['phone_utc_ms']-expected_utc)>previous.uncertainty_ms+uncertainty+CLOCK_MARGIN_MS:
                    raise Refused('Phone clock discontinuity refused')
            binding=session_model.ClockBinding(body['phone_utc_ms'],anchor,uncertainty)
            self.session.bind_clock(self.principal,binding,now);self.last_binding=binding
            return {'clock_bound':True,'uncertainty_ms':uncertainty,'source_model_only':True}
        if op=='location' and set(body)=={'sample'}:
            payload=json.dumps(body['sample'],ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii')
            self.session.location(self.principal,payload,now)
            return self.session.status(self.principal,now)
        raise Refused('Control operation refused')
