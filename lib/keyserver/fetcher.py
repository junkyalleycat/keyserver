#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import signal
import socket
import uvloop

from . import client

default_keydir = '/var/db/sshkeys'


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

    parser = argparse.ArgumentParser()
    parser.add_argument('-k', default=default_keydir, metavar='keydir')
    parser.add_argument('-s', metavar='server')
    parser.add_argument('-p', type=int, metavar='port')
    args = parser.parse_args()

    keydir = args.k
    server = args.s
    port = args.p

    os.makedirs(keydir, exist_ok=True)

    async def cb(host_keys):
        if len(host_keys) == 0:
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

    async def listener():
        while not finish.is_set():
            hostname = socket.getfqdn()
            try:
                await client.loop(cb, server=server, port=port, hostname=hostname)
            except asyncio.TimeoutError:
                logging.error("read timeout")
            except asyncio.IncompleteReadError as e:
                logging.error(e)
            except ConnectionRefusedError as e:
                logging.error(e)
            except socket.gaierror as e:
                logging.error(e)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logging.exception(e)
            await asyncio.sleep(1)

    asyncio.create_task(listener())

    await finish.wait()


if __name__ == '__main__':
    uvloop.install()
    asyncio.run(main())
