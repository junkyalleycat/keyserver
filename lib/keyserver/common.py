#!/usr/bin/env python3

default_port = 8282

nil = b'\0'

def parse_domain(domain):
    user, host = domain.split('@')
    return (user, host)
