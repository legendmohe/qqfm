#!/usr/bin/python
# encoding: utf-8
# Copyright 2014 Xinyu, He <legendmohe@foxmail.com>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.



import httplib
import json
import os
import sys
import subprocess
import time
import random
import threading
import signal
import urllib
import urllib2
import threading
import time
from datetime import datetime
import json

import tornado.ioloop
import tornado.web
import redis

import vendor.CmdRunner
import channels_list


g_storage = redis.Redis(host="127.0.0.1", port=6379)

channels = channels_list.CHANNELS["type1"]
channels_groupby_type = {}
for channel in channels:
    channels_groupby_type[channel["name"]] = channel
cur_channel = random.choice(channels)

reload(sys)
sys.setdefaultencoding('utf-8')

WATCHDOG_TIMEOUT = "1:00"
WATCHDOG_INTERVAL = 5

def init_log_file():
    now = datetime.now()
    log_file_name = "music_%s_%s_%s.log" % (now.year, now.month, now.day)
    print "init log file: ", log_file_name
    log_file = open(log_file_name, "w")
    return log_file

log_file = init_log_file()
lock = threading.Lock()
stop_playing = False

def processMp3Address(src):
    global cur_channel, g_storage

    src = src.decode("gb2312")
    res = src[13:-2] #  remove JsonCallBack and quotes
    song = json.loads(res)['songs'][0]
    url = song["url"]
    url = url[:url.index('/', 10) + 1]
    url = url + str(int(song["id"]) + 30000000) + ".mp3"
    
    song_data = song['data'].split("|")
    song_name = song_data[1].strip()
    song_singer = song_data[3].strip()
    timestamp = int(time.time())
    storage_str = u"%d|%s|%s|%s|%s" % (
            timestamp,
            cur_channel["name"],
            song_name,
            song_singer,
            url
            )
    print "redis rpush: ", storage_str
    g_storage.rpush("qqfm:play_history:list", storage_str)
    # print "url:", url
    return url

def processCMD(song):
    cmd = [ 'mplayer',
            '-http-header-fields',
            'Cookie: pgv_pvid=9151698519; qqmusic_uin=12345678; qqmusic_key=12345678; qqmusic_fromtag=0;',
            song]
    return cmd

def timeout_watchdog():
    global WATCHDOG_INTERVAL, WATCHDOG_TIMEOUT
    while True:
        output = subprocess.check_output(
                ["ps ax | grep \'[9]151698519\'|awk \'{print $1\",\"$4;}\'"]
                , stderr=subprocess.STDOUT
                , shell=True
                )
        for line in output.split():
            item = line.split(',')
            if item[1] > WATCHDOG_TIMEOUT:
                print "timeout! ", item[0], item[1]
                subprocess.call("./stop_all_qqfm_process.sh", shell=True)

        time.sleep(WATCHDOG_INTERVAL)

def music_worker():
    global player, channels, lock, stop_playing, cur_music_url, cur_channel
    while True:
        if stop_playing:
            lock.acquire()
            lock.release()

        channel_id = str(cur_channel['id'])
        print "current channel: ", cur_channel['name']
        try:
            params = {
                    "start":-1,
                    "num":1,
                    "labelid":channel_id,
                    "jsonpCallback":"MusicJsonCallback"
                    }
            rep = urllib.urlopen(
                    "http://radio.cloud.music.qq.com/fcgi-bin/qm_guessyoulike.fcg?%s" % urllib.urlencode(params))
            song = processMp3Address(rep.read())
            cmd = processCMD(song)
            with open(os.devnull, 'w') as tempf:
                player = subprocess.Popen(cmd,
                                        stdout=tempf,
                                        stderr=tempf,
                                        )
                print "player create: " + str(player.pid)
                cur_music_url = song
                player.communicate()
            time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, e:
            import traceback
            traceback.print_exc(file=sys.stdout)
            time.sleep(5)

if stop_playing is False:
    stop_playing = True
    lock.acquire() # acquire first, then run worker
music_thread = threading.Thread(target=music_worker)
music_thread.setDaemon(True)
music_thread.start()
watchdog_thread = threading.Thread(target=timeout_watchdog)
watchdog_thread.setDaemon(True)
watchdog_thread.start()

def sift3(s1,s2, maxOffset):
    s1L = len(s1)
    s2L = len(s2)
    if not s1:
        return (not s2 and 0 or s2L)
    if not s2:
        return s1L
    c1 = 0
    c2 = 0
    lcs = 0
    while c1<s1L and c2<s2L:
        if s1[c1] == s2[c2]:
            lcs += 1
        else:
            for i in range(1,maxOffset):
                if c1+i < s1L and s1[c1+i] == s2[c2]:
                    c1 += i
                    break
                if c2+i < s2L and s1[c1] == s2[c2+i]:
                    c2 += i
                    break
        c1 += 1
        c2 += 1
    return ((s1L+s2L)/2-lcs)

def song_type_match(src):
    global channels_groupby_type
    if src is None or len(src) == 0:
        return None
    ret = []
    for name in channels_groupby_type:
        score = sift3(src, name, 3)
        ret.append((name, score)) 
    ret.sort(key=lambda x: x[1])
    for value in ret:
        print value[0], value[1]
    return ret[0][0]

class NextHandler(tornado.web.RequestHandler):
    def get(self):
        global stop_playing, lock, player, cur_channel, channels

        song_type = self.get_argument("type", None)
        match_type = song_type_match(song_type)
        print "song_type:%s match:%s" % (song_type, match_type)
        if match_type is None:
            cur_channel = random.choice(channels)
        else:
            cur_channel = channels_groupby_type[match_type]
        if stop_playing:
            stop_playing = False
            lock.release()
        else:
            player.terminate()
            # os.killpg(player.pid, signal.SIGTERM)
        self.write(cur_channel['name'])


class PauseHandler(tornado.web.RequestHandler):
    def get(self):
        global stop_playing, lock, player
        print "pause."
        if stop_playing is False:
            stop_playing = True
            lock.acquire()
            player.terminate()
            # os.killpg(player.pid, signal.SIGTERM)
        self.write("pause")


class MarkHandler(tornado.web.RequestHandler):
    def get(self):
        global cur_music_url, cur_channel, log_file
        print "mark current."
        now = time.time()
        log_content = "%s|%s|%s|1\n" % (now, cur_channel['name'], cur_music_url)
        log_file.write(log_content)
        log_file.flush()
        self.write(log_content)


class ListHandler(tornado.web.RequestHandler):
    def get(self):
        global channels
        print "list music."
        response = "\n".join([item["name"] for item in channels])
        self.write(response)

# http://stackoverflow.com/questions/17101502/how-to-stop-the-tornado-web-server-with-ctrlc
is_closing = False
def signal_handler(signum, frame):
    global is_closing
    is_closing = True


def try_exit():
    global is_closing, player, stop_playing
    if is_closing:
        # clean up here
        print "exit qqfm."
        # if stop_playing is False:
        #     stop_playing = True
        #     lock.acquire()
        #     player.kill()
            # os.killpg(player.pid, signal.SIGTERM)
        subprocess.call("./stop_all_qqfm_process.sh", shell=True)
        tornado.ioloop.IOLoop.instance().stop()

application = tornado.web.Application([
    (r"/next", NextHandler),
    (r"/pause", PauseHandler),
    (r"/mark", MarkHandler),
    (r"/list", ListHandler),
])
application.listen(8888)
print "bind to 8888"
signal.signal(signal.SIGINT, signal_handler)
tornado.ioloop.PeriodicCallback(try_exit, 100).start()
tornado.ioloop.IOLoop.instance().start()
