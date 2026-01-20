import sys
import os
import subprocess
import platform
import re
from src import constants, runtimeMGR, authAPI, guiWizard, javaScanner
from src.configMGR import config_mgr


# ================= 1. 工具方法 =================

def run_sniffer(tool_java, original_args):
    """
    使用【内嵌Java】运行 fMcMain 来清洗和规范化参数。
    """
    # 【修改点】：调用 get_fmcmain_jar 自动释放文件
    fmcmain_jar = runtimeMGR.get_fmcmain_jar()

    # 双重检查
    if not os.path.exists(fmcmain_jar):
        print(f"[{constants.PROXY_NAME}] 致命错误: 无法释放/找到 fMcMain.jar", file=sys.stderr)
        return None

    # 构造命令： <EmbeddedJava> -jar <fMcMain.jar> [原始参数...]
    # cmd = [tool_java, "-jar", fmcmain_jar] + original_args
    cmd = [
              tool_java,
              "-cp", fmcmain_jar,
              "net.minecraft.client.main.Main"
          ] + original_args

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors='replace'
        )
        return proc.stdout + proc.stderr
    except Exception as e:
        print(f"[{constants.PROXY_NAME}] 参数嗅探器运行失败: {e}", file=sys.stderr)
        return None


def parse_sniffer_output(output):
    """解析 fMcMain 的标准输出"""
    args_list = []
    is_capturing = False

    if not output: return []

    for line in output.splitlines():
        line = line.strip()
        # 匹配 Java 端定义的标记
        if "---YGGPROXY_SNIFFER_START---" in line:
            is_capturing = True
            continue
        if "---YGGPROXY_SNIFFER_END---" in line:
            is_capturing = False
            break
        if is_capturing:
            args_list.append(line)

    return args_list


def get_game_dir(args):
    """从清洗后的参数中提取 gameDir"""
    for i, arg in enumerate(args):
        if arg == "--gameDir" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--gameDir="):
            return arg.split("=", 1)[1]
    return None


def ensure_account_valid(game_dir):
    """
    账号验证核心流程：
    1. 检查绑定
    2. 如果无绑定或 Token 失效 -> 弹出 GUI
    3. 如果 Token 过期 -> 自动刷新 -> 失败则弹出 GUI
    """
    config_mgr.load()

    # 1. 获取目标账号 UUID (绑定 > 默认)
    target_uuid = config_mgr.get_account_for_instance(game_dir)
    auth_data = config_mgr.get_account(target_uuid)

    # 2. 【关键拦截点】如果没有账号，强制弹出 GUI
    if not auth_data:
        print(f"[{constants.PROXY_NAME}] 当前实例未配置账号，正在唤起登录界面...", file=sys.stderr)

        # 弹出向导 (阻塞直到用户关闭窗口)
        guiWizard.show_wizard()
        config_mgr.load()  # 重新加载，读取 GUI 保存的数据

        # 再次尝试获取 (GUI 逻辑会把新登录的账号设为默认)
        target_uuid = config_mgr.get_account_for_instance(None)
        auth_data = config_mgr.get_account(target_uuid)

        # 如果获取到了，自动绑定到当前 gameDir
        if auth_data:
            config_mgr.set_instance_binding(game_dir, target_uuid)

    # 如果弹窗后还是没账号（用户直接关掉了窗口），返回 None，后续会终止启动
    if not auth_data:
        return None

    # 3. 验证 Token 有效性
    current_api = config_mgr.get_current_api_config()
    base_url = current_api.get("base_url", "").rstrip('/')

    validate_url = f"{base_url}/authserver/validate"
    refresh_url = f"{base_url}/authserver/refresh"

    is_valid = False
    try:
        is_valid = authAPI.validate(validate_url, auth_data["accessToken"], auth_data.get("clientToken"))
    except:
        is_valid = False

    if not is_valid:
        print(f"[{constants.PROXY_NAME}] Token 已过期，尝试自动刷新...", file=sys.stderr)
        try:
            new_tokens = authAPI.refresh(refresh_url, auth_data["accessToken"], auth_data.get("clientToken"))
            auth_data["accessToken"] = new_tokens["accessToken"]
            if "clientToken" in new_tokens:
                auth_data["clientToken"] = new_tokens["clientToken"]
            config_mgr.add_or_update_account(auth_data)
        except Exception as e:
            print(f"[{constants.PROXY_NAME}] 自动刷新失败: {e}", file=sys.stderr)
            # 刷新失败，再次强制弹窗
            print(f"[{constants.PROXY_NAME}] 需要重新登录...", file=sys.stderr)
            guiWizard.show_wizard()
            config_mgr.load()

            # 重新获取
            target_uuid = config_mgr.get_account_for_instance(None)
            auth_data = config_mgr.get_account(target_uuid)

    return auth_data


# ================= 2. 主入口 =================

