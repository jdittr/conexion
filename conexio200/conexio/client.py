"""HTTP access to the conexio 200 web interface (digest auth)."""

from __future__ import annotations

import random
import urllib.request

from .decoder import Reading, decode, extract_data


class ConexioClient:
    def __init__(self, url: str, username: str, password: str,
                 timeout: float = 10) -> None:
        self.base = url.rstrip("/")
        self.timeout = timeout
        passwords = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        passwords.add_password(None, self.base, username, password)
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPDigestAuthHandler(passwords),
            urllib.request.HTTPBasicAuthHandler(passwords),
        )

    def fetch_raw(self) -> str:
        # The vendor page adds a random dummy parameter to defeat caching.
        url = f"{self.base}/medius_val.xml?dummy={random.randrange(99999999)}"
        with self._opener.open(url, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def read(self) -> Reading:
        return decode(extract_data(self.fetch_raw()))
