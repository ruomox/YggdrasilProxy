# src/avatarMGR.py
import os
import threading
import requests
import base64
import json
import io
import glob
from PIL import Image, ImageDraw
from src.configMGR import config_mgr


class AvatarManager:
    CACHE_DIR = os.path.join(config_mgr._data_dir, "cache", "avatars")

    # 定义放大倍数
    SCALE_HEAD = 8  # 内层放大 8 倍 (8x8 -> 64x64)
    SCALE_HAT = 9  # 外层放大 9 倍 (8x8 -> 72x72) -> 这样帽子就比头大一圈
    CANVAS_SIZE = 72  # 最终图片大小

    @classmethod
    def get_avatar(cls, uuid, api_url, callback):
        threading.Thread(target=cls._worker, args=(uuid, api_url, callback), daemon=True).start()

    @classmethod
    def get_local_cache_sync(cls, uuid):
        clean_uuid = uuid.replace("-", "")
        if os.path.exists(cls.CACHE_DIR):
            pattern = os.path.join(cls.CACHE_DIR, f"{clean_uuid}@*.png")
            files = glob.glob(pattern)
            if files:
                try:
                    return Image.open(files[0])
                except:
                    pass
        return cls._get_default_steve()

    @classmethod
    def _worker(cls, uuid, api_url, callback):
        try:
            if not os.path.exists(cls.CACHE_DIR):
                os.makedirs(cls.CACHE_DIR, exist_ok=True)

            clean_uuid = uuid.replace("-", "")

            try:
                api_base = api_url.rstrip('/')
                profile_url = f"{api_base}/sessionserver/session/minecraft/profile/{clean_uuid}"

                resp = requests.get(profile_url, timeout=3)
                resp.raise_for_status()
                data = resp.json()

                skin_url = cls._extract_skin_url(data)

                if not skin_url:
                    callback(cls._get_default_steve())
                    return

                skin_hash = skin_url.split('/')[-1]
                expected_filename = f"{clean_uuid}@{skin_hash}.png"
                expected_path = os.path.join(cls.CACHE_DIR, expected_filename)

                if os.path.exists(expected_path):
                    return

                # 下载
                skin_resp = requests.get(skin_url, timeout=5)
                skin_resp.raise_for_status()
                skin_img = Image.open(io.BytesIO(skin_resp.content)).convert("RGBA")

                # --- 核心图像处理：差值放大法 (Hat Expansion) ---

                # 1. 裁剪原始像素 (8x8)
                raw_head = skin_img.crop((8, 8, 16, 16))
                raw_hat = skin_img.crop((40, 8, 48, 16))

                # 2. 差异化放大
                # 头部放大 8 倍 (64x64)
                head_big = raw_head.resize((cls.SCALE_HEAD * 8, cls.SCALE_HEAD * 8), Image.Resampling.NEAREST)
                # 帽子放大 9 倍 (72x72) -> 这样帽子就有了物理厚度
                hat_big = raw_hat.resize((cls.SCALE_HAT * 8, cls.SCALE_HAT * 8), Image.Resampling.NEAREST)

                # 3. 添加光照渐变 (仅给脸部加，帽子保持原色更通透)
                head_big = cls._add_lighting_gradient(head_big)

                # 4. 制作投影 (基于大号帽子的投影)
                # 投影也要有点偏移，让它投射在脸上
                hat_a = hat_big.split()[3]
                shadow_a = hat_a.point(lambda i: 60 if i > 0 else 0)  # 60透明度
                shadow_rgb = Image.new("RGB", hat_big.size, (0, 0, 0))
                shadow_layer = Image.merge("RGBA", (*shadow_rgb.split(), shadow_a))

                # 5. 合成画布 (72x72)
                # 创建全透明底图
                final = Image.new("RGBA", (cls.CANVAS_SIZE, cls.CANVAS_SIZE), (0, 0, 0, 0))

                # 计算头部居中坐标: (72 - 64) / 2 = 4
                offset = (cls.CANVAS_SIZE - head_big.width) // 2  # (4, 4)

                # A. 贴头部 (居中)
                final.paste(head_big, (offset, offset), head_big)

                # B. 贴投影 (帽子层产生的阴影)
                # 投影向右下偏移 4px
                final = Image.alpha_composite(final, Image.new("RGBA", final.size).paste(shadow_layer, (4,
                                                                                                        4)) or shadow_layer)  # 简化写法，直接覆盖
                # 修正：上面写法比较绕，直接用 composite
                # 创建一个跟final一样大的图层放阴影，阴影向右下偏移4px
                shadow_canvas = Image.new("RGBA", final.size, (0, 0, 0, 0))
                shadow_canvas.paste(shadow_layer, (4, 4))  # 阴影偏移
                final = Image.alpha_composite(final, shadow_canvas)

                # C. 贴帽子 (铺满 72x72)
                final = Image.alpha_composite(final, hat_big)

                final.save(expected_path)
                cls._clean_old_cache(clean_uuid, skin_hash)

                callback(final)

            except Exception:
                pass

        except Exception:
            pass

    @staticmethod
    def _add_lighting_gradient(img):
        width, height = img.size
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for y in range(height):
            factor = y / height
            if factor < 0.5:
                alpha = int((0.5 - factor) * 2 * 30)
                draw.line([(0, y), (width, y)], fill=(255, 255, 255, alpha))
            else:
                alpha = int((factor - 0.5) * 2 * 60)
                draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
        return Image.alpha_composite(img, overlay)

    @staticmethod
    def _extract_skin_url(profile_json):
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
        pattern = os.path.join(cls.CACHE_DIR, f"{uuid}@*.png")
        for f in glob.glob(pattern):
            if current_hash not in f:
                try:
                    os.remove(f)
                except:
                    pass

    @staticmethod
    def _get_default_steve():
        # Steve 基础 (8x8)
        base_color = (188, 134, 97)
        hair_color = (60, 40, 40)
        eye_white = (255, 255, 255)
        eye_pupil = (73, 76, 176)
        nose_color = (108, 66, 44)

        img = Image.new('RGBA', (8, 8), color=base_color)
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0), (7, 1)], fill=hair_color)
        draw.point((1, 3), fill=eye_white);
        draw.point((2, 3), fill=eye_pupil)
        draw.point((5, 3), fill=eye_white);
        draw.point((6, 3), fill=eye_pupil)
        draw.point((3, 4), fill=nose_color);
        draw.point((4, 4), fill=nose_color)
        draw.rectangle([(2, 5), (5, 5)], fill=nose_color)

        # 放大头部到 64x64
        head_big = img.resize((64, 64), Image.Resampling.NEAREST)
        head_big = AvatarManager._add_lighting_gradient(head_big)

        # 放置到 72x72 画布中心
        final = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
        offset = (72 - 64) // 2
        final.paste(head_big, (offset, offset))

        # 给 Steve 加一个假的“头发层”阴影，假装有帽子
        draw_shadow = ImageDraw.Draw(final)
        # 额头阴影
        draw_shadow.rectangle([(offset, offset + 16), (offset + 64, offset + 20)], fill=(0, 0, 0, 40))

        return final