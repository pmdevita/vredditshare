import json
import subprocess
import os
from io import BytesIO

# These functions need to be combined for optimization and cleanliness
# They are doing a lot of the sames stuff already so it's turned into a mess

FILESTREAM_TYPE = "FILESTREAM_TYPE"
PATH_TYPE = "PATH_TYPE"


class MediaInfo:
    def __init__(self, filestream):
        if isinstance(filestream, str):
            file_type = PATH_TYPE
        else:
            file_type = FILESTREAM_TYPE
            filestream.seek(0)

        self.temp_download = False
        self.data = self.get_data(filestream, file_type)
        self.video = self.get_video_stream(self.data['streams'])
        self.audio = self.get_audio_stream(self.data['streams'])
        # If it's a gif, we need to save it to the drive first
        if self.video['codec_name'] == 'gif':
            self.temp_download = "mediainfo.gif"
            with open(self.temp_download, 'wb') as f:
                filestream.seek(0)
                f.write(filestream.read())
            file_type = PATH_TYPE
            filestream = self.temp_download
            self.data = self.get_data(self.temp_download, PATH_TYPE)
            self.video = self.get_video_stream(self.data['streams'])
            self.audio = self.get_audio_stream(self.data['streams'])

        self.format = self.data['format']
        if self.video:
            # Width and Height
            self.dimensions = (self.video['width'], self.video['height'])
            # Frame count
            if self.video.get('nb_read_frames', False):
                self.frame_count = int(self.video['nb_read_frames'])
            elif self.video.get('nb_frames', False):
                self.frame_count = int(self.video['nb_frames'])
            else:
                self.frame_count = None
            # FPS
            fps = None
            if self.video.get('r_frame_rate', False):
                fps = self.video['r_frame_rate'].split("/")
                if fps[1] == "0" and self.video.get('avg_frame_rate', False):
                    fps = self.video['r_frame_rate'].split("/")
            elif self.video.get('avg_frame_rate', False):
                fps = self.video['avg_frame_rate'].split("/")
            if fps:
                if fps[1] != "0":
                    self.fps = int(fps[0]) / int(fps[1])
                else:
                    print(data, fps)
            else:
                fps = None
        # Duration
        if self.format.get('duration', False):
            self.duration = float(self.format['duration'])
        else:
            self.duration = 0

        if self.temp_download:
            os.remove(self.temp_download)

    def get_data(self, filestream, file_type):
        p = subprocess.Popen(
            ["ffprobe", "-i", filestream if file_type == PATH_TYPE else "pipe:0", "-v", "quiet",
             "-print_format", "json", "-show_format", "-show_streams", "-count_frames"],
            stdin=subprocess.PIPE if file_type == FILESTREAM_TYPE else None, stdout=subprocess.PIPE)
        if file_type == FILESTREAM_TYPE:
            output = p.communicate(input=filestream.read())
        else:
            output = p.communicate()
        json_data = output[0].decode("utf-8")
        data = json.loads(json_data)
        return data

    def get_video_stream(self, streams):
        for stream in streams:
            if stream['codec_type'] == 'video':
                return stream
        return None

    def get_audio_stream(self, streams):
        for stream in streams:
            if stream['codec_type'] == 'audio':
                return stream
        return None

