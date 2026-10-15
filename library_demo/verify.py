#!/usr/bin/env python3
"""Bounded live comparison of the same ML tools through two MCP hosts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time


class Client:
    def __init__(self, command, output, cwd=None):
        self.command = command
        self.output = output
        self.stderr = output.with_suffix('.stderr').open('w')
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.stderr)
        self.poll = selectors.DefaultSelector()
        self.poll.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b''
        self.serial = 0
        self.requests = []
        self.responses = []

    def call(self, method, params):
        self.serial += 1
        request = dict(jsonrpc='2.0', id=self.serial, method=method, params=params)
        self.requests.append(request)
        self.process.stdin.write((json.dumps(request) + '\n').encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.poll.select(timeout=.2):
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError('Server exited before response; inspect stderr')
                self.buffer += chunk
                while b'\n' in self.buffer:
                    line, self.buffer = self.buffer.split(b'\n', 1)
                    response = json.loads(line)
                    self.responses.append(response)
                    if response.get('id') == self.serial:
                        return response
        raise TimeoutError(f'{method} exceeded 180 seconds')

    def initialize(self):
        result = self.call('initialize', dict(protocolVersion='2025-11-25',
            capabilities={}, clientInfo=dict(name='shared-ml-demo', version='1')))
        assert 'result' in result, result
        self.process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        self.process.stdin.flush()

    def close(self):
        self.process.stdin.close()
        code = self.process.wait(timeout=30)
        assert code == 0, code
        return code

    def save(self, code=None):
        self.output.write_text(json.dumps(dict(command=self.command,
            requests=self.requests, responses=self.responses, exit_code=code), indent=2)+'\n')
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.stderr.close()
        self.poll.close()


def tool_text(response):
    result = response['result']
    assert not result.get('isError', False), response
    return '\n'.join(c['text'] for c in result['content'] if c.get('type') == 'text')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('/tmp/shared-ml-demo-evidence'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.original / 'mcp/Tools/MCP_Tools.thy'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    commands = {
        'pide': ['/usr/bin/host-spawn','--no-pty','flatpak','run','--command=isabelle',
            '--env=USER_HOME=/tmp/pide-mcp-adoption-home',
            '--env=ISABELLE_IDENTIFIER=PideMcpAdoption',
            'de.tum.in.isabelle.Isabelle','pide_mcp','-d',str(source.parent),'-l','MCP-Tools'],
        'original': [str(args.original / 'tools/isabelle'),'--profile','codex','--',
            'mcp_server','-s','MCP-Tools','-T','MCP-Tools.MCP_Tools']}
    outcomes = {}
    for host, command in commands.items():
        client = Client(command, args.output / f'{host}.json', cwd=args.original)
        code = None
        try:
            client.initialize()
            deadline = time.monotonic() + 180
            while True:
                listing = client.call('tools/list', {})
                names = {tool['name'] for tool in listing.get('result', {}).get('tools', [])}
                # Original host serves its Scala catalogue while ML readiness is pending.
                if ('demo_ml_catalogue' if host == 'pide' else 'shout') in names:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Original host did not become ready')
                time.sleep(1)
            listed = listing['result']['tools']
            if host == 'pide':
                assert len(listed) == 13, listing
                catalogue = client.call('tools/call', dict(name='demo_ml_catalogue', arguments={}))
                rows = catalogue['result']['structuredContent']['tools']
                assert any(r['name'] == 'MCP_Tools.shout' for r in rows), catalogue
                tool_text(client.call('tools/call', dict(name='list_sessions', arguments={})))
            else:
                assert any(r['name'] == 'shout' for r in listed), listing
            def invoke(name, values):
                if host == 'pide':
                    return client.call('tools/call', dict(name='demo_ml_invoke',
                        arguments=dict(name='MCP_Tools.'+name, arguments=values)))
                return client.call('tools/call', dict(name=name, arguments=values))
            shout = tool_text(invoke('shout', dict(input='shared tool')))
            summary = tool_text(invoke('edit_summary', dict(path='shared.thy',
                edits=[dict(old_text='old', new_text='new')])))
            assert shout == 'SHARED TOOL', shout
            assert summary == 'shared.thy:1', summary
            invalid = invoke('shout', {})
            assert invalid.get('result', {}).get('isError', False), invalid
            assert tool_text(invoke('shout', dict(input='shared tool'))) == shout
            code = client.close()
            outcomes[host] = dict(shout=shout, edit_summary=summary, exit_code=code)
            print(f'PASS {host}: discovery, same shout/edit_summary, argument error/recovery, shutdown')
        finally:
            client.save(code)
    assert outcomes['pide'] == outcomes['original'], outcomes
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    revisions = {name: subprocess.check_output(['git','rev-parse','HEAD'], cwd=path,
        text=True).strip() for name,path in [('pide',args.checkout),('original',args.original),
        ('library',args.original.parent / 'isabelle-tool-library')]}
    (args.output/'comparison.json').write_text(json.dumps(dict(source=str(source),
        source_sha256=source_hash, revisions=revisions, outcomes=outcomes), indent=2)+'\n')
    print('PASS: both hosts used unchanged existing ML source and returned matching results')


if __name__ == '__main__':
    main()
