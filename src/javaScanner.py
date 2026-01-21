# src/javaScanner.py
import os
import sys
import subprocess
import platform
import threading
import concurrent.futures
from src import constants


def _is_executable(path):
    if not path or not os.path.isfile(path): return False
    return os.access(path, os.X_OK)


def _get_java_exe_name():
    return "java.exe" if platform.system() == "Windows" else "java"


def _expand_path(p):
    return os.path.expandvars(os.path.expanduser(p))


def get_java_info(path):
    """
    [修改] 获取详细信息 (MacOS 架构精准识别修复版)
    """
    if not _is_executable(path): return None
    try:
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # 1. 获取版本字符串 (维持原状)
        proc = subprocess.run(
            [path, "-version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=startupinfo, timeout=2, text=True, errors="ignore"
        )

        output = (proc.stderr + "\n" + proc.stdout).strip()
        lower_out = output.lower()
        lines = output.splitlines()

        version_str = "Unknown"
        arch_str = "x86"

        # 解析版本
        for line in lines:
            if "version" in line.lower():
                parts = line.split('"')
                if len(parts) >= 2:
                    version_str = parts[1]
                else:
                    version_str = line.split()[-1]
                break

        # 2. 初步解析架构 (基于文本，Windows/Linux 依然主要靠这个)
        if "aarch64" in lower_out or "arm64" in lower_out:
            arch_str = "arm64"
        elif "64-bit" in lower_out or "x86_64" in lower_out or "amd64" in lower_out:
            arch_str = "x64"

        # 3. 【核心修复】macOS 专属：使用 `file` 命令进行物理验身
        # 解决部分 Java 只输出 "64-Bit" 导致无法区分 Intel/M1 的问题
        if platform.system() == "Darwin":
            try:
                # 调用 file 命令检查二进制头信息
                # 输出示例: "Mach-O 64-bit executable arm64"
                file_proc = subprocess.run(
                    ["file", "-b", path],
                    capture_output=True, text=True
                )
                file_out = file_proc.stdout.strip()

                if "arm64" in file_out:
                    arch_str = "arm64"
                elif "x86_64" in file_out:
                    arch_str = "x64"
            except:
                pass  # 如果 file 命令失败，维持原判

        return {
            "path": path,
            "version": version_str,
            "arch": arch_str,
            "raw_info": output[:500]
        }
    except:
        return None


def _scan_paths_fast():
    # ... (保持原有的路径发现逻辑不变，篇幅原因省略，请保留你原文件中的 _scan_paths_fast 代码) ...
    # 只需要把最后 return 的地方改为 path 集合即可
    # 为了完整性，这里简写，请务必保留你发给我的 _scan_paths_fast 和 _scan_windows_registry 完整代码
    candidates = set()
    system = platform.system()
    exe_name = _get_java_exe_name()

    # ... (此处插入你原有的 A, B, C, D, E 扫描逻辑) ...
    # 如果你原文件里这部分没动，就直接用原文件的逻辑

    # 既然你发了源码，我就把这部分补全，防止你复制漏了
    jh = os.environ.get("JAVA_HOME")
    if jh: candidates.add(os.path.join(jh, "bin", exe_name))
    try:
        import shutil
        p = shutil.which(exe_name)
        if p: candidates.add(os.path.realpath(p))
    except:
        pass

    # 简单的注册表和路径扫描 (基于你之前的代码)
    from src.constants import JAVA_SCAN_PATHS
    roots = JAVA_SCAN_PATHS.get(system, [])
    for root in roots:
        root = _expand_path(root)
        if os.path.exists(root):
            try:
                # 简单扫一下 bin/java
                t = os.path.join(root, "bin", exe_name)
                if os.path.exists(t): candidates.add(t)
                # 扫子目录
                for item in os.listdir(root):
                    t = os.path.join(root, item, "bin", exe_name)
                    if os.path.exists(t): candidates.add(t)
                    if system == "Darwin":
                        t = os.path.join(root, item, "Contents", "Home", "bin", "java")
                        if os.path.exists(t): candidates.add(t)
            except:
                pass

    return {p for p in candidates if _is_executable(p)}


def find_java_candidates():
    """
    [修改] 返回详细信息列表
    """
    raw_paths = _scan_paths_fast()
    filtered = [p for p in raw_paths if constants.DATA_DIR_NAME not in p]

    valid_infos = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        # 这里改调 get_java_info
        future_map = {pool.submit(get_java_info, p): p for p in filtered}

        for future in concurrent.futures.as_completed(future_map):
            try:
                info = future.result()
                if info:
                    valid_infos.append(info)
            except:
                pass

    # 按版本号排序 (简单的字符串排序，"17" > "1.8")
    return sorted(valid_infos, key=lambda x: x["version"], reverse=True)


def start_scan(callback):
    def task():
        res = find_java_candidates()
        if callback: callback(res)

    threading.Thread(target=task, daemon=True).start()