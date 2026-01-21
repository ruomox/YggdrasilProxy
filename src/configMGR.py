# src/configMGR.py
import os
import sys
import json
import shutil
import threading
import platform
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

        self._lock = threading.RLock()

        self._base_path = self._get_base_path()
        self._data_dir = os.path.join(self._base_path, constants.DATA_DIR_NAME)
        self._runtime_dir = os.path.join(self._data_dir, constants.RUNTIME_DIR_NAME)
        self._config_file = os.path.join(self._data_dir, constants.CONFIG_FILENAME)
        self._key_file = os.path.join(self._data_dir, constants.KEY_FILENAME)
        self._cipher_suite = None

        self._config_data = {
            "configVersion": constants.CONFIG_VERSION,
            "real_java_path": None,
            "accounts": {},
            "instance_map": {},
            "login_history": [],
            "default_account_uuid": None,  # 仍保留作为 GUI 选中的临时存储
            "api_list": constants.DEFAULT_API_LIST,
            "current_api_index": 0
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
        if not path: return None
        abs_path = os.path.abspath(path)
        if platform.system() == "Windows":
            return os.path.normcase(abs_path)
        else:
            return os.path.normpath(abs_path)

    def _load_or_create_key(self):
        with self._lock:
            if os.path.exists(self._key_file):
                try:
                    with open(self._key_file, 'rb') as f:
                        key = f.read()
                    self._cipher_suite = Fernet(key)
                except Exception:
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

                    if "accounts" in raw_data: self._config_data["accounts"] = raw_data["accounts"]
                    if "instance_map" in raw_data: self._config_data["instance_map"] = raw_data["instance_map"]
                    if "login_history" in raw_data: self._config_data["login_history"] = raw_data["login_history"]

                    for k, v in raw_data.items():
                        if k not in ["accounts", "instance_map", "login_history"]:
                            self._config_data[k] = v

                    accounts = self._config_data.get("accounts", {})
                    for uuid, acc_data in accounts.items():
                        if "accessToken" in acc_data and str(acc_data["accessToken"]).startswith("gAAAA"):
                            dec = self._decrypt_str(acc_data["accessToken"])
                            if dec:
                                acc_data["accessToken"] = dec
                            else:
                                acc_data["accessToken"] = ""

                    return True
                except Exception as e:
                    print(f"[{constants.PROXY_NAME}] Config Load Error: {e}", file=sys.stderr)
                    return False
            return False

    def save(self):
        with self._lock:
            try:
                data_to_save = json.loads(json.dumps(self._config_data))
                accounts = data_to_save.get("accounts", {})
                for uuid, acc_data in accounts.items():
                    if "accessToken" in acc_data:
                        acc_data["accessToken"] = self._encrypt_str(acc_data["accessToken"])

                tmp_file = self._config_file + ".tmp"
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, indent=4)

                shutil.move(tmp_file, self._config_file)
            except Exception as e:
                print(f"[{constants.PROXY_NAME}] Config Save Error: {e}", file=sys.stderr)

    # --- 账号管理 ---

    def add_or_update_account(self, auth_data):
        with self._lock:
            if not auth_data or "uuid" not in auth_data: return
            uuid = auth_data["uuid"]
            if "accounts" not in self._config_data:
                self._config_data["accounts"] = {}
            self._config_data["accounts"][uuid] = auth_data

            # 如果没有默认，顺便设一个，避免 GUI 取空
            if not self._config_data.get("default_account_uuid"):
                self._config_data["default_account_uuid"] = uuid

            self.save()

    def get_account(self, uuid):
        with self._lock:
            return self._config_data.get("accounts", {}).get(uuid)

    def get_all_accounts(self):
        with self._lock:
            return [v.copy() for v in self._config_data.get("accounts", {}).values()]

    def remove_account(self, uuid):
        with self._lock:
            if "accounts" in self._config_data and uuid in self._config_data["accounts"]:
                del self._config_data["accounts"][uuid]
                # 如果删的是默认的，重置默认
                if self._config_data.get("default_account_uuid") == uuid:
                    keys = list(self._config_data["accounts"].keys())
                    self._config_data["default_account_uuid"] = keys[0] if keys else None
                self.save()

    def get_history_users(self):
        with self._lock:
            return self._config_data.get("login_history", [])

    def add_history_user(self, email):
        with self._lock:
            hist = self._config_data.get("login_history", [])
            if email in hist: hist.remove(email)
            hist.insert(0, email)
            self._config_data["login_history"] = hist[:5]
            self.save()

    # --- 实例绑定 API ---

    def get_account_for_instance(self, game_dir):
        """
        根据游戏目录获取绑定的 UUID。
        传 None 则返回 default_account_uuid (供 GUI 获取当前选中)
        """
        with self._lock:
            if game_dir is None:
                return self._config_data.get("default_account_uuid")

            norm_path = self._normalize_path(game_dir)
            bound_uuid = self._config_data.get("instance_map", {}).get(norm_path)

            if bound_uuid and bound_uuid in self._config_data.get("accounts", {}):
                return bound_uuid

            return None

    def set_instance_binding(self, game_dir, uuid):
        with self._lock:
            if not game_dir or not uuid: return
            norm_path = self._normalize_path(game_dir)

            if "instance_map" not in self._config_data:
                self._config_data["instance_map"] = {}

            self._config_data["instance_map"][norm_path] = uuid
            self.save()

    # --- Getters/Setters ---

    # 【修复点】补上了缺失的 get_runtime_dir
    def get_runtime_dir(self):
        return self._runtime_dir

    def get_real_java_path(self):
        with self._lock: return self._config_data.get("real_java_path")

    def set_real_java_path(self, path):
        with self._lock: self._config_data["real_java_path"] = path

    def get_api_list(self):
        with self._lock: return list(self._config_data.get("api_list", constants.DEFAULT_API_LIST))

    def set_api_list(self, l):
        with self._lock: self._config_data["api_list"] = l

    def get_current_api_index(self):
        with self._lock: return self._config_data.get("current_api_index", 0)

    def set_current_api_index(self, i):
        with self._lock: self._config_data["current_api_index"] = i

    def get_current_api_config(self):
        with self._lock:
            l = self.get_api_list()
            i = self.get_current_api_index()
            cfg = l[i] if 0 <= i < len(l) else (l[0] if l else constants.DEFAULT_API_LIST[0])
            cfg = cfg.copy()
            if "base_url" in cfg: cfg["base_url"] = cfg["base_url"].rstrip('/')
            return cfg

    # GUI 用
    def set_default_account(self, uuid):
        with self._lock:
            if uuid in self._config_data.get("accounts", {}):
                self._config_data["default_account_uuid"] = uuid
                self.save()


config_mgr = ConfigManager()