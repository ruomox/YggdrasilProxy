# src/main.py
import sys
import os
import subprocess
import platform
import re
from src import constants, runtimeMGR, authAPI, guiWizard, javaScanner
from src.configMGR import config_mgr

# =========================================================================
# 【判定规则库】
# 只要命中以下任意规则，即认定为游戏启动
# =========================================================================

# 1. 明确的主类名 (HMCL / PCL / 官方启动器通常会明文传递)
GAME_MAIN_CLASSES = [
    "net.minecraft.client.main.Main",  # 原版
    "net.fabricmc.loader",  # Fabric
    "cpw.mods.bootstraplauncher",  # Forge (New)
    "cpw.mods.fml",  # Forge (Old)
    "net.minecraft.launchwrapper.Launch",  # Forge (Very Old)
    "net.neoforged"  # NeoForge
]

# 2. Classpath 特征关键词 (针对 Prism / MultiMC 这种隐藏参数的)
# 要求 -cp 内容中必须同时包含这些词
GAME_CP_KEYWORDS = ["minecraft", "client.jar"]


# ================= 1. 参数展开与嗅探 =================

def expand_args_via_sniffer(tool_java, raw_args):
    """
    使用 fMcMain 展开参数（主要是为了处理 @argfile）。
    """
    fmcmain_jar = runtimeMGR.get_fmcmain_jar()
    if not os.path.exists(fmcmain_jar):
        return raw_args  # 没法展开，只能返回原始的

    cmd = [tool_java, "-cp", fmcmain_jar, "net.minecraft.client.main.Main"] + raw_args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        return parse_sniffer_output(proc.stdout + proc.stderr)
    except:
        return raw_args


def parse_sniffer_output(output):
    args_list = []
    is_capturing = False
    if not output: return []
    for line in output.splitlines():
        line = line.strip()
        if "---YGGPROXY_SNIFFER_START---" in line:
            is_capturing = True;
            continue
        if "---YGGPROXY_SNIFFER_END---" in line:
            is_capturing = False;
            break
        if is_capturing: args_list.append(line)
    return args_list


# ================= 2. 核心过滤器 (复合判断) =================

def is_real_game_launch(args):
    """
    判断逻辑：
    只要满足以下任意一个特征，就认为是游戏启动。
    """
    args_str = " ".join(args)

    # 【特征 1】标准参数 --gameDir (HMCL, PCL, Official)
    if "--gameDir" in args: return True
    if any(a.startswith("--gameDir=") for a in args): return True

    # 【特征 2】主类白名单 (HMCL, Forge, Fabric)
    for kw in GAME_MAIN_CLASSES:
        if kw in args_str:
            return True

    # 【特征 3】Classpath 深度检查 (Prism / MultiMC)
    # 它们可能用 org.prismlauncher.EntryPoint，但 cp 里一定有 minecraft jar
    for i, arg in enumerate(args):
        if arg in ("-cp", "-classpath", "--cp") and i + 1 < len(args):
            cp_value = args[i + 1].lower()
            # 检查 cp_value 里是否包含 "minecraft" 且包含 ".jar"
            # 这样排除了 HMCL.jar, JavaCheck.jar 等工具
            match_all = True
            for kw in GAME_CP_KEYWORDS:
                if kw not in cp_value:
                    match_all = False
                    break
            if match_all:
                return True

    return False


# ================= 3. 业务逻辑 =================

def get_game_dir(args):
    # 尝试提取 gameDir
    for i, arg in enumerate(args):
        if arg == "--gameDir" and i + 1 < len(args): return args[i + 1]
        if arg.startswith("--gameDir="): return arg.split("=", 1)[1]
    # 没找到则回退到当前目录 (Prism 兼容)
    return os.getcwd()


