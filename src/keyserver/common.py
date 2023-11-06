#!/usr/bin/env python3

default_port = 8282
default_ssl_port = 8283

nil = b'\0'

def parse_domain(domain):
    user, host = domain.split('@')
    return (user, host)

class SSHKey:

    def __init__(self, data):
        keytype, keydata, comment = data.split()
        self.comment = comment
