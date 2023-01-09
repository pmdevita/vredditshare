from pony.orm import db_session, select
from vredditshare.core.history import Gif, GifHosts, OldGif
from vredditshare.core.gif import GifHostManager

ghm = GifHostManager()

hosts = ["", "Gfycat", "Imgur", "RedditGif", "RedditVideo", "Streamable", "LinkGif"]

with db_session:
    for i in select(g for g in Oldvreddit):
        new = Vreddit(origin_host=VredditHosts[hosts[i.origin_host]], origin_id=i.origin_id,
                      reversed_host=VredditHosts[hosts[i.reversed_host]], reversed_id=i.reversed_id, time=i.time, nsfw=i.nsfw,
                      total_requests=i.total_requests, last_requested_date=i.last_requested_date)
