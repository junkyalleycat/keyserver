#!/usr/bin/env python3

import os
import socket
import logging
import asyncio
import json
import argparse

from . import client

default_config_file = '/usr/local/etc/keyfetcher.yaml'
default_keydir = '/var/db/sshkeys'
default_server = 'keyserver'
# TODO increase
default_period = 10

class Config:

    def __init__(self, filename):
        try:
            with open(filename, 'r') as in_:
                self.config = yaml.load(in_.read())
        except FileNotFoundError:
            self.config = {}

    def get(self, key, default=None):
        if key in self.config:
            return self.config[key]
        if default is None:
            raise KeyError(key)
        return default

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', default=default_config_file, metavar='config')
    args = parser.parse_args()

    config = Config(args.c)
    keydir = config.get('keydir', default=default_keydir)
    server = config.get('server', default=default_server)
    period = config.get('period', default=default_period)

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
        await asyncio.sleep(period)
