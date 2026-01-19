# src/runtimeMGR.py
import sys
import os
import shutil
import platform
import subprocess
from src import constants
from src.configMGR import config_mgr


def _get_source_assets_path():
    """获取打包源文件中的 assets 目录路径"""
    if getattr(sys, 'frozen', False):
        # 打包后：资源在临时目录的 assets 文件夹下
        return os.path.join(sys._MEIPASS, "assets")
    else:
        # 脚本运行：资源在项目根目录的 assets 中
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def _is_java_executable(path):
    """简单验证一个文件是否为可执行的 Java"""
    if not os.path.isfile(path): return False
    if platform.system() != "Windows" and not os.access(path, os.X_OK): return False
    try:
        # 尝试运行 -version
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run([path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo,
                       timeout=2, check=True)
        return True
    except:
        return False


def ensure_runtime_ready():
    """确保内嵌的 JRE 和 Injector 已解压到配置目录并可用"""
    runtime_dir = config_mgr.get_runtime_dir()
    target_jre_dir = os.path.join(runtime_dir, constants.JRE_DIR_NAME)
    target_injector = os.path.join(runtime_dir, constants.INJECTOR_FILENAME)

    source_assets = _get_source_assets_path()
    source_jre = os.path.join(source_assets, constants.JRE_DIR_NAME)
    source_injector = os.path.join(source_assets, constants.INJECTOR_FILENAME)

    # --- 1. 处理 Injector ---
    if not os.path.exists(target_injector):
        print(f"[{constants.PROXY_NAME}] 正在解压 Authlib-Injector...", file=sys.stderr)
        try:
            shutil.copy2(source_injector, target_injector)
        except Exception as e:
            print(f"[{constants.PROXY_NAME}] Error extracting injector: {e}", file=sys.stderr)
            # 这是一个非致命错误，也许用户手动放了一个进去，我们继续

    # --- 2. 处理 JRE ---
    # 确定目标 Java 可执行文件路径
    if platform.system() == "Windows":
        java_exe = os.path.join(target_jre_dir, "bin", "java.exe")
    else:
        java_exe = os.path.join(target_jre_dir, "bin", "java")

    # 检查是否需要解压
    jre_needs_extract = False
    if not os.path.exists(target_jre_dir):
        jre_needs_extract = True
    elif not os.path.exists(java_exe):
        # 目录在但文件不在，可能是损坏了
        jre_needs_extract = True

    # 如果需要解压，或者存在但无法执行（例如用户替换了个坏的），则重新解压
    if jre_needs_extract or not _is_java_executable(java_exe):
        print(f"[{constants.PROXY_NAME}] 正在初始化内嵌 Java 运行环境...", file=sys.stderr)
        if os.path.exists(target_jre_dir):
            try:
                shutil.rmtree(target_jre_dir)
            except:
                pass  # 尽力而为
        try:
            shutil.copytree(source_jre, target_jre_dir)
            # 修复权限 (macOS/Linux)
            if platform.system() != "Windows" and os.path.exists(java_exe):
                st = os.stat(java_exe)
                os.chmod(java_exe, st.st_mode | 0o100)
        except Exception as e:
            print(f"[{constants.PROXY_NAME}] Critical Error extracting JRE: {e}", file=sys.stderr)
            # 解压失败是严重错误，因为兜底方案失效了
            return None, None

    # 再次确认路径
    final_java_path = java_exe if os.path.exists(java_exe) else None
    final_injector_path = target_injector if os.path.exists(target_injector) else None

    return final_java_path, final_injector_path


def get_fallback_java():
    """获取可用的兜底 Java (内嵌 JRE)"""
    # 确保运行时环境就绪
    java_path, _ = ensure_runtime_ready()
    return java_path


def get_injector_jar():
    """获取 Injector Jar 路径"""
    _, injector_path = ensure_runtime_ready()
    return injector_path