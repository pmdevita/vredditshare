from typing import Optional
import praw.models
from praw.const import API_PATH
from core import constants as consts
from core.regex import REPatterns
from core.gif import GifHostManager
from core.hosts import GifHost
from core.hosts.reddit import RedditVid
from pprint import pprint

# TODO: Minimize API calls through refresh() https://praw.readthedocs.io/en/latest/code_overview/models/comment.html


class CommentContext:
    def __init__(self, reddit, comment, ghm):
        """Determine the context of a summon by grabbing what comment/submission and url it is referring too"""
        self.ghm = ghm
        self.comment = comment
        self.rereverse = False
        self.unnecessary_manual = False
        self.nsfw = is_nsfw(comment)
        self.distinguish = False
        # self.reupload = is_reupload(comment.body)
        self.url = self.determine_target_url(reddit, self.comment)

    @classmethod
    def from_json(cls, reddit, data):
        # Skip the normal init function
        context = cls.__new__(cls)
        # Process rest of data
        for i in data:
            context.__setattr__(i, data[i])
            # Process comment differently
            if i == 'comment':
                # Get reddit object info
                params = {'id': data['comment']}
                r = reddit.get(API_PATH['info'], params=params)
                context.comment = r.children[0]

        return context

    def to_json(self):
        data = {}
        for i in vars(self):
            if i[0] != "_" and i != "ghm":
                data[i] = self.__getattribute__(i)
        data['comment'] = self.comment.name
        data['url'] = str(self.url)
        return data

    def determine_target_url(self, reddit, reddit_object, layer=0, checking_manual=False):
        """Recursively find the gif URL the user wants"""
        # If the object is a post, check it's URL
        if isinstance(reddit_object, praw.models.Submission):
            # Running through enough levels can cause a recursion error,
            # which we need to then refresh our comment
            try:
                # Any mention of NSFW must trip the NSFW flag
                if is_nsfw_text(reddit_object.title) and not checking_manual:
                    self.nsfw = True
                # If post is a text post, search it's content
                if reddit_object.is_self:
                    # Any mention of NSFW must trip the NSFW flag
                    if is_nsfw_text(reddit_object.selftext) and not checking_manual:
                        self.nsfw = True
                    # Search text for URL
                    url = self.ghm.host_names['RedditVideo'].get_gif(text=reddit_object.selftext, nsfw=self.nsfw)
                    # If found
                    if isinstance(url, RedditVid):
                        # Return it
                        return url
                # Else if the post is a link post, check it's URL
                else:
                    url = self.ghm.host_names['RedditVideo'].get_gif(text=reddit_object.url, nsfw=self.nsfw)
                    if isinstance(url, RedditVid):
                        return url
                    else:
                        return None
            except RecursionError:
                submission = reddit.submission(id=reddit_object.id)
                return self.determine_target_url(reddit, submission, layer + 1, checking_manual)

        # Else if the object is a comment, check it's text
        elif isinstance(reddit_object, praw.models.Comment):
            # Any mention of NSFW must trip the NSFW flag
            if is_nsfw_text(reddit_object.body) and not checking_manual:
                self.nsfw = True
            # If the comment was made by the bot, it must be a rereverse request
            # If the rereverse flag is already set, we must be at least a loop deep
            # if reddit_object.author == consts.username and not self.rereverse and not checking_manual \
            #         and not self.reupload:
            #     self.rereverse = True
            #     return self.determine_target_url(reddit, reddit_object.parent(), layer+1, checking_manual)
            # If it's an AutoModerator summon, move our summon comment to the AutoMod's parent
            if reddit_object.author == "AutoModerator":
                # IF this is layer 0, this is an Automoderator summon. Check if we are doing a comment replacement
                if layer == 0:
                    # Delete comment if a moderator
                    modded_subs = [i.name for i in reddit.user.me().moderated()]
                    if reddit_object.subreddit.name in modded_subs:
                        self.comment = reddit_object.parent()
                        if reddit_object.stickied:
                            self.distinguish = True
                        reddit_object.mod.remove()
                        reddit_object = self.comment
                        # Skip to the next object in the hierarchy
                        return self.determine_target_url(reddit, reddit_object, layer+1, checking_manual)
                # If we are rereversing and we encounter an AutoModerator comment that summoned us, immediately stop.
                # It's likely a AutoModerator summon loop
                elif self.rereverse:
                    # If this AutoModerator comment contains a summon
                    if REPatterns.reply_mention.findall(reddit_object.body):
                        # Immediately stop
                        print("Detected AutoModerator summon loop")
                        return None

            url = self.ghm.host_names['RedditVideo'].get_gif(text=reddit_object.body, nsfw=self.nsfw)
            # If found
            if isinstance(url, RedditVid):
                # Return it
                if layer == 0:  # If this is the summon comment
                    # Double check they didn't needlessly give us the URL again
                    next_url = self.determine_target_url(reddit, reddit_object.parent(), layer+1, True)
                    if url == next_url:
                        self.unnecessary_manual = True
                return url
            # We didn't find a gif, go up a level
            return self.determine_target_url(reddit, reddit_object.parent(), layer+1, checking_manual)


# Works but will mark a sfw gif first posted in an nsfw sub as nsfw ¯\_(ツ)_/¯
def is_nsfw(comment):
    # Identify if submission is nsfw
    if isinstance(comment, praw.models.Comment):
        post_nsfw = comment.submission.over_18
        # Why no underscore
        sub_nsfw = comment.subreddit.over18
        # print("nsfw", post_nsfw, sub_nsfw)
        return post_nsfw or sub_nsfw
    elif isinstance(comment, praw.models.Submission):
        post_nsfw = comment.over_18
        # Why no underscore
        sub_nsfw = comment.subreddit.over18
        # print("nsfw", post_nsfw, sub_nsfw)
        return post_nsfw or sub_nsfw


def is_nsfw_text(text):
    m = REPatterns.nsfw_text.findall(text)
    return len(m) != 0


def is_reupload(text):
    m = REPatterns.reupload_text.findall(text)
    return len(m) != 0