def ensure_account_valid(game_dir, force_gui=False):
    config_mgr.load()
    target_uuid = config_mgr.get_account_for_instance(game_dir)
    auth_data = config_mgr.get_account(target_uuid)

    need_gui = force_gui

    if not auth_data:
        need_gui = True
    elif not force_gui:
        # 验 Token
        current_api = config_mgr.get_current_api_config()
        base_url = current_api.get("base_url", "").rstrip('/')
        try:
            # 简单验证，失败则刷新
            if not authAPI.validate(f"{base_url}/authserver/validate", auth_data["accessToken"],
                                    auth_data.get("clientToken")):
                new_tokens = authAPI.refresh(f"{base_url}/authserver/refresh", auth_data["accessToken"],
                                             auth_data.get("clientToken"))
                auth_data["accessToken"] = new_tokens["accessToken"]
                if "clientToken" in new_tokens: auth_data["clientToken"] = new_tokens["clientToken"]
                config_mgr.add_or_update_account(auth_data)
        except:
            need_gui = True  # 刷新异常，弹窗

    if need_gui:
        if not guiWizard.show_wizard(force_show_settings=force_gui):
            return None
        config_mgr.load()
        target_uuid = config_mgr._config_data.get("default_account_uuid")
        auth_data = config_mgr.get_account(target_uuid)
        if auth_data:
            config_mgr.set_instance_binding(game_dir, target_uuid)

    return auth_data


# ================= 4. 主入口 =================

def main():
    raw_args = sys.argv[1:]

    # [逻辑 0] 显式配置模式
    if "--yggproconfig" in raw_args:
        guiWizard.show_wizard(force_show_settings=True)
        sys.exit(0)

    # 初始化
    config_mgr.load()
    tool_java = runtimeMGR.get_fallback_java()
    if not tool_java: sys.exit(1)

    target_java = config_mgr.get_real_java_path()
    if not target_java or not os.path.exists(target_java):
        candidates = javaScanner.find_java_candidates()
        if candidates:
            target_java = candidates[0];
            config_mgr.set_real_java_path(target_java);
            config_mgr.save()
    if not target_java: target_java = tool_java

    # [逻辑 1] 预处理：展开参数
    # 只有当参数里有 @ 时，才动用 fMcMain 去展开
    # 这样能保证 HMCL 的 argfile 被读到，同时不影响普通参数
    processing_args = raw_args
    if any(a.startswith("@") for a in raw_args):
        processing_args = expand_args_via_sniffer(tool_java, raw_args)
        # 如果展开失败（比如 sniffer 没跑起来），processing_args 会回退到 raw_args
        # 此时下面的检查可能过不去，自然透传，不会 crash

    # [逻辑 2] 核心分叉 (Filter)
    # 根据展开后的参数，决定是否拦截
    if not is_real_game_launch(processing_args):
        # ❌ 不是游戏 -> 透传原始参数
        sys.exit(subprocess.call([target_java] + raw_args))

    # [逻辑 3] ✅ 判定为游戏 -> 拦截
    game_dir = get_game_dir(processing_args)
    auth_data = ensure_account_valid(game_dir)

    if not auth_data:
        sys.exit(1)

    # --- 构造启动命令 ---
    injector_path = runtimeMGR.get_injector_jar()
    api_config = config_mgr.get_current_api_config()

    final_cmd = [target_java]
    final_cmd.append(f"-javaagent:{injector_path}={api_config['base_url']}")

    sensitive_keys = {"--username", "--uuid", "--accessToken", "--userProperties", "--yggproconfig"}
    skip_next = False

    # 使用处理过(展开过)的参数来构建命令，这样更稳
    # 但如果之前没展开（没有@），这里就是 raw_args
    for arg in processing_args:
        if skip_next: skip_next = False; continue
        if arg in sensitive_keys: skip_next = True; continue
        if any(arg.startswith(k + "=") for k in sensitive_keys): continue
        if "-javaagent:" in arg and "authlib-injector" in arg: continue

        final_cmd.append(arg)

    final_cmd.extend([
        "--username", auth_data["name"],
        "--uuid", auth_data["uuid"],
        "--accessToken", auth_data["accessToken"],
        "--userProperties", "{}"
    ])

    print(f"[{constants.PROXY_NAME}] Launching: {auth_data['name']}", file=sys.stderr)

    try:
        if platform.system() == "Windows":
            sys.exit(subprocess.call(final_cmd))
        else:
            os.execv(target_java, final_cmd)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()