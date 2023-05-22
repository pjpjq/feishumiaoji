# -*- coding:utf-8 -*-
import codecs
import os.path
import threading
import time
from contextlib import closing
import urllib.parse
import requests
import pandas as pd
from tqdm import tqdm

class MultiDownloader:
    def __init__(self, url, save_path=None, file_name=None, thread_count=10, headers=None):
        self.url = url
        self.headers = headers if isinstance(headers, dict) else {}
        current_file_path = os.path.dirname(os.path.abspath(__file__))
        self.save_path = save_path or os.path.join(current_file_path, "multi_download")
        self.total_range = None
        self.get_resp_header_info()
        self.file_name = file_name
        self.file_lock = threading.Lock()
        self.thread_count = thread_count
        self.failed_thread_list = []
        self.finished_thread_count = 0
        self.chunk_size = 1024 * 100

    def get_logger(self):
        logger = logging.getLogger("MultiDownloader")
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s-%(filename)s-line:%(lineno)d-%(levelname)s-%(process)s: %(message)s")
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        if not os.path.exists(self.save_path):
            os.mkdir(self.save_path)
        file_handler = logging.FileHandler(os.path.join(self.save_path, "download.log"), encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        return logger

    def get_resp_header_info(self):
        res = requests.head(self.url, headers=self.headers, allow_redirects=True)
        res_header = res.headers
        content_range = res_header.get("Content-Length", "0")
        self.total_range = int(content_range)
        self.url = res.url

    def page_dispatcher(self, content_size):
        page_size = content_size // self.thread_count
        start_pos = 0
        while start_pos + page_size < content_size:
            yield {
                'start_pos': start_pos,
                'end_pos': start_pos + page_size
            }
            start_pos += page_size + 1
        yield {
            'start_pos': start_pos,
            'end_pos': content_size - 1
        }

    def download_range(self, thread_name, page, file_handler):
        range_headers = {"Range": f'bytes={page["start_pos"]}-{page["end_pos"]}'}
        range_headers |= self.headers
        try_times = 3
        for _ in range(try_times):
            with closing(requests.get(url=self.url, headers=range_headers, stream=True, timeout=30)) as res:
                if res.status_code == 206:
                    for data in res.iter_content(chunk_size=self.chunk_size):
                        with self.file_lock:
                            file_handler.seek(page["start_pos"])
                            file_handler.write(data)
                        page["start_pos"] += len(data)
                    break
        self.finished_thread_count += 1


    def run(self):
        if not self.total_range or self.total_range < 1024:
            raise Exception("get file total size failed")
        thread_list = []
        os.mkdir(self.file_name.split('/')[0])
        with open(self.file_name, "wb+") as f:
            for i, page in enumerate(self.page_dispatcher(self.total_range)):
                thread_list.append(threading.Thread(target=self.download_range, args=(i, page, f)))
            for thread in thread_list:
                thread.start()
            for thread in thread_list:
                thread.join()
        if os.path.exists(self.file_name) and os.path.getsize(self.file_name) == 0:
            os.remove(self.file_name)
if __name__ == '__main__':
    cookie = 改成你的cookie
    bv_csrf_token = 改成你的bv_csrf_token
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
        'cookie': cookie,
        'referer': 'https://se6llxwh0q.feishu.cn/minutes/me',
        'content-type': 'application/x-www-form-urlencoded',
        'bv-csrf-token': bv_csrf_token,
    }

    # # 会议信息
    # df = pd.read_csv('飞书妙记1.csv')
    # existing_meeting_ids = df['meeting_id'].tolist()
    # existing_meeting_ids=[]
    # 遍历会议
    get_rec_url = 'https://se6llxwh0q.feishu.cn/minutes/api/space/list?&size=1000&space_name=2'
    resp = requests.get(url=get_rec_url, headers=headers)
    print(resp.json())
    df_to_append = pd.DataFrame()
    all_meetings = list(reversed(resp.json()['data']['list']))
    for index in tqdm(all_meetings, desc='Processing Meetings', unit=' meeting'):
        meeting_id = index['meeting_id']
#         if meeting_id in existing_meeting_ids:
#             print(f"Meeting with meeting_id {meeting_id} already exists in the CSV file. Skipping...")
#             continue
        object_token = index['object_token']
        get_download_url = f'https://se6llxwh0q.feishu.cn/minutes/api/status?object_token={object_token}&language=zh_cn&_t={int(time.time() * 1000)}'
        resp = requests.get(url=get_download_url, headers=headers)
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
        run_params = {'headers': headers,
                      'url': download_url,
                      "file_name": f'{file_name}/{file_name}.mp4',
                      "thread_count": 20
                      }
        downloader = MultiDownloader(**run_params)
        downloader.run()
        # 下载妙记SRT文件
        params = {'add_speaker': 'true',
                  'add_timestamp': 'true',
                  'format': '3',
                  'object_token': object_token,
                  }
        srt_url = 'https://se6llxwh0q.feishu.cn/minutes/api/export'
        print(dit)

        # pd.DataFrame([dit]).to_csv("飞书妙记1.csv", 'a')
        resp = requests.post(url=srt_url, params=params, headers=headers)
        resp.encoding = "utf-8"
        with open(f"{file_name}/{file_name}.txt", "w+") as f:
           f.write(resp.text)
        
