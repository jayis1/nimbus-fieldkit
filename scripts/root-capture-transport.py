#!/usr/bin/env python3
"""Offline transport prototype: command planning and existing-process IO only.

Never launches SSH or stages a worker. Closing control on failure is not proof of
remote shutdown/restoration. Do not terminate the SSH process as a recovery tool.
"""
import importlib.util
import ipaddress
import io
import os
from pathlib import Path
import re
import selectors
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
MAX_DIAGNOSTICS = 1024 * 1024
CHUNK = 65536


def ssh_plan(session, *, host):
    if not isinstance(session, str) or not re.fullmatch('[a-f0-9]{64}', session):
        raise ValueError('Expected fresh 256-bit session token.')
    try:address=ipaddress.IPv4Address(host)
    except (ipaddress.AddressValueError,TypeError):raise ValueError('Explicit current device IPv4 address required.') from None
    if not isinstance(host,str) or str(address)!=host or address.is_multicast or address.is_unspecified or address.is_loopback:
        raise ValueError('Explicit current device IPv4 address required.')
    return ['ssh', '-F', '/dev/null', '-T', '-p', '2225', '-i', str(Path.home()/'.ssh/nimbus-admin-ed25519'),
            '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + str(Path.home()/'.ssh/nimbus-test-known-hosts'),
            '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'KnownHostsCommand=none',
            '-o', 'UpdateHostKeys=no', '-o', 'HostKeyAlgorithms=ssh-ed25519',
            '-o', f'HostKeyAlias=[{host}]:2224',
            '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no',
            '-o', 'KbdInteractiveAuthentication=no',
            '-o', 'ControlMaster=no', '-o', 'ControlPath=none',
            '-o', 'ClearAllForwardings=yes', '-o', 'ForwardAgent=no',
            '-o', 'ForwardX11=no', '-o', 'RequestTTY=no',
            f'root@{host}',
            'exec sh /tmp/nimbus-root-capture-v1/worker.sh --worker ' + session]


def load_receiver():
    spec = importlib.util.spec_from_file_location('transport_receiver', ROOT/'scripts/receive-root-capture.py')
    receiver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(receiver)
    return receiver


class ProcessStream:
    """Multiplex unbuffered stdout/stderr with bounded storage and a deadline.

    EOF is returned to the receiver only after BOTH pipes close, process exit is
    zero and the private diagnostic log is synced. Thus promotion/receipt creation
    cannot precede transport exit. No signal or process launch is performed here.
    """
    def __init__(self, process, diagnostic_fd, seconds):
        if seconds <= 0 or process.stdout is None or process.stderr is None:
            raise ValueError('Expected binary process pipes and positive deadline.')
        self.process = process
        self.log = diagnostic_fd
        self.deadline = time.monotonic() + seconds
        self.selector = selectors.DefaultSelector()
        self.buffer = bytearray()
        self.logged = 0
        self.checked = False
        for pipe, kind in ((process.stdout, 'stdout'), (process.stderr, 'stderr')):
            os.set_blocking(pipe.fileno(), False)
            self.selector.register(pipe, selectors.EVENT_READ, kind)

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError('Transport deadline exceeded; remote state unknown.')
        return seconds

    def pump(self, discard=False):
        for key, _ in self.selector.select(self.remaining()):
            data = os.read(key.fd, CHUNK)
            if not data:
                self.selector.unregister(key.fileobj)
            elif key.data == 'stdout':
                if not discard:
                    self.buffer.extend(data)
            else:
                available = max(0, MAX_DIAGNOSTICS - self.logged)
                saved = data[:available]
                while saved:
                    written = os.write(self.log, saved)
                    if written <= 0:
                        raise OSError('Private diagnostic write failed.')
                    self.logged += written
                    saved = saved[written:]
                if len(data) > available and not discard:
                    raise ValueError('Diagnostic budget exceeded; attempt invalidated.')

    def verify_exit(self):
        if self.checked:
            return
        while self.selector.get_map():
            self.pump()
            if self.buffer:
                raise ValueError('Unexpected protocol bytes after EOF.')
        if self.process.wait(timeout=self.remaining()) != 0:
            raise ValueError('Transport exited nonzero; receipt refused.')
        os.fsync(self.log)
        self.checked = True

    def read(self, size):
        if not 0 < size <= 1024 * 1024:
            raise ValueError('Bounded positive reads required.')
        while not self.buffer and self.selector.get_map():
            self.pump()
        if not self.buffer:
            self.verify_exit()
            return b''
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def readline(self, limit):
        if not 0 < limit <= 257:
            raise ValueError('Bounded protocol line required.')
        while b'\n' not in self.buffer and len(self.buffer) < limit and self.selector.get_map():
            self.pump()
        end = self.buffer.find(b'\n')
        size = min(end + 1 if end >= 0 else len(self.buffer), limit)
        if not size:
            self.verify_exit()
            return b''
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def drain_failure(self):
        # Consume output rather than blocking remote cleanup on a full pipe.
        # Never signal an SSH process. A deadline expiry leaves state UNKNOWN.
        self.buffer.clear()
        while self.selector.get_map():
            self.pump(discard=True)
        self.process.wait(timeout=self.remaining())
        os.fsync(self.log)

    def close(self):
        self.selector.close()


class ProcessControl:
    """Single small ACK, with the same deadline and no buffered blocking writes."""
    def __init__(self, process, stream):
        self.pipe = process.stdin
        self.stream = stream
        self.sent = False
        os.set_blocking(self.pipe.fileno(), False)

    def write(self, data):
        if self.sent or not isinstance(data, bytes) or not 0 < len(data) <= 256:
            raise ValueError('Exactly one bounded ACK request permitted.')
        self.sent = True
        with selectors.DefaultSelector() as selector:
            selector.register(self.pipe, selectors.EVENT_WRITE)
            remaining = data
            while remaining:
                if not selector.select(self.stream.remaining()):
                    raise TimeoutError('ACK deadline expired; attempt invalidated.')
                written = os.write(self.pipe.fileno(), remaining)
                if written <= 0:
                    raise OSError('ACK write failed.')
                remaining = remaining[written:]
        return len(data)

    def flush(self):
        self.stream.remaining()


def receive_process(process, output, session, seconds=300, receiver=None):
    """Receive from an ALREADY started, caller-owned process; no live launcher.

    Caller must use unbuffered binary pipes and supply fresh approved staging.
    Failure closes ACK input and drains within the remaining budget. It does not
    prove remote worker death, reader shutdown or restoration, even after SSH exit.
    """
    receiver = receiver or load_receiver()
    output = receiver.check_output(output)
    if seconds <= 0 or any(not isinstance(pipe, io.FileIO) for pipe in (process.stdin, process.stdout, process.stderr)):
        raise ValueError('Positive deadline and unbuffered binary pipes required.')
    fd = receiver.private_fd(output/'TRANSPORT-STDERR.log')
    stream = None
    try:
        stream = ProcessStream(process, fd, seconds)
        try:
            control = ProcessControl(process, stream)
            return receiver.receive(stream, control, output, session)
        except BaseException:
            process.stdin.close()
            try:
                stream.drain_failure()
            except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired):
                # Keep original failure; absence of receipt is irreversible.
                pass
            raise
    finally:
        if stream is not None:
            stream.close()
        os.close(fd)


if __name__ == '__main__':
    raise SystemExit('Offline transport prototype only. No SSH launch/staging or device action supplied.')
