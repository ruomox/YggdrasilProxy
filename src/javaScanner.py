# src/javaScanner.py
import os
import sys
import subprocess
import platform
import threading
import concurrent.futures  # 引入线程池
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
    获取单个 Java 路径的版本信息。
    设置了严格的超时，防止卡死。
    """
    if not _is_executable(path):
        return None

    try:
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # 严格限制 1 秒超时，获取版本信息通常只需要几十毫秒
        proc = subprocess.run(
            [path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            timeout=1,  # 【关键】1秒超时，防卡死
            text=True,
            errors='ignore'  # 忽略编码错误
        )

        # Java 版本信息通常在 stderr，但也可能在 stdout
        output = proc.stderr + "\n" + proc.stdout

        # 简单解析：提取第一行包含 version 的内容，或者第一行
        for line in output.splitlines():
            if "version" in line.lower():
                # 清理掉多余的双引号
                return line.strip().replace('"', '')

        # 如果找不到 version 字样，返回第一行非空内容作为标识
        if output.strip():
            return output.strip().split('\n')[0][:30]  # 截取前30字符

        return "Unknown Version"

    except subprocess.TimeoutExpired:
        return None  # 超时视为无效或太慢
    except Exception:
        return None


# ================= 2. 极速路径发现 (不运行 Java) =================

def _scan_paths_fast():
    """只找路径，不验证，速度极快"""
    candidates = set()
    system = platform.system()
    exe_name = _get_java_exe_name()

    # --- A. 环境变量 ---
    jh = os.environ.get("JAVA_HOME")
    if jh:
        candidates.add(os.path.join(jh, "bin", exe_name))

    try:
        import shutil
        path_java = shutil.which(exe_name)
        if path_java:
            candidates.add(os.path.realpath(path_java))
    except:
        pass

    # --- B. macOS 专属极速工具 ---
    if system == "Darwin":
        try:
            proc = subprocess.run(["/usr/libexec/java_home", "-V"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, timeout=2)
            output = proc.stderr + proc.stdout
            for line in output.splitlines():
                if "JVMHomePath" in line:
                    path_part = line.split("JVMHomePath:")[-1].strip()
                    candidates.add(os.path.join(path_part, "bin", "java"))
        except:
            pass

    # --- C. Windows 注册表 ---
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

    # --- D. 常见目录 (浅层扫描) ---
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
                # 只扫两层：Root/JDK_Name/bin/java
                for item in os.listdir(root):
                    p = os.path.join(root, item)
                    if os.path.isdir(p):
                        target = os.path.join(p, "bin", exe_name)
                        if system == "Darwin":  # 处理 macOS 特殊结构
                            target_mac = os.path.join(p, "Contents", "Home", "bin", "java")
                            if os.path.exists(target_mac): candidates.add(target_mac)

                        if os.path.exists(target): candidates.add(target)
            except:
                pass

    # 过滤无效路径
    return {p for p in candidates if _is_executable(p)}


# ================= 3. 核心入口 (并发验证) =================

def find_java_candidates():
    """
    同步返回列表，包含版本信息。
    格式: ["/path/to/java", ...]
    (注意：为了保持兼容性，这里返回路径列表。
     如果想要显示版本，UI层可以调用 get_java_version 或我们在内部缓存)
    """
    # 1. 快速找路径
    raw_paths = _scan_paths_fast()
    valid_paths = []

    print(f"[{constants.PROXY_NAME}] 发现 {len(raw_paths)} 个潜在路径，开始并发验证...", file=sys.stderr)

    # 2. 并发验证 (多线程)
    # 开启最多 20 个线程同时运行 java -version
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # 提交任务
        future_to_path = {executor.submit(get_java_version, p): p for p in raw_paths}

        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                version_info = future.result()
                if version_info:
                    # 验证成功
                    # 你可以选择在这里把 path 改成 "path [version]" 的格式返回
                    # 但为了 main.py 能直接用，建议还是存路径，版本信息的显示交给 UI 处理
                    # 这里我们简单打印日志
                    # print(f"  √ {version_info} -> {path}", file=sys.stderr)
                    valid_paths.append(path)
            except Exception:
                pass

    return sorted(valid_paths)


def start_scan(callback):
    """后台任务接口"""

    def task():
        res = find_java_candidates()
        if callback:
            callback(res)

    threading.Thread(target=task, daemon=True).start()


# 如果你需要在 UI 显示版本号，可以导出这个辅助函数供 guiWizard.py 使用
def get_java_display_text(path):
    ver = get_java_version(path)
    if ver:
        return f"{path}  ({ver})"
    return path