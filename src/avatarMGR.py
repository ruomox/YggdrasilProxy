# src/avatarMGR.py
import os
import threading
import requests
import base64
import json
import io
import glob
from PIL import Image
from src.configMGR import config_mgr


class AvatarManager:
    """
    头像管理器
    负责：异步下载、基于Hash的缓存更新、图像裁剪
    """
    # 缓存路径：.YggProxy/cache/avatars
    CACHE_DIR = os.path.join(config_mgr._data_dir, "cache", "avatars")

    # 内存缓存 (Session级)，防止短时间内频繁读取磁盘
    # key: uuid, value: PIL.Image
    _MEM_CACHE = {}
    _LOCK = threading.Lock()

    @classmethod
    def get_avatar(cls, uuid, api_url, callback):
        """
        [异步入口] 获取头像
        :param uuid: 玩家 UUID
        :param api_url: 认证服务器 Base URL
        :param callback: 回调函数，接收参数 (PIL.Image or None)
        """
        # 启动后台线程，避免卡顿 GUI
        threading.Thread(target=cls._worker, args=(uuid, api_url, callback), daemon=True).start()

    @classmethod
    def _worker(cls, uuid, api_url, callback):
        try:
            # 1. 确保缓存目录存在
            if not os.path.exists(cls.CACHE_DIR):
                os.makedirs(cls.CACHE_DIR, exist_ok=True)

            # 2. 获取 Profile 以拿到最新的皮肤 Hash
            # 注意：这一步是轻量级网络请求，为了感知更新，这步是必须的
            # (如果完全离线，可以跳过这步直接读本地文件，但就无法感知更新了)
            try:
                profile_url = f"{api_url}/sessionserver/session/minecraft/profile/{uuid}"
                resp = requests.get(profile_url, timeout=3)
                resp.raise_for_status()
                data = resp.json()

                skin_url = cls._extract_skin_url(data)

                # 如果没有皮肤 (Steve/Alex)，尝试加载本地任意旧缓存，或者返回默认
                if not skin_url:
                    img = cls._get_default_steve()
                    callback(img)
                    return

                # 3. 计算 Hash (通常是 URL 的最后一部分)
                # 例如: http://.../texture/5f8c... -> 5f8c...
                skin_hash = skin_url.split('/')[-1]

                # 构造带 Hash 的缓存文件名
                # 格式: {uuid}@{hash}.png
                expected_filename = f"{uuid}@{skin_hash}.png"
                expected_path = os.path.join(cls.CACHE_DIR, expected_filename)

                # 4. 检查缓存
                if os.path.exists(expected_path):
                    # --- 命中缓存 ---
                    # print(f"[Avatar] Cache Hit: {uuid}")
                    img = Image.open(expected_path)
                    callback(img)
                    return

                # 5. 缓存未命中 (皮肤已更新 或 首次加载) -> 下载
                # print(f"[Avatar] Downloading new skin: {uuid}")

                skin_resp = requests.get(skin_url, timeout=5)
                skin_resp.raise_for_status()

                # 处理图片
                skin_bytes = io.BytesIO(skin_resp.content)
                skin_img = Image.open(skin_bytes)

                # 裁剪头部 (8, 8) 到 (16, 16)
                head_img = skin_img.crop((8, 8, 16, 16))
                # 放大到 64x64 (使用邻近采样保持像素风)
                head_img = head_img.resize((64, 64), Image.Resampling.NEAREST)

                # 保存新缓存
                head_img.save(expected_path)

                # 6. 清理该 UUID 的旧缓存 (删除 uuid@old_hash.png)
                cls._clean_old_cache(uuid, skin_hash)

                callback(head_img)

            except Exception as e:
                # print(f"[Avatar] Network/Parse Error: {e}")
                # 网络失败时，降级策略：查找本地是否有名为 {uuid}@*.png 的任何文件
                fallback = cls._find_any_local_cache(uuid)
                if fallback:
                    callback(fallback)
                else:
                    callback(cls._get_default_steve())

        except Exception as e:
            # print(f"[Avatar] Fatal Error: {e}")
            callback(None)

    @staticmethod
    def _extract_skin_url(profile_json):
        """从 Profile JSON 中解析 Base64 纹理"""
        try:
            properties = profile_json.get("properties", [])
            for prop in properties:
                if prop.get("name") == "textures":
                    texture_b64 = prop.get("value")
                    texture_json = json.loads(base64.b64decode(texture_b64))
                    return texture_json.get("textures", {}).get("SKIN", {}).get("url")
        except:
            pass
        return None

    @classmethod
    def _clean_old_cache(cls, uuid, current_hash):
        """删除同 UUID 但 Hash 不匹配的旧图片"""
        pattern = os.path.join(cls.CACHE_DIR, f"{uuid}@*.png")
        for f in glob.glob(pattern):
            # 如果文件名里不包含当前的 hash，删掉
            if current_hash not in f:
                try:
                    os.remove(f)
                    # print(f"[Avatar] Cleaned old cache: {f}")
                except:
                    pass

    @classmethod
    def _find_any_local_cache(cls, uuid):
        """网络断开时，寻找本地该 UUID 的任意一张缓存"""
        pattern = os.path.join(cls.CACHE_DIR, f"{uuid}@*.png")
        files = glob.glob(pattern)
        if files:
            # 返回找到的第一张 (通常也是唯一一张)
            return Image.open(files[0])
        return None

    @staticmethod
    def _get_default_steve():
        """生成一个灰色的默认头像"""
        img = Image.new('RGB', (64, 64), color='#777777')
        return img