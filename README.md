# natip
Obtain an externally routable IPv4 address using multiple resolvers.
The tool always supports HTTP/HTTPS (www) resolution using several
free sources.

The tool randomly selects a NAT resolver to obtain your IPv4 address.
This reduces the chances your infrastructure will fail if the upstream
resolver is down and also reduces your bandwidth to any one resolver.

There are arguments to select exactly one resolver or to remove 1+
resolver for debug or personal preference.

If the [BIND 9+|https://www.isc.org/bind/] `dig` client is in
your `PATH`, or specified with `--dig-bin`, additional DNS
resolution methods are added.

Finally, if [stunip|https://github.com/bmrzycki/stunip] `stunip.py`
is in your `PATH`, or specified with `--stunip-bin`, additional STUN
resolution methods are added.

## Installation

`natip.py` is self-contained and only needs Python 3. The simplest
use-case is to `git clone` this repo and run directly.
