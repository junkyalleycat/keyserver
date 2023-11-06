#!/usr/bin/env python3

from .common import *
import os
import asyncio
import argparse
import json
import keyserver.client
import signal
from pathlib import *

keydb=Path('/var/db/keyserver.db')
pidfile=Path('/var/run/keyserver.pid.child')

def validate_domains(domains):
    for domain in domains:
        parse_domain(domain)

def read_db():
    if keydb.exists():
        db = json.loads(keydb.read_text())
    else:
        db = {}
    db.setdefault('keys', {})
    return db

def write_db(db):
    keydb.write_text(json.dumps(db))
    reload_db()

def reload_db():
    pid = int(pidfile.read_text().strip())
    os.kill(pid, signal.SIGUSR1)

def out(data):
    print(json.dumps(data, indent=4))

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')

    add_key_parser = subparsers.add_parser('add-key')
    add_key_parser.add_argument('--name', metavar='name')
    add_key_parser.add_argument('--keyfile', type=Path, metavar='keyfile')
    add_key_parser.add_argument('--keydata', metavar='keydata')
    add_key_parser.add_argument('--domain', action='append', default=[], metavar='domain')
    add_key_parser.add_argument('--option', action='append', default=[], metavar='option')

    update_key_parser = subparsers.add_parser('update-key')
    update_key_parser.add_argument('--name', metavar='name', required=True)
    update_key_parser.add_argument('--keyfile', type=Path, metavar='keyfile')
    update_key_parser.add_argument('--keydata', metavar='keydata')
    update_key_parser.add_argument('--add-domain', action='append', default=[], metavar='domain')
    update_key_parser.add_argument('--remove-domain', action='append', default=[], metavar='domain')
    update_key_parser.add_argument('--rename', metavar='name')
    update_key_parser.add_argument('--add-option', action='append', default=[], metavar='option')
    update_key_parser.add_argument('--remove-option', action='append', default=[], metavar='option')

    describe_key_parser = subparsers.add_parser('describe-key')
    describe_key_parser.add_argument('--name', metavar='name', required=True)

    list_keys_parser = subparsers.add_parser('list-keys')
    list_keys_parser.add_argument('--domain', metavar='domain')
    list_keys_parser.add_argument('--host', metavar='host')
    list_keys_parser.add_argument('--user', metavar='user')

    remove_key_parser = subparsers.add_parser('remove-key')
    remove_key_parser.add_argument('--name', metavar='name', required=True)

    reload_parser = subparsers.add_parser('reload')

    args = parser.parse_args()

    db = read_db()

    if args.action == 'add-key':
        if args.keyfile:
            keydata = args.keyfile.read_text()
        elif args.keydata:
            keydata = args.keydata
        else:
            raise Exception("keyfile or keydata required")
        key = SSHKey(keydata)
        if args.name:
            name = args.name
        else:
            name = key.comment
        if name in db:
            raise Exception("key already exists: %s" % name)
        db['keys'][name] = {}
        db['keys'][name]['data'] = keydata
        validate_domains(args.domain)
        db['keys'][name]['domains'] = args.domain
        db['keys'][name]['options'] = args.option
        write_db(db)
    elif args.action == 'describe-key':
        out(db['keys'][args.name])
    elif args.action == 'update-key':
        name = args.name
        keydata = db['keys'][name]['data']
        if args.keyfile:
            keydata = args.keyfile.read_text()
        elif args.keydata:
            keydata = keydata
        SSHKey(keydata)
        db['keys'][name]['data'] = keydata

        domains = set(db['keys'][name]['domains'])
        validate_domains(args.remove_domain)
        domains -= set(args.remove_domain)
        validate_domains(args.add_domain)
        domains |= set(args.add_domain)
        db['keys'][name]['domains'] = list(domains)

        options = set(db['keys'][name].get('options', []))
        options -= set(args.remove_option)
        options |= set(args.add_option)
        db['keys'][name]['options'] = list(options)

        if args.rename:
            db['keys'][args.rename] = db['keys'][name]
            del db['keys'][name]
        write_db(db)
    elif args.action == 'list-keys':
        names = set()
        for name, key in db['keys'].items():
            if args.domain:
                for domain in key['domains']:
                    if domain == args.domain:
                        names.add(name)
            elif args.host:
                for domain in key['domains']:
                    _, host = parse_domain(domain)
                    if host == args.host:
                        names.add(name)
                    elif host == '*':
                        names.add(name)
            elif args.user:
                for domain in key['domains']:
                    user, _ = parse_domain(domain)
                    if user == args.user:
                        names.add(name)
            else:
                names.add(name)
        output = list(names)
        output.sort()
        out(output)
    elif args.action == 'remove-key':
        del db['keys'][args.name]
        write_db(db)
    elif args.action == 'reload':
        reload_db()
    else:
        raise Exception("action not specified")

