# -*- coding: utf-8 -*-
import re
import sys
import json
import time
from base64 import b64encode, b64decode
from urllib.parse import quote, unquote
from lxml import etree

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    from Crypto.Cipher import AES as _AES
except Exception:
    _AES = None

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "黄果短剧"

    def init(self, extend=""):
        self.host = "https://huangguoai.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
        ext = extend or ""
        self.pics_direct = "direct=1" in ext or "direct=1" in str(ext)
        self.categories = [
            {"type_id": "ai-duanju", "type_name": "AI成人短剧"},
            {"type_id": "ai-manju", "type_name": "AI成人漫剧"},
            {"type_id": "ai-huanlian", "type_name": "AI换脸"},
            {"type_id": "ai-mogai", "type_name": "AI魔改"},
            {"type_id": "ranks/hot", "type_name": "排行榜"},
        ]
        # 存储session cookies
        self.cookies = {}
        self._init_session()

    def _init_session(self):
        """初始化session，获取必要的cookies"""
        try:
            # 先访问首页获取cookie
            r = self.fetch(self.host, headers=self.headers, timeout=15, verify=False)
            if r and r.cookies:
                self.cookies.update(r.cookies)
            
            # 检查是否需要年龄验证
            if r and self._check_age_modal(r.text):
                self._handle_age_verification(r.text)
        except Exception as e:
            print(f"Init session error: {e}")

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
            # 方法1: 尝试提取token
            token_match = re.search(r'csrfmiddlewaretoken" value="([^"]+)"', html)
            token = token_match.group(1) if token_match else None
            
            # 方法2: 尝试提取年龄验证的action URL
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
            
            headers = dict(self.headers)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            # 尝试POST验证
            try:
                r = self.fetch(action_url, 
                              method="POST",
                              headers=headers,
                              data=data,
                              timeout=15,
                              verify=False)
                if r and r.cookies:
                    self.cookies.update(r.cookies)
            except Exception:
                pass
            
            # 方法3: 设置通用年龄验证cookies
            age_cookies = {
                "age_verified": "1",
                "age_gate_passed": "1",
                "over18": "1",
                "__age_verified": str(int(time.time())),
                "age_confirmed": "true",
                "hg_age_verified": "1",
            }
            self.cookies.update(age_cookies)
            
            # 方法4: 尝试直接GET请求带参数
            test_url = self.host + "?age_verified=1&over18=1"
            try:
                r = self.fetch(test_url, headers=self.headers, cookies=self.cookies, timeout=15, verify=False)
                if r and r.cookies:
                    self.cookies.update(r.cookies)
            except Exception:
                pass
                
            return True
        except Exception as e:
            print(f"Age verification error: {e}")
            return False

    def _get(self, url, referer=None, asjson=False):
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        
        # 合并cookies
        cookies = dict(self.cookies)
        
        for i in range(3):
            try:
                # 第一次请求
                r = self.fetch(url, headers=headers, cookies=cookies, timeout=15, verify=False)
                
                # 更新cookies
                if r and r.cookies:
                    cookies.update(r.cookies)
                    self.cookies.update(r.cookies)
                
                html = r.text
                
                # 检查是否需要年龄验证
                if self._check_age_modal(html):
                    # 尝试处理年龄验证
                    self._handle_age_verification(html)
                    # 重新请求
                    r = self.fetch(url, headers=headers, cookies=self.cookies, timeout=15, verify=False)
                    html = r.text
                
                if not asjson:
                    return html
                try:
                    return r.json()
                except Exception:
                    return {}
            except Exception as e:
                if i == 2:
                    break
                time.sleep(1)
        return {} if asjson else ""

    def _fix(self, u):
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _img_src(self, u):
        """剔除 CDN 防盗链的 auth_key 等查询参数, 得到不过期的稳定直链"""
        u = self._fix(u or "")
        if u.startswith("http") and "?" in u:
            u = re.sub(r'\?.*', '', u)
        return u

    def _proxy_pic(self, u):
        """图片 URL 统一通过本地代理加载, 避免防盗链过期/内容类型/直连被墙"""
        u = self._img_src(u)
        if not u:
            return ""
        if self.pics_direct:
            return u
        enc = quote(b64encode(u.encode("utf-8")).decode("utf-8"), safe="")
        return f"{self.getProxyUrl()}&url={enc}&type=img"

    # 站点图片为 AES-128-CBC 加密字节, 密钥/IV 取自站点前端 crypto-worker.js
    _IMG_KEY = bytes([102, 53, 100, 57, 54, 53, 100, 102, 55, 53, 51, 51, 54, 50, 55, 48])
    _IMG_IV = bytes([57, 55, 98, 54, 48, 51, 57, 52, 97, 98, 99, 50, 102, 98, 101, 49])

    def _decrypt_img(self, raw):
        if not raw or len(raw) % 16 != 0 or _AES is None:
            return raw
        try:
            pt = _AES.new(self._IMG_KEY, _AES.MODE_CBC, self._IMG_IV).decrypt(raw)
        except Exception:
            return raw
        # 解密后若不含图片特征说明源图并未加密, 原样返回
        if not (pt[:2] == b"\xff\xd8" or pt[:8] == b"\x89PNG\r\n\x1a\n"
                or pt[:4] == b"RIFF" or pt[:6] in (b"GIF87a", b"GIF89a")):
            return raw
        pad = pt[-1]
        if 0 < pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
            pt = pt[:-pad]
        if pt[:2] == b"\xff\xd8":
            i = pt.rfind(b"\xff\xd9")
            if i >= 0:
                pt = pt[:i + 2]
        elif pt[:8] == b"\x89PNG\r\n\x1a\n":
            i = pt.rfind(b"IEND")
            if i >= 0:
                pt = pt[:i + 8]
        return pt

    def _img_ct(self, data):
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        return "image/jpeg"

    def _get_bin(self, url):
        headers = dict(self.headers)
        cookies = dict(self.cookies)
        for i in range(3):
            try:
                r = self.fetch(url, headers=headers, cookies=cookies, timeout=15, verify=False)
                if r and r.status_code == 200:
                    if r.cookies:
                        self.cookies.update(r.cookies)
                    return r.content
            except Exception:
                if i == 2:
                    break
                time.sleep(1)
        return None

    def _extract_vod_id(self, url):
        """从URL中提取视频ID"""
        if not url:
            return None
        # 匹配 /detail/数字/ 或 /detail/数字
        m = re.search(r'/detail/(\d+)/?', url)
        if m:
            return m.group(1)
        # 匹配 /video/数字 格式
        m = re.search(r'/video/(\d+)/?', url)
        if m:
            return m.group(1)
        return None

    def _parse_card(self, card_element):
        """解析单个卡片元素"""
        try:
            # 尝试多种方式获取链接
            links = card_element.xpath('.//a[contains(@href,"/detail/")]')
            if not links:
                links = card_element.xpath('.//a[contains(@href,"/video/")]')
            if not links:
                return None
            
            link = links[0]
            href = link.get("href", "")
            vod_id = self._extract_vod_id(href)
            if not vod_id:
                return None
            
            # 获取图片 - 尝试多种属性
            img_src = ""
            img_elements = card_element.xpath('.//img')
            for img in img_elements:
                src = img.get("data-src") or img.get("src") or ""
                if src:
                    img_src = src
                    break
            
            # 获取标题 - 尝试多种选择器
            title = ""
            title_selectors = [
                './/*[contains(@class,"title")]//text()',
                './/*[contains(@class,"name")]//text()',
                './/*[contains(@class,"drama-name")]//text()',
                './/h3//text()',
                './/h4//text()',
            ]
            for selector in title_selectors:
                title_parts = card_element.xpath(selector)
                if title_parts:
                    title = "".join(title_parts).strip()
                    if title:
                        break
            
            if not title:
                title = link.get("title", "").strip()
            
            if not title:
                return None
            
            # 获取备注信息
            remark = ""
            remark_selectors = [
                './/*[contains(@class,"episode")]//text()',
                './/*[contains(@class,"info")]//text()',
                './/*[contains(@class,"meta")]//text()',
                './/*[contains(@class,"tags")]//text()',
            ]
            for selector in remark_selectors:
                remark_parts = card_element.xpath(selector)
                if remark_parts:
                    remark = "".join(remark_parts).strip()
                    if remark:
                        break
            
            return {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._proxy_pic(img_src),
                "vod_remarks": remark,
            }
        except Exception as e:
            print(f"Parse card error: {e}")
            return None

    def _cards(self, html, all_grids=False):
        """提取卡片列表"""
        if not html:
            return []
        try:
            tree = etree.HTML(html)
            
            # 尝试多种方式获取卡片容器
            card_containers = []
            
            # 方式1: 通过 class 查找
            if all_grids:
                containers = tree.xpath('//*[contains(@class,"grid")]')
                for container in containers:
                    card_containers.extend(container.xpath('.//*[contains(@class,"card")]'))
            else:
                containers = tree.xpath('//*[contains(@class,"grid")]')
                if containers:
                    card_containers = containers[0].xpath('.//*[contains(@class,"card")]')
            
            # 方式2: 如果没有找到，直接找所有卡片
            if not card_containers:
                card_containers = tree.xpath('//*[contains(@class,"card")]')
            
            # 方式3: 查找包含图片和链接的 div
            if not card_containers:
                card_containers = tree.xpath('//div[a[contains(@href,"/detail/")] and img]')
            
            # 方式4: 查找所有包含 detail 链接的 li 或 div
            if not card_containers:
                card_containers = tree.xpath('//li[a[contains(@href,"/detail/")]] | //div[a[contains(@href,"/detail/")]]')
            
            out, seen = [], set()
            for card in card_containers:
                try:
                    item = self._parse_card(card)
                    if not item or item["vod_id"] in seen:
                        continue
                    seen.add(item["vod_id"])
                    out.append(item)
                except Exception:
                    continue
            
            return out
        except Exception as e:
            print(f"Extract cards error: {e}")
            return []

    def _rank_items(self, html):
        """提取排行榜列表"""
        if not html:
            return []
        try:
            tree = etree.HTML(html)
            
            # 尝试多种方式获取排行榜项
            rank_items = []
            
            # 方式1: 通过 class 查找
            rank_items = tree.xpath('//*[contains(@class,"rank-item")]')
            
            # 方式2: 查找包含数字序号的项目
            if not rank_items:
                rank_items = tree.xpath('//li[contains(@class,"rank")] | //div[contains(@class,"rank")]')
            
            # 方式3: 查找排行榜列表中的项目
            if not rank_items:
                rank_lists = tree.xpath('//*[contains(@class,"rank-list")]')
                if rank_lists:
                    rank_items = rank_lists[0].xpath('.//li | .//div[contains(@class,"item")]')
            
            out, seen = [], set()
            for item in rank_items:
                try:
                    links = item.xpath('.//a[contains(@href,"/detail/")]')
                    if not links:
                        continue
                    
                    link = links[0]
                    href = link.get("href", "")
                    vod_id = self._extract_vod_id(href)
                    if not vod_id or vod_id in seen:
                        continue
                    
                    seen.add(vod_id)
                    
                    # 获取图片
                    img_src = ""
                    img_elements = item.xpath('.//img')
                    for img in img_elements:
                        src = img.get("data-src") or img.get("src") or ""
                        if src:
                            img_src = src
                            break
                    
                    # 获取标题
                    title = ""
                    title_selectors = [
                        './/*[contains(@class,"title")]//text()',
                        './/*[contains(@class,"name")]//text()',
                    ]
                    for selector in title_selectors:
                        title_parts = item.xpath(selector)
                        if title_parts:
                            title = "".join(title_parts).strip()
                            if title:
                                break
                    
                    if not title:
                        title = link.get("title", "").strip()
                    
                    if not title:
                        continue
                    
                    # 获取标签/备注
                    tags = ""
                    tag_parts = item.xpath('.//*[contains(@class,"tags")]//text() | .//*[contains(@class,"tag")]//text()')
                    if tag_parts:
                        tags = "".join(tag_parts).strip()
                    
                    out.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": self._proxy_pic(img_src),
                        "vod_remarks": tags,
                    })
                except Exception:
                    continue
            
            return out
        except Exception as e:
            print(f"Extract rank items error: {e}")
            return []

    def _panel_total(self, html):
        """提取总数"""
        if not html:
            return 0
        patterns = [
            r'data-panel-total="(\d+)"',
            r'data-total="(\d+)"',
            r'共(\d+)个',
            r'总计(\d+)',
            r'total["\']?\s*[:=]\s*["\']?(\d+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return int(m.group(1))
        return 0

    # ---------- 接口 ----------
    def homeContent(self, filter):
        try:
            html = self._get(self.host)
            cards = self._cards(html, all_grids=True)
            return {"class": self.categories, "list": cards, "filters": {}}
        except Exception as e:
            print(f"Home content error: {e}")
            return {"class": self.categories, "list": [], "filters": {}}

    def homeVideoContent(self):
        try:
            html = self._get(self.host)
            return {"list": self._cards(html, all_grids=True)}
        except Exception as e:
            print(f"Home video error: {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid).strip("/")
        try:
            if "rank" in tid:
                url = f"{self.host}/{tid}/" if pg == 1 else f"{self.host}/{tid}/{pg}/"
                return {"page": pg, "pagecount": 9999, "limit": 20, "total": 99999, "list": self._rank_items(self._get(url))}
            
            url = f"{self.host}/{tid}/" if pg == 1 else f"{self.host}/{tid}/{pg}/"
            html = self._get(url)
            cards = self._cards(html)
            total = self._panel_total(html)
            pagecount = max(1, (total + 23) // 24) if total else 9999
            return {"page": pg, "pagecount": pagecount, "limit": 24, "total": total or 99999, "list": cards}
        except Exception as e:
            print(f"Category content error: {e}")
            return {"page": pg, "pagecount": 1, "limit": 24, "total": 0, "list": []}

    def detailContent(self, ids):
        vid = str(ids[0])
        result = {"list": []}
        try:
            html = self._get(f"{self.host}/detail/{vid}/")
            if not html:
                return result
            
            tree = etree.HTML(html)
            
            # 获取标题
            name = "".join(tree.xpath('//h1/text()')).strip()
            if not name:
                name = "".join(tree.xpath('//*[contains(@class,"title")]//text()')).strip()
            if not name:
                return result
            
            # 获取图片
            pic = ""
            pic_selectors = [
                '//*[contains(@class,"poster")]//img/@data-src',
                '//*[contains(@class,"poster")]//img/@src',
                '//img[contains(@class,"cover")]/@data-src',
                '//img[contains(@class,"cover")]/@src',
                '//div[contains(@class,"cover")]//img/@data-src',
                '//div[contains(@class,"cover")]//img/@src',
            ]
            for selector in pic_selectors:
                pic_list = tree.xpath(selector)
                if pic_list:
                    pic = pic_list[0].strip()
                    break
            
            # 获取描述
            desc = ""
            desc_selectors = [
                '//*[contains(@class,"desc")]/text()',
                '//*[contains(@class,"description")]/text()',
                '//*[contains(@class,"intro")]/text()',
            ]
            for selector in desc_selectors:
                desc_parts = tree.xpath(selector)
                if desc_parts:
                    desc = "".join(desc_parts).strip()
                    break
            
            # 获取播放列表
            eps = []
            
            # 方式1: 通过 ep-grid 查找
            ep_containers = tree.xpath('//*[contains(@class,"ep-grid")]')
            for container in ep_containers:
                for a in container.xpath('.//a'):
                    href = a.get("href", "")
                    if href:
                        ep_name = "".join(a.xpath(".//text()")).strip()
                        if not ep_name:
                            ep_name = f"第{len(eps)+1}集"
                        eps.append(f'{ep_name}${self._fix(href)}')
            
            # 方式2: 如果没有找到，查找播放按钮
            if not eps:
                play_btns = tree.xpath('//*[contains(@class,"play")]//a | //a[contains(@href,"/play/")]')
                for a in play_btns:
                    href = a.get("href", "")
                    if href:
                        ep_name = "".join(a.xpath(".//text()")).strip()
                        if not ep_name:
                            ep_name = f"第{len(eps)+1}集"
                        eps.append(f'{ep_name}${self._fix(href)}')
            
            # 方式3: 查找所有包含 detail 的链接
            if not eps:
                detail_links = tree.xpath('//a[contains(@href,"/detail/") and not(contains(@href,"/detail/{}/".format(vid)))]'.format(vid))
                for a in detail_links[:20]:  # 限制数量
                    href = a.get("href", "")
                    if href:
                        ep_name = "".join(a.xpath(".//text()")).strip()
                        if not ep_name:
                            ep_name = f"第{len(eps)+1}集"
                        eps.append(f'{ep_name}${self._fix(href)}')
            
            if not eps:
                return result
            
            # 构建信息
            info = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._proxy_pic(pic),
                "vod_play_from": "黄果短剧",
                "vod_play_url": "#".join(eps),
                "vod_content": desc,
            }
            
            # 获取备注
            remark = ""
            remark_selectors = [
                '//*[contains(@class,"episode")]//text()',
                '//*[contains(@class,"info")]//text()',
            ]
            for selector in remark_selectors:
                remark_parts = tree.xpath(selector)
                if remark_parts:
                    remark = "".join(remark_parts).strip()
                    if remark:
                        break
            if remark:
                info["vod_remarks"] = remark
            
            # 获取标签
            tags = tree.xpath('//*[contains(@class,"tag")]//text()')
            if tags:
                info["vod_class"] = ",".join([t.strip() for t in tags if t.strip()])
            
            result["list"].append(info)
            return result
        except Exception as e:
            print(f"Detail content error: {e}")
            return result

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}/search/video/{quote(key)}/"
            return {"list": self._cards(self._get(url)), "page": int(pg or 1)}
        except Exception as e:
            print(f"Search error: {e}")
            return {"list": [], "page": int(pg or 1)}

    def playerContent(self, flag, id, vipFlags):
        url = self._fix(id)
        play = ""
        try:
            html = self._get(url, referer=self.host)
            if html:
                # 尝试多种方式获取播放地址
                # 方式1: JSON数据
                mm = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html, re.S)
                if mm:
                    try:
                        data = json.loads(mm.group(1))
                        if isinstance(data, dict):
                            em = re.search(r'/ep-(\d+)/', url)
                            ep = str(em.group(1)) if em else "1"
                            srcs = data.get("epPlaySrcs") or {}
                            play = srcs.get(ep) or data.get("videoSrc") or ""
                    except Exception:
                        pass
                
                # 方式2: video标签
                if not play:
                    video_src = re.search(r'<video[^>]*src=["\']([^"\']+)["\']', html, re.I)
                    if video_src:
                        play = video_src.group(1)
                
                # 方式3: iframe
                if not play:
                    iframe_src = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html, re.I)
                    if iframe_src:
                        play = iframe_src.group(1)
                
                # 方式4: source标签
                if not play:
                    source_src = re.search(r'<source[^>]*src=["\']([^"\']+)["\']', html, re.I)
                    if source_src:
                        play = source_src.group(1)
        except Exception as e:
            print(f"Player error: {e}")
        
        if play:
            play = play.replace("\\u0026", "&")
            if not play.startswith("http"):
                mm2 = re.search(r'(https?://[^\s"\']+)', play)
                play = mm2.group(1) if mm2 else ""
        
        header = {
            "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0"),
            "Referer": self.host + "/",
        }
        return {"parse": 0, "url": play, "header": header}

    def localProxy(self, param):
        try:
            if param and param.get("type") == "img":
                raw = param.get("url", "") or ""
                if raw:
                    url = b64decode(unquote(raw).encode("utf-8")).decode("utf-8")
                    url = self._img_src(url)
                    if url:
                        raw = self._get_bin(url)
                        if raw:
                            data = self._decrypt_img(raw)
                            return [200, self._img_ct(data), data]
        except Exception:
            pass
        return None

    def isVideoFormat(self, url):
        return ".m3u8" in (url or "") or ".mp4" in (url or "")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None