def main():
    raw_args = sys.argv[1:]

    # --- A. 额外功能：双击直接打开设置 ---
    if len(raw_args) == 0:
        guiWizard.show_wizard(force_show_settings=True)
        sys.exit(0)

    # 初始化
    config_mgr.load()

    # --- B. 准备运行时环境 ---

    # 1. 获取 Tool Java (内嵌，用于嗅探和伪装)
    tool_java = runtimeMGR.get_fallback_java()
    if not tool_java or not os.path.exists(tool_java):
        # 如果内嵌环境都坏了，必须报错，否则无法进行后续操作
        # 注意：这里打印到 stderr，启动器会显示错误日志
        print(f"[{constants.PROXY_NAME}] 致命错误: 无法加载内部 Java 环境。", file=sys.stderr)
        print(f"[{constants.PROXY_NAME}] 请检查 .YggProxy 目录或重新安装。", file=sys.stderr)
        sys.exit(1)

    # 2. 获取 Target Java (用户系统 Java，用于跑游戏)
    target_java = config_mgr.get_real_java_path()
    if not target_java or not os.path.exists(target_java):
        # 如果配置里没有，扫描一下
        candidates = javaScanner.find_java_candidates()
        if candidates:
            target_java = candidates[0]
            config_mgr.set_real_java_path(target_java)
            config_mgr.save()

    # 兜底：如果没有系统 Java，暂时用内嵌 Java 顶替 (虽然不建议跑大游戏)
    if not target_java:
        target_java = tool_java

    # --- C. 特殊参数处理 ---

    # 显式打开设置
    if any(arg in constants.SETTINGS_ARGS for arg in raw_args):
        guiWizard.show_wizard(force_show_settings=True)
        sys.exit(0)

    # 版本伪装 (-version)
    if any(arg.strip().lower() in ['-version', '--version'] for arg in raw_args):
        spoof_ver = config_mgr.get_spoof_version()
        if spoof_ver:
            # 开启伪装：用 Tool Java 获取输出并正则替换
            try:
                proc = subprocess.run([tool_java, "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True)
                # 替换第一行 version "xxx"
                new_output = re.sub(r'version "[^"]+"', f'version "{spoof_ver}"', proc.stdout, count=1)
                print(new_output, end='')  # 输出修改后的版本
            except:
                subprocess.call([tool_java, "-version"])
        else:
            # 关闭伪装：直接调用 Target Java
            subprocess.call([target_java, "-version"])
        sys.exit(0)

    # --- D. 参数嗅探 (核心拦截) ---

    sniffer_out = run_sniffer(tool_java, raw_args)
    captured_args = parse_sniffer_output(sniffer_out)

    # 如果截获到的参数为空，说明 sniffing 失败，或者这不是一个标准的 MC 启动命令
    if not captured_args:
        # 此时要做个判断：如果原始参数里看起来像是启动游戏（包含 net.minecraft 或 -cp），那就是出错了
        raw_str = " ".join(raw_args)
        if "net.minecraft" in raw_str or "-cp" in raw_str or "-jar" in raw_str:
            print(f"[{constants.PROXY_NAME}] 错误: 无法解析启动参数 (Sniffer Failed)。", file=sys.stderr)
            print(f"[{constants.PROXY_NAME}] 请检查 fMcMain.jar 是否存在。", file=sys.stderr)
            sys.exit(1)

        # 否则可能只是启动器在做其他检测，直接透传
        sys.exit(subprocess.call([target_java] + raw_args))

    # --- E. 业务处理 (GUI 介入点) ---

    game_dir = get_game_dir(captured_args)

    # 这里会检查账号，如果没有 -> 弹出 GUI
    auth_data = ensure_account_valid(game_dir)

    if not auth_data:
        print(f"[{constants.PROXY_NAME}] 启动终止: 用户取消或未登录。", file=sys.stderr)
        sys.exit(1)

    # --- F. 构造最终命令 ---

    injector_path = runtimeMGR.get_injector_jar()
    api_config = config_mgr.get_current_api_config()

    final_cmd = [target_java]

    # 注入 authlib-injector
    final_cmd.append(f"-javaagent:{injector_path}={api_config['base_url']}")

    # 过滤与重组参数
    sensitive_keys = {"--username", "--uuid", "--accessToken", "--userProperties"}
    skip_next = False

    for arg in captured_args:
        if skip_next:
            skip_next = False
            continue

        if arg in sensitive_keys:
            skip_next = True
            continue
        if any(arg.startswith(k + "=") for k in sensitive_keys):
            continue

        # 移除旧的 authlib-injector agent (防止双重注入)
        if "-javaagent:" in arg and "authlib-injector" in arg:
            continue

        final_cmd.append(arg)

    # 追加我们的账号参数
    final_cmd.extend([
        "--username", auth_data["name"],
        "--uuid", auth_data["uuid"],
        "--accessToken", auth_data["accessToken"],
        "--userProperties", "{}"
    ])

    # --- G. 发射 ---
    print(f"[{constants.PROXY_NAME}] 启动游戏: {auth_data['name']} (UUID: {auth_data['uuid']})", file=sys.stderr)

    try:
        if platform.system() == "Windows":
            sys.exit(subprocess.call(final_cmd))
        else:
            os.execv(target_java, final_cmd)
    except Exception as e:
        print(f"[{constants.PROXY_NAME}] 启动异常: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()