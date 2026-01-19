# src/javaScanner.py
import os
import sys
import subprocess
import platform
import threading
import concurrent.futures
from src import constants


# ================= 1. 基础工具 =================

def _is_executable(path):
    """快速检查文件是否可执行"""
    if not path or not os.path.exists(path):
        return False
    return os.access(path, os.X_OK)


def _get_java_exe_name():
    return "java.exe" if platform.system() == "Windows" else "java"


def get_java_version(path):
    """
    获取单个 Java 路径的版本信息 (带超时防止卡死)
    """
    if not _is_executable(path):
        return None
    try:
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # 1秒超时，仅用于获取版本字符串
        proc = subprocess.run(
            [path, "-version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=startupinfo, timeout=1, text=True, errors='ignore'
        )

        output = proc.stderr + "\n" + proc.stdout
        for line in output.splitlines():
            if "version" in line.lower():
                return line.strip().replace('"', '')

        if output.strip():
            return output.strip().split('\n')[0][:30]
        return "Unknown Version"
    except:
        return None


# ================= 2. 极速路径发现 =================

def _scan_paths_fast():
    """只找路径，不验证，速度极快"""
    candidates = set()
    system = platform.system()
    exe_name = _get_java_exe_name()

    # A. 环境变量
    jh = os.environ.get("JAVA_HOME")
    if jh: candidates.add(os.path.join(jh, "bin", exe_name))

    try:
        import shutil
        path_java = shutil.which(exe_name)
        if path_java: candidates.add(os.path.realpath(path_java))
    except:
        pass

    # B. macOS 专属工具
    if system == "Darwin":
        try:
            proc = subprocess.run(["/usr/libexec/java_home", "-V"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, timeout=2)
            for line in (proc.stderr + proc.stdout).splitlines():
                if "JVMHomePath" in line:
                    path_part = line.split("JVMHomePath:")[-1].strip()
                    candidates.add(os.path.join(path_part, "bin", "java"))
        except:
            pass

    # C. Windows 注册表
    if system == "Windows":
        try:
            import winreg
            search_keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Runtime Environment"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Development Kit"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\JavaSoft\Java Runtime Environment")
            ]
            for hive, key_path in search_keys:
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            ver_str = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, ver_str) as subkey:
                                java_home, _ = winreg.QueryValueEx(subkey, "JavaHome")
                                candidates.add(os.path.join(java_home, "bin", "java.exe"))
                except:
                    continue
        except:
            pass

    # D. 常见目录
    roots = []
    if system == "Windows":
        roots = [r"C:\Program Files\Java", r"C:\Program Files\Eclipse Adoptium"]
    elif system == "Darwin":
        roots = ["/Library/Java/JavaVirtualMachines", os.path.expanduser("~/Library/Java/JavaVirtualMachines")]
    elif system == "Linux":
        roots = ["/usr/lib/jvm"]

    for root in roots:
        if os.path.exists(root):
            try:
                for item in os.listdir(root):
                    p = os.path.join(root, item)
                    if os.path.isdir(p):
                        target = os.path.join(p, "bin", exe_name)
                        if system == "Darwin":
                            target_mac = os.path.join(p, "Contents", "Home", "bin", "java")
                            if os.path.exists(target_mac): candidates.add(target_mac)
                        if os.path.exists(target): candidates.add(target)
            except:
                pass

    return {p for p in candidates if _is_executable(p)}


# ================= 3. 核心入口 =================

def find_java_candidates():
    """并发扫描并验证系统 Java"""
    raw_paths = _scan_paths_fast()
    valid_paths = []

    # 过滤掉我们自己的数据目录，防止把“伪装Java”扫出来
    # 只要路径里包含 .YggdrasilProxy 就跳过
    filtered_paths = [p for p in raw_paths if constants.DATA_DIR_NAME not in p]

    print(f"[{constants.PROXY_NAME}] 发现 {len(filtered_paths)} 个潜在路径，开始并发验证...", file=sys.stderr)

    # 使用线程池快速验证
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_path = {executor.submit(get_java_version, p): p for p in filtered_paths}
        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                if future.result():  # 只要能获取到版本号，就算有效
                    valid_paths.append(path)
            except:
                pass

    return sorted(valid_paths)


def start_scan(callback):
    def task():
        res = find_java_candidates()
        if callback: callback(res)

    threading.Thread(target=task, daemon=True).start()