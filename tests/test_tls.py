"""The vendored intermediate and the context that completes Alaska's chain.

www.elections.alaska.gov sends the wrong intermediate certificate, so every
read of it failed on the runner with "unable to get local issuer
certificate" (rule 8). kyc/tls.py completes the chain from the certificate's
own issuer and checks no less. These tests are offline."""

import hashlib
import os
import ssl
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import certified, guide_photos, tls, voting

PEM = os.path.join(os.path.dirname(tls.__file__), "certs",
                   "globalsign-gcc-r46-ov-tls-ca-2025.pem")
# The certificate's fingerprints as recorded in its header (checked against
# GlobalSign Root R46 and GlobalSign's published thumbprint on 2026-10-26).
SHA256 = "d160e2de4e56cb10b66c1cb0adcb79cf93c78dcd9db30c2018220262c04063f9"
SHA1 = "82f8d711875fa3b9cf9201abf6224fbac6712770"
# basicConstraints (2.5.29.19), critical, CA:TRUE, pathlen:0, as DER.
CA_TRUE = bytes.fromhex("0603551d130101ff040830060101ff020100")


def der():
    return ssl.PEM_cert_to_DER_cert(tls.intermediates())


class TestVendoredCertificate(unittest.TestCase):

    def test_one_certificate_is_vendored(self):
        self.assertEqual(sorted(os.listdir(tls.CERTS)),
                         ["globalsign-gcc-r46-ov-tls-ca-2025.pem"])
        self.assertEqual(tls.intermediates().count("BEGIN CERTIFICATE"), 1)

    def test_it_parses_and_is_the_expected_ca(self):
        data = der()
        self.assertEqual(hashlib.sha256(data).hexdigest(), SHA256)
        self.assertEqual(hashlib.sha1(data).hexdigest(), SHA1)  # GlobalSign's thumbprint
        self.assertIn(b"GlobalSign GCC R46 OV TLS CA 2025", data)   # its subject
        self.assertIn(b"GlobalSign Root R46", data)                 # its issuer
        self.assertIn(CA_TRUE, data)

    def test_the_header_records_where_it_came_from(self):
        with open(PEM, encoding="ascii", newline="") as f:
            text = f.read()
        self.assertNotIn("\r", text)
        for words in ("http://secure.globalsign.com/cacert/gsgccr46ovtlsca2025.crt",
                      "2026-10-26", "elections.alaska.gov", SHA1,
                      "D1:60:E2:DE:4E:56:CB:10"):
            self.assertIn(words, text)

    def test_the_comment_header_is_not_handed_to_openssl(self):
        text = tls.intermediates()
        self.assertTrue(text.startswith("-----BEGIN CERTIFICATE-----\n"))
        self.assertNotIn("#", text)

    def test_a_pem_with_no_certificate_is_refused(self):
        with mock.patch.object(tls, "CERTS") as certs:
            fake = mock.Mock()
            fake.read_text.return_value = "# nothing here\n"
            certs.glob.return_value = [fake]
            with self.assertRaises(ValueError):
                tls.intermediates()


class TestContext(unittest.TestCase):

    def test_verification_stays_on(self):
        ctx = tls.context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_the_intermediate_is_no_anchor_of_its_own(self):
        flag = getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0)
        self.assertFalse(tls.context().verify_flags & flag)

    def test_it_holds_the_intermediate(self):
        self.assertIn(der(), tls.context().get_ca_certs(binary_form=True))

    def test_each_call_is_a_new_context(self):
        # Nothing global: no reader shares or changes another's context, and
        # ssl's own default is untouched.
        self.assertIsNot(tls.context(), tls.context())
        self.assertIs(ssl._create_default_https_context, ssl.create_default_context)


class _Response:
    status = 200

    def __init__(self, body=b"{}"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return self.body

    def geturl(self):
        return "https://www.elections.alaska.gov/"


class TestEveryAlaskaReaderUsesIt(unittest.TestCase):
    """Each reader that fetches elections.alaska.gov hands urlopen the
    helper's context (a fake urlopen records it)."""

    def record(self, module, body=b"{}"):
        seen = []

        def urlopen(request, *args, **kwargs):
            seen.append(kwargs.get("context"))
            return _Response(body)

        patcher = mock.patch.object(module.urllib.request, "urlopen", urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)
        return seen

    def assertHelper(self, seen):
        self.assertTrue(seen, "urlopen was not called")
        for ctx in seen:
            self.assertIsInstance(ctx, ssl.SSLContext)
            self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(ctx.check_hostname)
            self.assertIn(der(), ctx.get_ca_certs(binary_form=True))

    def test_certified_list(self):
        seen = self.record(certified)
        certified._read(certified.AK_URL)
        self.assertHelper(seen)

    def test_guide_photos_get(self):
        seen = self.record(guide_photos)
        with mock.patch.object(guide_photos, "_pace", lambda url: None):
            guide_photos.get(guide_photos.AK_LIST)
        self.assertHelper(seen)

    def test_guide_photos_dns_lookup(self):
        seen = self.record(guide_photos, b'{"Answer": [{"type": 1, "data": "192.0.2.1"}]}')
        self.assertEqual(guide_photos._address("www.elections.alaska.gov"), "192.0.2.1")
        self.assertHelper(seen)

    def test_guide_photos_pinned_read(self):
        # The read at dns.google's address checks the certificate with the
        # same context.
        import http.client
        seen = []

        class Connection:
            def __init__(self, host, port=None, timeout=None, context=None):
                seen.append(context)

            def request(self, *args, **kwargs):
                raise OSError("offline")

            def close(self):
                pass

        with mock.patch.object(guide_photos, "_address", lambda host: "192.0.2.1"), \
                mock.patch.object(http.client, "HTTPSConnection", Connection):
            with self.assertRaises(guide_photos.GuidePhotoError):
                guide_photos._get_resolved(guide_photos.AK_LIST, 10)
        self.assertHelper(seen)

    def test_voting_page_read(self):
        seen = self.record(voting, b"<html></html>")
        voting._get("https://www.elections.alaska.gov/")
        self.assertHelper(seen)

    def test_voting_link_check(self):
        seen = self.record(voting)
        self.assertEqual(voting._status("https://www.elections.alaska.gov/sample-ballots/")[0],
                         200)
        self.assertHelper(seen)


if __name__ == "__main__":
    unittest.main()
