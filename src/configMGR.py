# src/configMGR.py
import os
import sys
import json
import shutil
import threading
from cryptography.fernet import Fernet
from src import constants


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 线程锁
        self._lock = threading.RLock()

        self._base_path = self._get_base_path()
        self._data_dir = os.path.join(self._base_path, constants.DATA_DIR_NAME)
        self._runtime_dir = os.path.join(self._data_dir, constants.RUNTIME_DIR_NAME)
        self._config_file = os.path.join(self._data_dir, constants.CONFIG_FILENAME)
        self._key_file = os.path.join(self._data_dir, constants.KEY_FILENAME)
        self._cipher_suite = None

        # --- 新版配置结构 ---
        self._config_data = {
            "configVersion": constants.CONFIG_VERSION,
            "real_java_path": None,

            # 账号存储: { "UUID字符串": { "name": "...", "accessToken": "...", ... } }
            "accounts": {},

            # 实例绑定: { "norm_path": "UUID字符串" }
            "instance_map": {},

            # 登录历史 (仅保存用户名/邮箱)
            "login_history": [],

            # 全局默认账号 UUID
            "default_account_uuid": None,

            "api_list": constants.DEFAULT_API_LIST,
            "current_api_index": 0,
            "spoof_version": constants.DEFAULT_SPOOF_VERSION
        }

        self._ensure_data_dir()
        self._load_or_create_key()
        self._initialized = True

    def _get_base_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _ensure_data_dir(self):
        os.makedirs(self._data_dir, exist_ok=True)
        os.makedirs(self._runtime_dir, exist_ok=True)

    def _normalize_path(self, path):
        """统一路径格式，解决 Windows 大小写问题"""
        if not path: return None
        abs_path = os.path.abspath(path)
        return os.path.normcase(abs_path)

    def _load_or_create_key(self):
        with self._lock:
            if os.path.exists(self._key_file):
                try:
                    with open(self._key_file, 'rb') as f:
                        key = f.read()
                    self._cipher_suite = Fernet(key)
                except Exception as e:
                    print(f"[{constants.PROXY_NAME}] 密钥重置: {e}", file=sys.stderr)
                    try:
                        os.remove(self._key_file)
                    except:
                        pass
                    self._load_or_create_key()
            else:
                key = Fernet.generate_key()
                with open(self._key_file, 'wb') as f:
                    f.write(key)
                self._cipher_suite = Fernet(key)

    # --- 加密辅助 ---
    def _encrypt_str(self, text):
        if not text: return None
        return self._cipher_suite.encrypt(text.encode()).decode()

    def _decrypt_str(self, text):
        if not text: return None
        try:
            return self._cipher_suite.decrypt(text.encode()).decode()
        except:
            return None

    # --- IO 操作 ---
    def load(self):
        with self._lock:
            if os.path.exists(self._config_file):
                try:
                    with open(self._config_file, 'r', encoding='utf-8') as f:
                        raw_data = json.load(f)

                    # 迁移旧配置 logic (省略详细迁移代码，保持结构清晰)
                    if "auth_encrypted" in raw_data:
                        # ... (保持你原有的迁移逻辑) ...
                        pass

                    # 更新内存数据
                    # 使用 update 会导致删除的 key 在内存中残留，但在 Config 这种简单场景下通常问题不大
                    # 严谨做法是针对 accounts 等 dict 字段做全量替换
                    if "accounts" in raw_data:
                        self._config_data["accounts"] = raw_data["accounts"]
                    if "instance_map" in raw_data:
                        self._config_data["instance_map"] = raw_data["instance_map"]

                    # 更新其他字段
                    for k, v in raw_data.items():
                        if k not in ["accounts", "instance_map"]:
                            self._config_data[k] = v

                    # 解密 accounts 中的敏感字段
                    accounts = self._config_data.get("accounts", {})
                    for uuid, acc_data in accounts.items():
                        # 如果是密文 (简单判断)
                        if "accessToken" in acc_data and str(acc_data["accessToken"]).startswith("gAAAA"):
                            dec = self._decrypt_str(acc_data["accessToken"])
                            if dec:
                                acc_data["accessToken"] = dec
                            else:
                                # 解密失败，置空以触发重新登录
                                acc_data["accessToken"] = ""
                                print(f"[{constants.PROXY_NAME}] 警告: 账号 {acc_data.get('name')} Token 解密失败。",
                                      file=sys.stderr)

                    return True
                except Exception as e:
                    print(f"[{constants.PROXY_NAME}] 配置加载失败: {e}", file=sys.stderr)
                    return False
            return False

    def save(self):
        with self._lock:
            try:
                # 深拷贝一份用于保存
                data_to_save = json.loads(json.dumps(self._config_data))

                # 加密敏感字段
                accounts = data_to_save.get("accounts", {})
                for uuid, acc_data in accounts.items():
                    if "accessToken" in acc_data:
                        acc_data["accessToken"] = self._encrypt_str(acc_data["accessToken"])

                # 原子写入: write temp -> rename
                tmp_file = self._config_file + ".tmp"
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, indent=4)

                shutil.move(tmp_file, self._config_file)
            except Exception as e:
                print(f"[{constants.PROXY_NAME}] 配置保存失败: {e}", file=sys.stderr)

    # --- 账号管理 API ---

    def add_or_update_account(self, auth_data):
        with self._lock:
            if not auth_data or "uuid" not in auth_data: return
            uuid = auth_data["uuid"]

            if "accounts" not in self._config_data:
                self._config_data["accounts"] = {}

            self._config_data["accounts"][uuid] = auth_data

            # 如果没有默认账号，设为当前
            if not self._config_data.get("default_account_uuid"):
                self._config_data["default_account_uuid"] = uuid

            self.save()

    def get_account(self, uuid):
        with self._lock:
            return self._config_data.get("accounts", {}).get(uuid)

    def get_all_accounts(self):
        """返回所有账号列表"""
        with self._lock:
            # 返回副本以防外部修改影响内部状态
            return [v.copy() for v in self._config_data.get("accounts", {}).values()]

    def remove_account(self, uuid):
        with self._lock:
            if "accounts" in self._config_data and uuid in self._config_data["accounts"]:
                del self._config_data["accounts"][uuid]
                if self._config_data.get("default_account_uuid") == uuid:
                    keys = list(self._config_data["accounts"].keys())
                    self._config_data["default_account_uuid"] = keys[0] if keys else None
                self.save()

    # --- 历史记录 API (新增) ---
    def get_history_users(self):
        with self._lock:
            return self._config_data.get("login_history", [])

    def add_history_user(self, email):
        with self._lock:
            if "login_history" not in self._config_data:
                self._config_data["login_history"] = []

            history = self._config_data["login_history"]
            if email in history:
                history.remove(email)
            history.insert(0, email)

            # 限制历史记录数量 (例如 5 条)
            if len(history) > 5:
                self._config_data["login_history"] = history[:5]

            self.save()

    # --- 实例绑定 API ---

    def get_account_for_instance(self, game_dir):
        with self._lock:
            if not game_dir:
                return self._config_data.get("default_account_uuid")

            norm_path = self._normalize_path(game_dir)
            bound_uuid = self._config_data.get("instance_map", {}).get(norm_path)

            if bound_uuid and bound_uuid in self._config_data.get("accounts", {}):
                return bound_uuid

            return self._config_data.get("default_account_uuid")

    def set_instance_binding(self, game_dir, uuid):
        with self._lock:
            if not game_dir or not uuid: return
            norm_path = self._normalize_path(game_dir)

            if "instance_map" not in self._config_data:
                self._config_data["instance_map"] = {}

            self._config_data["instance_map"][norm_path] = uuid
            self.save()

    # --- Getters/Setters ---

    def get_runtime_dir(self):
        return self._runtime_dir

    def get_real_java_path(self):
        with self._lock:
            return self._config_data.get("real_java_path")

    def set_real_java_path(self, path):
        with self._lock:
            self._config_data["real_java_path"] = path

    def get_spoof_version(self):
        with self._lock:
            return self._config_data.get("spoof_version", constants.DEFAULT_SPOOF_VERSION)

    def set_spoof_version(self, v):
        with self._lock:
            self._config_data["spoof_version"] = v

    def get_api_list(self):
        with self._lock:
            # 返回副本
            return list(self._config_data.get("api_list", constants.DEFAULT_API_LIST))

    def set_api_list(self, api_list):
        with self._lock:
            self._config_data["api_list"] = api_list

    def get_current_api_index(self):
        with self._lock:
            return self._config_data.get("current_api_index", 0)

    def set_current_api_index(self, index):
        with self._lock:
            self._config_data["current_api_index"] = index

    def get_current_api_config(self):
        with self._lock:
            api_list = self.get_api_list()
            idx = self.get_current_api_index()
            if 0 <= idx < len(api_list):
                cfg = api_list[idx]
            elif api_list:
                cfg = api_list[0]
            else:
                cfg = constants.DEFAULT_API_LIST[0]

            cfg = cfg.copy()
            if "base_url" in cfg:
                cfg["base_url"] = cfg["base_url"].rstrip('/')
            return cfg

    # 简便方法：设置默认账号
    def set_default_account(self, uuid):
        with self._lock:
            if uuid in self._config_data.get("accounts", {}):
                self._config_data["default_account_uuid"] = uuid
                self.save()


config_mgr = ConfigManager()