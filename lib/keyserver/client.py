#!/usr/bin/env python3

import asyncio
import argparse
import json

default_port = 8282
default_server = 'keyserver'
default_timeout = 5

class Client:

    def __init__(self, *, server=None, port=None):
        self.server = default_server if server is None else server
        self.port = default_port if port is None else port
        self.reader = None
        self.writer = None
        self.lock = asyncio.Lock()
       
    async def __aenter__(self):
        if self.writer is not None:
            raise Exception("already opened")
        self.reader, self.writer = await asyncio.open_connection(self.server, self.port)
        return self

    async def __aexit__(self, *args):
        if self.writer is not None:
            self.writer.close()

    async def fetch(self, *, hostname=None, timeout=None):
        timeout = default_timeout if timeout is None else timeout
        async with self.lock:
            return await asyncio.wait_for(self._fetch(hostname=hostname), timeout)

    async def _fetch(self, *, hostname=None):
        hostname_blob = b'' if hostname is None else hostname.encode('utf8')
        hostname_len_blob = len(hostname_blob).to_bytes(1, byteorder='big')
        self.writer.write(hostname_len_blob)
        self.writer.write(hostname_blob)
        host_keys_len = int.from_bytes(await self.reader.readexactly(2), byteorder='big')
        host_keys_blob = await self.reader.readexactly(host_keys_len)
        return json.loads(host_keys_blob)

async def fetch(*, server=None, port=None, hostname=None):
    async with Client(server=server, port=port) as client:
        return await client.fetch(hostname=hostname)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', nargs='?', const='*', metavar='hostname', required=True)
    parser.add_argument('-s', metavar='server')
    parser.add_argument('-p', type=int, metavar='port')
    args = parser.parse_args()
    hostname = args.f
    server = args.s
    port = args.p
    async with Client(server=server, port=port) as client:
        host_keys = await client.fetch(hostname=hostname) 
    print(json.dumps(host_keys, indent=2, sort_keys=True))
