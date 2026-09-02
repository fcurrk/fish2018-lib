# -*- coding: utf-8 -*-
# 黄果短剧爬虫 - 基于测试成功版本

import sys
import re
import json
import time
import requests
from urllib.parse import urljoin, quote, unquote
from base64 import b64encode, b64decode

# 禁用SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from Crypto.Cipher import AES as _AES
except Exception:
    _AES = None

sys.path.append('../')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass

class Spider(Spider):
    def __init__(self):
        self.host = "https://huangguoai.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://huangguoai.com/",
        }
        self.cookies = {}
        
        # 分类配置
        self.categories = [
            {"type_id": "ai-duanju", "type_name": "AI成人短剧"},
            {"type_id": "ai-manju", "type_name": "AI成人漫剧"},
            {"type_id": "ai-huanlian", "type_name": "AI换脸"},
            {"type_id": "ai-mogai", "type_name": "AI魔改"},
            {"type_id": "ranks/hot", "type_name": "排行榜"},
        ]
        
        # 图片解密密钥
        self._IMG_KEY = bytes([102, 53, 100, 57, 54, 53, 100, 102, 55, 53, 51, 51, 54, 50, 55, 48])
        self._IMG_IV = bytes([57, 55, 98, 54, 48, 51, 57, 52, 97, 98, 99, 50, 102, 98, 101, 49])
        
        self._initialized = False

    def getName(self):
        return "黄果短剧"

    def init(self, extend=""):
        if self._initialized:
            return
        self._init_session()
        self._initialized = True

    def _init_session(self):
        """初始化session，处理年龄验证"""
        try:
            # 先请求首页
            response = self._fetch(self.host)
            if response and response.status_code == 200:
                html = response.text
                # 检查是否需要年龄验证
                if '年龄' in html or 'age-modal' in html or '我已年满 18 周岁' in html:
                    self._handle_age_verification(html)
        except Exception as e:
            print(f"Init session error: {e}")

    def _fetch(self, url, method="GET", data=None):
        """统一的请求方法 - 直接使用测试成功的模式"""
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=self.headers, cookies=self.cookies, data=data, timeout=15, verify=False)
            else:
                response = requests.get(url, headers=self.headers, cookies=self.cookies, timeout=15, verify=False)
            
            if response.cookies:
                self.cookies.update(response.cookies.get_dict())
            
            return response
        except Exception as e:
            print(f"Request error: {e}")
            return None

    def _handle_age_verification(self, html):
        """处理年龄验证 - 使用测试成功的方法"""
        print("处理年龄验证...")
        
        # 设置年龄验证 cookies
        self.cookies.update({
            "age_verified": "1",
            "age_gate_passed": "1",
            "over18": "1",
            "hg_age_verified": "1",
        })
        
        # 尝试查找表单并提交
        token_match = re.search(r'csrfmiddlewaretoken" value="([^"]+)"', html)
        token = token_match.group(1) if token_match else None
        
        if token:
            data = {
                "csrfmiddlewaretoken": token,
                "age_verified": "1",
                "confirm": "true",
            }
            response = self._fetch(self.host + "/", method="POST", data=data)
            if response and response.status_code == 200:
                print("验证提交成功")
        
        print("年龄验证处理完成")

    def _extract_cards(self, html):
        """提取视频卡片 - 使用测试成功的方法"""
        if not html:
            return []
        
        cards = []
        seen = set()
        
        # 查找 detail 链接
        pattern = r'<a[^>]*href="([^"]*detail/(\d+)[^"]*)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>.*?</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            href, vid, img = match
            if vid in seen:
                continue
            seen.add(vid)
            
            # 尝试提取标题
            title_match = re.search(r'<a[^>]*href="[^"]*detail/{}[^"]*"[^>]*>([^<]+)</a>'.format(vid), html)
            title = title_match.group(1).strip() if title_match else f"视频{vid}"
            
            # 提取备注（集数等信息）
            remark = ""
            remark_match = re.search(r'<[^>]*class="[^"]*episode[^"]*"[^>]*>([^<]+)</[^>]*>', html)
            if remark_match:
                remark = remark_match.group(1).strip()
            
            cards.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": remark
            })
        
        return cards

    def _extract_rank_items(self, html):
        """提取排行榜列表"""
        if not html:
            return []
        
        items = []
        seen = set()
        
        # 排行榜的提取方式类似
        pattern = r'<a[^>]*href="([^"]*detail/(\d+)[^"]*)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>.*?</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            href, vid, img = match
            if vid in seen:
                continue
            seen.add(vid)
            
            # 提取标题
            title_match = re.search(r'<a[^>]*href="[^"]*detail/{}[^"]*"[^>]*>([^<]+)</a>'.format(vid), html)
            title = title_match.group(1).strip() if title_match else f"视频{vid}"
            
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": ""
            })
        
        return items

    def _get_pic_proxy(self, pic_url):
        """获取图片代理URL"""
        if not pic_url:
            return ""
        if pic_url.startswith('/'):
            pic_url = self.host + pic_url
        if '?' in pic_url:
            pic_url = pic_url.split('?')[0]
        try:
            encoded = quote(b64encode(pic_url.encode('utf-8')).decode('utf-8'), safe="")
            return self.getProxyUrl() + "&url=" + encoded + "&type=img"
        except Exception:
            return pic_url

    def _fix_url(self, url):
        """补全URL"""
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    # ========== 框架接口方法 ==========
    
    def homeContent(self, filter):
        """首页内容"""
        result = {
            "class": self.categories,
            "list": [],
            "filters": {}
        }
        
        try:
            response = self._fetch(self.host)
            if response and response.status_code == 200:
                html = response.text
                cards = self._extract_cards(html)
                result["list"] = cards
        except Exception as e:
            print(f"Home content error: {e}")
        
        return result

    def homeVideoContent(self):
        """首页视频列表"""
        result = {"list": []}
        try:
            response = self._fetch(self.host)
            if response and response.status_code == 200:
                html = response.text
                cards = self._extract_cards(html)
                result["list"] = cards
        except Exception as e:
            print(f"Home video error: {e}")
        return result

    def categoryContent(self, tid, pg, filter, extend):
        """分类/排行榜内容"""
        pg = int(pg or 1)
        tid = str(tid).strip("/")
        result = {
            "page": pg,
            "pagecount": 9999,
            "limit": 24,
            "total": 99999,
            "list": []
        }
        
        try:
            # 处理排行榜
            if "rank" in tid:
                url = f"{self.host}/{tid}/" if pg == 1 else f"{self.host}/{tid}/{pg}/"
                response = self._fetch(url)
                if response and response.status_code == 200:
                    items = self._extract_rank_items(response.text)
                    result["list"] = items
                return result
            
            # 普通分类
            url = f"{self.host}/{tid}/" if pg == 1 else f"{self.host}/{tid}/{pg}/"
            response = self._fetch(url)
            if response and response.status_code == 200:
                html = response.text
                cards = self._extract_cards(html)
                result["list"] = cards
        except Exception as e:
            print(f"Category content error: {e}")
        
        return result

    def detailContent(self, ids):
        """详情内容"""
        vid = str(ids[0])
        result = {"list": []}
        
        try:
            url = f"{self.host}/detail/{vid}/"
            response = self._fetch(url)
            if not response or response.status_code != 200:
                return result
            
            html = response.text
            
            # 提取标题
            title = ""
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if title_match:
                title = title_match.group(1).strip()
            
            if not title:
                title_match = re.search(r'<title>([^<]+)</title>', html)
                if title_match:
                    title = title_match.group(1).strip()
                    title = re.split(r'[-—_|]', title, 1)[0].strip()
            
            if not title:
                return result
            
            # 提取图片
            pic = ""
            pic_match = re.search(r'<img[^>]*(?:data-src|src)="([^"]+)"[^>]*class="[^"]*poster[^"]*"[^>]*>', html)
            if not pic_match:
                pic_match = re.search(r'<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>', html)
            if pic_match:
                pic = pic_match.group(1)
            
            # 提取描述
            desc = ""
            desc_match = re.search(r'<[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</[^>]*>', html)
            if desc_match:
                desc = desc_match.group(1).strip()
            
            # 提取播放列表
            eps = []
            
            # 查找ep-grid中的链接
            ep_grid_pattern = r'<div[^>]*class="[^"]*ep-grid[^"]*"[^>]*>(.*?)</div>'
            ep_grid_matches = re.findall(ep_grid_pattern, html, re.DOTALL)
            for grid_html in ep_grid_matches:
                link_pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
                links = re.findall(link_pattern, grid_html)
                for href, text in links:
                    if href:
                        ep_name = text.strip() or f"第{len(eps)+1}集"
                        eps.append(f'{ep_name}${self._fix_url(href)}')
            
            # 查找data-ep-id
            if not eps:
                ep_pattern = r'<a[^>]*href="([^"]*)"[^>]*data-ep-id="([^"]*)"[^>]*>([^<]*)</a>'
                ep_matches = re.findall(ep_pattern, html)
                for href, eid, text in ep_matches:
                    if href:
                        ep_name = f"第{eid}集" if eid else text.strip()
                        if not ep_name:
                            ep_name = f"第{len(eps)+1}集"
                        eps.append(f'{ep_name}${self._fix_url(href)}')
            
            if not eps:
                return result
            
            info = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._get_pic_proxy(pic),
                "vod_play_from": "黄果短剧",
                "vod_play_url": "#".join(eps),
                "vod_content": desc,
            }
            
            result["list"].append(info)
        except Exception as e:
            print(f"Detail content error: {e}")
        
        return result

    def searchContent(self, key, quick, pg=1):
        """搜索内容"""
        result = {"list": [], "page": int(pg or 1)}
        try:
            url = f"{self.host}/search/video/{quote(key)}/"
            response = self._fetch(url)
            if response and response.status_code == 200:
                html = response.text
                cards = self._extract_cards(html)
                result["list"] = cards
        except Exception as e:
            print(f"Search error: {e}")
        return result

    def playerContent(self, flag, id, vipFlags):
        """播放器内容"""
        url = self._fix_url(id)
        play_url = ""
        
        try:
            response = self._fetch(url, referer=self.host)
            if response and response.status_code == 200:
                html = response.text
                
                # 尝试从JSON数据中提取
                json_match = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        if isinstance(data, dict):
                            ep_match = re.search(r'/ep-(\d+)/', url)
                            ep = str(ep_match.group(1)) if ep_match else "1"
                            srcs = data.get("epPlaySrcs") or {}
                            play_url = srcs.get(ep) or data.get("videoSrc") or ""
                    except Exception:
                        pass
                
                # 尝试从video标签提取
                if not play_url:
                    video_match = re.search(r'<video[^>]*src=["\']([^"\']+)["\']', html, re.I)
                    if video_match:
                        play_url = video_match.group(1)
                
                # 尝试从iframe提取
                if not play_url:
                    iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html, re.I)
                    if iframe_match:
                        play_url = iframe_match.group(1)
        except Exception as e:
            print(f"Player error: {e}")
        
        if play_url:
            play_url = play_url.replace("\\u0026", "&")
        
        return {
            "parse": 0,
            "url": play_url,
            "header": {
                "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0"),
                "Referer": self.host + "/",
            }
        }

    def isVideoFormat(self, url):
        return ".m3u8" in (url or "") or ".mp4" in (url or "")

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """本地代理，用于处理加密图片"""
        try:
            if param and param.get("type") == "img":
                raw = param.get("url", "") or ""
                if raw:
                    url = b64decode(unquote(raw).encode("utf-8")).decode("utf-8")
                    if "?" in url:
                        url = url.split("?")[0]
                    if url:
                        response = self._fetch(url)
                        if response:
                            data = self._decrypt_img(response.content)
                            content_type = "image/jpeg"
                            if data[:8] == b"\x89PNG\r\n\x1a\n":
                                content_type = "image/png"
                            return [200, content_type, data]
        except Exception:
            pass
        return None

    def _decrypt_img(self, raw):
        """解密图片"""
        if not raw or len(raw) % 16 != 0 or _AES is None:
            return raw
        try:
            cipher = _AES.new(self._IMG_KEY, _AES.MODE_CBC, self._IMG_IV)
            pt = cipher.decrypt(raw)
        except Exception:
            return raw
        if not (pt[:2] == b"\xff\xd8" or pt[:8] == b"\x89PNG\r\n\x1a\n"):
            return raw
        pad = pt[-1]
        if 0 < pad <= 16:
            pt = pt[:-pad]
        return pt

    def destroy(self):
        pass


if __name__ == '__main__':
    spider = Spider()
    spider.init()
    
    print("=== 测试首页 ===")
    result = spider.homeContent(None)
    videos = result.get('list', [])
    print(f"视频数量: {len(videos)}")
    for v in videos[:5]:
        print(f"  - {v.get('vod_name')} (ID: {v.get('vod_id')})")
    
    if videos:
        print("\n=== 测试详情 ===")
        vid = videos[0].get('vod_id')
        detail = spider.detailContent([vid])
        if detail.get('list'):
            info = detail['list'][0]
            print(f"标题: {info.get('vod_name')}")
            play_url = info.get('vod_play_url', '')
            if play_url:
                eps = play_url.split('#')
                print(f"剧集数: {len(eps)}")
                for ep in eps[:3]:
                    print(f"  - {ep}")
    
    print("\n=== 测试分类 (AI成人短剧) ===")
    result = spider.categoryContent("ai-duanju", 1, None, None)
    videos = result.get('list', [])
    print(f"视频数量: {len(videos)}")
    for v in videos[:5]:
        print(f"  - {v.get('vod_name')} (ID: {v.get('vod_id')})")