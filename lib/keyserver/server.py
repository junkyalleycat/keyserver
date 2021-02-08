#!/usr/bin/env python3

import signal
import sys
import asyncio
import logging
import yaml
import json

keydb = '/var/db/keyserver.db'

class Keys:

    def __init__(self):
        self.keys = Keys.load()

#keys = hostname -> user, keys
#host_keys = user, keys
#user_keys = keys
#key = key

    @staticmethod
    def load():
        with open(keydb, 'r') as in_:
            keys_data = in_.read()
        pre_flat_keys = yaml.load(keys_data, Loader=yaml.FullLoader)

        def resolve(host_keys, pre_host_keys):
            for user, pre_user_keys in pre_host_keys.items():
                if len(pre_user_keys) == 0:
                    continue
                if user not in host_keys:
                    host_keys[user] = []
                user_keys = host_keys[user]
                for pre_key in pre_user_keys:
                    if pre_key.startswith('file!'):
                        with open(pre_key[5:], 'r') as in_:
                            key = in_.read().rstrip()
                    else:
                        key = pre_key
                    if key not in user_keys:
                        user_keys.append(key)

        star_host_keys = {}
        if '*' in pre_flat_keys:
            resolve(star_host_keys, pre_flat_keys['*'])

        keys = {}
        keys['*'] = star_host_keys
        for hostname, pre_host_keys in pre_flat_keys.items():
            if hostname == '*':
                continue
            host_keys = {}
            keys[hostname] = host_keys
            for user, user_keys in star_host_keys.items():
                host_keys[user] = list(user_keys)
            resolve(host_keys, pre_host_keys)

        return keys

    def reload(self):
        try:
            self.keys = Keys.load()
        except Exception as e:
            logging.error(e)

    def get_host_keys(self, *, hostname=None):
        if hostname is None:
            return self.keys['*']
        if hostname in self.keys:
            return self.keys[hostname]
        return self.keys['*']

async def main():
    logging.basicConfig(level=logging.INFO)

    loop = asyncio.get_event_loop()
    finish = asyncio.Event()

    def on_signal(*args):
        finish.set()
    loop.add_signal_handler(signal.SIGINT, on_signal)
    loop.add_signal_handler(signal.SIGTERM, on_signal)

    uncaught = None
    def uncaught_exception(loop, context):
        try:
            loop.default_exception_handler(context)
        except Exception as e:
            logging.error(e)
        finally:
            finish.set()
    loop.set_exception_handler(uncaught_exception)

    keys = Keys()

    def reload_handler(*args):
        keys.reload()
    loop.add_signal_handler(signal.SIGUSR1, reload_handler)

    async def handler(reader, writer):
        try:
            while True:
                hostname_len = int.from_bytes(await reader.readexactly(1), byteorder='big')
                if hostname_len == 0:
                    hostname = None
                else:
                    hostname = (await reader.readexactly(hostname_len)).decode('utf8')
                host_keys = keys.get_host_keys(hostname=hostname)
                host_keys_blob = json.dumps(host_keys).encode('utf8')
                writer.write(len(host_keys_blob).to_bytes(2, byteorder='big'))
                writer.write(host_keys_blob)
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            logging.error(e)
        finally:
            writer.close()
    await asyncio.start_server(handler, '0.0.0.0', 8282)

    await finish.wait()
