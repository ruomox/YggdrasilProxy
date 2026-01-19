# src/constants.py

# 程序基础信息
PROXY_NAME = "YggdrasilProxy"
PROXY_VERSION = "1.0.0"
CONFIG_VERSION = 1

# Yggdrasil 协议标准常量
AUTH_AGENT = {
    "name": "Minecraft",
    "version": 1
}

# 文件名常量
CONFIG_FILENAME = "YggProxy.json"
KEY_FILENAME = "YggProxy.key"
DATA_DIR_NAME = ".YggProxy"
# 运行时子目录名
RUNTIME_DIR_NAME = "YggProRuntime"
JRE_DIR_NAME = "YggProJRE"
INJECTOR_FILENAME = "authlib-injector.jar"

# 强制显示设置界面的参数集合
SETTINGS_ARGS = {"--yggproconfig"}

# Minecraft 主类名标识
MC_MAIN_CLASS = "net.minecraft.client.main.Main"

# 默认的伪装版本字符串
DEFAULT_SPOOF_VERSION = ""

# 默认 API 列表模板
DEFAULT_API_LIST = [
    {
        "name": "LittleSkin (默认)",
        "base_url": "https://littleskin.cn/api/yggdrasil",
    }
]