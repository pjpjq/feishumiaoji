# -*- coding:utf-8 -*-
import csv
import logging
import os.path
import threading
import time
from contextlib import closing
import requests


class MultiDownloader:
    def __init__(self, url, file_name=None, thread_count=10, headers=None):
        self.url = url
        self.headers = headers if isinstance(headers, dict) else {}
        self.total_range = None
        self.logger = self.get_logger()
        self.get_resp_header_info()
        self.file_name = file_name
        self.file_lock = threading.Lock()
        self.thread_count = thread_count
        self.failed_thread_list = []
        self.finished_thread_count = 0
        self.chunk_size = 1024 * 100
        self.logger.info(f"init multi task, url:{self.url}")
        self.logger.info(f"init multi task, file_name:{self.file_name}")
        self.logger.info(f"init multi task, thread_count:{self.thread_count}")
        self.logger.info(f"init multi task, headers:{self.headers}")

    def get_logger(self):
        logger = logging.getLogger("MultiDownloader")
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s-%(filename)s-line:%(lineno)d-%(levelname)s-%(process)s: %(message)s")
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        file_handler = logging.FileHandler("download.log", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        return logger

    def get_resp_header_info(self):
        res = requests.head(self.url, headers=self.headers, allow_redirects=True)
        res_header = res.headers
        self.logger.info(f"get_resp_header_info() res_header: {res_header}")
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
        self.logger.info(f"thread {thread_name} start to download")
        range_headers = {"Range": f'bytes={page["start_pos"]}-{page["end_pos"]}'}
        range_headers |= self.headers
        try:
            start_time = time.time()
            try_times = 3
            is_success = False
            for _ in range(try_times):
                try:
                    with closing(requests.get(url=self.url, headers=range_headers, stream=True, timeout=30)) as res:
                        self.logger.info(f"thread {thread_name} download length: {len(res.content)}")
                        if res.status_code == 206:
                            for data in res.iter_content(chunk_size=self.chunk_size):
                                with self.file_lock:
                                    file_handler.seek(page["start_pos"])
                                    file_handler.write(data)
                                page["start_pos"] += len(data)
                            is_success = True
                            break
                except Exception as e:
                    self.logger.error(f"download_range() request error: {e}")
            self.finished_thread_count += 1
            spent_time = time.time() - start_time
            if is_success:
                self.logger.info(f"thread {thread_name} download success, spent_time: {spent_time}, progress: {self.finished_thread_count}/{self.thread_count}")


            else:
                self.logger.error(f"thread {thread_name} download {try_times} times but failed")

                self.failed_thread_list.append(thread_name)
        except Exception as e:
            self.logger.error(f"thread {thread_name} download failed: {e}")
            self.failed_thread_list.append(thread_name)

    def run(self):
        self.logger.info(f"run() get file total range: {self.total_range}")
        if not self.total_range or self.total_range < 1024:
            raise Exception("get file total size failed")
        thread_list = []
        self.logger.info(f"ready to download, file_name: {self.file_name}")
        start_time = time.time()
        os.mkdir(self.file_name.split('/')[0])
        with open(self.file_name, "wb+") as f:
            for i, page in enumerate(self.page_dispatcher(self.total_range)):
                self.logger.info(f'page: {page}, page difference: {page["end_pos"] - page["start_pos"]}')
                thread_list.append(threading.Thread(target=self.download_range, args=(i, page, f)))
            for thread in thread_list:
                thread.start()
            for thread in thread_list:
                thread.join()
        try:
            actual_size = os.path.getsize(self.file_name)
        except Exception as e:
            actual_size = 0
            self.logger.warning(f"get actual file size failed:, self.file_name: {self.file_name}, error: {e}")
        if os.path.exists(self.file_name) and os.path.getsize(self.file_name) == 0:
            self.logger.warning(f"file size is 0, remove, self.file_name:{self.file_name}")
            os.remove(self.file_name)
        total_time = time.time() - start_time
        self.logger.info("download finishing..........")
        self.logger.info("total size %d Bytes (%.2f MB), actual file size %d Bytes, are they equal? %s" % (
            self.total_range, self.total_range / (1024 * 1024), actual_size, self.total_range == actual_size,
        ))
        self.logger.info("total spent time: %.2f second, average download speed: %.2f MB/s" % (
            total_time, actual_size / (1024 * 1024) / total_time
        ))
        if self.failed_thread_list:
            self.logger.info(f"failed_thread_list: {self.failed_thread_list}")
        final_result = "download success!" if self.total_range == actual_size else "download failed"
        self.logger.info(final_result)


if __name__ == '__main__':
    cookie = 在这里写你的cookie
    bv_csrf_token = 在这里写你的token

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
        'cookie': cookie,
        'referer': 'https://se6llxwh0q.feishu.cn/minutes/me',
        'content-type': 'application/x-www-form-urlencoded',
        'bv-csrf-token': bv_csrf_token,
    }

    # 会议信息
    f = open('飞书妙记1.csv', mode='w', newline='')
    csv_writer = csv.DictWriter(f, fieldnames=[
        'meeting_id',
        'topic',
        'start_time',
        'stop_time',
        'url',
        'download_url',
        'video_cover',
    ])
    csv_writer.writeheader()  # 写入表头

    # 遍历会议
    get_rec_url = 'https://se6llxwh0q.feishu.cn/minutes/api/space/list?&size=1&space_name=2'
    resp = requests.get(url=get_rec_url, headers=headers)
    for index in resp.json()['data']['list']:
        object_token = index['object_token']
        get_download_url = f'https://se6llxwh0q.feishu.cn/minutes/api/status?object_token={object_token}&language=zh_cn&_t={int(time.time() * 1000)}'
        resp = requests.get(url=get_download_url, headers=headers)
        download_url = resp.json()['data']['video_info']['video_download_url']
        start_time = time.strftime("%Y年%m月%d日%H时%M分", time.localtime(index['start_time'] / 1000))
        stop_time = time.strftime("%Y年%m月%d日%H时%M分", time.localtime(index['stop_time'] / 1000))
        dit = {
            'meeting_id': index['meeting_id'],
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
        resp = requests.post(url=srt_url, params=params, headers=headers)
        resp.encoding = "utf-8"
        with open(f"{file_name}/{file_name}.txt", "w") as f:
            f.write(resp.text)

        csv_writer.writerow(dit)
        print(dit)
