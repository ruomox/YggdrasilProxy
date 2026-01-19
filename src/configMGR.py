# src/configMGR.py
import os
import sys
import json
import shutil
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
        self._base_path = self._get_base_path()
        self._data_dir = os.path.join(self._base_path, constants.DATA_DIR_NAME)
        self._runtime_dir = os.path.join(self._data_dir, constants.RUNTIME_DIR_NAME)
        self._config_file = os.path.join(self._data_dir, constants.CONFIG_FILENAME)
        self._key_file = os.path.join(self._data_dir, constants.KEY_FILENAME)
        self._cipher_suite = None
        # 默认配置结构更新
        self._config_data = {
            "configVersion": constants.CONFIG_VERSION,
            "real_java_path": None,
            "auth_encrypted": None,
            "api_list": constants.DEFAULT_API_LIST,  # API 列表
            "current_api_index": 0,  # 当前选中的 API 索引
            "spoof_version": constants.DEFAULT_SPOOF_VERSION    # 伪装版本号
        }
        self._ensure_data_dir()
        self._load_or_create_key()
        self._initialized = True

    def get_enable_embedded_java(self):
        return self._config_data.get("enable_embedded_java", False)

    def set_enable_embedded_java(self, enabled):
        self._config_data["enable_embedded_java"] = enabled

    def _get_base_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _ensure_data_dir(self):
        os.makedirs(self._data_dir, exist_ok=True)
        os.makedirs(self._runtime_dir, exist_ok=True)

    def _load_or_create_key(self):
        if os.path.exists(self._key_file):
            try:
                with open(self._key_file, 'rb') as f:
                    key = f.read()
                self._cipher_suite = Fernet(key)
            except Exception as e:
                print(f"[{constants.PROXY_NAME}] 密钥文件损坏，将重新生成: {e}", file=sys.stderr)
                os.remove(self._key_file)
                self._load_or_create_key()
        else:
            key = Fernet.generate_key()
            with open(self._key_file, 'wb') as f:
                f.write(key)
            self._cipher_suite = Fernet(key)

    def _encrypt(self, data_dict):
        json_str = json.dumps(data_dict)
        return self._cipher_suite.encrypt(json_str.encode()).decode()

    def _decrypt(self, encrypted_str):
        try:
            decrypted_json = self._cipher_suite.decrypt(encrypted_str.encode()).decode()
            return json.loads(decrypted_json)
        except Exception:
            print(f"[{constants.PROXY_NAME}] 数据解密失败，可能是密钥不匹配或数据损坏。", file=sys.stderr)
            return None

    def load(self):
        if "spoof_version" not in self._config_data:
            self._config_data["spoof_version"] = constants.DEFAULT_SPOOF_VERSION
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # 简单的版本检查，如果版本旧，可能需要迁移逻辑(这里简单处理为合并覆盖)
                    if loaded_config.get("configVersion") != constants.CONFIG_VERSION:
                        print(f"[{constants.PROXY_NAME}] 配置文件版本旧，将自动更新结构。")
                    self._config_data.update(loaded_config)
                # 确保新字段存在 (处理旧配置文件升级的情况)
                if "api_list" not in self._config_data:
                    self._config_data["api_list"] = constants.DEFAULT_API_LIST
                if "current_api_index" not in self._config_data:
                    self._config_data["current_api_index"] = 0
                return True
            except Exception as e:
                print(f"[{constants.PROXY_NAME}] 加载配置文件失败: {e}，将使用默认设置。", file=sys.stderr)
                # 如果加载失败，备份旧文件
                try:
                    shutil.copy(self._config_file, self._config_file + ".bak")
                    print(f"[{constants.PROXY_NAME}] 已备份损坏的配置文件。", file=sys.stderr)
                except:
                    pass
                return False
        return False

    def save(self):
        try:
            self._config_data["configVersion"] = constants.CONFIG_VERSION
            with open(self._config_file, 'w') as f:
                json.dump(self._config_data, f, indent=4)
        except Exception as e:
            print(f"[{constants.PROXY_NAME}] 严重错误: 无法保存配置文件: {e}", file=sys.stderr)

    # --- 公共 API ---
    def get_runtime_dir(self):
        return self._runtime_dir

    def get_spoof_version(self):
        return self._config_data.get("spoof_version", constants.DEFAULT_SPOOF_VERSION)

    def set_spoof_version(self, version):
        self._config_data["spoof_version"] = version

    def get_real_java_path(self):
        return self._config_data.get("real_java_path")

    def set_real_java_path(self, path):
        self._config_data["real_java_path"] = path

    def get_auth_data(self):
        if not self._config_data.get("auth_encrypted"):
            return None
        return self._decrypt(self._config_data["auth_encrypted"])

    def set_auth_data(self, auth_dict):
        if auth_dict is None:
            self._config_data["auth_encrypted"] = None
        else:
            self._config_data["auth_encrypted"] = self._encrypt(auth_dict)

    # --- API 管理相关 ---
    def get_api_list(self):
        # 直接返回存储的列表，不做任何动态拼接
        return self._config_data.get("api_list", constants.DEFAULT_API_LIST)

    def set_api_list(self, api_list):
        self._config_data["api_list"] = api_list

    def get_current_api_index(self):
        return self._config_data.get("current_api_index", 0)

    def set_current_api_index(self, index):
        self._config_data["current_api_index"] = index

    def get_current_api_config(self):
        """获取当前选中的 API 配置字典"""
        api_list = self.get_api_list()
        idx = self.get_current_api_index()
        # 确保返回一个有效的配置项，包含 base_url
        if 0 <= idx < len(api_list):
            api_config = api_list[idx]
        elif api_list:
            api_config = api_list[0]
        else:
            api_config = constants.DEFAULT_API_LIST[0]

        # 确保 base_url 没有尾部的斜杠，方便后续拼接
        if "base_url" in api_config:
            api_config["base_url"] = api_config["base_url"].rstrip('/')

        return api_config


config_mgr = ConfigManager()  # 导出单例实例