# src/constants.py

# 程序基础信息
PROXY_NAME = "YggdrasilProxy"
PROXY_VERSION = "1.0.0"
CONFIG_VERSION = 1
# Minecraft 主界面左下角显示用的 versionType
PROXY_VERSION_TYPE = f"{PROXY_NAME} {PROXY_VERSION}"

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

# 默认的伪装版本字符串
DEFAULT_SPOOF_VERSION = ""

# 默认 API 列表模板
DEFAULT_API_LIST = [
    {
        "name": "LittleSkin (默认)",
        "base_url": "https://littleskin.cn/api/yggdrasil",
    }
]

# =========================================================================
# 【特征定义库】(用于识别游戏启动)
# =========================================================================

# 1. 已知的 Wrapper 类 (陷阱模式)
# 遇到这些类时，启用 Classpath Shadowing 策略
KNOWN_WRAPPERS = [
    "org.prismlauncher.EntryPoint",
    "org.multimc.EntryPoint",
]

# 2. 已知的游戏主类 (标准模式)
# 遇到这些类或 @argfile 时，启用标准嗅探策略
KNOWN_GAME_MAINS = [
    "net.minecraft.client.main.Main",
    "net.fabricmc.loader",
    "cpw.mods.bootstraplauncher",
    "cpw.mods.fml",
    "net.minecraft.launchwrapper.Launch",
    "net.neoforged"
]

# 最终要调用的真实游戏主类 (用于替换 Wrapper)
REAL_MINECRAFT_MAIN = "net.minecraft.client.main.Main"

# ================= 调试开关 =================
DEBUG_MODE = False