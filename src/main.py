# src/main.py
import sys
import os
import subprocess
import platform
from src import constants, runtimeMGR, authAPI, guiWizard, javaScanner, preSetup
from src.configMGR import config_mgr


# ================= 1. 嗅探逻辑 (策略模式) =================

def get_fmcmain():
    path = runtimeMGR.get_fmcmain_jar()
    return path if os.path.exists(path) else None


def parse_sniffer_output(output):
    args_list = []
    is_capturing = False
    if not output: return []
    for line in output.splitlines():
        line = line.strip()
        if "---YGGPROXY_SNIFFER_START---" in line:
            is_capturing = True
            continue
        if "---YGGPROXY_SNIFFER_END---" in line:
            is_capturing = False
            break
        if is_capturing: args_list.append(line)
    return args_list


# --- 策略 A: 陷阱嗅探 (针对 Wrapper) ---
def run_trap_sniffer(tool_java, raw_args):
    fmcmain = get_fmcmain()
    if not fmcmain: return None

    trap_args = list(raw_args)
    injected = False

    for i, arg in enumerate(trap_args):
        if arg in ("-cp", "-classpath", "--cp") and i + 1 < len(trap_args):
            original_cp = trap_args[i + 1]
            sep = ";" if platform.system() == "Windows" else ":"
            trap_args[i + 1] = f"{fmcmain}{sep}{original_cp}"
            injected = True
            break

    if not injected: return None

    try:
        proc = subprocess.run([tool_java] + trap_args, capture_output=True, text=True, errors='replace')
        return parse_sniffer_output(proc.stdout + proc.stderr)
    except:
        return None


# --- 策略 B: 标准嗅探 (针对 HMCL/Official) ---
def run_standard_sniffer(tool_java, raw_args):
    fmcmain = get_fmcmain()
    if not fmcmain: return None

    cmd = [tool_java, "-cp", fmcmain, "net.minecraft.client.main.Main"] + raw_args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        return parse_sniffer_output(proc.stdout + proc.stderr)
    except:
        return None


# ================= 2. 判别与分发 =================

def detect_launch_type(args):
    args_str = " ".join(args)

    # 使用 constants 中的列表
    for wrapper in constants.KNOWN_WRAPPERS:
        if wrapper in args_str:
            return "WRAPPER"

    if any(a.startswith("@") for a in args): return "STANDARD"
    for main_cls in constants.KNOWN_GAME_MAINS:
        if main_cls in args_str:
            return "STANDARD"

    return "PASSTHROUGH"


# ================= 3. 业务流程 =================

def get_game_dir(args):
    for i, arg in enumerate(args):
        if arg == "--gameDir" and i + 1 < len(args): return args[i + 1]
        if arg.startswith("--gameDir="): return arg.split("=", 1)[1]
    return os.getcwd()


