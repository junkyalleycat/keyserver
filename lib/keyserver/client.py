#!/usr/bin/env python3

import logging
import asyncio
import argparse
import json
from asyncio import wait_for

default_port = 8282
default_server = 'keyserver'
timeout = 5

nil = chr(0).encode('ascii')
async def loop(cb, *, server=None, port=None, hostname=None):
    server = default_server if server is None else server
    port = default_port if port is None else port
    reader, writer = await wait_for(asyncio.open_connection(server, port), timeout)
    try:
        hostname_blob = b'' if hostname is None else hostname.encode('utf8')
        hostname_len_blob = len(hostname_blob).to_bytes(1, byteorder='big')
        writer.write(hostname_len_blob)
        writer.write(hostname_blob)
        hb_timeout_blob = await wait_for(reader.readexactly(2), timeout)
        hb_timeout = int.from_bytes(hb_timeout_blob, byteorder='big')
        while True:
            host_keys_len_blob = await wait_for(reader.readexactly(3), hb_timeout*2)
            host_keys_len = int.from_bytes(host_keys_len_blob, byteorder='big')
            if host_keys_len == 0:
                logging.debug("ping!")
            else:
                host_keys_blob = await wait_for(reader.readexactly(host_keys_len), timeout)
                host_keys = json.loads(host_keys_blob)
                await cb(host_keys)
            writer.write(nil)
    finally:
        writer.close()

async def fetch(*, server=None, port=None, hostname=None):
    ev = asyncio.Event()
    host_keys = None
    async def cb(host_keys_):
        nonlocal host_keys
        host_keys = host_keys_
        ev.set()
    loop_task = asyncio.create_task(loop(cb, server=server, port=port, hostname=hostname))
    done, _ = await asyncio.wait([ev.wait(), loop_task], return_when=asyncio.FIRST_COMPLETED)
    if loop_task in done:
        await loop_task
    loop_task.cancel()
    return host_keys

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', nargs='?', const='*', metavar='hostname')
    parser.add_argument('-l', nargs='?', const='*', metavar='hostname')
    parser.add_argument('-s', metavar='server')
    parser.add_argument('-p', type=int, metavar='port')
    args = parser.parse_args()
    server = args.s
    port = args.p
    
    if args.f:
        hostname = args.f
        host_keys = await fetch(server=server, port=port, hostname=hostname) 
        print(json.dumps(host_keys, indent=2, sort_keys=True))
    elif args.l:
        hostname = args.l
        async def cb(host_keys):
            print(json.dumps(host_keys, indent=2, sort_keys=True))
        await loop(cb, server=server, port=port, hostname=hostname)
    else:
        raise Exception("please specify action")
