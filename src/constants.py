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
JRE_DIR_NAME = "YggProJAVA"
INJECTOR_FILENAME = "authlib-injector.jar"

# 默认 API 列表模板
DEFAULT_API_LIST = [
    {
        "name": "LittleSkin",
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

# 是否开放内嵌 Java
ENABLE_LOCAL_JAVA = True

# =========================================================================
# Java 扫描路径
# =========================================================================
JAVA_SCAN_PATHS = {
    "Darwin": [
        # --- Local Java ---
        ".YggProxy/YggProRuntime/",

        # --- Prism Launcher ---
        "~/Library/Application Support/PrismLauncher/java",
        "~/Library/Application Support/PrismLauncher/jre",
        "~/Library/Application Support/PrismLauncher/runtime",

        # --- Homebrew ---
        "/opt/homebrew/opt/openjdk",
        "/opt/homebrew/Cellar/openjdk",
        "/usr/local/opt/openjdk",
        "/usr/local/Cellar/openjdk",

        # --- Apple 官方 ---
        "/Library/Java/JavaVirtualMachines",
        "~/Library/Java/JavaVirtualMachines",
    ],

    "Windows": [
        # --- Local Java ---
        ".YggProxy/YggProRuntime/",

        # --- Prism Launcher ---
        "%APPDATA%\\PrismLauncher\\java",
        "%APPDATA%\\PrismLauncher\\jre",
        "%APPDATA%\\PrismLauncher\\runtime",

        # --- 官方 / 第三方 ---
        "C:\\Program Files\\Java",
        "C:\\Program Files\\Eclipse Adoptium",
    ],

    "Linux": [
        # --- Local Java ---
        ".YggProxy/YggProRuntime/",

        # --- Prism Launcher ---
        "~/.local/share/PrismLauncher/java",
        "~/.local/share/PrismLauncher/jre",
        "~/.local/share/PrismLauncher/runtime",

        # --- 系统 ---
        "/usr/lib/jvm",
        "/usr/java",
    ],
}

WINDOWS_JAVA_REGISTRY_KEYS = [
    r"SOFTWARE\JavaSoft\Java Runtime Environment",
    r"SOFTWARE\JavaSoft\Java Development Kit",
    r"SOFTWARE\Wow6432Node\JavaSoft\Java Runtime Environment",
]

# ================= 调试开关 =================
DEBUG_MODE = False