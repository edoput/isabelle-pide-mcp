#!/usr/bin/env python3
"""Bounded, LLM-free smoke test for the paper tools in adapted PIDE MCP."""
import argparse
from pathlib import Path
import sys
import time

from verify import Client


def result_text(reply):
    result = reply.get('result', {})
    text = '\n'.join(item['text'] for item in result.get('content', [])
                     if item.get('type') == 'text')
    if result.get('isError'):
        raise RuntimeError(text or repr(reply))
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/pide-paper-smoke'))
    parser.add_argument('server_command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.server_command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        parser.error('pass the server command after --')
    args.output.mkdir(parents=True, exist_ok=True)
    record = args.output / 'pide.json'
    client = Client(command, record)
    code = None
    try:
        client.initialize()
        listing = client.call('tools/list', {})
        exposed = {row['name'] for row in listing['result']['tools']}
        assert not {'demo_ml_catalogue', 'demo_ml_invoke'} & exposed, exposed
        rows = listing['result']['tools']
        names = {row['name'] for row in rows}
        expected = {'Proof_Tasks.proof_tasks',
                    'Change_Detection.theory_add', 'Change_Detection.theory_diff'}
        deadline = time.monotonic() + 180
        while not expected <= names and time.monotonic() < deadline:
            time.sleep(0.2)
            listing = client.call('tools/list', {})
            rows = listing['result']['tools']
            names = {row['name'] for row in rows}
        assert expected <= names, names
        for row in rows:
            if row['name'] in expected:
                assert row['inputSchema']['properties']['theories']['type'] == 'array', row
                assert 'theories' in row['inputSchema']['required'], row

        def invoke(name, theory):
            reply = client.call('tools/call', {'name': name, 'arguments': {'theories': [theory]}})
            return result_text(reply)

        tasks = invoke('Proof_Tasks.proof_tasks', 'MCP-Tool-Library-Paper-Examples.Paper_Proof_Fixture')
        assert 'Paper_Proof_Fixture.open_obligation' in tasks, tasks
        checkpoint = invoke('Change_Detection.theory_add', 'Paper_Signature_Fixture')
        assert 'checkpoint saved' in checkpoint, checkpoint
        comparison = invoke('Change_Detection.theory_diff', 'Paper_Signature_Fixture')
        assert 'protected logical signature unchanged' in comparison, comparison
        assert client.responses[0]['result']['capabilities']['tools']['listChanged'] is True
        assert any(r.get('method') == 'notifications/tools/list_changed'
                   for r in client.responses), client.responses
        notifications_before_stop = sum(r.get('method') == 'notifications/tools/list_changed'
                                        for r in client.responses)
        result_text(client.call('tools/call', {'name': 'stop_session', 'arguments': {}}))
        remaining = client.call('tools/list', {})['result']['tools']
        assert not expected.intersection(row['name'] for row in remaining), remaining
        assert sum(r.get('method') == 'notifications/tools/list_changed'
                   for r in client.responses) > notifications_before_stop
        missing = client.call('tools/call',
            {'name': 'Proof_Tasks.proof_tasks', 'arguments': {'theories': []}})
        assert missing.get('error', {}).get('code') == -32602, missing
        code = client.close()
        print('PASS: server startup, direct names and schemas, proof task, checkpoint, diff, shutdown')
        print(f'Logs: {record} and {record.with_suffix(".stderr")}')
    finally:
        client.save(code)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
