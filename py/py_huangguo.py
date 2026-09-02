# -*- coding: utf-8 -*-
# 黄果短剧爬虫

import sys
import re
import json
import time
from urllib.parse import urljoin, quote, unquote
from base64 import b64encode, b64decode

try:
    import requests
except ImportError:
    requests = None

try:
    from Crypto.Cipher import AES as _AES
except Exception:
    _AES = None

sys.path.append('../')
try:
    from base.spider import Spider
except ImportError:
    # 定义一个基础接口类，用于本地测试
    class Spider:
        def init(self, extend=""):
            pass

class Spider(Spider):
    def __init__(self):
        self.host = 'https://huangguoai.com'
        self.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.headers = {
            "User-Agent": self.userAgent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Referer": self.host + "/",
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
        
        # 标记是否已初始化
        self._initialized = False

    def getName(self):
        return "黄果短剧"

    def init(self, extend=""):
        """初始化爬虫"""
        if self._initialized:
            return
        # 初始化session，处理年龄验证
        self._init_session()
        self._initialized = True

    def _init_session(self):
        """初始化session，获取必要的cookies"""
        try:
            # 先访问首页获取cookie
            response = self._fetch(self.host)
            if response:
                html = response.text
                # 检查是否需要年龄验证
                if self._check_age_modal(html):
                    self._handle_age_verification(html)
                    # 验证后重新请求
                    response = self._fetch(self.host)
        except Exception as e:
            print(f"Init session error: {e}")

    def _fetch(self, url, method="GET", data=None, referer=None):
        """统一的网络请求接口"""
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        
        # 如果 requests 可用，使用 requests
        if requests is not None:
            try:
                # 转换方法
                if method.upper() == "POST":
                    response = requests.post(url, headers=headers, cookies=self.cookies, data=data, timeout=15, verify=False)
                else:
                    response = requests.get(url, headers=headers, cookies=self.cookies, timeout=15, verify=False)
                
                # 更新 cookies
                if response.cookies:
                    self.cookies.update(response.cookies.get_dict())
                
                return response
            except Exception as e:
                print(f"Fetch error: {e}")
                return None
        
        # 如果框架有 fetch 方法，使用框架的
        try:
            if method.upper() == "POST":
                r = self.fetch(url, headers=headers, cookies=self.cookies, data=data, timeout=15, verify=False)
            else:
                r = self.fetch(url, headers=headers, cookies=self.cookies, timeout=15, verify=False)
            if r and r.cookies:
                self.cookies.update(r.cookies)
            return r
        except Exception:
            return None

    def _check_age_modal(self, html):
        """检查页面是否包含年龄验证弹窗"""
        if not html:
            return False
        return ('hg-age-modal' in html or 
                'age-modal' in html or 
                '我已年满 18 周岁' in html or
                '仅限年满 18 周岁' in html or
                'age-gate' in html)

    def _handle_age_verification(self, html):
        """处理年龄验证"""
        try:
            print("处理年龄验证...")
            
            # 方法1: 提取csrf token
            token_match = re.search(r'csrfmiddlewaretoken" value="([^"]+)"', html)
            token = token_match.group(1) if token_match else None
            
            # 方法2: 提取action URL
            action_match = re.search(r'<form[^>]*action="([^"]+)"[^>]*>', html)
            action_url = action_match.group(1) if action_match else "/"
            if not action_url.startswith("http"):
                action_url = self.host + action_url
            
            # 准备验证数据
            data = {
                "age_verified": "1",
                "confirm": "true",
                "action": "enter",
                "csrfmiddlewaretoken": token or "",
            }
            
            # 尝试POST验证
            try:
                response = self._fetch(action_url, method="POST", data=data)
                if response and response.cookies:
                    self.cookies.update(response.cookies.get_dict() if hasattr(response.cookies, 'get_dict') else {})
            except Exception:
                pass
            
            # 方法3: 设置年龄验证cookies
            self.cookies.update({
                "age_verified": "1",
                "age_gate_passed": "1",
                "over18": "1",
                "hg_age_verified": "1",
                "__age_verified": str(int(time.time())),
            })
            
            # 方法4: 带参数重试
            test_url = self.host + "?age_verified=1&over18=1"
            try:
                self._fetch(test_url)
            except Exception:
                pass
                
            print("年龄验证处理完成")
            return True
        except Exception as e:
            print(f"Age verification error: {e}")
            return False

    def _extract_vod_id(self, url):
        """从URL中提取视频ID"""
        if not url:
            return None
        m = re.search(r'/detail/(\d+)/?', url)
        if m:
            return m.group(1)
        m = re.search(r'/video/(\d+)/?', url)
        if m:
            return m.group(1)
        return None

    def _extract_cards(self, html):
        """从HTML中提取视频卡片"""
        if not html:
            return []
        
        cards = []
        seen = set()
        
        # 使用正则表达式提取卡片
        # 模式1: 标准卡片
        pattern = r'<div[^>]*class="[^"]*hg-drama-card[^"]*"[^>]*>.*?<a[^>]*href="([^"]*detail/(\d+)[^"]*)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>.*?<[^>]*class="[^"]*hg-drama-card__title[^"]*"[^>]*>([^<]+)</[^>]*>.*?</div>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        
        if not matches:
            # 模式2: 更宽松的匹配
            pattern = r'<a[^>]*href="([^"]*detail/(\d+)[^"]*)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>.*?</a>'
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            try:
                if len(match) >= 3:
                    href, vid, img = match[0], match[1], match[2]
                    title = match[3] if len(match) > 3 else ""
                    
                    if vid in seen:
                        continue
                    seen.add(vid)
                    
                    # 如果没有标题，尝试从链接文本中获取
                    if not title:
                        title_match = re.search(r'<a[^>]*href="[^"]*detail/{}[^"]*"[^>]*>([^<]+)</a>'.format(vid), html)
                        if title_match:
                            title = title_match.group(1).strip()
                    
                    # 如果没有标题，使用默认
                    if not title:
                        title = f"视频{vid}"
                    
                    # 提取备注
                    remark = ""
                    remark_match = re.search(r'<[^>]*class="[^"]*hg-drama-card__episode[^"]*"[^>]*>([^<]+)</[^>]*>', html)
                    if remark_match:
                        remark = remark_match.group(1).strip()
                    
                    cards.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": img,
                        "vod_remarks": remark
                    })
            except Exception:
                continue
        
        return cards

    def _extract_rank_items(self, html):
        """提取排行榜列表"""
        if not html:
            return []
        
        items = []
        seen = set()
        
        pattern = r'<div[^>]*class="[^"]*hg-rank-item[^"]*"[^>]*>.*?<a[^>]*href="([^"]*detail/(\d+)[^"]*)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>.*?<[^>]*class="[^"]*hg-rank-item__title[^"]*"[^>]*>([^<]+)</[^>]*>.*?</div>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            try:
                href, vid, img, title = match
                if vid in seen:
                    continue
                seen.add(vid)
                
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": img,
                    "vod_remarks": ""
                })
            except Exception:
                continue
        
        return items

    def _get_pic_proxy(self, pic_url):
        """获取图片代理URL"""
        if not pic_url:
            return ""
        # 如果是相对路径，补全
        if pic_url.startswith('/'):
            pic_url = self.host + pic_url
        # 移除auth_key等参数
        if '?' in pic_url:
            pic_url = pic_url.split('?')[0]
        # 通过代理加载
        try:
            # 使用框架的代理
            return self.getProxyUrl() + "&url=" + quote(b64encode(pic_url.encode('utf-8')).decode('utf-8')) + "&type=img"
        except Exception:
            return pic_url

    def _decrypt_img(self, raw):
        """解密图片"""
        if not raw or len(raw) % 16 != 0 or _AES is None:
            return raw
        try:
            cipher = _AES.new(self._IMG_KEY, _AES.MODE_CBC, self._IMG_IV)
            pt = cipher.decrypt(raw)
        except Exception:
            return raw
        
        # 检查是否为有效图片
        if not (pt[:2] == b"\xff\xd8" or pt[:8] == b"\x89PNG\r\n\x1a\n"):
            return raw
        
        # 去除PKCS7填充
        pad = pt[-1]
        if 0 < pad <= 16:
            pt = pt[:-pad]
        
        return pt

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
            if response:
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
            if response:
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
            if "rank" in tid or "ranks" in tid:
                url = f"{self.host}/{tid}/" if pg == 1 else f"{self.host}/{tid}/{pg}/"
                response = self._fetch(url)
                if response:
                    items = self._extract_rank_items(response.text)
                    result["list"] = items
                return result
            
            # 普通分类
            url = f"{self.host}/{tid}/" if pg == 1 else f"{self.host}/{tid}/{pg}/"
            response = self._fetch(url)
            if response:
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
            if not response:
                return result
            
            html = response.text
            
            # 提取标题
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            title = title_match.group(1).strip() if title_match else ""
            
            if not title:
                title_match = re.search(r'<[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</[^>]*>', html)
                title = title_match.group(1).strip() if title_match else ""
            
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
            # 方式1: 通过data-ep-id
            ep_matches = re.findall(r'<a[^>]*href="([^"]*)"[^>]*data-ep-id="([^"]*)"[^>]*>([^<]*)</a>', html)
            for href, eid, text in ep_matches:
                if href:
                    ep_name = f"第{eid}集" if eid else text.strip()
                    if not ep_name:
                        ep_name = f"第{len(eps)+1}集"
                    eps.append(f'{ep_name}${self._fix_url(href)}')
            
            # 方式2: 普通播放链接
            if not eps:
                play_matches = re.findall(r'<a[^>]*href="([^"]*play[^"]*)"[^>]*>([^<]*)</a>', html)
                for href, text in play_matches:
                    if href:
                        ep_name = text.strip() or f"第{len(eps)+1}集"
                        eps.append(f'{ep_name}${self._fix_url(href)}')
            
            # 方式3: ep-grid中的链接
            if not eps:
                ep_grid_matches = re.findall(r'<div[^>]*class="[^"]*ep-grid[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
                for grid_html in ep_grid_matches:
                    grid_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', grid_html)
                    for href, text in grid_links:
                        if href:
                            ep_name = text.strip() or f"第{len(eps)+1}集"
                            eps.append(f'{ep_name}${self._fix_url(href)}')
            
            if not eps:
                return result
            
            # 构建视频信息
            info = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._get_pic_proxy(pic),
                "vod_play_from": "黄果短剧",
                "vod_play_url": "#".join(eps),
                "vod_content": desc,
            }
            
            # 提取备注
            remark_match = re.search(r'<[^>]*class="[^"]*episode[^"]*"[^>]*>([^<]+)</[^>]*>', html)
            if remark_match:
                info["vod_remarks"] = remark_match.group(1).strip()
            
            # 提取标签
            tags = re.findall(r'<[^>]*class="[^"]*tag[^"]*"[^>]*>([^<]+)</[^>]*>', html)
            if tags:
                info["vod_class"] = ",".join([t.strip() for t in tags if t.strip()])
            
            result["list"].append(info)
        except Exception as e:
            print(f"Detail content error: {e}")
        
        return result

    def _fix_url(self, url):
        """补全URL"""
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def searchContent(self, key, quick, pg=1):
        """搜索内容"""
        result = {"list": [], "page": int(pg or 1)}
        try:
            url = f"{self.host}/search/video/{quote(key)}/"
            response = self._fetch(url)
            if response:
                cards = self._extract_cards(response.text)
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
            if response:
                html = response.text
                
                # 尝试从JSON数据中提取
                json_match = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        if isinstance(data, dict):
                            # 提取剧集ID
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
                
                # 尝试从source标签提取
                if not play_url:
                    source_match = re.search(r'<source[^>]*src=["\']([^"\']+)["\']', html, re.I)
                    if source_match:
                        play_url = source_match.group(1)
        except Exception as e:
            print(f"Player error: {e}")
        
        if play_url:
            play_url = play_url.replace("\\u0026", "&")
        
        return {
            "parse": 0,
            "url": play_url,
            "header": {
                "User-Agent": self.userAgent,
                "Referer": self.host + "/",
            }
        }

    def isVideoFormat(self, url):
        """判断是否为视频格式"""
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
                    # 移除auth_key
                    if "?" in url:
                        url = url.split("?")[0]
                    if url:
                        response = self._fetch(url)
                        if response:
                            data = self._decrypt_img(response.content)
                            # 返回图片数据
                            content_type = "image/jpeg"
                            if data[:8] == b"\x89PNG\r\n\x1a\n":
                                content_type = "image/png"
                            return [200, content_type, data]
        except Exception as e:
            print(f"Local proxy error: {e}")
        return None

    def destroy(self):
        """清理资源"""
        pass


# ========== 本地测试 ==========
if __name__ == '__main__':
    spider = Spider()
    spider.init()
    
    print("=== 测试首页 ===")
    result = spider.homeContent(None)
    print(f"分类: {result.get('class', [])}")
    print(f"视频数量: {len(result.get('list', []))}")
    for v in result.get('list', [])[:5]:
        print(f"  - {v.get('vod_name')} (ID: {v.get('vod_id')})")
    
    print("\n=== 测试分类 (AI成人短剧) ===")
    result = spider.categoryContent("ai-duanju", 1, None, None)
    print(f"视频数量: {len(result.get('list', []))}")
    for v in result.get('list', [])[:5]:
        print(f"  - {v.get('vod_name')} (ID: {v.get('vod_id')})")
    
    print("\n=== 测试详情 ===")
    # 使用第一个视频ID
    vid = result.get('list', [{}])[0].get('vod_id', '') if result.get('list') else ''
    if vid:
        detail = spider.detailContent([vid])
        if detail.get('list'):
            info = detail['list'][0]
            print(f"标题: {info.get('vod_name')}")
            print(f"播放链接: {info.get('vod_play_url', '')[:100]}...")