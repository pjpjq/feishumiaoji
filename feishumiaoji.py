# -*- coding:utf-8 -*-
import requests
import threading
import os
import shutil
import time
from tqdm import tqdm


class MultiDownloader:
    """
    多线程下载器
    """
    def __init__(self, headers, url, file_name, thread_count=10):
        self.headers = headers
        self.url = url
        self.file_name = file_name
        self.thread_count = thread_count
        self.file_size = int(requests.head(url, headers=headers).headers['Content-Length'])
        self.part = self.file_size // thread_count

    def download_range(self, start, end, f):
        headers = self.headers.copy()
        headers['Range'] = f'bytes={start}-{end}'
        res = requests.get(url=self.url, headers=headers, stream=True)
        f.seek(start)
        f.write(res.content)

    def run(self):
        thread_list = []
        with open(self.file_name, 'wb') as f:
            for i in range(self.thread_count):
                start = i * self.part
                if i == self.thread_count - 1:
                    end = self.file_size
                else:
                    end = start + self.part - 1
                thread_list.append(threading.Thread(target=self.download_range, args=(start, end, f)))
            for thread in thread_list:
                thread.start()
            for thread in thread_list:
                thread.join()
        if os.path.exists(self.file_name) and os.path.getsize(self.file_name) == 0:
            os.remove(self.file_name)


class MeetingDownloader:
    """
    会议下载器
    """
    def __init__(self, cookie, bv_csrf_token):
        self.cookie = cookie
        self.bv_csrf_token = bv_csrf_token
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
            'cookie': self.cookie,
            'referer': 'https://se6llxwh0q.feishu.cn/minutes/me',
            'content-type': 'application/x-www-form-urlencoded',
            'bv-csrf-token': self.bv_csrf_token,
        }

    def get_meeting_info(self):
        """
        获取会议信息
        """
        get_rec_url = 'https://se6llxwh0q.feishu.cn/minutes/api/space/list?&size=1000&space_name=2'
        resp = requests.get(url=get_rec_url, headers=self.headers)
        return list(reversed(resp.json()['data']['list']))

    def download_meeting_video(self, index):
        """
        下载会议视频
        """
        meeting_id = index['meeting_id']
        object_token = index['object_token']
        get_download_url = f'https://se6llxwh0q.feishu.cn/minutes/api/status?object_token={object_token}&language=zh_cn&_t={int(time.time() * 1000)}'
        resp = requests.get(url=get_download_url, headers=self.headers)
        download_url = resp.json()['data']['video_info']['video_download_url']
        start_time = time.strftime("%Y年%m月%d日%H时%M分", time.localtime(index['start_time'] / 1000))
        stop_time = time.strftime("%Y年%m月%d日%H时%M分", time.localtime(index['stop_time'] / 1000))
        dit = {
            'meeting_id': meeting_id,
            'topic': index['topic'],
            'start_time': start_time,
            'stop_time': stop_time,
            'url': index['url'],
            'download_url': download_url,
            'video_cover': index['video_cover'],
        }
        file_name = f'{start_time}至{stop_time}' + index['topic'].replace('|', '').replace(' ', '')
        run_params = {'headers': self.headers,
                        'url': download_url,
                        "file_name": f'{file_name}/{file_name}.mp4',
                        "thread_count": 20
                        }
        downloader = MultiDownloader(**run_params)
        downloader.run()
        return dit, file_name

    def download_subtitle(self, object_token, file_name):
        """
        下载字幕
        """
        params = {'add_speaker': 'true',
                    'add_timestamp': 'true',
                    'format': '3',
                    'object_token': object_token,
                    }
        srt_url = 'https://se6llxwh0q.feishu.cn/minutes/api/export'
        resp = requests.post(url=srt_url, params=params, headers=self.headers)
        if resp.status_code != 200:
            shutil.rmtree(file_name)
            raise Exception(f"下载字幕失败，请检查你的cookie！\nStatus code: {resp.status_code}")
        resp.encoding = "utf-8"
        with open(f"{file_name}/{file_name}.txt", "w+") as f:
            f.write(resp.text)

    def download_some_meetings(self, num):
        """
        下载并删除最久的num个会议
        """
        all_meetings = self.get_meeting_info()
        num = num if num <= len(all_meetings) else 1
        some_meetings = all_meetings[:num]
        for index in tqdm(some_meetings, desc='Processing Meetings', unit=' meeting'):
            dit, file_name = self.download_meeting_video(index)
            self.download_subtitle(index['object_token'], file_name)
            # 下载完成后删除会议
            delete_url = "https://se6llxwh0q.feishu.cn/minutes/api/space/delete"
            params = {'object_tokens': index['object_token'],
                        'is_destroyed': 'false',
                        'language': 'zh_cn'}
            resp = requests.post(url=delete_url, params=params, headers=self.headers)
            if resp.status_code != 200:
                raise Exception(f"删除会议失败！\n{file_name}. Status code: {resp.status_code}")
            params.update({'is_destroyed': 'true'})
            resp = requests.post(url=delete_url, params=params, headers=self.headers)
            if resp.status_code != 200:
                raise Exception(f"删除会议失败！\n{file_name}. Status code: {resp.status_code}")
            print(dit)

# if __name__ == '__main__':
#     bv_csrf_token = input('bv_csrf_token: ')
#     cookie = input('cookie: ')
#     while True:
#         print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
#         downloader = MeetingDownloader(cookie, bv_csrf_token)
#         downloader.download_some_meetings()
#         time.sleep(259200)  # 每三天执行一次

# 检查额度
if __name__ == '__main__':
    bv_csrf_token = input('bv_csrf_token: ')
    cookie = input('cookie: ')
    # 打开https://se6llxwh0q.feishu.cn/admin/billing/equity-data获取cookie和X-Csrf-Token
    headers = {'cookie': ''
        , 'X-Csrf-Token': ''}
    query_url = "https://se6llxwh0q.feishu.cn/suite/admin/api/gaea/usages"
    while True:
        print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
        res = requests.get(url=query_url, headers=headers)
        usage_bytes = int(res.json()['data']['items'][6]['usage'])
        print(f'已用空间：{usage_bytes/2**30:.2f}GB')
        if usage_bytes > 2 ** 30 * 1.5:  # 如果已用1.5G空间
            downloader = MeetingDownloader(cookie, bv_csrf_token)
            downloader.download_some_meetings(3)
        time.sleep(3600)
