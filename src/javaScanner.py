import os
import sys
import subprocess
import platform
import threading
import concurrent.futures
from src import constants


# ================= 1. 基础工具 =================

def _is_executable(path):
    if not path or not os.path.isfile(path):
        return False
    return os.access(path, os.X_OK)


def _get_java_exe_name():
    return "java.exe" if platform.system() == "Windows" else "java"


def _expand_path(p):
    return os.path.expandvars(os.path.expanduser(p))


def get_java_version(path):
    """
    获取 Java 版本信息（仅用于验证存活）
    """
    if not _is_executable(path):
        return None

    try:
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.run(
            [path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            timeout=1,
            text=True,
            errors="ignore"
        )

        output = proc.stderr + "\n" + proc.stdout
        for line in output.splitlines():
            if "version" in line.lower():
                return line.strip().replace('"', "")

        if output.strip():
            return output.strip().splitlines()[0][:40]

        return "Unknown Version"

    except Exception:
        return None


# ================= 2. Windows 注册表扫描 =================

def _scan_windows_registry():
    """
    从 Windows 注册表中扫描 Java
    """
    results = set()

    if platform.system() != "Windows":
        return results

    try:
        import winreg
    except ImportError:
        return results

    for key_path in constants.WINDOWS_JAVA_REGISTRY_KEYS:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    ver = winreg.EnumKey(root, i)
                    try:
                        with winreg.OpenKey(root, ver) as subkey:
                            java_home, _ = winreg.QueryValueEx(subkey, "JavaHome")
                            java_exe = os.path.join(java_home, "bin", "java.exe")
                            if _is_executable(java_exe):
                                results.add(java_exe)
                    except Exception:
                        continue
        except Exception:
            continue

    return results


# ================= 3. 极速路径发现（不验证） =================

def _scan_paths_fast():
    """
    只负责发现路径，不验证
    """
    candidates = set()
    system = platform.system()
    exe_name = _get_java_exe_name()

    # ---------- A. JAVA_HOME ----------
    jh = os.environ.get("JAVA_HOME")
    if jh:
        candidates.add(os.path.join(jh, "bin", exe_name))

    # ---------- B. PATH ----------
    try:
        import shutil
        p = shutil.which(exe_name)
        if p:
            candidates.add(os.path.realpath(p))
    except Exception:
        pass

    # ---------- C. macOS java_home ----------
    if system == "Darwin":
        try:
            proc = subprocess.run(
                ["/usr/libexec/java_home", "-V"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2
            )
            for line in (proc.stderr + proc.stdout).splitlines():
                if "JVMHomePath" in line:
                    home = line.split("JVMHomePath:")[-1].strip()
                    candidates.add(os.path.join(home, "bin", "java"))
        except Exception:
            pass

    # ---------- D. Windows 注册表 ----------
    candidates.update(_scan_windows_registry())

    # ---------- E. 路径列表扫描（Prism / 系统 / Homebrew 等） ----------
    roots = constants.JAVA_SCAN_PATHS.get(system, [])

    for root in roots:
        root = _expand_path(root)
        if not os.path.exists(root):
            continue

        try:
            # 直接 bin/java
            direct = os.path.join(root, "bin", exe_name)
            if os.path.isfile(direct):
                candidates.add(direct)

            # 子目录结构（JDK / Prism / Zulu）
            for item in os.listdir(root):
                p = os.path.join(root, item)
                if not os.path.isdir(p):
                    continue

                if system == "Darwin":
                    mac_java = os.path.join(p, "Contents", "Home", "bin", "java")
                    if os.path.exists(mac_java):
                        candidates.add(mac_java)

                generic = os.path.join(p, "bin", exe_name)
                if os.path.exists(generic):
                    candidates.add(generic)

        except Exception:
            pass

    return {p for p in candidates if _is_executable(p)}


# ================= 4. 对外主接口 =================

def find_java_candidates():
    """
    扫描并验证 Java（并发）
    """
    raw_paths = _scan_paths_fast()

    # 排除自身数据目录，防止扫到伪装 Java
    filtered = [
        p for p in raw_paths
        if constants.DATA_DIR_NAME not in p
    ]

    print(
        f"[{constants.PROXY_NAME}] Find {len(filtered)} Java path(s), verifying...",
        file=sys.stderr
    )

    valid = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        future_map = {
            pool.submit(get_java_version, p): p
            for p in filtered
        }

        for future in concurrent.futures.as_completed(future_map):
            path = future_map[future]
            try:
                if future.result():
                    valid.append(path)
            except Exception:
                pass

    return sorted(valid)


def start_scan(callback):
    """
    GUI / 异步入口
    """
    def task():
        res = find_java_candidates()
        if callback:
            callback(res)

    threading.Thread(target=task, daemon=True).start()