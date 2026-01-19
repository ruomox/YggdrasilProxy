# src/guiWizard.py
import sys
import os
import platform
import threading
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import requests
from src import constants, authAPI, javaScanner, runtimeMGR
from src.configMGR import config_mgr


class LoginWizard:
    def __init__(self, is_relogin=False, force_show_settings=False):
        self.is_relogin = is_relogin
        self.force_show_settings = force_show_settings
        self.setup_success = False
        self.window = tk.Tk()
        self._setup_ui()

    def _setup_ui(self):
        title_prefix = f"{constants.PROXY_NAME} - "
        if self.is_relogin:
            title = title_prefix + "会话失效，请重新登录"
        elif self.force_show_settings:
            title = title_prefix + "设置"
        else:
            title = title_prefix + "初始化向导"

        self.window.title(title)
        # 设定最小尺寸，防止界面过于拥挤
        self.window.minsize(500, 650)

        style = ttk.Style()
        style.theme_use('clam')

        # 主滚动区域 (防止屏幕太小显示不全)
        main_canvas = tk.Canvas(self.window)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=main_canvas.yview)
        self.scrollable_frame = ttk.Frame(main_canvas, padding="20")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(
                scrollregion=main_canvas.bbox("all")
            )
        )

        main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 标题
        ttk.Label(self.scrollable_frame, text=title, font=("Arial", 14, "bold")).pack(pady=(0, 20), anchor="center")

        if self.is_relogin:
            ttk.Label(self.scrollable_frame, text="您的登录信息已过期，需要重新验证。", foreground="red").pack(
                pady=(0, 10))

        # --- Java 选择区域 ---
        # 即使是重新登录，如果强制显示设置，也允许修改 Java
        if not self.is_relogin or self.force_show_settings:
            self.java_path_var = tk.StringVar(value=config_mgr.get_real_java_path() or "")
            self._create_java_section(self.scrollable_frame)

        # --- API 选择区域 ---
        self._create_api_section(self.scrollable_frame)

        # --- 登录区域 ---
        self._create_login_section(self.scrollable_frame)

        # --- 高级设置区域 ---
        self._create_advanced_section(self.scrollable_frame)

        # --- 底部按钮 ---
        btn_text = "保存设置" if (self.force_show_settings and not self.is_relogin) else "登录并保存"
        self.login_btn = ttk.Button(self.scrollable_frame, text=btn_text, command=self._start_login_thread,
                                    style="Accent.TButton")
        self.login_btn.pack(fill="x", pady=(20, 0))

        # 绑定鼠标滚轮事件
        self.window.bind_all("<MouseWheel>", lambda e: main_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.window.bind('<Return>', lambda e: self._start_login_thread())
        self.window.protocol("WM_DELETE_WINDOW", sys.exit)

        self._center_window()

    def _create_java_section(self, parent):
        java_frame = ttk.LabelFrame(parent, text="外部 Java 运行环境 (游戏主力)", padding="10")
        java_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(java_frame, text="请选择用于运行游戏的真实 JDK (推荐 Java 17+):", font=("Arial", 9)).pack(anchor="w",
                                                                                                            pady=(0, 5))

        input_frame = ttk.Frame(java_frame)
        input_frame.pack(fill="x")

        self.java_combo = ttk.Combobox(input_frame, textvariable=self.java_path_var, width=50, state="readonly")
        self.java_combo.set("正在扫描系统 Java...")
        self.java_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))

        javaScanner.start_scan(self._on_java_scan_finished)

        ttk.Button(input_frame, text="浏览...", command=self._browse_java).pack(side="right")

        self.enable_embedded_var = tk.BooleanVar(value=config_mgr.get_enable_embedded_java())
        ttk.Checkbutton(java_frame, text="启用内嵌精简 Java 作为最终兜底 (需要解压，占用额外空间)",
                        variable=self.enable_embedded_var).pack(anchor="w", pady=(5, 0))

    # --- 2: 回调函数 ---
    def _on_java_scan_finished(self, found_javas):
        """Java 扫描完成的回调"""
        # 尝试获取内嵌和已配置的 Java，合并列表
        embedded_java = runtimeMGR.get_fallback_java()
        if embedded_java and embedded_java not in found_javas:
            found_javas.append(embedded_java)

        current_configured = config_mgr.get_real_java_path()
        if current_configured and current_configured not in found_javas and os.path.exists(current_configured):
            found_javas.append(current_configured)

        found_javas = sorted(list(set(found_javas)))

        # 在主线程更新 UI
        self.window.after(0, lambda: self._update_java_combo(found_javas, embedded_java))
        # 可选：扫描完成后弹个小提示
        # self.window.after(0, lambda: messagebox.showinfo("提示", f"Java 扫描完成，找到 {len(found_javas)} 个可用环境。"))

    def _create_api_section(self, parent):
        api_frame = ttk.LabelFrame(parent, text="认证服务器 (API)", padding="10")
        api_frame.pack(fill="x", pady=(0, 15))

        api_list = config_mgr.get_api_list()
        api_names = [api['name'] for api in api_list]
        self.api_combo = ttk.Combobox(api_frame, values=api_names, state="readonly")
        self.api_combo.current(config_mgr.get_current_api_index())
        self.api_combo.pack(fill="x", pady=(0, 10))
        self.api_combo.bind("<<ComboboxSelected>>", self._on_api_selected)

        self.api_url_var = tk.StringVar()
        self.api_url_entry = ttk.Entry(api_frame, textvariable=self.api_url_var, state="readonly")
        self.api_url_entry.pack(fill="x", pady=(0, 5))
        ttk.Label(api_frame, text="* 请输入 API 基础地址 (例如 https://littleskin.cn/api/yggdrasil)。", font=("Arial", 8), foreground="gray").pack(anchor="w")

        btn_frame = ttk.Frame(api_frame)
        btn_frame.pack(fill="x", pady=(5, 0))

        self.new_api_btn = ttk.Button(btn_frame, text="新建/自定义", command=self._enable_api_edit)
        self.new_api_btn.pack(side="left", padx=(0, 5))

        self.save_api_btn = ttk.Button(btn_frame, text="保存 API", command=self._save_current_api, state="disabled")
        self.save_api_btn.pack(side="left", padx=(0, 5))

        self.del_api_btn = ttk.Button(btn_frame, text="删除", command=self._delete_current_api)
        self.del_api_btn.pack(side="right")

        self._on_api_selected()

    def _create_login_section(self, parent):
        login_frame = ttk.LabelFrame(parent, text="账号信息", padding="10")
        login_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(login_frame, text="邮箱/用户名:").pack(anchor="w")
        self.email_entry = ttk.Entry(login_frame, width=40)
        self.email_entry.pack(fill="x", pady=(5, 10))

        ttk.Label(login_frame, text="密码:").pack(anchor="w")
        self.pwd_entry = ttk.Entry(login_frame, show="*", width=40)
        self.pwd_entry.pack(fill="x", pady=(5, 10))

        old_auth = config_mgr.get_auth_data()
        if self.is_relogin and old_auth and old_auth.get("name"):
            ttk.Label(login_frame, text=f"当前角色: {old_auth['name']}").pack(anchor="e")

    def _create_advanced_section(self, parent):
        # 创建一个可折叠的高级设置区域
        self.adv_frame = ttk.LabelFrame(parent, text="高级设置 (可选)", padding="10")
        self.adv_frame.pack(fill="x", pady=(0, 10))

        # 默认收起，通过一个变量控制显示
        self.show_adv_var = tk.BooleanVar(value=False)

        # 切换按钮
        toggle_btn = ttk.Checkbutton(self.adv_frame, text="显示高级选项", variable=self.show_adv_var,
                                     command=self._toggle_advanced)
        toggle_btn.pack(anchor="w", pady=(0, 10))

        # 内容容器
        self.adv_content_frame = ttk.Frame(self.adv_frame)

        # --- 伪装版本设置 ---
        ttk.Label(self.adv_content_frame, text="伪装 Java 版本号:").pack(anchor="w")
        self.spoof_version_var = tk.StringVar(value=config_mgr.get_spoof_version())
        spoof_entry = ttk.Entry(self.adv_content_frame, textvariable=self.spoof_version_var, width=20)
        spoof_entry.pack(anchor="w", pady=(5, 0))
        ttk.Label(self.adv_content_frame, text="* 用于欺骗启动器的版本检查，建议保持默认 (如 17.0.9)。",
                  font=("Arial", 8), foreground="gray").pack(anchor="w", pady=(0, 10))

        # 初始化折叠状态
        self._toggle_advanced()

    def _toggle_advanced(self):
        if self.show_adv_var.get():
            self.adv_content_frame.pack(fill="x", expand=True)
        else:
            self.adv_content_frame.pack_forget()

    # --- 事件处理 ---
    def _run_java_scan(self):
        # 扫描系统 Java
        found_javas = javaScanner.find_java_candidates()

        # 尝试获取已解压的内嵌 Java
        embedded_java = runtimeMGR.get_fallback_java(force=False)
        if embedded_java and embedded_java not in found_javas:
            # 将内嵌 Java 加入列表，并使用特殊标识
            found_javas.append(embedded_java)

        # 如果有已配置的路径，也加入
        current_configured = config_mgr.get_real_java_path()
        if current_configured and current_configured not in found_javas and os.path.exists(current_configured):
            found_javas.append(current_configured)

        # 排序并去重
        found_javas = sorted(list(set(found_javas)))

        self.window.after(0, lambda: self._update_java_combo(found_javas, embedded_java))

    def _update_java_combo(self, found_javas, embedded_java_path):
        if not self.window.winfo_exists(): return

        display_values = []
        real_values = []

        # 构建显示列表，加入版本信息
        for path in found_javas:
            real_values.append(path)

            # 获取版本信息
            # 注意：虽然这里再次调用了 subprocess，但由于刚才的扫描已经预热了系统缓存，
            # 且我们加了 1 秒超时，这里通常会很快。
            raw_ver = javaScanner.get_java_version(path)

            # 格式化显示字符串
            if raw_ver:
                # 清理版本号字符串 (去除 "java version", 引号等)
                clean_ver = raw_ver.replace('"', '').strip()
                if "version" in clean_ver.lower():
                    # 例如 "java version 1.8.0_202" -> "1.8.0_202"
                    clean_ver = clean_ver.split('version')[-1].strip()

                # 最终显示格式: "17.0.1 (C:\Path\To\Java)"
                label = f"{clean_ver} ({path})"
            else:
                label = path

            # 为内嵌 Java 加上特殊前缀
            if path == embedded_java_path:
                display_values.append(f"[内嵌] {label}")
            else:
                display_values.append(label)

        self.java_combo['values'] = display_values
        self.java_combo_real_values = real_values  # 存储真实路径映射

        # 恢复之前的选中状态
        current_path = self.java_path_var.get()
        if current_path:
            if current_path in real_values:
                idx = real_values.index(current_path)
                self.java_combo.current(idx)
            elif embedded_java_path and current_path == embedded_java_path:
                # 处理已配置为内嵌的情况
                try:
                    idx = real_values.index(embedded_java_path)
                    self.java_combo.current(idx)
                except ValueError:
                    self.java_combo.set(current_path)  # 不在列表里就直接显示路径
            else:
                self.java_combo.set(current_path)  # 显示当前配置的路径
        elif display_values:
            self.java_combo.current(0)  # 默认选第一个
        else:
            self.java_combo.set("未找到可用 Java，请手动浏览...")

        if display_values:
            self.java_combo.state(["!readonly"])

    def _browse_java(self):
        filetypes = [("Java Executable", "java.exe"), ("All Files", "*")] if platform.system() == "Windows" else [
            ("All Files", "*")]
        filename = filedialog.askopenfilename(title="选择 java 或 javaw", filetypes=filetypes)
        if filename:
            self.java_path_var.set(filename)
            # 如果选择的路径不在下拉列表里，添加到列表头并选中
            if hasattr(self, 'java_combo_real_values') and filename not in self.java_combo_real_values:
                current_display = list(self.java_combo['values'])
                current_real = self.java_combo_real_values
                self.java_combo['values'] = [filename] + current_display
                self.java_combo_real_values = [filename] + current_real
            try:
                idx = self.java_combo_real_values.index(filename)
                self.java_combo.current(idx)
            except:
                pass

    # ... (API 部分的处理函数 _on_api_selected, _enable_api_edit, _save_current_api, _delete_current_api 保持不变) ...
    # 为节省篇幅，请直接复制上一版代码中对应的 API 处理函数
    def _on_api_selected(self, event=None):
        idx = self.api_combo.current()
        api_list = config_mgr.get_api_list()
        if 0 <= idx < len(api_list):
            self.api_url_var.set(api_list[idx]["base_url"])
            self.api_url_entry.config(state="readonly")
            self.save_api_btn.config(state="disabled")
            if idx == 0:
                self.del_api_btn.config(state="disabled")
            else:
                self.del_api_btn.config(state="normal")
        config_mgr.set_current_api_index(idx)

    def _enable_api_edit(self):
        self.api_combo.set("自定义 API (未保存)")
        self.api_url_var.set("")
        self.api_url_entry.config(state="normal")
        self.api_url_entry.focus_set()
        self.save_api_btn.config(state="normal")
        self.del_api_btn.config(state="disabled")

    def _save_current_api(self):
        # 【修改】获取用户输入的基础地址
        base_url = self.api_url_var.get().strip().rstrip('/')
        if not base_url.startswith("http"):
            messagebox.showerror("错误", "API 地址必须以 http:// 或 https:// 开头")
            return

        # 不再需要复杂的推导，直接用 base_url
        try:
            # 简单提取域名作为名称的一部分
            domain = base_url.split('//')[1].split('/')[0]
            new_api = {
                "name": f"自定义 ({domain})",
                "base_url": base_url
                # 其他字段由 config_mgr 动态生成，这里只存基础信息
            }
        except Exception:
            messagebox.showerror("错误", "API 地址格式不正确。")
            return

        api_list = config_mgr.get_api_list()
        api_list.append(new_api)
        config_mgr.set_api_list(api_list)
        self.api_combo['values'] = [api['name'] for api in api_list]
        self.api_combo.current(len(api_list) - 1)
        self._on_api_selected()
        config_mgr.save()

    def _delete_current_api(self):
        idx = self.api_combo.current()
        if idx == 0: return
        api_list = config_mgr.get_api_list()
        if 0 <= idx < len(api_list):
            if messagebox.askyesno("确认", f"确定要删除 API: {api_list[idx]['name']} 吗？"):
                api_list.pop(idx)
                config_mgr.set_api_list(api_list)
                self.api_combo['values'] = [api['name'] for api in api_list]
                self.api_combo.current(0)
                self._on_api_selected()
                config_mgr.save()

    # --- 登录与保存逻辑 ---
    def _start_login_thread(self):
        # 1. 获取并保存 Java 路径选择
        if not self.is_relogin or self.force_show_settings:
            # 从Combobox的当前选中项获取真实路径，因为显示值可能带后缀
            current_idx = self.java_combo.current()

            if current_idx >= 0 and hasattr(self, 'java_combo_real_values'):
                real_java = self.java_combo_real_values[current_idx]
            else:
                # 用户手动输入的路径
                real_java = self.java_path_var.get()

            # 允许为空，为空则在启动时自动选择
            if real_java and not os.path.exists(real_java):
                messagebox.showerror("错误", "所选的 Java 路径不存在，请检查。")
                return
            config_mgr.set_real_java_path(real_java)
            config_mgr.set_enable_embedded_java(self.enable_embedded_var.get())

        # 2. 获取并保存伪装版本号
        spoof_ver = self.spoof_version_var.get().strip()
        if spoof_ver:
            config_mgr.set_spoof_version(spoof_ver)
        else:
            # 如果用户清空了，恢复默认
            config_mgr.set_spoof_version(constants.DEFAULT_SPOOF_VERSION)

        # 3. 如果只是强制设置且不是重新登录，保存配置后直接退出
        if self.force_show_settings and not self.is_relogin:
            try:
                config_mgr.save()
                self.setup_success = True
                self.window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"保存配置失败: {e}")
            return

        # 4. 执行登录验证
        email = self.email_entry.get()
        pwd = self.pwd_entry.get()
        if not email or not pwd:
            messagebox.showerror("错误", "请输入账号和密码。")
            return

        current_api = config_mgr.get_current_api_config()
        base_url = current_api.get("base_url")
        if not base_url:
            messagebox.showerror("错误", "无效的 API 配置：缺少基础地址。")
            return

        full_auth_url = f"{base_url}/authserver/authenticate"

        self._set_ui_state("disabled")
        self.login_btn.config(text="正在登录...")

        threading.Thread(target=self._login_task, args=(email, pwd, full_auth_url), daemon=True).start()

    def _login_task(self, email, pwd, auth_url):
        try:
            data = authAPI.authenticate(auth_url, email, pwd)
            self.window.after(0, lambda: self._on_login_success(data))
        except Exception as e:
            self.window.after(0, lambda: self._on_login_error(e))

    def _on_login_success(self, data):
        try:
            # 保存认证数据
            config_mgr.set_auth_data({
                "accessToken": data["accessToken"],
                "clientToken": data["clientToken"],
                "uuid": data["selectedProfile"]["id"],
                "name": data["selectedProfile"]["name"]
            })
            # 统一保存所有配置（Java路径、伪装版本、认证数据）
            config_mgr.save()
            self.setup_success = True
            self.window.destroy()
        except Exception as e:
            self._on_login_error(f"保存配置失败: {e}")

    def _on_login_error(self, e):
        self._set_ui_state("normal")
        btn_text = "保存设置" if (self.force_show_settings and not self.is_relogin) else "登录并保存"
        self.login_btn.config(text=btn_text)

        err_msg = str(e)
        if isinstance(e, requests.exceptions.HTTPError):
            try:
                err_msg = e.response.json().get("errorMessage", err_msg)
            except:
                pass
        messagebox.showerror("登录失败", f"验证失败:\n{err_msg}")

    def _set_ui_state(self, state):
        self.email_entry.config(state=state)
        self.pwd_entry.config(state=state)
        self.api_combo.config(state=state)
        self.new_api_btn.config(state=state)
        # Java选择和高级设置在登录中也禁用，防止状态不一致
        self.java_combo.config(state=state)

    def _center_window(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        # 确保高度不超过屏幕
        screen_height = self.window.winfo_screenheight()
        if height > screen_height * 0.9:
            height = int(screen_height * 0.9)
            self.window.geometry(f'{width}x{height}')

        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def run(self):
        self.window.mainloop()
        return self.setup_success


def show_wizard(is_relogin=False, force_show_settings=False):
    wizard = LoginWizard(is_relogin, force_show_settings)
    return wizard.run()