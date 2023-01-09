# Add project root folder to python path
import os
import sys

import praw
import datetime
from vredditshare.core import constants as consts
from vredditshare.core.credentials import CredentialsLoader
from vredditshare.core.gif import GifHostManager
from vredditshare.core.history import delete_from_database, list_by_oldest_access

CUTOFF = datetime.date.today() - datetime.timedelta(weeks=9 * 4)

def main():
    print(CUTOFF)

    credentials = CredentialsLoader().get_credentials()

    # Only needed to initialize ghm
    reddit = praw.Reddit(user_agent=consts.user_agent,
                         client_id=credentials['reddit']['client_id'],
                         client_secret=credentials['reddit']['client_secret'],
                         username=credentials['reddit']['username'],
                         password=credentials['reddit']['password'])

    ghm = GifHostManager(reddit)
    catbox = ghm.host_names['Catbox']

    gifs = list_by_oldest_access(catbox, CUTOFF)
    print(len(gifs))
    if gifs:
        print(gifs[0].reversed_id, gifs[0].last_requested_date)

    for gif in gifs:
        catbox_gif = catbox.get_gif(id=gif.reversed_id)
        catbox.delete(catbox_gif)
        delete_from_database(catbox_gif)


if __name__ == '__main__':
    main()
