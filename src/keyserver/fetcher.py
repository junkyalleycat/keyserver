#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import signal
import socket
import uvloop
from pathlib import *

from . import client

default_keydir = Path('/var/db/sshkeys')

async def main():
    logging.basicConfig(level=logging.INFO)

    loop = asyncio.get_event_loop()
    finish = asyncio.Event()

    loop.add_signal_handler(signal.SIGINT, finish.set)
    loop.add_signal_handler(signal.SIGTERM, finish.set)

    def uncaught_exception(loop, context):
        loop.default_exception_handler(context)
        finish.set()

    loop.set_exception_handler(uncaught_exception)

    parser = argparse.ArgumentParser()
    parser.add_argument('-k', type=Path, default=default_keydir, metavar='keydir')
    parser.add_argument('-s', metavar='server')
    parser.add_argument('-p', type=int, metavar='port')
    parser.add_argument('--fqdn', default=socket.getfqdn(), metavar='fqdn')
    parser.add_argument('-d', action='store_true', help='debug')
    args = parser.parse_args()

    if args.d:
        logging.root.setLevel(logging.DEBUG)
    
    keydir = args.k
    server = args.s
    port = args.p
    fqdn = args.fqdn

    keydir.mkdir(parents=True, exist_ok=True)

    async def cb(host_keys):
        if len(host_keys) == 0:
            logging.warn('0 host keys found, ignoring')
            return
        for keys_file in keydir.iterdir():
            if keys_file.suffix != '.keys':
                continue
            user = keys_file.stem
            if user not in host_keys:
                logging.debug(f'unlink({keys_file})')
                keys_file.unlink()
        for user, keys in host_keys.items():
            keys_file = keydir.joinpath(f'{user}.keys')
            data = '\n'.join(keys)
            keys_file.write_text(data)

    async def listener():
        while not finish.is_set():
            try:
                await client.loop(cb, server=server, port=port, hostname=fqdn)
            except asyncio.TimeoutError:
                logging.error("read timeout")
            except asyncio.IncompleteReadError as e:
                logging.error(e)
            except ConnectionRefusedError as e:
                logging.error(e)
            except socket.gaierror as e:
                logging.error(e)
            except Exception as e:
                logging.exception(e)
            await asyncio.sleep(1)

    asyncio.create_task(listener())

    await finish.wait()


def entry():
    uvloop.install()
    asyncio.run(main())

