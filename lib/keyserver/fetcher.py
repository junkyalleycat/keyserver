#!/usr/bin/env python3

import os
import socket
import logging
import asyncio
import json
import argparse

from . import client

default_keydir = '/var/db/sshkeys'

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', default=default_keydir, metavar='keydir')
    parser.add_argument('-s', metavar='server')
    parser.add_argument('-p', type=int, metavar='port')
    args = parser.parse_args()

    keydir = args.k
    server = args.s
    port = args.p

    os.makedirs(keydir, exist_ok=True)

    previous = None
    while True:
        try:
            async def cb(host_keys):
                nonlocal previous
                if host_keys == previous:
                    logging.info('no changes detected, ignoring')
                    return
                elif len(host_keys) == 0:
                    logging.warn('0 host keys found, ignoring')
                    return
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
            hostname = socket.getfqdn()
            await client.loop(cb, server=server, port=port, hostname=hostname)
        except asyncio.TimeoutError:
            logging.error("read timeout")
        except asyncio.IncompleteReadError as e:
            logging.error(e)
        except ConnectionRefusedError as e:
            logging.error(e)
        except Exception as e:
            logging.exception(e)
        await asyncio.sleep(1)
