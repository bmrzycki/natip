#!/usr/bin/env python3

import argparse

from ipaddress import IPv4Address
from pathlib import Path
from random import choice
from shutil import which
from signal import signal, SIGPIPE, SIG_DFL
from subprocess import run
from sys import argv
from urllib.parse import urlparse
from urllib.request import urlopen

VERBOSE = 0

class NATAddressWWW:
    def __init__(self, url, timeout=5):
        self.url = url
        self.timeout = timeout

    def get(self):
        if VERBOSE > 1:
            print(f"# www: {self.url}")
        try:
            rsp = urlopen(url=self.url, timeout=self.timeout)
        except Exception as e:
            return False, f"{e} url='{self.url}'"
        if rsp.status != 200:
            return False, "status {rsp.status} url='{self.url}'"
        try:
            ip = rsp.read().decode('ascii').strip()
        except Exception as e:
            return False, f"{e} url='{self.url}'"
        return True, ip


class NATAddressDNS:
    def __init__(self, dig_bin, servers, dns_name,
                 dns_class='', dns_type='', timeout=5):
        self.dig_bin = dig_bin
        self.servers = servers
        self.dns_name = dns_name
        self.dns_class = dns_class
        self.dns_type = dns_type
        self.timeout = timeout

    def get(self):
        cmd = [ self.dig_bin, f"@{choice(self.servers)}" ]
        if self.dns_class:
            cmd += [ '-c', self.dns_class ]
        if self.dns_type:
            cmd += [ '-t', self.dns_type ]
        cmd += [ '-q', self.dns_name, "+short", f"+time={self.timeout}" ]

        if VERBOSE > 1:
            print(f"# DNS: {' '.join(cmd)}")
        try:
            cp = run(cmd, check=True, universal_newlines=True,
                     capture_output=True)
        except Exception as e:
            return False, f"DNS exception {e} cmd={cmd}"
        # Remove '"' characters and any prefix words. The currently supported
        # services alaways place the returned IP last separated by spaces
        # on the first line (when using +short with dig).
        try:
            ip = cp.stdout.split('\n')[0].replace('"', '').split()[-1]
        except Exception as e:
            return False, f"DNS dig response {e} cmd={cmd}"
        return True, ip


class NATAddressSTUN:
    def __init__(self, stunip_bin, server, timeout=5):
        self.stunip_bin = stunip_bin
        self.server = server
        self.timeout = timeout

    def get(self):
        cmd = [ self.stunip_bin, '-t', '1', '-m', str(self.timeout),
                self.server ]
        if VERBOSE > 1:
            print(f"# STUN: {' '.join(cmd)}")
        try:
            cp = run(cmd, check=True, universal_newlines=True,
                     capture_output=True)
        except Exception as e:
            return False, f"STUN exception {e} cmd={cmd}"
        try:
            ip = cp.stdout.split('\n')[0].strip()
        except Exception as e:
            return False, f"STUN stunip.py response {e} cmd={cmd}"
        return True, ip


class NATAddress:
    def __init__(self, dig_bin='', stunip_bin='', timeout=5):
        self.dig_bin = dig_bin
        self.stunip_bin = stunip_bin
        self.timeout = timeout
        self._objs = {}

    def names(self, sort=True):
        n = list(self._objs)
        if sort:
            n = sorted(n)
        return n

    def get(self, name=''):
        if not self._objs:
            return False, f"no resolvers available"
        if not name:
            name = choice(self.names(sort=False))
        o = self._objs.get(name, None)
        if o is None:
            return False, f"invalid name '{name}'"
        if VERBOSE > 0:
            print(f"# name: {name}")
        ok, msg = o.get()
        if not ok:
            return False, msg
        try:
            ip = IPv4Address(msg)
        except Exception as e:
            return False, f"IPv4 Address exception {e} for ip='{msg}'"
        return True, str(ip)

    def add_www(self, url, name=''):
        if not name:
            o = urlparse(url)
            # Obtain domain just below the tld, w/o the port num
            name = o.netloc.split(':')[0].split('.')[-2]
        name = f"www_{name}"
        if name in self._objs:
                raise RuntimeError(f"duplicate name '{name}'")
        self._objs[name] = NATAddressWWW(url=url, timeout=self.timeout)

    def add_dns(self, servers, dns_name, dns_class='', dns_type='', name=''):
        if not self.dig_bin:
            return
        if not name:
            name = dns_name.split('.')[-2]
        name = f"dns_{name}"
        if name in self._objs:
            raise RuntimeError(f"duplicate name '{name}'")
        self._objs[name] = NATAddressDNS(
            dig_bin=self.dig_bin, servers=servers, dns_name=dns_name,
            dns_class=dns_class, dns_type=dns_type, timeout=self.timeout)

    def add_stun(self, server, name=''):
        if not self.stunip_bin:
            return
        if not name:
            # Obtain domain just below the tld, w/o the port num
            name = server.split(':')[0].split('.')[-2]
        name = f"stun_{name}"
        if name in self._objs:
            raise RuntimeError(f"duplicate name '{name}'")
        self._objs[name] = NATAddressSTUN(
            stunip_bin=self.stunip_bin, server=server,
            timeout=self.timeout)