def ensure_account_valid(game_dir, force_gui=False):
    config_mgr.load()

    # --- 调试: 打印当前判定的游戏目录 ---
    print(f"[{constants.PROXY_NAME}] Instance Path: {game_dir}", file=sys.stderr)

    target_uuid = config_mgr.get_account_for_instance(game_dir)
    auth_data = config_mgr.get_account(target_uuid)

    # --- 调试: 打印查找到的账号 ---
    if target_uuid:
        print(
            f"[{constants.PROXY_NAME}] Found Binding: {auth_data.get('name', 'Unknown') if auth_data else 'Invalid Data'}",
            file=sys.stderr)
    else:
        print(f"[{constants.PROXY_NAME}] No Binding Found (New Instance)", file=sys.stderr)

    need_gui = force_gui
    if not auth_data:
        need_gui = True
    elif not force_gui:
        api = config_mgr.get_current_api_config()
        base = api.get("base_url", "").rstrip('/')
        try:
            if not authAPI.validate(f"{base}/authserver/validate", auth_data["accessToken"],
                                    auth_data.get("clientToken")):
                print(f"[{constants.PROXY_NAME}] Token Expired, Refreshing...", file=sys.stderr)
                new = authAPI.refresh(f"{base}/authserver/refresh", auth_data["accessToken"],
                                      auth_data.get("clientToken"))
                auth_data["accessToken"] = new["accessToken"]
                if "clientToken" in new: auth_data["clientToken"] = new["clientToken"]
                config_mgr.add_or_update_account(auth_data)
        except Exception as e:
            print(f"[{constants.PROXY_NAME}] Refresh Failed: {e}", file=sys.stderr)
            # 标记账号失效
            if auth_data:
                auth_data["invalid"] = True
                config_mgr.add_or_update_account(auth_data)
            need_gui = True

    if need_gui:
        print(f"[{constants.PROXY_NAME}] Opening GUI...", file=sys.stderr)
        if not guiWizard.show_wizard(force_show_settings=force_gui, game_dir=game_dir): return None

        config_mgr.load()
        # 获取用户在 GUI 里刚刚选中的账号 (暂存在 default)
        target_uuid = config_mgr._config_data.get("default_account_uuid")
        auth_data = config_mgr.get_account(target_uuid)

        if auth_data:
            print(f"[{constants.PROXY_NAME}] Binding Account {auth_data['name']} to Instance.", file=sys.stderr)
            config_mgr.set_instance_binding(game_dir, target_uuid)

    return auth_data


# ================= 4. 主入口 =================

