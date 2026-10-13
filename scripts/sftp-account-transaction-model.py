#!/usr/bin/env python3
"""Pure offline account commit/rollback model, NOT a device installer.

Returns private bytes in memory only. No filesystem/network/service operation or
lock claim is supplied. Real writer exclusion and crash recovery remain gates.
"""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('account_plan_model',ROOT/'scripts/prepare-sftp-accounts.py')
planner=importlib.util.module_from_spec(spec);spec.loader.exec_module(planner)
NAMES=('passwd','group','shadow')
COMMIT_ORDER=('group','shadow','passwd')
ROLLBACK_ORDER=('passwd','shadow','group')


def checked_plan(baseline,proposed,header,files_uid=2206,privsep_uid=2207):
    if not isinstance(baseline,dict) or not isinstance(proposed,dict) or set(baseline)!=set(NAMES) or set(proposed)!=set(NAMES):
        raise ValueError('Exactly three private tables required')
    expected,record=planner.plan(**baseline,header=header,files_uid=files_uid,privsep_uid=privsep_uid)
    if proposed!=expected:raise ValueError('Proposal differs from append-only reviewed plan')
    return record


def commit_model(current,baseline,proposed,header,files_uid=2206,privsep_uid=2207):
    checked_plan(baseline,proposed,header,files_uid,privsep_uid)
    if current!=baseline:raise ValueError('Current inputs changed; prepare/review a new private plan')
    return {'schema':'nimbus-offline-account-commit-model/v1',
            'candidate_tables':dict(proposed),'order':COMMIT_ORDER,
            'installer_supplied':False,'writer_exclusion_verified':False,
            'native_verified':False,'device_changed':False}


def rollback_model(current,baseline,proposed,header,files_uid=2206,privsep_uid=2207):
    """Remove ONLY exact proposed role records, preserving unrelated current bytes.

    Supports whole-table commit prefixes, not arbitrary missing/modified role
    records. Unrelated later edits survive. Unexpected role/ID references or an
    ambiguous role record require manual private review, never baseline restore.
    This is a byte-selection model, not authority to stop sessions or write files.
    """
    record=checked_plan(baseline,proposed,header,files_uid,privsep_uid)
    if not isinstance(current,dict) or set(current)!=set(NAMES):
        raise ValueError('Exactly three current private tables required')
    parsed={name:planner.table(current[name],name) for name in NAMES}
    if not any(row[0]=='root' and row[2:4]==['0','0'] for row in parsed['passwd']):
        raise ValueError('Current root identity differs; private review required')
    roles=set(planner.ROLE_NAMES);ids=set(record['ids'].values())
    for row in parsed['passwd']:
        if row[0] not in roles and (int(row[2]) in ids or int(row[3]) in ids):
            raise ValueError('Later account references a dedicated role ID')
    for row in parsed['group']:
        if row[0] not in roles and (int(row[2]) in ids or roles.intersection(row[3].split(','))):
            raise ValueError('Later group references a dedicated role identity')
    present={};result={}
    for name in NAMES:
        expected={line.split(b':',1)[0]:line for line in proposed[name][len(baseline[name]):].splitlines(keepends=True)}
        seen=set();kept=[]
        for line in current[name].splitlines(keepends=True):
            role=line.split(b':',1)[0]
            if role in expected:
                if line!=expected[role]:raise ValueError('Role record changed; do not remove or restore automatically')
                seen.add(role)
            else:kept.append(line)
        if seen and seen!=set(expected):raise ValueError('Partial role records are ambiguous')
        present[name]=bool(seen);result[name]=b''.join(kept)
        planner.table(result[name],name)
    # A crash during the reviewed order may leave no tables, group only,
    # group+shadow, or all three. Do not infer safety from arbitrary subsets.
    state=tuple(present[name] for name in COMMIT_ORDER)
    if state not in ((False,False,False),(True,False,False),(True,True,False),(True,True,True)):
        raise ValueError('Role presence is not a reviewed commit prefix')
    return {'schema':'nimbus-offline-account-rollback-model/v1',
            'candidate_tables':result,
            'order':tuple(name for name in ROLLBACK_ORDER if present[name]),
            'unrelated_current_bytes_preserved':True,'baseline_restored':False,
            'installer_supplied':False,'writer_exclusion_verified':False,
            'session_drain_verified':False,'native_verified':False,'device_changed':False}
