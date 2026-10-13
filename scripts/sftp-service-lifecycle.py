#!/usr/bin/env python3
"""Offline SFTP shutdown/USB decision model. Emits labels, never commands.

No process lookup, signaling, mount/service invocation or native evidence is
provided. A future reviewed executor must supply fresh identity-bound facts.
"""
PREREQUISITES=('exact_trial_approved','native_runtime_verified','dedicated_enrollment_verified',
               'confinement_verified','read_only_views_verified','usb_inactive',
               'fallback_verified','listen_address_verified','bounded_session_supervision_verified')


class Lifecycle:
    def __init__(self):
        self.state='new'
        self.invalidated=False
        self.ownership_lost=False
        self.listener_gone=False
        self.descendants_drained=False
        self.views_gone=False

    def _state(self,expected):
        if self.state!=expected:raise ValueError('Out-of-order SFTP lifecycle event')

    def begin(self,facts):
        self._state('new')
        if not isinstance(facts,dict) or any(facts.get(name) is not True for name in PREREQUISITES):
            raise ValueError('Unqualified/unknown SFTP start prerequisites')
        self.state='starting'
        return 'start-exact-reviewed-listener'

    def listener_ready(self,*,identity_bound,policy_matches,views_readonly,usb_inactive):
        self._state('starting')
        if any(value is not True for value in (identity_bound,policy_matches,views_readonly,usb_inactive)):
            return self.stop(reason='start-verification-failed',ownership_lost=usb_inactive is not True)
        self.state='serving'
        return 'serve-readonly-with-bounded-supervision'

    def observe(self,*,usb_state,views_readonly,fallback_verified,session_count,deadline_expired=False):
        if self.state not in ('starting','serving'):raise ValueError('Observation outside running lifecycle')
        ownership_lost=usb_state!='inactive'
        invalid_count=type(session_count) is not int or not 0<=session_count<=1
        if ownership_lost or views_readonly is not True or fallback_verified is not True or invalid_count or deadline_expired is not False:
            return self.stop(reason='runtime-observation-invalid',ownership_lost=ownership_lost)
        return 'continue-bounded-observation'

    def stop(self,*,reason='owner-stop',ownership_lost=False):
        if self.state not in ('starting','serving','stopping','draining'):
            raise ValueError('No running listener/session lifecycle to stop')
        if type(ownership_lost) is not bool:raise ValueError('Unknown ownership-loss flag')
        self.invalidated=self.invalidated or reason!='owner-stop'
        self.ownership_lost=self.ownership_lost or ownership_lost
        if self.state in ('stopping','draining'):return 'retain-shutdown-in-progress'
        self.state='stopping'
        return 'stop-only-identity-bound-listener'

    def listener_stopped(self,*,identity_bound,absent):
        self._state('stopping')
        if identity_bound is not True or absent is not True:
            self.invalidated=True;self.state='blocked'
            return 'refuse-unknown-or-replacement-listener-no-media-action'
        self.listener_gone=True;self.state='draining'
        return 'cancel-and-drain-all-enrolled-sessions'

    def sessions_drained(self,*,complete_inventory,no_live_descendants,no_media_handles,usb_state):
        self._state('draining')
        if any(value is not True for value in (complete_inventory,no_live_descendants,no_media_handles)):
            self.invalidated=True
            return 'retain-draining-no-unmount-no-usb-release'
        self.descendants_drained=True
        self.ownership_lost=self.ownership_lost or usb_state!='inactive'
        if self.ownership_lost:
            self.invalidated=True;self.state='blocked'
            return 'ownership-lost-preserve-views-for-explicit-review'
        self.state='detaching'
        return 'detach-only-exact-reviewed-readonly-views'

    def views_detached(self,*,complete_inventory,exact_views_absent,usb_state):
        self._state('detaching')
        self.ownership_lost=self.ownership_lost or usb_state!='inactive'
        if any(value is not True for value in (complete_inventory,exact_views_absent)) or usb_state!='inactive':
            self.invalidated=True;self.state='blocked'
            return 'detach-unconfirmed-no-usb-release'
        self.views_gone=True;self.state='stopped'
        return 'shutdown-observed-request-separate-vendor-transition-review'

    def receipt(self):
        cleared=(self.state=='stopped' and self.listener_gone and self.descendants_drained and self.views_gone and not self.ownership_lost)
        return {'schema':'nimbus-sftp-lifecycle-model/v1','state':self.state,
                'invalidated':self.invalidated,'ownership_lost':self.ownership_lost,
                'shutdown_observed':cleared,'vendor_transition_reviewable':cleared,
                'native_verified':False,'usb_handoff_verified':False,
                'listener_authorized':False,'production_ready':False,'flash_authorized':False}


if __name__=='__main__':
    raise SystemExit('Offline decision model only; no listener, mount, session signal or USB action supplied.')
