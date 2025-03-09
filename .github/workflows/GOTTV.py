import requests
import time
import re


class IPTVChecker:
    def __init__(self):
        self.session = requests.Session()

    def _speed_test(self, url):
        try:
            start_time = time.time()
            with self.session.get(url, stream=True, timeout=(5, 15)) as response:
                response.raise_for_status()

                # 测试前1MB数据
                target_size = 1024 * 1024
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded >= target_size or time.time() - start_time > 20:
                        break

                duration = max(time.time() - start_time, 0.1)
                speed = (downloaded / 1024) / duration
                return round(speed, 2)
        except Exception as e:
            print(f"⛔ 测速失败 {url}: {str(e)}")
            return 0

    def download_file(self, file_url):
        try:
            response = self.session.get(file_url)
            response.raise_for_status()
            with open('WZId.txt', 'wb') as file:
                file.write(response.content)
            return True
        except Exception as e:
            print(f"下载文件失败: {str(e)}")
            return False

    def process_file(self):
        try:
            with open('WZId.txt', 'r', encoding='utf-8') as file:
                lines = file.readlines()
                for line in lines:
                    line = line.strip()
                    if line:
                        self.process_url(line)
        except Exception as e:
            print(f"处理文件失败: {str(e)}")

    def process_url(self, url):
        try:
            response = self.session.get(url, timeout=6)
            response.raise_for_status()
            content = response.text

            # 整理内容为台名,网址 形式
            matches = re.findall(r'(.*?)copy to clip\s+(https?://[^\s]+)', content)
            for match in matches:
                station_name, station_url = match
                speed = self._speed_test(station_url)
                if speed > 0:
                    with open('GOTTV.txt', 'a', encoding='utf-8') as output_file:
                        output_file.write(f"{station_name.strip()},{station_url.strip()}\n")
        except Exception as e:
            print(f"处理链接 {url} 失败: {str(e)}")


if __name__ == "__main__":
    file_url = "https://d.kstore.dev/download/10694/%E6%97%A7%E6%96%87%E4%BB%B6/%E7%BD%91%E5%9D%80Id/WZId.txt"
    checker = IPTVChecker()
    if checker.download_file(file_url):
        checker.process_file()


