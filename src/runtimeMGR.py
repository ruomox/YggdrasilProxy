# src/runtimeMGR.py
import sys
import os
import shutil
import platform
import subprocess
import zipfile
from src import constants
from src.configMGR import config_mgr


def _get_source_assets_path():
    """获取打包源文件中的 assets 目录路径"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的临时目录
        return os.path.join(sys._MEIPASS, "assets")
    else:
        # 源码运行时的目录
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def _is_java_executable(path):
    """验证 Java 是否可运行"""
    if not path or not os.path.isfile(path): return False
    if platform.system() != "Windows" and not os.access(path, os.X_OK): return False
    try:
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run([path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       startupinfo=startupinfo, timeout=2, check=True)
        return True
    except:
        return False


def _extract_file_from_assets(filename):
    """通用方法：将文件从 assets 复制到运行时目录"""
    runtime_dir = config_mgr.get_runtime_dir()
    target_path = os.path.join(runtime_dir, filename)
    source_assets = _get_source_assets_path()

    # 候选源路径
    candidates = [
        os.path.join(source_assets, filename),
        os.path.join(source_assets, constants.JRE_DIR_NAME, filename)  # 有时候会在子目录
    ]

    # 简单的“存在即返回”策略（生产环境建议加Hash校验，这里为了性能先这样）
    if os.path.exists(target_path):
        return target_path

    # 开始寻找并复制
    for source in candidates:
        if os.path.exists(source):
            try:
                shutil.copy2(source, target_path)
                return target_path
            except Exception as e:
                print(f"[{constants.PROXY_NAME}] 释放文件 {filename} 失败: {e}", file=sys.stderr)

    return target_path  # 即使复制失败也返回路径，让调用者去报错


def get_injector_jar():
    """获取 authlib-injector.jar (自动释放)"""
    return _extract_file_from_assets(constants.INJECTOR_FILENAME)


def get_fmcmain_jar():
    """获取 fMcMain.jar (自动释放)"""
    return _extract_file_from_assets("fMcMain.jar")


def get_fallback_java():
    """
    获取兜底 Java。
    逻辑：检查是否存在且可用 -> 是则返回 -> 否则解压。
    """
    runtime_dir = config_mgr.get_runtime_dir()
    target_jre_dir = os.path.join(runtime_dir, constants.JRE_DIR_NAME)

    # 1. 确定 bin 路径
    bin_name = "java.exe" if platform.system() == "Windows" else "java"
    if platform.system() == "Darwin":
        java_exe = os.path.join(target_jre_dir, "Contents", "Home", "bin", bin_name)
    else:
        java_exe = os.path.join(target_jre_dir, "bin", bin_name)

    # 存在且可用，直接返回
    if os.path.exists(java_exe) and _is_java_executable(java_exe):
        return java_exe

    # 2. 解压流程
    # print(f"[{constants.PROXY_NAME}] 正在初始化运行环境...", file=sys.stderr) # 减少刷屏

    source_assets = _get_source_assets_path()
    source_zip = os.path.join(source_assets, f"{constants.JRE_DIR_NAME}.zip")
    source_folder = os.path.join(source_assets, constants.JRE_DIR_NAME)

    try:
        # 清理旧目录
        if os.path.exists(target_jre_dir):
            try:
                def remove_readonly(func, path, _):
                    os.chmod(path, 0o777)
                    func(path)

                shutil.rmtree(target_jre_dir, onerror=remove_readonly)
            except:
                pass  # 忽略清理失败，尝试直接覆盖

        # 解压
        if os.path.exists(source_zip):
            with zipfile.ZipFile(source_zip, 'r') as zf:
                zf.extractall(runtime_dir)
        elif os.path.exists(source_folder):
            shutil.copytree(source_folder, target_jre_dir, dirs_exist_ok=True)
        else:
            return None

        # 权限修复 (*nix)
        if platform.system() != "Windows" and os.path.exists(java_exe):
            st = os.stat(java_exe)
            os.chmod(java_exe, st.st_mode | 0o111)

        if _is_java_executable(java_exe):
            return java_exe

    except Exception as e:
        print(f"[{constants.PROXY_NAME}] 环境初始化异常: {e}", file=sys.stderr)

    return None