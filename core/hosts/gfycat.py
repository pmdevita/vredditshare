import json
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import time
from math import ceil
from io import BytesIO
from pprint import pprint

from core.credentials import CredentialsLoader
from core import constants as consts
from core.hosts import GifHost, Gif, GifFile, NO_NSFW
from core.regex import REPatterns

ENCODE_TIMEOUT = 3200
WAIT = 7
ENCODE_LOOPS = ceil(ENCODE_TIMEOUT / WAIT)


class InvalidRefreshToken(Exception):
    def __init__(self):
        super(InvalidRefreshToken, self).__init__("The provided refresh token was invalid")


class GfycatClient:
    instance = None
    CREDENTIALS_BLOCK = 'gfycat'
    SERVICE_NAME = "Gfycat"
    TOKEN_URL = "https://api.gfycat.com/v1/oauth/token"
    GFYCAT_INFO = "https://api.gfycat.com/v1/gfycats/{}"
    GFYCAT_CREATE = "https://api.gfycat.com/v1/gfycats"
    GFYCAT_UPLOAD = "https://filedrop.gfycat.com"
    GFYCAT_STATUS = "https://api.gfycat.com/v1/gfycats/fetch/status/{}"


    def __init__(self):
        creds = CredentialsLoader.get_credentials()[self.CREDENTIALS_BLOCK]
        self.gfyid = creds["gfycat_id"]
        self.gfysecret = creds["gfycat_secret"]
        self.access = creds.get('access_token', None)
        self.refresh = creds.get('refresh_token', None)
        self.timeout = int(creds.get('token_expiration', 0))

        if self.refresh is None:
            self.authenticate(True)
        if self.access is None:
            self.get_token()

        # self.timeout, self.token = self._load_data()

    @classmethod
    def get(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

    def web_auth(self):
        print("Authorize here: "
              "https://gfycat.com/oauth/authorize?client_id={}&scope=all&state=gifreversingbot"
              "&response_type=code&redirect_uri=http://127.0.0.1:8000/test/".format(self.gfyid))
        import http.server
        server_address = ('', 8000)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self, *args, **kwargs):
                print(args, kwargs, self.path)
                self.send_response(200, "test")
                return "test"

        httpd = http.server.HTTPServer(server_address, Handler)
        httpd.serve_forever()

    def authenticate(self, password=False):
        # For some dumb reason it has to be a string
        if password:
            print("Log into {}".format(self.SERVICE_NAME))
            username = input("Username: ")
            password = input("Password: ")

            data = {"grant_type": "password", "client_id": self.gfyid, "client_secret": self.gfysecret,
                    "username": username, "password": password}
        else:
            data = {"grant_type": "client_credentials", "client_id": self.gfyid,
                    "client_secret": self.gfysecret}

        url = self.TOKEN_URL
        r = requests.post(url, data=str(data), headers={'User-Agent': consts.user_agent})
        try:
            response = r.json()
        except json.decoder.JSONDecodeError as e:
            print(r.text)
            raise
        try:
            self.timeout = int(time.time()) + response["expires_in"]
            self.access = response["access_token"]
            self.refresh = response["refresh_token"]
        except KeyError:
            print(r.text)
            raise
        CredentialsLoader.set_credential(self.CREDENTIALS_BLOCK, 'refresh_token', self.refresh)
        CredentialsLoader.set_credential(self.CREDENTIALS_BLOCK, 'access_token', self.access)
        CredentialsLoader.set_credential(self.CREDENTIALS_BLOCK, 'token_expiration', str(self.timeout))

    def get_token(self):
        # If the token has expired, request a new one
        if self.timeout < int(time.time()):
            data = {"grant_type": "refresh", "client_id": self.gfyid,
                    "client_secret": self.gfysecret, "refresh_token": self.refresh}
            url = self.TOKEN_URL
            # For some dumb reason, data has to be a string
            r = requests.post(url, data=str(data), headers={'User-Agent': consts.user_agent})
            try:
                response = r.json()
            except json.decoder.JSONDecodeError as e:
                print(r.text)
                raise
            # Sometimes Gfycat randomly invalidates refresh tokens >:(
            if r.status_code == 401:
                raise InvalidRefreshToken
            self.timeout = int(time.time()) + response["expires_in"]
            self.access = response["access_token"]
            CredentialsLoader.set_credential(self.CREDENTIALS_BLOCK, 'access_token', self.access)
            CredentialsLoader.set_credential(self.CREDENTIALS_BLOCK, 'token_expiration', str(self.timeout))
        return self.access

    def get_gfycat(self, id):
        headers = {"Authorization": "Bearer {}".format(self.get_token())}
        url = self.GFYCAT_INFO.format(id)
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print("Gfycat - get problem status code {}".format(str(r.status_code)))
            return None
        return r.json()['gfyItem']

    def upload(self, filestream, media_type, nsfw=False, audio=False, title=None, description=None, noMd5=None):
        # If we hit a problem, restart this segment
        tries = 4
        while tries:
            # get gfyname
            url = self.GFYCAT_CREATE
            headers = {"Authorization": "Bearer " + self.get_token(), 'User-Agent': consts.user_agent,
                       'Content-Type': 'application/json'}
            params = {}
            if media_type == consts.LINK:
                params['fetchUrl'] = filestream
            if description:
                params['description'] = description
            if title:
                params['title'] = title
            if nsfw:
                params["nsfw"] = 1
            if audio:
                params['keepAudio'] = True
            if noMd5:
                params['noMd5'] = True
            print("getting gfyname...", params)
            r = requests.post(url, headers=headers, data=str(params))
            # print(r.text)
            try:
                metadata = r.json()
            except json.decoder.JSONDecodeError:
                print(r.text)
                if r.status_code == 401:
                    # Retry block
                    tries -= 1
                    if tries:
                        if media_type != consts.LINK:
                            filestream.seek(0)
                        time.sleep(5)
                        continue
                    else:
                        break
                else:
                    raise

            if 'gfyname' not in metadata:
                print(metadata)
                print("What the heck???")
                # Retry block
                tries -= 1
                if tries:
                    if media_type != consts.LINK:
                        filestream.seek(0)
                    time.sleep(5)
                    continue
                else:
                    break

            # upload
            if media_type != consts.LINK:
                url = self.GFYCAT_UPLOAD
                if media_type == consts.MP4 or media_type == consts.WEBM:
                    files = {"key": metadata["gfyname"], "file": (metadata["gfyname"], filestream, "video/" + media_type)}
                elif media_type == consts.GIF:
                    files = {"key": metadata["gfyname"], "file": (metadata["gfyname"], filestream, "image/gif")}
                m = MultipartEncoder(fields=files)
                print("uploading to gfyid {}...".format(metadata['gfyname']))
                r = requests.post(url, data=m, headers={'Content-Type': m.content_type, 'User-Agent': consts.user_agent})

            # check status for gif's id
            url = self.GFYCAT_STATUS.format(metadata["gfyname"])
            headers = {'User-Agent': consts.user_agent}
            print("waiting for encode...", end=" ")
            r = requests.get(url, headers=headers)
            try:
                ticket = r.json()
            except json.decoder.JSONDecodeError as e:
                print(r.text)
                raise
            # Sometimes we have to wait
            percentage = 0
            notfoundo = 5
            for i in range(ENCODE_LOOPS):
                print(ticket)
                if ticket["task"] == "encoding":
                    time.sleep(WAIT)
                    r = requests.get(url, headers=headers)
                    try:
                        ticket = r.json()
                    except json.decoder.JSONDecodeError as e:
                        print(r.text)
                        raise e
                    # print(ticket)
                    if float(ticket.get('progress', 0)) > percentage:
                        percentage = float(ticket['progress'])
                        print(percentage, end=" ")
                elif ticket['task'] == 'NotFoundo':
                    print("notfoundo", end=" ")
                    time.sleep(WAIT * 2)
                    r = requests.get(url, headers=headers)
                    ticket = r.json()
                    # print(ticket)
                    if float(ticket.get('progress', 0)) > percentage:
                        percentage = float(ticket['progress'])
                        print(percentage, end=" ")
                else:
                    break
            # If there was something wrong, we loop back and try again
            if ticket["task"] == "NotFoundo" or ticket["task"] == "error" or ticket['task'] == "review_issue":
                print("Error uploading? Trying again", ticket)
                # Retry block
                tries -= 1
                if tries:
                    if media_type != consts.LINK:
                        filestream.seek(0)
                    time.sleep(5)
                    continue
                else:
                    break
            elif ticket['task'] == 'encoding':
                print("Upload timed out? Trying again", ticket)
                # Retry block
                tries -= 1
                if tries:
                    if media_type != consts.LINK:
                        filestream.seek(0)
                    time.sleep(5)
                    continue
                else:
                    break
            if "gfyName" in ticket:
                image_id = ticket["gfyName"]
            elif "gfyname" in ticket:
                image_id = ticket["gfyname"]
            print("Done!")
            break

        if tries:
            # return OldGif(consts.GFYCAT, image_id, nsfw=nsfw)
            return image_id
        else:
            return None


