"""An SSL context that completes a server's chain from vendored intermediates.

A server must send the intermediate certificates between its own and a
root. www.elections.alaska.gov sends the wrong one: its certificate is
issued by "GlobalSign GCC R46 OV TLS CA 2025" and it sends "GlobalSign RSA
OV SSL CA 2018" with it. A browser fetches the missing intermediate from the
certificate's Authority Information Access; Python does not, so every read
of Alaska's certified list, its guide's statements and its voting links
failed with "unable to get local issuer certificate" on the GitHub runner,
and the site kept 2026-10-17's list (rule 8, rule 77).

:func:`context` is ``ssl.create_default_context()`` - the system's roots,
certificate and hostname verification on - with the intermediates under
``kyc/certs/`` added to its store. An intermediate is not a root: since
Python 3.13 the default context sets ``VERIFY_X509_PARTIAL_CHAIN``, which
would make any certificate in the store an anchor of its own, so this
context clears it, and OpenSSL uses the intermediate only to build a chain
that still ends at a self-signed root the system trusts. Adding one
completes the chains it signs and trusts nothing more. Each file names
where it came from, its fingerprints and how it was checked.

Never ``CERT_NONE``, never ``check_hostname = False``, never a global
default context: a server that sends the wrong intermediate is completed
from its own certificate's issuer, never trusted less.
"""

import functools
import pathlib
import re
import ssl

CERTS = pathlib.Path(__file__).with_name("certs")

_BLOCK = re.compile(r"-----BEGIN CERTIFICATE-----\n.+?\n-----END CERTIFICATE-----",
                    re.S)


def intermediates():
    """The vendored certificates as PEM text, comment headers left out."""
    blocks = []
    for path in sorted(CERTS.glob("*.pem")):
        text = path.read_text(encoding="ascii").replace("\r\n", "\n")
        found = _BLOCK.findall(text)
        if not found:
            raise ValueError(f"{path} holds no certificate")
        blocks.extend(found)
    return "\n".join(blocks) + "\n"


@functools.lru_cache(maxsize=None)
def _cadata():
    return intermediates()


def context(cafile=None):
    """A new verifying client context with the vendored intermediates.
    *cafile* replaces the system's roots (the tests' and a local proof's
    way to stand where the runner stands); ``None`` is the system's."""
    ctx = ssl.create_default_context(cafile=cafile)
    ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0)
    ctx.load_verify_locations(cadata=_cadata())
    return ctx
