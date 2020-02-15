from core.hosts import GifHost, Gif
from core.regex import REPatterns


class VredditCC(Gif):
    pass


class VredditCCHost(GifHost):
    name = "vredditcc"
    regex = REPatterns.reddit_vid
    url_template = "https://vreddit.cc/{}"
    gif_type = VredditCC
    can_gif = False
    can_vid = False


