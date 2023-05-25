#!/usr/bin/env python3

import ssl
import argparse
import asyncio
import json
import logging
from asyncio import wait_for
import uvloop

from .common import *

default_server = 'keyserver'
default_ssl_server = 'keyserver.lan.raincity.io'
default_timeout = 5

# basic client, to fetch only one break out of loop
class Client:

    def __init__(self, endpoint, *, timeout=None, ssl=None):
        self.endpoint = endpoint
        self.timeout = default_timeout if timeout is None else timeout
        self.ssl = ssl

    async def _connect_handshake(self, reader, writer, hostname):
        hostname_blob = b'' if hostname is None else hostname.encode('utf8')
        hostname_len_blob = len(hostname_blob).to_bytes(1, byteorder='big')
        writer.write(hostname_len_blob)
        writer.write(hostname_blob)
        hb_timeout_blob = await wait_for(reader.readexactly(2), self.timeout)
        return int.from_bytes(hb_timeout_blob, byteorder='big')
    
    async def _wait_on_host_keys(self, reader, writer, hb_timeout):
        host_keys_len_blob = await wait_for(reader.readexactly(3), hb_timeout * 2)
        host_keys_len = int.from_bytes(host_keys_len_blob, byteorder='big')
        if host_keys_len == 0:
            host_keys = None
        else:
            host_keys_blob = await wait_for(reader.readexactly(host_keys_len), self.timeout)
            host_keys = json.loads(host_keys_blob)
        writer.write(nil)
        return host_keys
   
    async def loop(self, *, hostname=None):
        reader, writer = await wait_for(asyncio.open_connection(
                self.endpoint[0], self.endpoint[1], ssl=self.ssl), self.timeout)
        try:
            hb_timeout = await self._connect_handshake(reader, writer, hostname)
            previous = None
            while True:
                host_keys = await self._wait_on_host_keys(reader, writer, hb_timeout)
                if host_keys is not None:
                    if host_keys == previous:
                        logging.debug('skipping duplicate')
                    else:
                        yield host_keys
                        previous = host_keys
        finally:
            writer.close()

    # TODO py310, use anext
    async def fetch(self, *, hostname=None):
        return await self.loop(hostname=hostname).__anext__()

def create_client(server, port, *, enable_ssl=True):
    if enable_ssl:
        ssl_ctx = ssl.create_default_context()
        server = default_ssl_server if server is None else server
        port = default_ssl_port if port is None else port
    else:
        ssl_ctx = None
        server = default_server if server is None else server
        port = default_port if port is None else port
    return Client(endpoint=(server, port), ssl=ssl_ctx)

async def loop(cb, *, server=None, port=None, hostname=None):
    client = create_client(server, port)
    async for host_keys in client.loop(hostname=hostname):
        await cb(host_keys)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', nargs='?', const='*', metavar='hostname')
    parser.add_argument('-l', nargs='?', const='*', metavar='hostname')
    parser.add_argument('-s', metavar='server')
    parser.add_argument('-p', type=int, metavar='port')
    parser.add_argument('--disable-ssl', action='store_true')
    args = parser.parse_args()

    enable_ssl = not args.disable_ssl
    client = create_client(args.s, args.p, enable_ssl=enable_ssl)

    if args.f:
        host_keys = await client.fetch(hostname=args.f)
        print(json.dumps(host_keys, indent=2, sort_keys=True))
    elif args.l:
        async for host_keys in client.loop(hostname=args.l):
            print(json.dumps(host_keys, indent=2, sort_keys=True))
    else:
        raise Exception("please specify action")


if __name__ == '__main__':
    uvloop.install()
    asyncio.run(main())
