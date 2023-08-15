import os
import requests
import threading
import time
import shutil
from tqdm import tqdm


proxies = { "http": None, "https": None}

class MultiDownloader:
    def __init__(self, headers, url, file_name, thread_count=20):
        self.headers = headers
        self.url = url
        self.file_name = file_name
        self.thread_count = thread_count
        self.chunk_size = 1024 * 1024
        self.total_range = self.get_file_size()
        self.finished_thread_count = 0
        self.file_lock = threading.Lock()

    def get_file_size(self):
        res = requests.head(self.url, headers=self.headers, proxies=proxies)
        if res.status_code == 200:
            return int(res.headers.get('Content-Length'))
        return None

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
            with requests.get(url=self.url, headers=range_headers, stream=True, timeout=30, proxies=proxies) as res:
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


class MeetingDownloader:
    def __init__(self, headers):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'cookie': headers.get('cookie'),
            'referer': 'https://se6llxwh0q.feishu.cn/minutes/me',
            'content-type': 'application/x-www-form-urlencoded',
            'bv-csrf-token': headers.get('bv_csrf_token')
        }

    def get_meeting_info(self):
        """
        获取会议信息
        """
        get_rec_url = 'https://se6llxwh0q.feishu.cn/minutes/api/space/list?&size=1000&space_name=2'
        resp = requests.get(url=get_rec_url, headers=self.headers, proxies=proxies)
        return list(reversed(resp.json()['data']['list']))

    def download_meeting_video(self, index):
        """
        下载单个会议视频
        """
        meeting_id = index['meeting_id']
        object_token = index['object_token']
        get_download_url = f'https://se6llxwh0q.feishu.cn/minutes/api/status?object_token={object_token}&language=zh_cn&_t={int(time.time() * 1000)}'
        resp = requests.get(url=get_download_url, headers=self.headers, proxies=proxies)
        download_url = resp.json()['data']['video_info']['video_download_url']
        start_time = time.strftime("%Y年%m月%d日%H时%M分", time.localtime(index['start_time'] / 1000))
        stop_time = time.strftime("%Y年%m月%d日%H时%M分", time.localtime(index['stop_time'] / 1000))
        file_name = f'{start_time}至{stop_time}' + index['topic'].replace('|', '').replace(' ', '')
        run_params = {'headers': self.headers,
                        'url': download_url,
                        "file_name": f'{file_name}/{file_name}.mp4',
                        "thread_count": 20
                        }
        downloader = MultiDownloader(**run_params)
        downloader.run()
        return file_name

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
        resp = requests.post(url=srt_url, params=params, headers=self.headers, proxies=proxies)
        if resp.status_code != 200:
            shutil.rmtree(file_name)
            raise Exception(f"下载字幕失败，请检查你的cookie！\nStatus code: {resp.status_code}")
        resp.encoding = "utf-8"
        with open(f"{file_name}/{file_name}.txt", "w+") as f:
            f.write(resp.text)

    def download_meetings(self):
        """
        会议下载
        """
        need_down_meetings = self.get_meeting_info()
        
        # 检查记录中不存在的会议进行下载
        if os.path.exists('meetings.txt'):
            with open('meetings.txt', 'r') as f:
                downloaded_meetings = f.readlines()
            need_down_meetings = [index for index in need_down_meetings if index['meeting_id']+'\n' not in downloaded_meetings]

        if need_down_meetings:
            for index in tqdm(need_down_meetings, desc='Downloading Meetings', unit=' meeting'):
                file_name = self.download_meeting_video(index)
                self.download_subtitle(index['object_token'], file_name)
                # 将已下载的会议记录到文件中
                with open('meetings.txt', 'a+') as f:
                    f.write(index['meeting_id'] + '\n')

    def delete_meetings(self, num):
        """
        会议删除
        """
        all_meetings = self.get_meeting_info()
        num = num if num <= len(all_meetings) else 1
        some_meetings = all_meetings[:num]
        delete_url = "https://se6llxwh0q.feishu.cn/minutes/api/space/delete"
        for index in tqdm(some_meetings, desc='Deleting Meetings', unit=' meeting'):
            params = {'object_tokens': index['object_token'],
                        'is_destroyed': 'false',
                        'language': 'zh_cn'}
            resp = requests.post(url=delete_url, params=params, headers=self.headers, proxies=proxies)
            if resp.status_code != 200:
                raise Exception(f"删除会议失败！ {index['meeting_id']} Status code: {resp.status_code}")
            params['is_destroyed'] = 'true'
            resp = requests.post(url=delete_url, params=params, headers=self.headers, proxies=proxies)
            if resp.status_code != 200:
                raise Exception(f"删除会议失败！ {index['meeting_id']} Status code: {resp.status_code}")


if __name__ == '__main__':
    # 在飞书妙记主页https://se6llxwh0q.feishu.cn/minutes/home获取cookie和bv_csrf_token
    minutes_headers = {
        'cookie': ''
        , 'bv_csrf_token' : ''
    }

    # （可选）在飞书管理后台https://se6llxwh0q.feishu.cn/admin/billing/equity-data获取cookie和X-Csrf-Token
    manager_headers = {
        'cookie': ''
        , 'X-Csrf-Token': ''}
    
    # 如果未填写管理参数，则定时下载会议
    if not manager_headers['cookie'] or not manager_headers['X-Csrf-Token']:
        # 定时查询飞书空间使用情况
        while True:
            print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            downloader = MeetingDownloader(minutes_headers)
            downloader.download_meetings()
            downloader.delete_meetings(1)
            time.sleep(3600)

    # 如果填写了管理参数，则定时查询飞书空间使用情况，超过9.65G空间则删除最早的两个会议
    else :
        query_url = "https://se6llxwh0q.feishu.cn/suite/admin/api/gaea/usages"
        usage_bytes_old = 0
        while True:
            print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            res = requests.get(url=query_url, headers=manager_headers, proxies=proxies)
            usage_bytes = int(res.json()['data']['items'][6]['usage'])
            print(f'已用空间：{usage_bytes / 2 ** 30:.2f}GB')
            # 如果已用空间有变化则下载会议
            if usage_bytes != usage_bytes_old:
                downloader = MeetingDownloader(minutes_headers)
                downloader.download_meetings()
                if usage_bytes > 2 ** 30 * 9.65:
                    downloader.delete_meetings(2)
            usage_bytes_old = usage_bytes
            time.sleep(3600)
