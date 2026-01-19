# src/main.py
import sys
import os
import subprocess
import platform
import re
# 引入所有必要的模块，包括新的 injector
from src import constants, javaScanner, authAPI, guiWizard, runtimeMGR
from src.configMGR import config_mgr


# ... (ensure_session_valid 函数逻辑无需改动，直接使用之前的版本) ...
def ensure_session_valid(force_settings=False):
    """确保会话有效，处理刷新、重新登录和强制设置"""
    auth_data = config_mgr.get_auth_data()
    current_api = config_mgr.get_current_api_config()
    base_url = current_api.get("base_url")

    # 情况 0: 强制显示设置界面
    if force_settings:
        print(f"[{constants.PROXY_NAME}] 检测到强制设置参数，打开设置界面。", file=sys.stderr)
        if not guiWizard.show_wizard(is_relogin=False, force_show_settings=True):
            print(f"[{constants.PROXY_NAME}] 设置未完成，退出。", file=sys.stderr)
            sys.exit(1)
        return  # 设置完成，理论上 auth_data 已更新，可以直接进入启动流程

    # 情况 1: 没有授权数据 -> 首次运行
    if not auth_data:
        print(f"[{constants.PROXY_NAME}] 未找到授权信息，启动初始化向导。", file=sys.stderr)
        if not guiWizard.show_wizard(is_relogin=False):
            print(f"[{constants.PROXY_NAME}] 初始化未完成，退出。", file=sys.stderr)
            sys.exit(1)
        return

    # 情况 2: 尝试静默验证
    access_token = auth_data.get("accessToken")
    client_token = auth_data.get("clientToken")
    print(f"[{constants.PROXY_NAME}] 正在检查会话有效性...", file=sys.stderr)
    # 确保配置文件里有 validate_url (兼容旧配置)
    validate_url = f"{base_url}/authserver/validate"
    if authAPI.validate(validate_url, access_token, client_token):
        print(f"[{constants.PROXY_NAME}] 会话有效。", file=sys.stderr)
        return

    # 情况 3: 验证失败，尝试后台刷新
    print(f"[{constants.PROXY_NAME}] 会话失效，尝试后台刷新...", file=sys.stderr)
    try:
        refresh_url = f"{base_url}/authserver/refresh"
        data = authAPI.refresh(refresh_url, access_token, client_token)
        print(f"[{constants.PROXY_NAME}] 刷新成功！更新本地凭据。", file=sys.stderr)
        auth_data["accessToken"] = data["accessToken"]
        if "clientToken" in data: auth_data["clientToken"] = data["clientToken"]
        config_mgr.set_auth_data(auth_data)
        config_mgr.save()
        return
    except Exception as e:
        print(f"[{constants.PROXY_NAME}] 刷新失败 ({e})。", file=sys.stderr)

    # 情况 4: 刷新失败，强制重新登录
    print(f"[{constants.PROXY_NAME}] 需要用户重新登录。", file=sys.stderr)
    if not guiWizard.show_wizard(is_relogin=True):
        print(f"[{constants.PROXY_NAME}] 重新登录未完成，退出。", file=sys.stderr)
        sys.exit(1)


