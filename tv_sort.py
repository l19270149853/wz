import requests
import concurrent.futures
import time
import re
from urllib.parse import urlparse

# ---------- 配置 ----------
URLS = [
    "https://raw.giteeusercontent.com/g1753462733/zb/raw/main/itvlist.txt",
    "https://raw.githubusercontent.com/fleung49/star/81aebd6f658e6f5747a0500f35a6962a86b2d9b2/mit",
    "https://raw.githubusercontent.com/alantang1977/TVsmile/0678f5f6d492f7db53f8fb0ddb02ebb7f9f830f5/%E7%BD%91%E7%BB%9C%E6%94%B6%E9%9B%86.txt",
    "https://raw.githubusercontent.com/lg-yyds/gdtvapi/cdedbbad15e0a959c6187975150577706870edab/output/result_new.txt"
]
TIMEOUT = 5
THREADS = 20
OUTPUT_FILE = "tv_list_sorted.txt"

# ---------- 港澳台明确列表 ----------
HMT_SPECIAL = [
    "中旺電視", "東森超視美洲台", "民視新聞台", "台視新聞台",
    "漢天衛視", "KTSF26洛杉磯三藩市", "中旺电视", "東森中國台",

"八大戲劇","靖洋戏剧","龍華經典","龙华戏剧",


    "東森美洲衛視", "東森美洲HD", "美國城市衛視ICITI",
    "寰宇新聞台", "寰宇新聞台灣台", "鏡電視新聞台",
    "東森新聞台", "東森財經新聞台", "三立新聞iNEWS",
    "三立綜合台", "民視第一台"
]
HMT_SPECIAL_LOWER = [s.lower() for s in HMT_SPECIAL]

# ---------- 频道标准化 ----------
def normalize_channel(name):
    """将各种变体统一为标准名称"""
    name = name.strip()
    # 先处理CCTV系列
    lower = name.lower()
    # 完全匹配映射
    cctv_map = {
        "cctv-1": "CCTV1", "cctv1": "CCTV1", "中央台一": "CCTV1", "cctv-综合": "CCTV1",
        "cctv-2": "CCTV2", "cctv2": "CCTV2",
        "cctv-3": "CCTV3", "cctv3": "CCTV3",
        "cctv-4": "CCTV4", "cctv4": "CCTV4",
        "cctv-5": "CCTV5", "cctv5": "CCTV5",
        "cctv-6": "CCTV6", "cctv6": "CCTV6",
        "cctv-7": "CCTV7", "cctv7": "CCTV7",
        "cctv-8": "CCTV8", "cctv8": "CCTV8",
        "cctv-9": "CCTV9", "cctv9": "CCTV9",
        "cctv-10": "CCTV10", "cctv10": "CCTV10",
        "cctv-11": "CCTV11", "cctv11": "CCTV11",
        "cctv-12": "CCTV12", "cctv12": "CCTV12",
        "cctv-13": "CCTV13", "cctv13": "CCTV13",
        "cctv-14": "CCTV14", "cctv14": "CCTV14",
        "cctv-15": "CCTV15", "cctv15": "CCTV15",
        "cctv-16": "CCTV16", "cctv16": "CCTV16",
        "cctv-17": "CCTV17", "cctv17": "CCTV17",
        "cctv5+": "CCTV5+", "cctv-5+": "CCTV5+",
        "cctv世界地理": "CCTV世界地理",
        "cctv兵器科技": "CCTV兵器科技",
    }
    if lower in cctv_map:
        return cctv_map[lower]
    # 处理 CCTV 后面带数字和字母的情况，如 CCTV-5HD, CCTV5HD
    cctv_match = re.match(r'(cctv)[\-]?(\d+)(.*)', lower)
    if cctv_match:
        prefix, num, suffix = cctv_match.groups()
        # 只保留数字，忽略后缀（如HD）
        return f"CCTV{num}"
    # 凤凰系列
    if "凤凰中文" in name or "凤凰卫视中文" in name:
        return "凤凰卫视"
    if "凤凰资讯" in name or "凤凰卫视资讯" in name:
        return "凤凰资讯"
    # 去除常见的后缀：HD、高清、-、_ 等
    clean = re.sub(r'[-\s_高清HD]+$', '', name, flags=re.IGNORECASE)
    clean = re.sub(r'[-\s_高清HD]+', '', clean, flags=re.IGNORECASE)  # 去除中间
    return clean.strip()

