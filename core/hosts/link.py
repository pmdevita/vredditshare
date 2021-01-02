import requests
import time
from io import BytesIO

from core.hosts import GifHost, Gif, GifFile, get_response_size
from core.regex import REPatterns
from core import constants as consts


class LinkGif(Gif):
    def analyze(self) -> bool:
        # Safely download the gif to determine if it
        self.size = get_response_size(self.url, 400)
        if not self.size:
            return False
        # Is it a gif?
        headers = {"User-Agent": consts.spoof_user_agent}
        try:
            r = requests.get(self.url, headers=headers)
        except ConnectionError as e:
            print("got rejected, waiting for a second")
            time.sleep(15)
            r = requests.get(self.url, headers=headers)
        header = r.content[:3]
        if header != b'GIF':
            return None
        self.type = consts.GIF
        self.file = BytesIO(r.content)
        self.files.append(GifFile(self.file, self.host, self.type, self.size, self.duration))
        return True


class LinkGifHost(GifHost):
    name = "LinkGif"
    regex = REPatterns.link_gif
    url_template = "{}"
    gif_type = LinkGif
    priority = 10
    can_vid = False
    can_gif = False