class GfycatGif(Gif):
    def analyze(self) -> bool:
        self.pic = self.host.API.get_gfycat(self.id)
        if not self.pic:
            return False
        try:
            self.id = self.pic['gfyName']
        except KeyError:
            print("GfyName missing, is it deleted?")
            return False

        self.url = self.pic["webmUrl"]
        self.type = consts.WEBM
        if self.url == "":  # If we received no URL, the GIF was brought down or otherwise missing
            print("{} gif missing".format(self.host.name))
            return False
        self.duration = self.pic['numFrames'] / self.pic['frameRate']
        audio = self.pic['hasAudio']
        frames = self.pic['numFrames']
        self.file = BytesIO(requests.get(self.url).content)
        if int(self.pic['nsfw']):
            print("{} says it's nsfw".format(self.host.name))
            # pprint(self.pic)
        # self.nsfw = self.nsfw or int(self.pic['nsfw']) # Gfycat's NSFW flag is essentially useless
        self.size = self.pic['webmSize'] / 1000000
        self.files.append(GifFile(self.file, self.host, self.type, self.size, self.duration, audio=audio))
        self.files.append(GifFile(self.file, self.host, consts.GIF, self.size, self.duration, frames, audio=audio))
        return True


class GfycatHost(GifHost):
    name = "Gfycat"
    regex = REPatterns.gfycat
    url_template = "https://gfycat.com/{}"
    gif_type = GfycatGif
    audio = True
    NSFW = NO_NSFW
    video_type = consts.WEBM
    vid_len_limit = 61  # This has been double verified now lol
    gif_size_limit = 1700   # Gfycat doesn't have a real limit but I doubt anything higher than this will work
    gif_frame_limit = 2100
    API = GfycatClient.get()

    @classmethod
    def upload(cls, file, gif_type, nsfw, audio=False):
        id = cls.API.upload(file, gif_type, nsfw=nsfw, audio=audio)
        if id:
            return cls.gif_type(cls, id, nsfw=nsfw)

