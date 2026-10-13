#!/usr/bin/env python3
"""Pocket GO protocol/state model. No listener, radio, storage or native runtime.

This is host-side executable specification, not an authenticated device endpoint.
Never pass private fixes to public logs or use fixture gates as hardware evidence.
"""
from dataclasses import dataclass
import json
import math
import re

SCHEMA='nimbus-go-location/v1'
MAX_WIRE_BYTES=1024
MAX_DURATION_MS=900000
MAX_SAMPLES=1800
MAX_FIX_AGE_MS=5000
MAX_CLOCK_AGE_MS=60000
MAX_CLOCK_UNCERTAINTY_MS=1000
MAX_ACCURACY_M=100
GATES=('authenticated_nonroot_channel','scope_authorized','scan_qualified',
       'control_radio_coexistence_qualified','private_storage_ready',
       'media_ownership_verified','bounded_worker_qualified','restoration_qualified')


class Refused(ValueError):
    """Fixed public error, never includes a location, identifier or input value."""


def integer(value,low,high):
    return type(value) is int and low<=value<=high


def identifier(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{32}',value) is not None


def number(value,low,high):
    return type(value) in (int,float) and low<=value<=high and math.isfinite(value)


def decode_location(wire):
    if not isinstance(wire,bytes) or not 1<=len(wire)<=MAX_WIRE_BYTES:
        raise Refused('Location message refused')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise Refused('Location message refused')
            result[key]=value
        return result
    def reject_constant(_):
        raise Refused('Location message refused')
    try:
        message=json.loads(wire.decode('utf-8'),object_pairs_hook=unique,
                           parse_constant=reject_constant)
    except (UnicodeError,ValueError,RecursionError):
        raise Refused('Location message refused') from None
    keys={'schema','session_id','sequence','permission','fix_status','provider',
          'acquired_at_ms','latitude','longitude','accuracy_m'}
    if not isinstance(message,dict) or set(message)!=keys or message['schema']!=SCHEMA or not identifier(message['session_id']):
        raise Refused('Location message refused')
    if not integer(message['sequence'],1,MAX_SAMPLES) or message['permission'] not in ('granted','denied','revoked'):
        raise Refused('Location message refused')
    if message['fix_status'] not in ('fix','unavailable','suspended') or message['provider'] not in ('native_gps','fused','none'):
        raise Refused('Location message refused')
    if message['fix_status']=='fix':
        if message['permission']!='granted' or message['provider']=='none' or not integer(message['acquired_at_ms'],1,2**53-1):
            raise Refused('Location message refused')
        if not number(message['latitude'],-90,90) or not number(message['longitude'],-180,180) or not number(message['accuracy_m'],0,100000):
            raise Refused('Location message refused')
    elif any(message[key] is not None for key in ('acquired_at_ms','latitude','longitude','accuracy_m')) or message['provider']!='none':
        raise Refused('Location message refused')
    return message


@dataclass(frozen=True,repr=False)
class ClockBinding:
    # Reviewed authenticated clock exchange must supply these, including a
    # conservative delay/uncertainty bound. Phone timestamps alone are not proof.
    phone_utc_ms:int
    server_mono_ms:int
    uncertainty_ms:int

    def valid(self,now):
        return (integer(self.phone_utc_ms,1,2**53-1) and
                integer(self.server_mono_ms,0,2**53-1) and
                integer(self.uncertainty_ms,0,MAX_CLOCK_UNCERTAINTY_MS) and
                self.server_mono_ms<=now<=self.server_mono_ms+MAX_CLOCK_AGE_MS)


class PocketSession:
    def __init__(self,session_id,principal,duration_ms,now,gates,consent):
        if not identifier(session_id) or not identifier(principal) or not integer(now,0,2**53-1):
            raise Refused('Session start refused')
        if not integer(duration_ms,1000,MAX_DURATION_MS) or consent is not True:
            raise Refused('Session start refused')
        if not isinstance(gates,dict) or set(gates)!=set(GATES) or any(gates[name] is not True for name in GATES):
            raise Refused('Session capabilities unqualified')
        self.session_id=session_id;self.principal=principal
        self.deadline=now+duration_ms;self.last_now=now;self.sequence=0
        self.state='active';self.location_state='unknown';self.fix=None
        self.consent=True;self.clock=None;self.last_acquired=None

    def __repr__(self):
        return '<PocketSession source-model-only; private state redacted>'

    def clear_fix(self,state):
        self.fix=None;self.location_state=state

    def authorize(self,principal):
        if principal!=self.principal:raise Refused('Session access refused')

    def tick(self,now):
        if not integer(now,0,2**53-1) or now<self.last_now:
            self.state='stopping';self.consent=False;self.clock=None;self.clear_fix('clock_invalid')
            raise Refused('Session clock refused')
        self.last_now=now
        if self.state=='active' and now>=self.deadline:
            self.state='stopping';self.consent=False;self.clock=None;self.clear_fix('session_expired')
        if self.fix is not None:
            if self.clock is None or not self.clock.valid(now):self.clear_fix('clock_unqualified')
            elif now-self.fix['estimated_mono_ms']+self.clock.uncertainty_ms>MAX_FIX_AGE_MS:self.clear_fix('stale')

    def bind_clock(self,principal,binding,now):
        self.authorize(principal);self.tick(now)
        self.clock=None;self.clear_fix('clock_unqualified')
        if self.state!='active' or not self.consent or not isinstance(binding,ClockBinding) or not binding.valid(now):
            raise Refused('Clock binding refused')
        self.clock=binding
        self.last_acquired=None

    def location(self,principal,wire,now):
        self.authorize(principal);self.tick(now)
        if self.state!='active' or not self.consent:raise Refused('Location session inactive')
        # Malformed/replayed/wrong-session input from the enrolled owner must
        # never leave an old coordinate labelled fresh.
        self.clear_fix('unknown')
        message=decode_location(wire)
        if message['session_id']!=self.session_id or message['sequence']<=self.sequence:
            raise Refused('Location replay or session mismatch')
        self.sequence=message['sequence']
        if message['permission']!='granted':
            self.consent=False;self.clock=None;self.clear_fix('permission_'+message['permission'])
            return
        if message['fix_status']!='fix':
            self.clear_fix(message['fix_status']);return
        if self.last_acquired is not None and message['acquired_at_ms']<=self.last_acquired:
            raise Refused('Location acquisition replay')
        self.last_acquired=message['acquired_at_ms']
        if self.clock is None or not self.clock.valid(now):
            self.clear_fix('clock_unqualified');return
        estimated=self.clock.server_mono_ms+message['acquired_at_ms']-self.clock.phone_utc_ms
        if estimated>now+self.clock.uncertainty_ms:
            self.clear_fix('clock_mismatch');return
        if now-estimated+self.clock.uncertainty_ms>MAX_FIX_AGE_MS:
            self.clear_fix('stale');return
        if message['accuracy_m']>MAX_ACCURACY_M:
            self.clear_fix('inaccurate');return
        self.fix={'latitude':message['latitude'],'longitude':message['longitude'],
                  'accuracy_m':message['accuracy_m'],'provider':message['provider'],
                  'acquired_at_ms':message['acquired_at_ms'],'estimated_mono_ms':estimated,
                  'received_mono_ms':now,'sequence':self.sequence}
        self.location_state='fresh'

    def status(self,principal,now):
        self.authorize(principal);self.tick(now)
        # Status is deliberately coordinate-free; maps/results need a separate
        # authenticated private response. Native support is never inferred here.
        return {'schema':'nimbus-go-status/v1','state':self.state,
                'location':self.location_state,'consent':self.consent,
                'remaining_ms':max(0,self.deadline-now) if self.state=='active' else 0,
                'source_model_only':True,'native_verified':False,
                'radio_started':False,'records_persisted':False}

    def observation_location(self,principal,observed_mono_ms,now):
        """Private attribution for an observation, never a public status field.

        Conservatively refuse a fix acquired after the observation, a future
        observation, or an old sample. No historical backfilling or fake points.
        Returned coordinates must stay in the authenticated private data path.
        """
        self.authorize(principal);self.tick(now)
        if self.state!='active' or not self.consent or self.fix is None:return None
        if not integer(observed_mono_ms,0,now):return None
        uncertainty=self.clock.uncertainty_ms
        age=observed_mono_ms-self.fix['estimated_mono_ms']
        if age<uncertainty or age+uncertainty>MAX_FIX_AGE_MS:return None
        return {key:self.fix[key] for key in ('latitude','longitude','accuracy_m',
                                            'provider','acquired_at_ms','sequence')}

    def stop(self,principal,now):
        self.authorize(principal);self.tick(now)
        if self.state=='active':self.state='stopping'
        self.consent=False;self.clock=None;self.clear_fix('stopped')

    def finish(self,principal,now,worker_drained,restored):
        self.authorize(principal);self.tick(now)
        if self.state!='stopping':raise Refused('Session completion refused')
        self.consent=False;self.clock=None;self.clear_fix('stopped')
        if worker_drained is not True or restored is not True:self.state='restoration_unconfirmed'
        else:self.state='complete'

    def capability_lost(self,principal,now):
        # Caller must signal link/media/worker/optional-node loss; no polling or
        # automatic fallback/mount/reconnect is implemented by this model.
        self.stop(principal,now)
