# -*- coding: utf-8 -*-

import sys
import requests
from urllib.parse import urljoin, quote_plus
import re
import time
from bs4 import BeautifulSoup

sys.path.append('../../')
try:
    from base.spider import Spider
except ImportError:
    # 定义一个基础接口类，用于本地测试
    class Spider:
        def init(self, extend=""):
            pass

class Spider(Spider):
    def __init__(self):
        self.siteUrl = 'https://duanjugou.top'
        self.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        self.cateManual = {
            "首页": "__home__"
        }
        self.session = None
        self.verified = False
        self.cookies = {}
        
    def getName(self):
        return "短剧狗"
    
    def init(self, extend=""):
        """初始化，处理BTWAF验证"""
        try:
            print("开始初始化短剧狗爬虫...")
            
            # 创建session
            self.session = requests.Session()
            
            # 设置headers
            headers = {
                "User-Agent": self.userAgent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
            self.session.headers.update(headers)
            
            # 尝试访问首页，处理验证
            self._handle_btwaf_verification()
            
            print("初始化完成")
            return
        except Exception as e:
            print(f"初始化失败: {str(e)}")
            # 即使初始化失败也继续，后续请求会再次尝试
            if self.session is None:
                self.session = requests.Session()
            return
    
    def _handle_btwaf_verification(self, retry_count=0):
        """处理BTWAF验证"""
        max_retries = 5
        
        try:
            print(f"尝试访问首页，第{retry_count + 1}次...")
            response = self.session.get(self.siteUrl, timeout=30, allow_redirects=True)
            
            # 检查响应内容
            html_content = response.text
            
            # 检测是否在验证页面
            if '正在检测上网环境' in html_content or 'btwaf' in response.url:
                print("检测到BTWAF验证页面，正在处理...")
                
                # 提取验证信息
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 方法1: 尝试提取btwaf参数
                btwaf_param = self._extract_btwaf_param(soup, html_content)
                
                if btwaf_param:
                    print(f"提取到验证参数: {btwaf_param}")
                    # 构造验证URL
                    verify_url = f"{self.siteUrl}/?btwaf={btwaf_param}"
                    
                    # 等待一段时间，模拟浏览器行为
                    wait_time = 3 + retry_count * 2
                    print(f"等待 {wait_time} 秒后继续...")
                    time.sleep(wait_time)
                    
                    # 发送验证请求
                    verify_response = self.session.get(verify_url, timeout=30, allow_redirects=True)
                    
                    # 检查验证是否成功
                    if '正在检测上网环境' not in verify_response.text and 'btwaf' not in verify_response.url:
                        print("BTWAF验证成功!")
                        self.verified = True
                        self.cookies = self.session.cookies.get_dict()
                        return True
                    else:
                        print("BTWAF验证失败，尝试其他方法...")
                
                # 方法2: 尝试直接携带cookies重试
                print("尝试直接重试...")
                time.sleep(2)
                
                # 更新cookies
                if hasattr(response, 'cookies'):
                    self.session.cookies.update(response.cookies)
                
                # 再次请求
                retry_response = self.session.get(self.siteUrl, timeout=30, allow_redirects=True)
                
                if '正在检测上网环境' not in retry_response.text and 'btwaf' not in retry_response.url:
                    print("重试成功!")
                    self.verified = True
                    self.cookies = self.session.cookies.get_dict()
                    return True
                
                # 方法3: 如果还有重试次数，递归重试
                if retry_count < max_retries:
                    print(f"验证未完成，准备第{retry_count + 2}次尝试...")
                    time.sleep(2)
                    return self._handle_btwaf_verification(retry_count + 1)
                else:
                    print("已达到最大重试次数，验证失败")
                    return False
                    
            else:
                # 没有验证页面，直接成功
                print("无需验证，直接访问成功")
                self.verified = True
                self.cookies = self.session.cookies.get_dict()
                return True
                
        except Exception as e:
            print(f"处理验证时出错: {str(e)}")
            if retry_count < max_retries:
                time.sleep(2)
                return self._handle_btwaf_verification(retry_count + 1)
            return False
    
    def _extract_btwaf_param(self, soup, html_content):
        """从页面中提取btwaf参数"""
        # 方法1: 从script中提取
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # 查找btwaf参数
                patterns = [
                    r'btwaf["\']?\s*[:=]\s*["\']([^"\'&]+)["\']',
                    r'window\.location\.href\s*=\s*["\']([^"\']*btwaf[^"\']+)["\']',
                    r'location\.href\s*=\s*["\']([^"\']*btwaf[^"\']+)["\']',
                    r'[\'"]([^"\']*btwaf=[^"\']+)[\'"]',
                ]
                for pattern in patterns:
                    match = re.search(pattern, script.string)
                    if match:
                        param = match.group(1)
                        # 如果匹配到的是完整URL，提取参数
                        if 'btwaf=' in param:
                            param = param.split('btwaf=')[1].split('&')[0]
                        return param
        
        # 方法2: 从meta或链接中提取
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            if meta.get('http-equiv') == 'refresh':
                content = meta.get('content', '')
                match = re.search(r'url=([^"\']+)', content)
                if match:
                    url = match.group(1)
                    if 'btwaf=' in url:
                        return url.split('btwaf=')[1].split('&')[0]
        
        # 方法3: 从文本中提取
        text_match = re.search(r'btwaf[=:]\s*([a-zA-Z0-9]+)', html_content)
        if text_match:
            return text_match.group(1)
        
        return None
    
    def fetch(self, url, headers=None, retry_count=0):
        """统一的网络请求接口，带BTWAF处理"""
        max_retries = 3
        
        try:
            # 确保session存在
            if self.session is None:
                self.session = requests.Session()
                self.session.headers.update({
                    "User-Agent": self.userAgent,
                })
            
            # 更新headers
            if headers:
                current_headers = self.session.headers.copy()
                current_headers.update(headers)
                self.session.headers.update(current_headers)
            
            # 如果尚未验证，先验证
            if not self.verified:
                print("尚未通过验证，先进行验证...")
                self._handle_btwaf_verification()
                time.sleep(1)
            
            # 发送请求
            print(f"请求URL: {url}")
            response = self.session.get(url, timeout=30, allow_redirects=True)
            
            # 检查响应
            html_content = response.text
            
            # 如果再次遇到验证页面
            if '正在检测上网环境' in html_content or 'btwaf' in response.url:
                print("请求中遇到验证页面，重新处理...")
                if retry_count < max_retries:
                    self.verified = False
                    time.sleep(2)
                    return self.fetch(url, headers, retry_count + 1)
                else:
                    print("验证失败，返回空响应")
                    return None
            
            return response
            
        except Exception as e:
            print(f"请求异常: {url}, 错误: {str(e)}")
            if retry_count < max_retries:
                time.sleep(2)
                return self.fetch(url, headers, retry_count + 1)
            return None
    
    def isVideoFormat(self, url):
        # 对于网盘链接，不是直接的视频格式
        return False
    
    def manualVideoCheck(self):
        # 不需要手动检查
        return False
    
    def homeContent(self, filter):
        result = {}

        # 构建分类列表
        classes = []
        for k in self.cateManual:
            classes.append({
                'type_id': self.cateManual[k],
                'type_name': k
            })

        result['class'] = classes

        # 首页只获取第1页，后续翻页由categoryContent逐页加载
        try:
            result['list'] = self.homeVideoContent()['list']
        except Exception as e:
            print(f"获取首页内容失败: {str(e)}")
            result['list'] = []

        result['page'] = 1
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result
    
    def homeVideoContent(self):
        videos = []
        
        # 只读首页，后续翻页由APK自动调用categoryContent逐页加载
        for page_num in range(1, 2):
            if page_num == 1:
                page_url = self.siteUrl
            else:
                page_url = f"{self.siteUrl}/page_{page_num}.html"
        
            try:
                print(f"正在解析第 {page_num} 页：{page_url}")
                response = self.fetch(page_url)
                if not response:
                    print(f"第 {page_num} 页请求失败，跳过...")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                list_container = soup.find('div', class_='post-list')
                if not list_container:
                    print(f"第 {page_num} 页未找到内容容器")
                    continue
                    
                items = list_container.find_all('article', class_='post-item-row')
                print(f"第 {page_num} 页发现 {len(items)} 个条目")
                
                for item in items:
                    try:
                        a_div = item.find('h2', class_='post-title')
                        if not a_div:
                            continue
                        link_tag = a_div.find('a')
                        if not link_tag:
                            continue
                        
                        title = link_tag.text.strip()
                        relative_link = link_tag['href']
                        full_link = urljoin(self.siteUrl, relative_link)
                        
                        time_text = ""
                        i_div = item.select_one('span.post-date')
                        if i_div:
                            time_text = i_div.text.strip()
                        
                        videos.append({
                            "vod_id": full_link.replace(self.siteUrl, ""),
                            "vod_name": title,
                            "vod_remarks": time_text
                        })
                    except Exception as e:
                        print(f"处理条目时出错：{str(e)}")
                        continue
                        
            except Exception as e:
                print(f"解析第 {page_num} 页时发生异常：{str(e)}")
                continue
        
        print(f"共爬取 {len(videos)} 个视频")
        return {'list': videos}
    
    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        videos = []
        pg = int(pg)

        if tid == '__home__':
            # 首页翻页：加载 /page_{pg}.html
            if pg == 1:
                page_url = self.siteUrl
            else:
                page_url = f"{self.siteUrl}/page_{pg}.html"

            try:
                print(f"首页翻页 第{pg}页: {page_url}")
                response = self.fetch(page_url)
                if response:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    list_container = soup.find('div', class_='post-list')
                    if list_container:
                        items = list_container.find_all('article', class_='post-item-row')
                        for item in items:
                            try:
                                a_div = item.find('h2', class_='post-title')
                                if not a_div:
                                    continue
                                link_tag = a_div.find('a')
                                if not link_tag:
                                    continue
                                title = link_tag.text.strip()
                                relative_link = link_tag['href']
                                full_link = urljoin(self.siteUrl, relative_link)
                                time_text = ""
                                i_div = item.select_one('span.post-date')
                                if i_div:
                                    time_text = i_div.text.strip()
                                videos.append({
                                    "vod_id": full_link.replace(self.siteUrl, ""),
                                    "vod_name": title,
                                    "vod_remarks": time_text
                                })
                            except Exception as e:
                                print(f"处理条目时出错：{str(e)}")
                                continue
            except Exception as e:
                print(f"首页翻页异常: {str(e)}")
        else:
            # 搜索翻页
            result = self.switch(tid, pg)
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 90
            result['total'] = 999999
            return result

        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result
        
    def switch(self, tid, pg):
        url = f"{self.siteUrl}/search.php?q={tid}&page={pg}"

        try:
            response = self.fetch(url)
            if not response:
                return {'list': []}
            
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            main_list_section = soup.find('div', class_='post-list')
            if not main_list_section:
                print(f"未找到post-list容器")
                return {'list': []}
                
            item_list = main_list_section.find_all('article', class_='post-item-row')
            if not item_list:
                print(f"未找到article列表")
                return {'list': []}
            
            videos = []
            
            items = main_list_section.find_all('article', class_='post-item-row')
            
            for item in items:
                try:
                    a_div = item.find('h2', class_='post-title')
                    if not a_div:
                        continue

                    link_elem = a_div.find('a')
                    if not link_elem:
                        continue
                    
                    title = a_div.text.strip()
                    link = link_elem.get('href')
                    
                    time_text = ""
                    i_div = item.select_one('span.post-date')
                    if i_div:
                        time_text = i_div.text.strip()
                    
                    if not link.startswith('http'):
                        link = urljoin(self.siteUrl, link)
                    
                    videos.append({
                        "vod_id": link.replace("https://duanjugou.top", ""),
                        "vod_name": title,
                        "vod_remarks": f"{time_text}"
                    })
                except Exception as e:
                    print(f"处理单个短剧时出错: {str(e)}")
                    continue
            
            return {'list': videos}
        except Exception as e:
            print(f"获取首页内容时出错: {str(e)}")
            return {'list': []}


    
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        url = ids[0]
        if not url.startswith('http'):
            url = urljoin(self.siteUrl, url)
            
        try:
            response = self.fetch(url)
            if not response:
                return {}
                
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            main_content = soup.find('div', class_='main-wrapper')
            if not main_content:
                print(f'无法找到main-wrapper容器')
                return {}
            
            title = '未知标题'
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
                title = re.split(r'[-—_]', title, 1)[0].strip()
            
            pan_domains = {
                "百度网盘": ["pan.baidu.com"],
                "阿里云盘": ["alipan.com", "aliyundrive.com"],
                "夸克网盘": ["pan.quark.cn"],
                "迅雷网盘": ["pan.xunlei.com"],
                "天翼云盘": ["cloud.189.cn"],
                "移动云盘": ["caiyun.139.com"],
                "UC网盘": ["drive.uc.cn"],
                "115网盘": ["115cdn.com", "115.com", "anxia.com"],
                "PikPak": ["mypikpak.com"],
                "123网盘": ["123684.com", "123685.com", "123912.com", "123pan.com", "123pan.cn", "123592.com"]
            }

            pan_links = []
            download_links = []
            
            link_pattern = re.compile(r"((?!https?://t\.me)(?:https?://[^\s'\"<>【】\n\.]+(?:\.[^\s'\"<>【】\n\.]+)+(?:/[^\s'\"<>【】\n\.]*)?|magnet:\?xt=urn:btih:[a-zA-Z0-9]+))")
            all_links = link_pattern.findall(html_content)
            
            link_map = {}
            
            def clean_link(link):
                clean = re.sub(r'[\'">].*$', '', link)
                clean = re.sub(r'\.{3,}$', '', clean)
                clean = clean.rstrip('/')
                return clean
            
            for link in all_links:
                clean_link_str = clean_link(link)
                if clean_link_str and len(clean_link_str) > 10:
                    base_url = clean_link_str.split('?')[0]
                    if base_url not in link_map:
                        link_map[base_url] = clean_link_str
            
            a_tags = main_content.find_all('a', href=True)
            for a in a_tags:
                href = a.get('href', '').strip()
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    clean_href = clean_link(href)
                    if clean_href and len(clean_href) > 10:
                        base_url = clean_href.split('?')[0]
                        if base_url not in link_map:
                            link_map[base_url] = clean_href
            
            cleaned_links = list(link_map.values())
            
            for href in cleaned_links:
                if not href or href == '#' or href.startswith('javascript:'):
                    continue
                
                text = ""
                for a in a_tags:
                    if clean_link(a.get('href', '')) == href:
                        text = a.text.strip()
                        break
                
                if not text:
                    text = "链接"
                
                if href.startswith('magnet:'):
                    download_links.append({
                        'name': f"{text or '磁力链接'}",
                        'url': href
                    })
                    continue
                
                is_pan_link = False
                for pan_name, domains in pan_domains.items():
                    if any(domain in href for domain in domains):
                        pan_links.append({
                            'name': f"{text or pan_name}",
                            'url': href
                        })
                        is_pan_link = True
                        break
                
                if not is_pan_link and re.search(r'(ed2k|thunder|ftp):', href):
                    download_links.append({
                        'name': f"{text or '下载链接'}",
                        'url': href
                    })
            
            pwd_pattern = re.compile(r'提取码[:：]\s*([a-zA-Z0-9]{4})')
            pwd_match = pwd_pattern.search(html_content)
            pwd = pwd_match.group(1) if pwd_match else ''
            
            vod_play_from = []
            vod_play_url = []
            
            if pan_links:
                vod_play_from.append('网盘链接')
                play_urls = []
                for i, link in enumerate(pan_links):
                    play_urls.append(f"{link['name']}${link['url']}")
                vod_play_url.append('#'.join(play_urls))
            
            if download_links:
                vod_play_from.append('下载链接')
                play_urls = []
                for i, link in enumerate(download_links):
                    play_urls.append(f"{link['name']}${link['url']}")
                vod_play_url.append('#'.join(play_urls))
            
            description_parts = []
            if pan_links:
                description_parts.append("【网盘链接】")
                for link in pan_links:
                    description_parts.append(f"{link['name']}: {link['url']}")
            if download_links:
                description_parts.append("【下载链接】")
                for link in download_links:
                    description_parts.append(f"{link['name']}: {link['url']}")
            if pwd:
                description_parts.append(f"提取码: {pwd}")

            if description_parts:
                description = "\n".join(description_parts)
            else:
                content_text = main_content.text.strip()
                content_text = re.sub(r'\s+', ' ', content_text)
                description = content_text[:500] + '...' if len(content_text) > 500 else content_text
            
            vod = {
                'vod_id': ids[0],
                'vod_name': title,
                'type_name': '短剧',
                'vod_year': '',
                'vod_area': '',
                'vod_remarks': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_content': description
            }
            
            if vod_play_from:
                vod['vod_play_from'] = '$$$'.join(vod_play_from)
                vod['vod_play_url'] = '$$$'.join(vod_play_url)
            
            return {
                'list': [vod]
            }
        except Exception as e:
            print(f"获取详情内容时出错: {str(e)}")
            return {}
    
    def searchContent(self, key, quick, pg=1):
        result = self.switch(key, pg=pg)
        result['page'] = pg
        return result
    
    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)
    
    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "url": id,
            "header": {
                "User-Agent": self.userAgent
            }
        }
    
    def localProxy(self, param):
        return None
    
    def destroy(self):
        if hasattr(self, 'session') and self.session:
            self.session.close()
        pass


# 测试代码
if __name__ == '__main__':
    spider = Spider()
    
    # 初始化（处理BTWAF验证）
    print("=== 初始化 ===")
    spider.init()
    
    # 测试首页视频列表
    print("\n=== 测试 homeVideoContent ===")
    result = spider.homeVideoContent()
    print(f"获取到 {len(result['list'])} 个视频")
    for v in result['list'][:5]:
        print(v)
    
    # 测试分类搜索
    print("\n=== 测试 categoryContent (分类: 爱) ===")
    cat_result = spider.categoryContent(tid="爱", pg=1, filter=None, extend=None)
    print(f"获取到 {len(cat_result['list'])} 个视频")
    
    # 测试详情页
    print("\n=== 测试 detailContent ===")
    if result['list']:
        detail_result = spider.detailContent(ids=[result['list'][0]['vod_id']])
        if detail_result and 'list' in detail_result and detail_result['list']:
            print(f"标题: {detail_result['list'][0]['vod_name']}")
            print(f"内容: {detail_result['list'][0]['vod_content'][:200]}...")