def main():
    # 前置页面
    preSetup.check_entry_mode()
    sys_args = sys.argv[1:]

    # ===================== DEBUG: 原始入口 =====================
    if constants.DEBUG_MODE:
        print("\n" + "=" * 60, file=sys.stderr)
        print("[YggProxy DEBUG] Raw sys.argv =", file=sys.stderr)
        for i, a in enumerate(sys.argv):
            print(f"  argv[{i}] = {a}", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
    # ===================== DEBUG: 原始入口 =====================

    # [第2层] 状态记录：检测用户意图
    # 兼容旧参数名以防万一，统一逻辑状态
    force_config_mode = ("--yggpro" in sys_args)

    # [第1层] 入口清洗
    raw_args = [arg for arg in sys_args if arg not in ("--yggpro", "--yggprodebug")]

    config_mgr.load()

    # 初始候选
    tool_java = runtimeMGR.get_fallback_java()
    target_java = config_mgr.get_real_java_path()

    def is_valid_java(p):
        return p and os.path.exists(p)

    # [第2层] 优先使用 config 中仍然存在的 Java
    if not is_valid_java(target_java):
        target_java = None

    # [第3层] config Java 不可用 → 重新扫描
    if not target_java:
        print(f"[{constants.PROXY_NAME}] Java path invalid or missing, rescanning...")
        candidates = javaScanner.find_java_candidates()
        if candidates:
            target_java = candidates[0]["path"]
            config_mgr.set_real_java_path(target_java)
            config_mgr.save()
            print(f"[{constants.PROXY_NAME}] Auto-selected Java: {target_java}")

    # [第4层] 兜底：runtime 自带 Java（也要验证）
    if not is_valid_java(target_java) and is_valid_java(tool_java):
        target_java = tool_java

    # [第5层] 仍然没有 → 这是唯一允许 exit 的地方
    if not is_valid_java(target_java):
        print(f"[{constants.PROXY_NAME}] No usable Java found.", file=sys.stderr)
        sys.exit(1)

    # 嗅探器用 Java：优先 runtime，其次 target
    sniffer_java = tool_java if is_valid_java(tool_java) else target_java

    # [第6层] 无参数时直接探测
    if not raw_args:
        subprocess.call([target_java])
        sys.exit(0)

    # [1] 识别
    launch_type = detect_launch_type(raw_args)

    captured_game_args = []
    jvm_args_prefix = []

    if launch_type == "PASSTHROUGH":
        sys.exit(subprocess.call([target_java] + raw_args))

    elif launch_type == "WRAPPER":
        captured_game_args = run_trap_sniffer(sniffer_java, raw_args)

        found_wrapper = False
        for arg in raw_args:
            is_wrapper_cls = any(w in arg for w in constants.KNOWN_WRAPPERS)
            if is_wrapper_cls:
                found_wrapper = True
                continue
            if not found_wrapper:
                jvm_args_prefix.append(arg)

        jvm_args_prefix.append(constants.REAL_MINECRAFT_MAIN)

    elif launch_type == "STANDARD":
        captured_game_args = run_standard_sniffer(sniffer_java, raw_args)
        jvm_args_prefix = []

    if not captured_game_args:
        sys.exit(subprocess.call([target_java] + raw_args))

    # [2] 补充清洗 检查解包后的参数（针对 @argfile 或 Wrapper 隐藏参数的情况）
    if "--yggpro" in captured_game_args:
        force_config_mode = True
        # 再次清洗，确保不传给游戏
        captured_game_args = [arg for arg in captured_game_args if arg not in ("--yggpro", "--yggprodebug")]

    # [3] versionType 统一修正
    new_game_args = []
    i = 0
    found_version_type = False

    while i < len(captured_game_args):
        arg = captured_game_args[i]

        if arg == "--versionType":
            new_game_args.append("--versionType")
            new_game_args.append(constants.PROXY_VERSION_TYPE)
            found_version_type = True
            i += 2
            continue

        if arg.startswith("--versionType="):
            new_game_args.append(f"--versionType={constants.PROXY_VERSION_TYPE}")
            found_version_type = True
            i += 1
            continue

        new_game_args.append(arg)
        i += 1

    if not found_version_type:
        new_game_args.extend([
            "--versionType",
            constants.PROXY_VERSION_TYPE
        ])

    captured_game_args = new_game_args

    # [4] 账号
    game_dir = get_game_dir(captured_game_args)
    auth_data = ensure_account_valid(game_dir, force_gui=force_config_mode)
    if not auth_data: sys.exit(0)

    # === 实际启动 Java 选择链：instance -> target -> tool ===
    instance_java = config_mgr.get_java_for_instance(game_dir)
    launch_java = (
        instance_java if instance_java and os.path.exists(instance_java)
        else target_java if target_java and os.path.exists(target_java)
        else tool_java
    )

    if not launch_java:
        print(f"[{constants.PROXY_NAME}] No usable Java for launch.", file=sys.stderr)
        sys.exit(1)

    # [5] 组装
    injector = runtimeMGR.get_injector_jar()
    api = config_mgr.get_current_api_config()

    final_cmd = [launch_java]
    final_cmd.append(f"-javaagent:{injector}={api['base_url']}")
    final_cmd.append("-Dauthlibinjector.noShowServerName")

    if jvm_args_prefix:
        final_cmd.extend(jvm_args_prefix)

    sensitive = {"--username", "--uuid", "--accessToken", "--userProperties", "--yggpro"}
    skip = False

    for arg in captured_game_args:
        if skip:
            if arg.startswith("-"):
                skip = False
            else:
                skip = False; continue

        if "-javaagent:" in arg and "authlib-injector" in arg: continue
        if arg in sensitive:
            skip = True
            continue

        final_cmd.append(arg)

    final_cmd.extend([
        "--username", auth_data["name"],
        "--uuid", auth_data["uuid"],
        "--accessToken", auth_data["accessToken"],
        "--userProperties", "{}"
    ])

    print(f"[{constants.PROXY_NAME}] Launching: {auth_data['name']}", file=sys.stderr)

    # ===================== DEBUG: 最终传递 =====================
    if constants.DEBUG_MODE:
        print("\n" + "=" * 60, file=sys.stderr)
        print("[YggProxy DEBUG] Final sys.argv:", file=sys.stderr)
        for i, a in enumerate(final_cmd):
            print(f"  final_cmd[{i}] = {a}", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
    # ===================== DEBUG: 最终传递 =====================

    try:
        if platform.system() == "Windows":
            sys.exit(subprocess.call(final_cmd))
        else:
            os.execv(launch_java, final_cmd)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()