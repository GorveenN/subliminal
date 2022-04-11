# -*- coding: utf-8 -*-
import logging
import re
import tempfile
from typing import Optional

import ffmpeg
from babelfish import Language
from charset_normalizer import from_bytes
from requests import Session

from ..subtitle import Subtitle
from . import Provider

logger = logging.getLogger(__name__)


def get_subhash(hash):
    """Get a second hash based on napiprojekt's hash.

    :param str hash: napiprojekt's hash.
    :return: the subhash.
    :rtype: str

    """
    idx = [0xE, 0x3, 0x6, 0x8, 0x2]
    mul = [2, 2, 5, 4, 3]
    add = [0, 0xD, 0x10, 0xB, 0x5]

    b = []
    for i in range(len(idx)):
        a = add[i]
        m = mul[i]
        i = idx[i]
        t = a + int(hash[i], 16)
        v = int(hash[t : t + 2], 16)
        b.append(("%x" % (v * m))[-1])

    return "".join(b)


class NapiProjektSubtitle(Subtitle):
    """NapiProjekt Subtitle."""

    provider_name = "napiprojekt"

    def __init__(self, language, hash):
        super(NapiProjektSubtitle, self).__init__(language)
        self.hash = hash
        self._content = None

    @property
    def id(self):
        return self.hash

    @property
    def info(self):
        return self.hash

    def get_matches(self, video):
        matches = set()

        # hash
        if "napiprojekt" in video.hashes and video.hashes["napiprojekt"] == self.hash:
            matches.add("hash")

        return matches

    @property
    def content(self) -> Optional[bytes]:
        return self._content

    @content.setter
    def content(self, content: Optional[bytes]) -> None:
        if content is None:
            return

        content = str(from_bytes(content).best()).encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".txt") as input:
            input.write(content)
            input.flush()
            with tempfile.TemporaryDirectory() as tmp_dir_name:
                outfile_name = f"{tmp_dir_name}/tmp.srt"
                ffmpeg.input(input.name).output(outfile_name).run()
                with open(outfile_name) as output:
                    content_str = output.read()
                    content_str = re.sub(r"^\/(.*)", r"<i>\1<\/i>", content_str)
                    content_str = re.sub(r"\\r", r"", content_str)
                    self._content = content_str.encode("utf-8")


class NapiProjektProvider(Provider):
    """NapiProjekt Provider."""

    languages = {Language.fromalpha2(l) for l in ["pl"]}
    required_hash = "napiprojekt"
    server_url = "http://napiprojekt.pl/unit_napisy/dl.php"
    subtitle_class = NapiProjektSubtitle

    def __init__(self):
        self.session = None

    def initialize(self):
        self.session = Session()
        self.session.headers["User-Agent"] = self.user_agent

    def terminate(self):
        self.session.close()

    def query(self, language, hash):
        params = {
            "v": "dreambox",
            "kolejka": "false",
            "nick": "",
            "pass": "",
            "napios": "Linux",
            "l": language.alpha2.upper(),
            "f": hash,
            "t": get_subhash(hash),
        }
        logger.info("Searching subtitle %r", params)
        logger.info("smth")
        r = self.session.get(self.server_url, params=params, timeout=10)
        r.raise_for_status()

        # handle subtitles not found and errors
        if r.content[:4] == b"NPc0":
            logger.debug("No subtitles found")
            return None

        subtitle = self.subtitle_class(language, hash)
        subtitle.content = r.content
        logger.debug("Found subtitle %r", subtitle)

        return subtitle

    def list_subtitles(self, video, languages):
        return [
            s
            for s in [self.query(l, video.hashes["napiprojekt"]) for l in languages]
            if s is not None
        ]

    def download_subtitle(self, subtitle):
        # there is no download step, content is already filled from listing subtitles
        pass
