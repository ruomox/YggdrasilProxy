# src/main.py
import sys
import os
import subprocess
import platform
import re
from src import constants, javaScanner, authAPI, guiWizard, runtimeMGR
from src.configMGR import config_mgr


# ==============================================================================
# 辅助函数
# ==============================================================================
def ensure_session_valid(force_settings=False):
    """确保会话有效，处理刷新、重新登录"""
    config_mgr.load()
    auth_data = config_mgr.get_auth_data()
    current_api = config_mgr.get_current_api_config()
    base_url = current_api.get("base_url")

    # 1. 无凭据 -> 登录
    if not auth_data:
        print(f"[{constants.PROXY_NAME}] 需要验证账号...", file=sys.stderr)
        if not guiWizard.show_wizard(force_show_settings=False):
            sys.exit(1)
        config_mgr.load()
        return

    # 2. 有凭据 -> 验证
    access_token = auth_data.get("accessToken")
    client_token = auth_data.get("clientToken")

    # 简单验证
    if authAPI.validate(f"{base_url}/authserver/validate", access_token, client_token):
        return

    # 3. 验证失败 -> 刷新
    print(f"[{constants.PROXY_NAME}] Token 失效，尝试刷新...", file=sys.stderr)
    try:
        data = authAPI.refresh(f"{base_url}/authserver/refresh", access_token, client_token)
        auth_data["accessToken"] = data["accessToken"]
        if "clientToken" in data: auth_data["clientToken"] = data["clientToken"]
        config_mgr.set_auth_data(auth_data)
        config_mgr.save()
        return
    except:
        pass

    # 4. 刷新失败 -> 重新登录
    print(f"[{constants.PROXY_NAME}] 凭证过期，请重新登录。", file=sys.stderr)
    if not guiWizard.show_wizard(force_show_settings=False):
        sys.exit(1)
    config_mgr.load()


