#!/usr/bin/env python3

import asyncio
import argparse
import json

async def fetch(*, server=None, port=None, hostname=None):
    server = '127.0.0.1' if server is None else server
    port = 8282 if port is None else port
    writer = None
    try:
        reader, writer = await asyncio.open_connection(server, port)
        if hostname is None:
            hostname_blob = b''
        else:
            hostname_blob = hostname.encode('utf8')
        hostname_len_blob = len(hostname_blob).to_bytes(1, byteorder='big')
        writer.write(hostname_len_blob)
        writer.write(hostname_blob)
        host_keys_len = int.from_bytes(await reader.readexactly(2), byteorder='big')
        host_keys_blob = await reader.readexactly(host_keys_len)
        return json.loads(host_keys_blob)
    finally:
        if writer is not None:
            writer.close()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', nargs='?', const='*', metavar='hostname', required=True)
    parser.add_argument('-s', default='127.0.0.1:8282', metavar='server')
    args = parser.parse_args()
    server, portstr = args.s.split(':')
    host_keys = await fetch(server=server, port=int(portstr), hostname=args.f)
    print(json.dumps(host_keys, indent=2, sort_keys=True))
