"""License identifiers and download helpers."""

from __future__ import annotations

import logging
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# SPDX-ish ids accepted on the CLI (case-insensitive).
LICENSE_CHOICES = (
    "apache-2.0",
    "mit",
    "bsd-3-clause",
    "gpl-3.0",
    "lgpl-3.0",
    "mpl-2.0",
    "unlicense",
)

DEFAULT_LICENSE = "apache-2.0"

# Authoritative text sources (SPDX license-list-data).
_SPDX_BASE = (
    "https://raw.githubusercontent.com/spdx/license-list-data/main/text"
)

_LICENSE_URLS: dict[str, str] = {
    "apache-2.0": f"{_SPDX_BASE}/Apache-2.0.txt",
    "mit": f"{_SPDX_BASE}/MIT.txt",
    "bsd-3-clause": f"{_SPDX_BASE}/BSD-3-Clause.txt",
    "gpl-3.0": f"{_SPDX_BASE}/GPL-3.0-only.txt",
    "lgpl-3.0": f"{_SPDX_BASE}/LGPL-3.0-only.txt",
    "mpl-2.0": f"{_SPDX_BASE}/MPL-2.0.txt",
    "unlicense": f"{_SPDX_BASE}/Unlicense.txt",
}

# Fallback bodies used only if the network is unavailable.
_FALLBACK_BODIES: dict[str, str] = {
    "apache-2.0": """\
Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

Copyright {year} {holder}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
""",
    "mit": """\
MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""",
    "bsd-3-clause": """\
BSD 3-Clause License

Copyright (c) {year}, {holder}
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
""",
    "unlicense": """\
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>
""",
}


@dataclass(frozen=True)
class LicenseResult:
    """Result of fetching a license body."""

    license_id: str
    text: str
    source: str


def normalize_license_id(value: str) -> str:
    """Normalize a user-supplied license id."""
    key = value.strip().lower()
    aliases = {
        "apache": "apache-2.0",
        "apache2": "apache-2.0",
        "apache-2": "apache-2.0",
        "asl2": "apache-2.0",
        "bsd": "bsd-3-clause",
        "bsd3": "bsd-3-clause",
        "gpl": "gpl-3.0",
        "gpl3": "gpl-3.0",
        "lgpl": "lgpl-3.0",
        "lgpl3": "lgpl-3.0",
        "mpl": "mpl-2.0",
        "mpl2": "mpl-2.0",
    }
    key = aliases.get(key, key)
    if key not in _LICENSE_URLS:
        allowed = ", ".join(LICENSE_CHOICES)
        raise ValueError(f"unsupported license {value!r}; choose one of: {allowed}")
    return key


def _download_text(url: str, timeout: float) -> str:
    """Download URL body as text, trying urllib then curl (for broken SSL envs)."""
    request = urllib.request.Request(url, headers={"User-Agent": "cppboot/0.1"})
    try:
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as first_error:
        logger.debug("urllib download failed for %s: %s", url, first_error)

    curl = shutil.which("curl")
    if curl is not None:
        completed = subprocess.run(
            [curl, "-fsSL", "--max-time", str(int(timeout)), url],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout

    raise OSError(f"unable to download {url}")


def fetch_license_text(
    license_id: str,
    *,
    year: str,
    holder: str,
    timeout: float = 30.0,
) -> LicenseResult:
    """Download license text from an authoritative source, with fallbacks."""
    license_id = normalize_license_id(license_id)
    url = _LICENSE_URLS[license_id]
    try:
        body = _download_text(url, timeout=timeout)
        return LicenseResult(license_id=license_id, text=body, source=url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.debug("license download failed: %s", exc)
        fallback = _FALLBACK_BODIES.get(license_id)
        if fallback is None:
            # Minimal last-resort stub for licenses without a local fallback.
            body = (
                f"{license_id}\n\n"
                f"Copyright (c) {year} {holder}\n\n"
                f"See {url} for the full license text.\n"
            )
            return LicenseResult(
                license_id=license_id,
                text=body,
                source=f"fallback-stub:{url}",
            )
        body = fallback.format(year=year, holder=holder)
        return LicenseResult(
            license_id=license_id,
            text=body,
            source=f"fallback:{license_id}",
        )
