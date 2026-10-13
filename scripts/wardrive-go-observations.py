#!/usr/bin/env python3
"""Bounded host parser for private iw scan-cache text. Never invokes iw/scans.

Cache observations are not live acquisitions. Their ages are reported estimates,
and no GPS fix or AP identity/security/internet claim is fabricated.
"""
from dataclasses import dataclass
import math
import re

MAX_BYTES=65536
MAX_RECORDS=128
MAX_LINE_BYTES=512
MAX_CACHE_AGE_MS=60000
HEADER=re.compile(rb'BSS ([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\(on (wlan[01])\)(?: -- associated)?$')


class Refused(ValueError):pass


@dataclass(frozen=True,repr=False)
class CacheObservation:
    bssid:str
    interface:str
    frequency_mhz:int
    signal_dbm:float
    ssid_display:str
    received_mono_ms:int
    reported_age_ms:int

    def __repr__(self):return '<CacheObservation private; cached age is unverified>'

    def private_record(self):
        # Caller must keep this OUT of chat/status/public shares. iw display
        # escapes are preserved, not asserted to be original SSID bytes.
        return {'schema':'nimbus-go-observation/v1','bssid':self.bssid,
                'interface':self.interface,'frequency_mhz':self.frequency_mhz,
                'signal_dbm':self.signal_dbm,'ssid_display':self.ssid_display,
                'ssid_encoding':'iw_display_not_lossless_export',
                'source':'sandisk_iw_cache','acquisition_mode':'unknown',
                'received_mono_ms':self.received_mono_ms,
                'reported_age_ms':self.reported_age_ms,
                'estimated_observed_mono_ms':self.received_mono_ms-self.reported_age_ms,
                'observation_time_verified':False,'location':None,
                'native_scan_verified':False}


def parse_cache(data,interface,received_mono_ms):
    if (not isinstance(data,bytes) or len(data)>MAX_BYTES or interface not in ('wlan0','wlan1') or
            type(received_mono_ms) is not int or not 0<=received_mono_ms<=2**53-1):
        raise Refused('Survey cache input refused')
    if not data:return []
    if not data.endswith(b'\n') or b'\0' in data:raise Refused('Survey cache input refused')
    observations=[];current=None;seen=set()

    def finish():
        if current is None:return
        if set(current)!={'bssid','interface','frequency_mhz','signal_dbm','ssid_display','reported_age_ms'}:
            raise Refused('Survey cache record incomplete')
        if current['reported_age_ms']>received_mono_ms:
            raise Refused('Survey cache clock mismatch')
        observations.append(CacheObservation(**current,received_mono_ms=received_mono_ms))

    for line in data.splitlines():
        if len(line)>MAX_LINE_BYTES:raise Refused('Survey cache line refused')
        if line.startswith(b'BSS '):
            finish()
            header=HEADER.fullmatch(line)
            if header is None or len(seen)>=MAX_RECORDS:raise Refused('Survey cache header refused')
            bssid=header[1].decode('ascii').lower();device=header[2].decode('ascii')
            first=int(bssid[:2],16)
            if device!=interface or first & 1 or bssid=='00:00:00:00:00:00' or bssid in seen:
                raise Refused('Survey cache identity refused')
            seen.add(bssid);current={'bssid':bssid,'interface':device};continue
        if current is None:raise Refused('Survey cache header missing')
        # Only the selected top-level iw fields become records. All other IEs,
        # security/vendor elements and association annotations are discarded.
        stripped=line.lstrip(b'\t ')
        field=None;value=None
        if stripped.startswith(b'freq:'):
            match=re.fullmatch(rb'freq: ([0-9]{4})',stripped)
            if not match:raise Refused('Survey cache frequency refused')
            value=int(match[1]);field='frequency_mhz'
            if not 2000<=value<=7125:raise Refused('Survey cache frequency refused')
        elif stripped.startswith(b'signal:'):
            match=re.fullmatch(rb'signal: (-?[0-9]{1,3}(?:\.[0-9]{1,2})?) dBm',stripped)
            if not match:raise Refused('Survey cache signal refused')
            value=float(match[1]);field='signal_dbm'
            if not math.isfinite(value) or not -150<=value<=0:raise Refused('Survey cache signal refused')
        elif stripped.startswith(b'last seen:'):
            match=re.fullmatch(rb'last seen: ([0-9]{1,8}) ms ago',stripped)
            if not match:raise Refused('Survey cache age refused')
            value=int(match[1]);field='reported_age_ms'
            if value>MAX_CACHE_AGE_MS:raise Refused('Survey cache age refused')
        elif stripped.startswith(b'SSID:'):
            if not stripped.startswith(b'SSID: '):raise Refused('Survey cache SSID display refused')
            raw=stripped[len(b'SSID: '):]
            if len(raw)>128 or any(byte<32 or byte>126 for byte in raw):raise Refused('Survey cache SSID display refused')
            value=raw.decode('ascii');field='ssid_display'
        if field is not None:
            if field in current:raise Refused('Duplicate survey cache field')
            current[field]=value
    finish()
    return observations