def main(args_raw):
    global VERBOSE
    p = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='IPv4 NAT address lookup tool')
    p.add_argument(
        '-l', '--list',
        default=False, action='store_true',
        help='only list lookup resolvers')
    p.add_argument(
        '-n', '--name',
        default='',
        help='when set uses specific "name" lookup')
    p.add_argument(
        '-t', '--timeout',
        default=5, type=int,
        help='timeout (in seconds) to wait for a response')
    p.add_argument(
        '-d', '--disable',
        default=[], action='append',
        help='disable resolver "name" from being used')
    p.add_argument(
        '-v', '--verbose',
        default=VERBOSE, action='count',
        help='verbosity, repeat to increase')
    p.add_argument(
        '--dig-bin',
        default='dig',
        help='full path to "dig" binary, empty disables DNS')
    p.add_argument(
        '--stunip-bin',
        default='stunip.py',
        help='full path to "stunip.py" binary, empty disables STUN')
    args = p.parse_args(args_raw)
    VERBOSE = args.verbose

    if args.dig_bin:
        dig = which(args.dig_bin)
        if dig is None:
            args.dig_bin = ''
        else:
            args.dig_bin = str(Path(dig).resolve())
    if args.stunip_bin:
        stunip = which(args.stunip_bin)
        if stunip is None:
            args.stunip_bin = ''
        else:
            args.stunip_bin = str(Path(stunip).resolve())

    na = NATAddress(dig_bin=args.dig_bin, stunip_bin=args.stunip_bin,
                    timeout=args.timeout)

    na.add_www('http://whatismyip.akamai.com')
    na.add_www('http://checkip.amazonaws.com')
    na.add_www('http://curlmyip.net')
    na.add_www('http://icanhazip.com')
    na.add_www('http://v4.ident.me')
    na.add_www('http://ifconfig.me')
    na.add_www('https://ip-addr.es')
    na.add_www('http://ipecho.net/plain')
    na.add_www('https://api.ipify.org')
    na.add_www('http://ipinfo.io/ip')
    na.add_www('http://4.ipquail.com/ip')
    na.add_www('http://myexternalip.com/raw')
    na.add_www('https://ipaddr.pub/cli', name='ipaddr-pub')
    na.add_www('https://myip.dnsomatic.com')

    # https://bit.ly/2AHfQMb
    # nameservers discovered via:
    #  curl -s https://rdap.verisign.com/net/v1/domain/akamaitech.net |
    #    jq -r .nameservers[].ldhName | tr '[A-Z]' '[a-z]' | grep ^ns
    na.add_dns(servers=['ns1-1.akamaitech.net', 'ns2-193.akamaitech.net',
                        'ns3-193.akamaitech.net', 'ns4-193.akamaitech.net',
                        'ns5-193.akamaitech.net'],
               dns_name='whoami.akamai.net')
    # https://bit.ly/2AHfQMb
    # nameserver discovered via:
    #  curl -s https://rdap.verisign.com/net/v1/domain/akam.net |
    #    jq -r .nameservers[].ldhName | tr '[A-Z]' '[a-z]'
    na.add_dns(servers=['a1-67.akam.net', 'a11-67.akam.net',
                        'a12-67.akam.net', 'a13-67.akam.net',
                        'a18-67.akam.net', 'a22-67.akam.net',
                        'a28-67.akam.net', 'a3-67.akam.net',
                        'a4-67.akam.net', 'a5-67.akam.net',
                        'a6-67.akam.net', 'a7-67.akam.net',
                        'a9-67.akam.net'],
               dns_name='whoami.ds.akahelp.net', dns_type='txt')
    # https://bit.ly/3AUhNzS
    na.add_dns(servers=['1.1.1.1', '1.0.0.1'], dns_class='ch',
               dns_name='whoami.cloudflare', dns_type='txt',
               name='cloudflare')
    # https://gist.github.com/ipoddubny/27111c83c3a2870a55e1
    na.add_dns(servers=['ns1.google.com', 'ns2.google.com',
                        'ns3.google.com', 'ns4.google.com' ],
               dns_name='o-o.myaddr.l.google.com', dns_type='txt')

    # STUN servers curated from:
    #  https://github.com/pradt2/always-online-stun/blob/master/valid_hosts.txt
    na.add_stun('stun1.l.google.com:19302', name='google-1')
    na.add_stun('stun2.l.google.com:19302', name='google-2')
    na.add_stun('stun3.l.google.com:19302', name='google-3')
    na.add_stun('stun4.l.google.com:19302', name='google-4')
    na.add_stun('stun.acronis.com')
    na.add_stun('stun.bethesda.net')
    na.add_stun('stun.callwithus.com')
    na.add_stun('stun.counterpath.net')
    na.add_stun('stun.easyvoip.com')
    na.add_stun('stun.ekiga.net')
    na.add_stun('stun.gmx.net')
    na.add_stun('stun.intervoip.com')
    na.add_stun('stun.ooma.com')
    na.add_stun('stun.poivy.com')
    na.add_stun('stun.sipgate.net')
    na.add_stun('stun.siptraffic.com')
    na.add_stun('stun.sonetel.com')
    na.add_stun('stun.stunprotocol.org')
    na.add_stun('stun.vivox.com')
    na.add_stun('stun.voipbuster.com')
    na.add_stun('stun.voipgate.com')
    na.add_stun('stun.voipstunt.com')
    na.add_stun('stun.xten.com')

    if args.list:
        print('\n'.join(na.names()))
        return

    if args.disable:
        if args.name and args.name in args.disable:
            p.error(f"name '{args.name}' disabled by user")
        tmp = set(na.names(sort=False)) - set(args.disable)
        if not tmp:
            p.error("all resolvers disabled")
        args.name = choice(list(tmp))

    ok, msg = na.get(name=args.name)
    if not ok:
        p.error(msg)
    print(msg)


if __name__ == '__main__':
    signal(SIGPIPE, SIG_DFL)  # Avoid exceptions for broken pipes
    main(argv[1:])
