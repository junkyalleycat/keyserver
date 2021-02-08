#!/usr/bin/env python3

import os
import socket
import logging
import asyncio

from . import client

keydir = '/var/db/sshkeys'
server = 'raincity.lan'

async def main():
    os.makedirs(keydir, exist_ok=True)

    previous = None
    while True:
        try:
            hostname = socket.gethostname()
            host_keys = await client.fetch(server=server, hostname=hostname)
            if host_keys == previous:
                logging.info('no changes detected, ignoring')
            elif len(host_keys) == 0:
                logging.warn('0 host keys found, ignoring')
            else:
                for keys_file in os.listdir(keydir):
                    user, ext = os.path.splitext(keys_file)
                    if ext != '.keys':
                        continue
                    if user not in host_keys:
                        os.unlink("%s/%s" % (keydir, keys_file))
                for user, user_keys in host_keys.items():
                    keys_file = "%s/%s.keys" % (keydir, user)
                    keys_file_tmp = "%s.tmp" % keys_file
                    with open(keys_file_tmp, 'w') as out:
                        for key in user_keys:
                            out.write("%s\n" % key)
                    os.rename(keys_file_tmp, keys_file)
                previous = host_keys
        except Exception as e:
            logging.exception(e)
        await asyncio.sleep(1)