def main():
    args = sys.argv[1:]

    # ========================== 1. 意图判断 ==========================
    is_launching_game = False
    if any(arg == "--accessToken" for arg in args):
        is_launching_game = True
    elif any(constants.MC_MAIN_CLASS in arg for arg in args):
        is_launching_game = True
    elif len(args) > 4 and any(arg.endswith(".jar") for arg in args):
        is_launching_game = True

    is_version_check = any(arg.strip().lower() in ['-version', '--version'] for arg in args)
    is_forcing_settings = any(arg.lower() in constants.SETTINGS_ARGS for arg in args)

    is_maintenance_mode = not is_launching_game and not is_forcing_settings

    # ========================== 2. 寻找 Actor Java (保留之前的解压修复) ==========================
    config_mgr.load()

    # 【修改点 1】只调用一次强制解压，并保存结果
    # 这一步现在是强制的：清理旧文件 -> 解压新文件
    embedded_java = runtimeMGR.get_fallback_java()

    actor_java = config_mgr.get_real_java_path()

    # 策略 A: 优先扫系统 (如果配置里没有指定)
    if not actor_java or not os.path.exists(actor_java):
        candidates = javaScanner.find_java_candidates()
        if candidates:
            actor_java = candidates[0]
        else:
            actor_java = None

    # 【修改点 2】删除这里的重复调用
    # 这里的 runtimeMGR.get_fallback_java() 删掉，因为上面已经做过了

    # 策略 B: 系统无 -> 使用刚才解压好的内嵌 Java
    if not actor_java:
        # 【修改点 3】直接使用变量 embedded_java，不再调用函数
        if embedded_java and os.path.exists(embedded_java):
            actor_java = embedded_java

    # ========================== 3. 分支一：维护/欺骗模式 ==========================
    if is_maintenance_mode:
        if is_version_check:
            spoof_ver = config_mgr.get_spoof_version()
            if not spoof_ver: sys.exit(subprocess.call([actor_java] + args))
            try:
                proc = subprocess.run([actor_java] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      errors='replace')
                pattern = re.compile(r'version\s+"(\d+(\.\d+)*(_\d+)?(-\w+)?)"')
                modified_stderr = proc.stderr
                match = pattern.search(modified_stderr)
                if match:
                    real_ver = match.group(1)
                    if real_ver != spoof_ver:
                        modified_stderr = modified_stderr.replace(f'version "{real_ver}"', f'version "{spoof_ver}"')
                        modified_stderr = modified_stderr.replace(f'build {real_ver.split(".")[0]}',
                                                                  f'build {spoof_ver.split(".")[0]}')
                print(modified_stderr, file=sys.stderr, end='')
                if proc.stdout: print(proc.stdout, file=sys.stdout, end='')
                sys.exit(proc.returncode)
            except:
                sys.exit(subprocess.call([actor_java] + args))
        else:
            sys.exit(subprocess.call([actor_java] + args))

    # ========================== 4. 分支二：启动游戏模式 ==========================

    # --- 加载配置 ---
    config_mgr.load()

    print("=" * 50, file=sys.stderr)
    print(f"[{constants.PROXY_NAME} v{constants.PROXY_VERSION}] 介入...", file=sys.stderr)

    # --- 核心业务：确保会话有效 ---
    # 如果是强制设置模式，且不启动游戏，在 ensure_session_valid 内部的弹窗关闭后直接退出
    # 但为了逻辑严密，我们在这里处理纯设置逻辑
    if is_forcing_settings and not is_launching_game:
        guiWizard.show_wizard(force_show_settings=True)
        print(f"[{constants.PROXY_NAME}] 设置完成。", file=sys.stderr)
        sys.exit(0)

    # 1. 确保有 Real Java
    real_java = config_mgr.get_real_java_path()
    if not real_java or not os.path.exists(real_java):
        # 优先尝试系统扫描，避免强制弹窗影响“无 Java 机器”的自动兜底体验
        candidates = javaScanner.find_java_candidates()
        if candidates:
            real_java = candidates[0]
            config_mgr.set_real_java_path(real_java)
            config_mgr.save()
        else:
            # 系统仍无 Java：使用内嵌作为兜底“真实 Java”
            if embedded_java and os.path.exists(embedded_java):
                real_java = embedded_java
            else:
                print(f"[{constants.PROXY_NAME}] 请配置 Java 环境...", file=sys.stderr)
                if not guiWizard.show_wizard(force_show_settings=True): sys.exit(1)
                config_mgr.load()
                real_java = config_mgr.get_real_java_path()

    # 2. 确保 Token 有效
    ensure_session_valid(force_settings=is_forcing_settings)

    # 3. 获取启动信息
    auth_data = config_mgr.get_auth_data()
    current_api = config_mgr.get_current_api_config()
    injector_path = runtimeMGR.get_injector_jar()

    if not auth_data or not real_java or not current_api or not injector_path:
        print(f"[{constants.PROXY_NAME}] 严重错误：缺少必要信息，无法启动。", file=sys.stderr)
        sys.exit(1)

    # ==============================================================================
    # 6. 参数精细化重组 (严格执行劈开参数逻辑)
    # ==============================================================================

    final_cmd = []

    # 检查是否存在主类，作为分界线
    if constants.MC_MAIN_CLASS in args:
        # === 经典模式 (Vanilla / OptiFine) ===
        original_jvm_args = []
        original_game_args = []
        main_class_found = False

        for arg in args:
            if arg == constants.MC_MAIN_CLASS:
                main_class_found = True
                continue  # 主类名稍后单独加

            if not main_class_found:
                # 主类名之前 -> JVM 参数
                if arg not in constants.SETTINGS_ARGS:
                    original_jvm_args.append(arg)
            else:
                # 主类名之后 -> 游戏参数
                if arg not in constants.SETTINGS_ARGS:
                    original_game_args.append(arg)

        # --- A. 构造 JVM 参数 ---
        final_jvm_args = []
        final_jvm_args.extend(original_jvm_args)

        # 1. 注入 Authlib-Injector
        final_jvm_args.append(f"-javaagent:{injector_path}={current_api['base_url']}")

        # 2. 移除可能冲突的旧 Agent
        final_jvm_args = [arg for arg in final_jvm_args if "authlib-injector" not in arg]

        # 3. 强制覆盖品牌 (JVM 属性)
        final_jvm_args.append(f"-Dminecraft.launcher.brand={constants.PROXY_NAME}")
        final_jvm_args.append(f"-Dminecraft.launcher.version={constants.PROXY_VERSION}")

        # --- B. 构造 游戏 参数 ---
        final_game_args = []

        skip_next = False
        sensitive_keys = ["--username", "--uuid", "--accessToken", "--userProperties", "--versionType"]

        for arg in original_game_args:
            if skip_next:
                skip_next = False
                continue

            # 严格拦截旧参数 (空格格式)
            if arg in sensitive_keys:
                skip_next = True
                continue

            # 严格拦截旧参数 (等号格式兼容，防止漏网)
            is_assign = False
            for k in sensitive_keys:
                if arg.startswith(k + "="):
                    is_assign = True
                    break
            if is_assign:
                continue

            final_game_args.append(arg)

        # 注入认证信息
        final_game_args.extend(["--username", auth_data["name"]])
        final_game_args.extend(["--uuid", auth_data["uuid"]])
        final_game_args.extend(["--accessToken", auth_data["accessToken"]])
        final_game_args.extend(["--userProperties", "{}"])

        # 注入自定义显示版本
        my_branding = f"{constants.PROXY_NAME} v{constants.PROXY_VERSION}"
        final_game_args.extend(["--versionType", my_branding])

        # 组装
        final_cmd = [real_java] + final_jvm_args + [constants.MC_MAIN_CLASS] + final_game_args

    else:
        # === 兼容模式 (Forge/Fabric) ===
        # 找不到 MC_MAIN_CLASS，我们只能尽可能清洗，并按照 JVM在前 Game在后的原则注入

        # 1. 头部 JVM 注入
        jvm_inject = [
            f"-javaagent:{injector_path}={current_api['base_url']}",
            f"-Dminecraft.launcher.brand={constants.PROXY_NAME}",
            f"-Dminecraft.launcher.version={constants.PROXY_VERSION}"
        ]

        # 2. 尾部 Game 注入
        my_branding = f"{constants.PROXY_NAME} v{constants.PROXY_VERSION}"
        game_inject = [
            "--username", auth_data["name"],
            "--uuid", auth_data["uuid"],
            "--accessToken", auth_data["accessToken"],
            "--userProperties", "{}",
            "--versionType", my_branding
        ]

        # 3. 中间参数清洗
        cleaned_args = []
        skip_next = False
        sensitive_keys = ["--username", "--uuid", "--accessToken", "--userProperties", "--versionType"]

        for arg in args:
            if skip_next:
                skip_next = False
                continue

            # 过滤 Game 参数
            if arg in sensitive_keys:
                skip_next = True
                continue

            # 过滤 JVM Brand (如果启动器传了)
            if arg.startswith("-Dminecraft.launcher.brand=") or arg.startswith("-Dminecraft.launcher.version="):
                continue

            # 过滤 Injector
            if "authlib-injector" in arg:
                continue

            # 过滤设置参数
            if arg in constants.SETTINGS_ARGS:
                continue

            cleaned_args.append(arg)

        final_cmd = [real_java] + jvm_inject + cleaned_args + game_inject

    print(f"[{constants.PROXY_NAME}] 启动参数重组完毕，转交控制权...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # 7. 最终执行
    try:
        if platform.system() == "Windows":
            if not final_cmd[0].lower().endswith(".exe"):
                final_cmd[0] += ".exe"
            sys.exit(subprocess.call(final_cmd))
        else:
            os.execv(real_java, final_cmd)

    except OSError as e:
        err_msg = f"无法启动外部真实 JDK 进程:\n{real_java}\n\n错误信息: {e}"
        print(f"[{constants.PROXY_NAME}] {err_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()