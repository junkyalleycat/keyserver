#!/usr/bin/env python3

import os
import asyncio
import argparse
import sshpubkeys
import yaml
import json
import keyserver.client

keydb='/var/db/keyserver2.db'

def parse_domain(domain):
    host, name = domain.split(':')
    return (host, name,)

def validate_domains(domains):
    for domain in domains:
        parse_domain(domain)

def read_db():
    if os.path.exists(keydb):
        with open(keydb, 'r') as infile:
            db = json.load(infile)
    else:
        db = {}
    db.setdefault('keys', {})
    return db

def write_db(db):
    data = json.dumps(db)
    with open(keydb, 'w') as outfile:
        outfile.write(data)

def out(data):
    print(json.dumps(data, indent=4))

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')

    add_key_parser = subparsers.add_parser('add-key')
    add_key_parser.add_argument('--name', metavar='name')
    add_key_parser.add_argument('--keyfile', metavar='keyfile')
    add_key_parser.add_argument('--keydata', metavar='keydata')
    add_key_parser.add_argument('--domain', action='append', default=[], metavar='domain')

    update_key_parser = subparsers.add_parser('update-key')
    update_key_parser.add_argument('--name', metavar='name', required=True)
    update_key_parser.add_argument('--keyfile', metavar='keyfile')
    update_key_parser.add_argument('--keydata', metavar='keydata')
    update_key_parser.add_argument('--add-domain', action='append', default=[], metavar='domain')
    update_key_parser.add_argument('--remove-domain', action='append', default=[], metavar='domain')
    update_key_parser.add_argument('--rename', metavar='name')

    describe_key_parser = subparsers.add_parser('describe-key')
    describe_key_parser.add_argument('--name', metavar='name', required=True)

    list_keys_parser = subparsers.add_parser('list-keys')
    list_keys_parser.add_argument('--domain', metavar='domain')
    list_keys_parser.add_argument('--host', metavar='host')
    list_keys_parser.add_argument('--user', metavar='user')

    remove_key_parser = subparsers.add_parser('remove-key')
    remove_key_parser.add_argument('--name', metavar='name', required=True)

    args = parser.parse_args()

    db = read_db()

    if args.action == 'add-key':
        if args.keyfile:
            with open(args.keyfile, 'r') as infile:
                keydata = infile.read()
        elif args.keydata:
            keydata = args.keydata
        else:
            raise Exception("keyfile or keydata required")
        key = sshpubkeys.SSHKey(keydata)
        if args.name:
            name = args.name
        else:
            name = key.comment
        if name in db.get('keys', {}):
            raise Exception("key already exists: %s" % name)
        db['keys'][name] = {}
        db['keys'][name]['data'] = keydata
        validate_domains(args.domain)
        db['keys'][name]['domains'] = args.domain
        write_db(db)
    elif args.action == 'describe-key':
        out(db['keys'][args.name])
    elif args.action == 'update-key':
        name = args.name
        keydata = db['keys'][name]['data']
        if args.keyfile:
            with open(args.keyfile, 'r') as infile:
                keydata = infile.read()
        elif args.keydata:
            keydata = keydata
        key = sshpubkeys.SSHKey(keydata)
        db['keys'][name]['data'] = keydata
        domains = set(db['keys'][name]['domains'])
        validate_domains(args.remove_domain)
        domains -= set(args.remove_domain)
        validate_domains(args.add_domain)
        domains |= set(args.add_domain)
        db['keys'][name]['domains'] = list(domains)
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
                    host, _ = parse_domain(domain)
                    if host == args.host:
                        names.add(name)
            elif args.user:
                for domain in key['domains']:
                    _, user = parse_domain(domain)
                    if user == args.user:
                        names.add(name)
            else:
                names.add(name)
        out(list(names))
    elif args.action == 'remove-key':
        del db['keys'][args.name]
        write_db(db)
    else:
        raise Exception("action not specified")

if __name__ == '__main__':
    main()
