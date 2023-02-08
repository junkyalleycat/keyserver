#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import signal
from asyncio import wait_for
import uvloop
import yaml
import glob

keydb = '/var/db/keyserver.db'
enable_monitor = True
timeout = 5
hb_timeout = 60
default_port = 8282


def parse_domain(domain):
    user, host = domain.split('@')
    return (user, host,)

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

class Keys:

    def __init__(self):
        self.keys = {}

    @staticmethod
    async def create():
        keys = Keys()
        keys.reload()
        return keys

    def reload(self):
        if os.path.exists(keydb):
            with open(keydb, 'r') as infile:
                db = json.load(infile)
        else:
            db = {'keys':{}}
        keys = {}
        wild = {}
        # keys = hostname->user->keys[]
        # wild = user->keys[]
        for _, key in db['keys'].items():
            keydata = key['data']
            for domain in key['domains']:
                user, host = parse_domain(domain)
                if host == '*':
                    userkeys = wild.setdefault(user, set())
                    userkeys.add(keydata)
                else:
                    hostkeys = keys.setdefault(host, {})
                    userkeys = hostkeys.setdefault(user, set())
                    userkeys.add(keydata)
        flat_keys = {}
        flat_keys['*'] = json.dumps(wild, cls=SetEncoder).encode('utf-8')
        for host, users in keys.items():
            for wilduser, wilduserkeys in wild.items():
                userkeys = users.setdefault(wilduser, set())
                userkeys |= wilduserkeys
            flat_keys[host] = json.dumps(users, cls=SetEncoder).encode('utf-8')
        self.keys = flat_keys

    def get_host_keys(self, *, hostname=None):
        if hostname is None:
            return self.keys['*']
        if hostname in self.keys:
            return self.keys[hostname]
        return self.keys['*']

nil = chr(0).encode('ascii')

async def handle_client(keys, reader, writer, sem):
    hostname_len_blob = await wait_for(reader.readexactly(1), timeout)
    hostname_len = int.from_bytes(hostname_len_blob, byteorder='big')
    if hostname_len == 0:
        hostname = None
    else:
        hostname_blob = await wait_for(reader.readexactly(hostname_len), timeout)
        hostname = hostname_blob.decode('utf8')
    writer.write(hb_timeout.to_bytes(2, byteorder='big'))
    while True:
        try:
            await wait_for(sem.acquire(), hb_timeout)
            host_keys_blob = keys.get_host_keys(hostname=hostname)
            writer.write(len(host_keys_blob).to_bytes(3, byteorder='big'))
            writer.write(host_keys_blob)
        except asyncio.TimeoutError:
            writer.write((0).to_bytes(3, byteorder='big'))
        ack = await wait_for(reader.readexactly(1), timeout)
        if ack != nil:
            raise Exception("invalid ack: %s" % ack)


async def main():
    logging.basicConfig(level=logging.INFO)

    loop = asyncio.get_event_loop()
    finish = asyncio.Event()

    def on_signal(*args):
        finish.set()

    loop.add_signal_handler(signal.SIGINT, on_signal)
    loop.add_signal_handler(signal.SIGTERM, on_signal)

    def uncaught_exception(loop, context):
        try:
            loop.default_exception_handler(context)
        except Exception as e:
            logging.error(e)
        finally:
            finish.set()

    loop.set_exception_handler(uncaught_exception)

    keys = await Keys.create()

    peers = {}

    async def handler(reader, writer):
        try:
            peer = writer.get_extra_info('peername')
            sem = asyncio.Semaphore(1)
            peers[peer] = sem
            await handle_client(keys, reader, writer, sem)
        except asyncio.TimeoutError:
            logging.info("timeout for peer: %s" % str(peer))
        except asyncio.IncompleteReadError:
            pass
        except ConnectionResetError:
            pass
        except Exception as e:
            logging.exception(e)
        finally:
            if peer in peers:
                del peers[peer]
            writer.close()

    await asyncio.start_server(handler, '0.0.0.0', default_port)

    def reload_handler(*args):
        keys.reload()
        for sem in peers.values():
            sem.release()
    loop.add_signal_handler(signal.SIGUSR1, reload_handler)

    await finish.wait()

if __name__ == '__main__':
    uvloop.install()
    asyncio.run(main())