def get_duration(filestream):
    filestream.seek(0)
    p = subprocess.Popen(
        ["ffprobe", "-i", "pipe:0", "-v", "quiet", "-print_format", "json", "-show_format"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output = p.communicate(input=filestream.read())[0].decode("utf-8")
    data = json.loads(output)
    if not data.get('format', {}).get('duration', None):
        # Can happen sometimes if the file isn't on the drive
        with open('tempfile', 'wb') as f:
            filestream.seek(0)
            f.write(filestream.read())
        p = subprocess.Popen(
            ["ffprobe", "-i", "tempfile", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = p.communicate()[0].decode("utf-8")
        data = json.loads(output)
        os.remove('tempfile')
    if data['format'].get('duration', None):
        return float(data['format']['duration'])
    return 0


def get_fps(filestream, ffprobe_path="ffprobe"):
    filestream.seek(0)
    p = subprocess.Popen(
        [ffprobe_path, "-i", "pipe:0", "-v", "quiet", "-print_format", "json", "-show_streams"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    data = json.loads(p.communicate(input=filestream.read())[0].decode("utf-8"))
    if data:
        raw_fps = data["streams"][0]["avg_frame_rate"].split("/")
        # if not int(raw_fps[0]) or not int(raw_fps[1]):
        #     raw_fps = data["streams"][0]["r_frame_rate"].split("/")
    else:
        raw_fps = [0, 0]
    if not int(raw_fps[0]) or not int(raw_fps[1]):
        # Can happen sometimes if the file isn't on the drive
        with open('tempfile', 'wb') as f:
            filestream.seek(0)
            f.write(filestream.read())
        p = subprocess.Popen(
            [ffprobe_path, "-i", "tempfile", "-v", "quiet", "-print_format", "json", "-show_streams"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        data = json.loads(p.communicate()[0].decode("utf-8"))
        raw_fps = data["streams"][0]["avg_frame_rate"].split("/")
        if not int(raw_fps[0]) or not int(raw_fps[1]):
            raw_fps = data["streams"][0]["r_frame_rate"].split("/")
        os.remove('tempfile')

    fps = int(raw_fps[0]) / int(raw_fps[1])
    return fps


def is_valid(file):
    file.seek(0)
    p = subprocess.Popen(
        ["ffprobe", "-i", "pipe:0", "-v", "quiet", "-print_format", "json", "-show_streams", "-count_frames"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    data = json.loads(p.communicate(input=file.read())[0].decode("utf-8"))
    if data:
        return data['streams'][0]['codec_type'] == "video"
    return False


def get_frames(file):
    file.seek(0)
    p = subprocess.Popen(
        ["ffprobe", "-i", "pipe:0", "-v", "quiet", "-print_format", "json", "-show_streams", "-count_frames"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    data = json.loads(p.communicate(input=file.read())[0].decode("utf-8"))
    if (not data or not (data.get('streams', [{}])[0].get('nb_read_frames', False) or data.get('streams', [{}])[0].get('nb_frames', False))) and isinstance(file, BytesIO):
        # Can happen sometimes if the file isn't on the drive
        with open('tempfile', 'wb') as f:
            file.seek(0)
            f.write(file.read())
        p = subprocess.Popen(
            ["ffprobe", "-i", "tempfile", "-v", "quiet", "-print_format", "json", "-show_streams", "-count_frames"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        data = json.loads(p.communicate()[0].decode("utf-8"))

    frames = int(data["streams"][0].get('nb_read_frames', 0))
    if not frames:
        frames = int(data['streams'][0].get('nb_read_frames', 0))

    return frames


def has_audio(file):
    file.seek(0)
    audio = False
    p = subprocess.Popen(
        ["ffprobe", "-i", "pipe:0", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    data = json.loads(p.communicate(input=file.read())[0].decode("utf-8"))
    for i in data['streams']:
        if i['codec_type'] == 'audio':
            audio = True

    return audio


def estimate_frames_to_pngs(width, height, frames):
    # PIXEL_TO_SIZE = 0.5812  # 1x1 pixel is .581 in bytes
    PIXEL_TO_SIZE = 0.6812  # 1x1 pixel is .581 in bytes
    return round((width * height * frames) * PIXEL_TO_SIZE / 1000000, 2)


def estimate_frames_to_gif(width, height, frames):
    PIXEL_TO_SIZE = .3063
    return round((width * height * frames) * PIXEL_TO_SIZE / 1000000, 2)

if __name__ == '__main__':
    print(estimate_frames_to_pngs(1280, 720, 2699))