def main():
    # 1. 第一时间获取参数
    args = sys.argv[1:]

    # 2. 判断意图
    # 检查是否为版本检查
    is_version_check = any(
        arg.strip().lower() in ['-version', '--version', '-fullversion', '-showversion'] for arg in args)
    is_launching_game = any(constants.MC_MAIN_CLASS in arg for arg in args)
    is_forcing_settings = any(arg.lower() in constants.SETTINGS_ARGS for arg in args)

    # ==============================================================================
    # 准备阶段：确定要使用的“演员” Java
    # ==============================================================================
    config_mgr.load()  # 提前加载配置

    # 策略：优先用配置的外部 Java -> 其次扫描系统 Java -> 最后用内嵌 Java 兜底
    actor_java = config_mgr.get_real_java_path()

    if not actor_java or not os.path.exists(actor_java):
        # 没有配置或配置无效，尝试扫描
        print(f"[{constants.PROXY_NAME}] 未配置外部 Java，尝试扫描系统...", file=sys.stderr)
        candidates = javaScanner.find_java_candidates()
        if candidates:
            actor_java = candidates[0]
            print(f"[{constants.PROXY_NAME}] 选中系统 Java: {actor_java}", file=sys.stderr)
        else:
            # 扫描失败，检查是否启用了兜底方案
            # 【修改】增加对 enable_embedded_java 的判断
            if config_mgr.get_enable_embedded_java():
                print(f"[{constants.PROXY_NAME}] 系统扫描失败，启用内嵌 Java 兜底 (将触发解压)。", file=sys.stderr)
                # 只有在这里调用 get_fallback_java 才会触发解压
                actor_java = runtimeMGR.get_fallback_java()
            else:
                print(f"[{constants.PROXY_NAME}] 系统扫描失败，且未启用内嵌 Java 兜底。", file=sys.stderr)

    if not actor_java:
        # 彻底绝望了
        # 【修改】提示信息更明确
        print(
            f"[{constants.PROXY_NAME}] Critical Error: No usable Java environment found. Please install Java or enable embedded fallback in settings.",
            file=sys.stderr)
        sys.exit(1)

    # ==============================================================================
    # 分支一：特洛伊木马模式 (The "Fake" Java Mode)
    # ==============================================================================
    if not is_launching_game and not is_forcing_settings:
        if is_version_check:
            # 版本伪装逻辑
            try:
                # 获取配置的伪装版本
                spoof_version = config_mgr.get_spoof_version()

                # 【修改】如果未配置伪装版本，直接直通
                if not spoof_version:
                    ret_code = subprocess.call([actor_java] + args)
                    sys.exit(ret_code)

                # 运行选定的 Java，捕获输出
                proc = subprocess.run(
                    [actor_java] + args,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, check=False, errors='replace'  # 处理可能的编码问题
                )

                # 使用正则进行智能替换
                # 匹配模式：version "任意数字.任意数字.任意数字_任意后缀"
                version_pattern = re.compile(r'version\s+"(\d+(\.\d+)*(_\d+)?(-\w+)?)"')

                modified_stderr = proc.stderr
                # 查找真实版本号
                match = version_pattern.search(modified_stderr)
                if match:
                    real_version = match.group(1)
                    # 如果真实版本与目标伪装版本不同，进行替换
                    if real_version != spoof_version:
                        # 只替换版本号部分，保留前后文，更真实
                        modified_stderr = modified_stderr.replace(f'version "{real_version}"',
                                                                  f'version "{spoof_version}"')
                        # 尝试替换 build 版本信息 (更高级的伪装)
                        # 例如把 (build 25...) 替换为 (build 17...)
                        real_major = real_version.split('.')[0]
                        spoof_major = spoof_version.split('.')[0]
                        if real_major != spoof_major:
                            modified_stderr = modified_stderr.replace(f'build {real_major}', f'build {spoof_major}')

                # 输出最终结果
                print(modified_stderr, file=sys.stderr, end='', flush=True)
                if proc.stdout:
                    print(proc.stdout, file=sys.stdout, end='', flush=True)
                sys.exit(proc.returncode)

            except Exception as e:
                # 伪装失败，直通兜底
                print(f"[{constants.PROXY_NAME}] Warning: Version spoofing failed ({e}), passing through.",
                      file=sys.stderr)
                ret_code = subprocess.call([actor_java] + args)
                sys.exit(ret_code)
        else:
            # 其他复杂检查，直通
            try:
                ret_code = subprocess.call([actor_java] + args)
                sys.exit(ret_code)
            except Exception as e:
                sys.exit(1)

    # ==============================================================================
    # 分支二：代理模式 (The Proxy Mode)
    # 启动游戏或强制设置
    # ==============================================================================

    # 3. 加载配置
    config_mgr.load()

    print("=" * 50, file=sys.stderr)
    print(f"[{constants.PROXY_NAME} v{constants.PROXY_VERSION}] 介入...", file=sys.stderr)

    # 4. 核心业务：确保会话有效 (含 UI 弹出逻辑)
    ensure_session_valid(force_settings=is_forcing_settings)

    # 如果只是强制设置，设置完就退出
    if is_forcing_settings and not is_launching_game:
        print(f"[{constants.PROXY_NAME}] 设置完成。", file=sys.stderr)
        sys.exit(0)

    # 5. 获取必要的启动信息
    auth_data = config_mgr.get_auth_data()
    real_java = config_mgr.get_real_java_path()
    current_api = config_mgr.get_current_api_config()  # 获取当前 API 配置
    # 【新增】获取内嵌的 authlib-injector 路径
    injector_path = runtimeMGR.get_injector_jar()

    # 多重检查确保所有必要组件就位
    if not auth_data or not real_java or not current_api or not injector_path:
        print(f"[{constants.PROXY_NAME}] 严重错误：缺少必要信息（凭据/真实Java/API配置/Injector），无法启动。",
              file=sys.stderr)
        sys.exit(1)

    # 6. 参数注入 (Token + Authlib-Injector)
    new_args = []

    # 【修复 1】注入 authlib-injector (增加引号以支持带空格的路径)
    # 格式: -javaagent:"/path/to/injector.jar"=https://yggdrasil.server.url
    injector_arg = f"-javaagent:{injector_path}={current_api['base_url']}"
    new_args.append(injector_arg)
    print(f"[{constants.PROXY_NAME}] 已注入 Authlib-Injector: {current_api['base_url']}", file=sys.stderr)

    # 【新增】准备自定义版本标识字符串
    # 这将显示在游戏主界面左下角
    my_branding = f"{constants.PROXY_NAME} v{constants.PROXY_VERSION}"

    skip_next = False
    print(f"[{constants.PROXY_NAME}] 正在为用户 [{auth_data['name']}] 注入凭据与版本标识...", file=sys.stderr)

    # 过滤掉我们的设置参数
    game_args = [arg for arg in args if arg.lower() not in constants.SETTINGS_ARGS]

    for arg in game_args:
        if skip_next:
            skip_next = False
            continue

        # 【修复 2】拦截启动器传入的原始 versionType (防止冲突)
        if arg == "--versionType":
            skip_next = True  # 跳过下一个参数（即原有的版本类型字符串，如 "release"）
            continue  # 并且不把 "--versionType" 加进去

        # 注入认证参数
        if arg == "--username":
            new_args.extend(["--username", auth_data["name"]])
            skip_next = True
        elif arg == "--uuid":
            new_args.extend(["--uuid", auth_data["uuid"]])
            skip_next = True
        elif arg == "--accessToken":
            new_args.extend(["--accessToken", auth_data["accessToken"]])
            skip_next = True
        elif arg == "--userProperties":
            new_args.extend(["--userProperties", "{}"])
            skip_next = True
        # 过滤掉启动器可能自带的旧 injector 参数，避免冲突
        elif arg.startswith("-javaagent:") and "authlib-injector" in arg:
            print(f"[{constants.PROXY_NAME}] 移除启动器自带的旧 Injector 参数: {arg}", file=sys.stderr)
            continue
        else:
            new_args.append(arg)

    # 【修复 3】在最后强制追加我们自定义的 versionType
    new_args.extend(["--versionType", my_branding])

    # 7. 移交执行权给外部真实 JDK
    print(f"[{constants.PROXY_NAME}] 转交控制权给外部真实 JDK: {real_java}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    try:
        # Windows 下确保以 .exe 结尾
        if platform.system() == "Windows" and not real_java.lower().endswith(".exe"):
            real_java += ".exe"

        # 执行启动
        if platform.system() == "Windows":
            sys.exit(subprocess.call([real_java] + new_args))
        else:
            os.execv(real_java, [real_java] + new_args)

    except OSError as e:
        err_msg = f"无法启动外部真实 JDK 进程:\n{real_java}\n\n错误信息: {e}"
        print(f"[{constants.PROXY_NAME}] {err_msg}", file=sys.stderr)
        # 在非版本检查模式下，弹窗提示错误
        try:
            import tkinter.messagebox
            tkinter.messagebox.showerror(f"{constants.PROXY_NAME} 严重错误", err_msg)
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()