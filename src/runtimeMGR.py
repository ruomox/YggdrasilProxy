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
    """获取打包源文件中的 assets 目录路径 (保持你最原始的逻辑)"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "assets")
    else:
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
        # 1秒超时快速验证
        subprocess.run([path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       startupinfo=startupinfo, timeout=1, check=True)
        return True
    except:
        return False


def get_injector_jar():
    """获取 authlib-injector.jar (强制覆盖)"""
    runtime_dir = config_mgr.get_runtime_dir()
    target_injector = os.path.join(runtime_dir, constants.INJECTOR_FILENAME)

    # ==========================================
    # [删除] 原来的存在即返回逻辑
    # if os.path.exists(target_injector):
    #     return target_injector
    # ==========================================

    source_assets = _get_source_assets_path()
    candidates = [
        os.path.join(source_assets, constants.INJECTOR_FILENAME),
        os.path.join(source_assets, constants.JRE_DIR_NAME, constants.INJECTOR_FILENAME)
    ]

    for p in candidates:
        if os.path.exists(p):
            try:
                # 使用 copy2 覆盖
                shutil.copy2(p, target_injector)
                return target_injector
            except Exception as e:
                print(f"无法更新 injector: {e}")
                pass

    return target_injector


def get_fallback_java():
    """
    获取兜底 Java。
    逻辑：【已修改】强制覆盖解压 -> 返回路径。
    """
    runtime_dir = config_mgr.get_runtime_dir()
    target_jre_dir = os.path.join(runtime_dir, constants.JRE_DIR_NAME)

    # 1. 确定 bin 路径
    bin_name = "java.exe" if platform.system() == "Windows" else "java"
    if platform.system() == "Darwin":
        java_exe = os.path.join(target_jre_dir, "Contents", "Home", "bin", bin_name)
    else:
        java_exe = os.path.join(target_jre_dir, "bin", bin_name)

    # ==========================================
    # [删除或注释] 原来的检测逻辑，强制进入解压
    # if _is_java_executable(java_exe):
    #     return java_exe
    # ==========================================

    print(f"[{constants.PROXY_NAME}] 正在初始化运行环境 (强制解压)...", file=sys.stderr)

    source_assets = _get_source_assets_path()
    source_zip = os.path.join(source_assets, f"{constants.JRE_DIR_NAME}.zip")
    source_folder = os.path.join(source_assets, constants.JRE_DIR_NAME)

    try:
        # 强制清理旧环境
        # 注意：如果此时有旧的 java.exe 正在后台运行，Windows 下这一步会报错（文件被占用）
        if os.path.exists(target_jre_dir):
            try:
                # 尝试修改权限以确保能删除 (针对只读文件)
                def remove_readonly(func, path, _):
                    os.chmod(path, 0o777)
                    func(path)
                shutil.rmtree(target_jre_dir, onerror=remove_readonly)
            except Exception as e:
                print(f"[{constants.PROXY_NAME}] 清理旧文件失败 (可能被占用): {e}", file=sys.stderr)
                # 如果删不掉，可能无法继续解压，这里可以选择 return java_exe 或者抛出异常
                # 但为了强制更新，通常建议让用户手动关闭占用的程序

        if os.path.exists(source_zip):
            with zipfile.ZipFile(source_zip, 'r') as zf:
                zf.extractall(runtime_dir)
        elif os.path.exists(source_folder):
            shutil.copytree(source_folder, target_jre_dir)
        else:
            print(f"[{constants.PROXY_NAME}] 错误：未找到内嵌 Java 源文件。", file=sys.stderr)
            return None

        # 权限修复
        if platform.system() != "Windows" and os.path.exists(java_exe):
            st = os.stat(java_exe)
            os.chmod(java_exe, st.st_mode | 0o111)

        # 解压完成后再验证
        if _is_java_executable(java_exe):
            return java_exe

    except Exception as e:
        print(f"[{constants.PROXY_NAME}] 解压失败: {e}", file=sys.stderr)

    return None

    return None