# ---------- 获取数据 ----------
def fetch_source(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        return resp.text if resp.status_code == 200 else ""
    except Exception as e:
        print(f"⚠️ 抓取失败: {url} - {e}")
        return ""

# ---------- 解析直播源 ----------
def parse_channels(text):
    channels = []
    current_group = "未分类"
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ",#genre#" in line or "，#genre#" in line:
            parts = re.split(r',#genre#|，#genre#', line)
            if parts:
                current_group = parts[0].strip()
            continue
        if ',' in line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name, url = parts[0].strip(), parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    channels.append((name, url, current_group))
    return channels

# ---------- 测速 ----------
def test_speed(channel):
    name, url, group = channel
    try:
        start = time.time()
        r = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        elapsed = time.time() - start
        if r.status_code < 400:
            return (name, url, group, round(elapsed, 2))
    except:
        pass
    return None

# ---------- 分类 ----------
def classify_channel(name, url):
    """返回分组名称"""
    lower = name.lower()
    # 1. 先检查是否在港澳台明确列表中
    if any(s in lower for s in HMT_SPECIAL_LOWER):
        return "港澳台"
    # 2. 中央台
    if "cctv" in lower or "中央台" in lower:
        return "中央电视"
    # 3. 海峡卫视 -> 省级
    if "海峡卫视" in name:
        return "省级卫视"
    # 4. CHC -> 省级
    if "chc" in lower:
        return "省级卫视"
    # 5. 港澳台关键词
    gangaotai = ["凤凰", "tvb", "无线", "港澳", "香港", "澳门", "台湾", "中天", "tvbs", "东森", "华视", "民视",
                 "寰宇", "鏡電視", "三立", "台視", "中旺", "漢天", "ktsf", "美國城市"]
    if any(k in lower for k in gangaotai):
        return "港澳台"
    # 6. 直辖市
    if any(city in name for city in ["北京", "上海", "天津", "重庆"]):
        return "直辖市卫视"
    # 7. 省级卫视（包含“卫视”且不属于以上）
    if "卫视" in name:
        return "省级卫视"
    # 8. 其它
    return "其它"

# ---------- 排序键 ----------
def cctv_sort_key(item):
    name = item[0]  # item is (name, url, speed)
    # 提取数字
    m = re.match(r'CCTV(\d+)', name)
    if m:
        return (0, int(m.group(1)))  # 数字小排前面
    # CCTV5+ 特殊
    if name == "CCTV5+":
        return (1, 0)
    # 世界地理、兵器科技等按字母
    if name.startswith("CCTV"):
        return (2, name)
    return (3, name)  # 其他

# ---------- 主函数 ----------
def main():
    print("📡 开始抓取直播源...")
    all_text = ""
    for url in URLS:
        print(f"  → 抓取: {url}")
        all_text += fetch_source(url) + "\n"

    print("📝 解析频道列表...")
    raw_channels = parse_channels(all_text)
    print(f"  找到 {len(raw_channels)} 个频道")

    print(f"⚡ 并发测速中 (超时 {TIMEOUT}s, 线程 {THREADS})...")
    valid = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(test_speed, ch) for ch in raw_channels]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result:
                valid.append(result)
            if (i+1) % 50 == 0:
                print(f"  进度: {i+1}/{len(raw_channels)}")

    print(f"✅ 有效频道: {len(valid)} 个")

    # 标准化并分类
    classified = {}
    for name, url, group, speed in valid:
        std_name = normalize_channel(name)
        cat = classify_channel(std_name, url)
        classified.setdefault(cat, []).append((std_name, url, speed))

    # 对中央电视组按CCTV数字排序
    if "中央电视" in classified:
        classified["中央电视"].sort(key=cctv_sort_key)
    # 其他组按速度排序（快→慢）
    for cat in classified:
        if cat != "中央电视":
            classified[cat].sort(key=lambda x: x[2])

    # 输出（顺序：中央电视、省级卫视、直辖市卫视、康巴卫视、港澳台、其它）
    order = ["中央电视", "省级卫视", "直辖市卫视", "康巴卫视", "港澳台", "其它"]
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for cat in order:
            if cat not in classified or not classified[cat]:
                continue
            f.write(f"{cat},#genre#,\n")
            for name, url, speed in classified[cat]:
                # 新格式：频道名,URL$速度s
                f.write(f"{name},{url}${speed}s\n")
            f.write("\n")

    print(f"✅ 结果已保存至: {OUTPUT_FILE}")
    for cat in order:
        if cat in classified:
            print(f"  {cat}: {len(classified[cat])} 个")

if __name__ == "__main__":
    main()
