# src/guiWizard.py
import sys
import os
import platform
import threading
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import requests

from src import constants, authAPI, javaScanner
from src.configMGR import config_mgr

# ================= 1. 样式与常量定义 =================
SYSTEM = platform.system()
FONT_FAMILY = "Microsoft YaHei UI" if SYSTEM == "Windows" else "PingFang SC"
if SYSTEM == "Linux": FONT_FAMILY = "DejaVu Sans"

# 暗色主题色板
COLOR_BG = "#1E1E1E"  # 窗体背景
COLOR_PANEL = "#252526"  # 卡片背景
COLOR_BORDER = "#3E3E42"  # 边框
COLOR_TEXT = "#CCCCCC"  # 主要文字
COLOR_TEXT_DIM = "#858585"  # 次要文字
COLOR_ACCENT = "#007ACC"  # 强调色(蓝)
COLOR_ACCENT_HOVER = "#0098FF"
COLOR_INPUT_BG = "#3C3C3C"  # 输入框背景
COLOR_SUCCESS = "#4EC9B0"  # 成功绿


class LoginWizard:
    def __init__(self, force_show_settings=False):
        self.force_show_settings = force_show_settings
        self.setup_success = False

        # --- 运行时状态 ---
        # 当前完整的认证响应数据（包含所有 availableProfiles）
        # 用于在下拉框切换角色时重新查找 UUID
        self.current_auth_response = None

        # 当前选中的 Auth Data (最终要保存的数据)
        self.current_auth_data = None

        # 账号映射表 (用于已保存账号的快速查找)
        self.saved_accounts_map = {}

        self.window = tk.Tk()
        self._init_styles()
        self._setup_window()
        self._build_layout()

        # 初始化数据
        self._refresh_account_list()

    def _init_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # 全局
        style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=(FONT_FAMILY, 9), borderwidth=0)

        # 容器
        style.configure("Bg.TFrame", background=COLOR_BG)
        style.configure("Panel.TFrame", background=COLOR_PANEL)

        # 卡片
        style.configure("Card.TLabelframe", background=COLOR_PANEL, bordercolor=COLOR_BORDER, relief="solid",
                        borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=COLOR_PANEL, foreground=COLOR_ACCENT,
                        font=(FONT_FAMILY, 10, "bold"))

        # 输入框
        style.configure("TEntry", fieldbackground=COLOR_INPUT_BG, foreground="white", bordercolor=COLOR_BORDER,
                        padding=5)
        style.map("TEntry", bordercolor=[("focus", COLOR_ACCENT)])

        # 下拉框
        style.configure("TCombobox", fieldbackground=COLOR_INPUT_BG, background=COLOR_PANEL, foreground="white",
                        arrowcolor=COLOR_TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", COLOR_INPUT_BG)],
                  selectbackground=[("readonly", COLOR_ACCENT)])

        # 按钮 (Primary)
        style.configure("Primary.TButton", background=COLOR_ACCENT, foreground="white", borderwidth=0,
                        font=("Arial", 9, "bold"), padding=6)
        style.map("Primary.TButton", background=[('active', COLOR_ACCENT_HOVER), ('disabled', '#333333')],
                  foreground=[('disabled', '#888888')])

        # 按钮 (Secondary)
        style.configure("Secondary.TButton", background="#3E3E42", foreground="white", borderwidth=0, padding=4)
        style.map("Secondary.TButton", background=[('active', '#505050')])

        # Checkbox
        style.configure("Dark.TCheckbutton", background=COLOR_BG, foreground=COLOR_TEXT_DIM)
        style.map("Dark.TCheckbutton", background=[('active', COLOR_BG)])

        # Labels
        style.configure("Header.TLabel", background=COLOR_BG, foreground="white", font=(FONT_FAMILY, 16, "bold"))
        style.configure("SubHeader.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_DIM)
        style.configure("CardHeader.TLabel", background=COLOR_PANEL, foreground=COLOR_ACCENT,
                        font=(FONT_FAMILY, 10, "bold"))

    def _setup_window(self):
        self.window.title(f"{constants.PROXY_NAME} 配置向导")
        self.window.config(bg=COLOR_BG)
        w, h = 540, 750
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.window.minsize(450, 600)
        # Windows 下设置图标等 (可选)

    def _build_layout(self):
        # 滚动容器
        canvas = tk.Canvas(self.window, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        self.content = ttk.Frame(canvas, style="Bg.TFrame")

        self.content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.win_id = canvas.create_window((0, 0), window=self.content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.window.bind_all("<MouseWheel>", _on_mousewheel)

        # 构建模块
        self._ui_header()
        self._ui_java_card()
        self._ui_api_card()
        self._ui_account_card()  # 核心修改区域
        self._ui_advanced_card()
        self._ui_footer()

    def _ui_header(self):
        f = ttk.Frame(self.content, style="Bg.TFrame", padding=(25, 25, 25, 5))
        f.pack(fill="x")
        title = "启动环境配置" if self.force_show_settings else "欢迎使用"
        ttk.Label(f, text=title, style="Header.TLabel").pack(anchor="w")
        ttk.Label(f, text="请配置 Java 环境与 Yggdrasil 账号。", style="SubHeader.TLabel").pack(anchor="w", pady=(5, 0))

    def _ui_java_card(self):
        card = ttk.LabelFrame(self.content, style="Card.TLabelframe", padding=15)
        card.pack(fill="x", padx=20, pady=10)
        ttk.Label(card, text="Java 运行环境", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        box = ttk.Frame(card, style="Panel.TFrame")
        box.pack(fill="x")

        self.java_path_var = tk.StringVar(value=config_mgr.get_real_java_path() or "")
        self.java_combo = ttk.Combobox(box, textvariable=self.java_path_var, style="TCombobox")
        self.java_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.java_combo.set("正在扫描系统 Java...")

        ttk.Button(box, text="浏览", style="Secondary.TButton", width=6, command=self._browse_java).pack(side="right")

        tk.Label(card, text="* 推荐使用 Java 17 或更高版本 (用于运行游戏)", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Arial", 8), anchor="w").pack(fill="x", pady=(5, 0))

        # 启动后台扫描
        javaScanner.start_scan(self._on_java_scan_finished)

    def _ui_api_card(self):
        card = ttk.LabelFrame(self.content, style="Card.TLabelframe", padding=15)
        card.pack(fill="x", padx=20, pady=10)
        ttk.Label(card, text="认证服务器 (API)", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        apis = config_mgr.get_api_list()
        names = [a['name'] for a in apis]

        self.api_combo = ttk.Combobox(card, values=names, state="readonly", style="TCombobox")
        self.api_combo.pack(fill="x", pady=(0, 5))
        self.api_combo.bind("<<ComboboxSelected>>", self._on_api_selected)

        # API URL 显示/编辑框
        self.api_url_var = tk.StringVar()
        self.api_url_entry = ttk.Entry(card, textvariable=self.api_url_var, state="readonly")
        self.api_url_entry.pack(fill="x", pady=(0, 10))

        # 按钮组
        btn_box = ttk.Frame(card, style="Panel.TFrame")
        btn_box.pack(fill="x")

        ttk.Button(btn_box, text="新建", style="Secondary.TButton", width=5, command=self._new_api).pack(side="left",
                                                                                                         padx=(0, 5))
        self.save_api_btn = ttk.Button(btn_box, text="保存", style="Secondary.TButton", width=5, command=self._save_api,
                                       state="disabled")
        self.save_api_btn.pack(side="left", padx=(0, 5))
        self.del_api_btn = ttk.Button(btn_box, text="删除", style="Secondary.TButton", width=5, command=self._del_api)
        self.del_api_btn.pack(side="right")

        # 初始化选中
        self.api_combo.current(config_mgr.get_current_api_index())
        self._on_api_selected()

    def _ui_account_card(self):
        """核心账号区域：包含登录、角色选择、UUID复制"""
        card = ttk.LabelFrame(self.content, style="Card.TLabelframe", padding=15)
        card.pack(fill="x", padx=20, pady=10)
        ttk.Label(card, text="账号与角色", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        # --- A. 账号切换 ---
        tk.Label(card, text="切换已保存账号:", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 2))

        self.saved_acc_combo = ttk.Combobox(card, state="readonly", style="TCombobox")
        self.saved_acc_combo.pack(fill="x", pady=(0, 10))
        self.saved_acc_combo.bind("<<ComboboxSelected>>", self._on_saved_acc_selected)

        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=5)

        # --- B. 登录表单 ---
        tk.Label(card, text="登录新账号 (邮箱/用户名):", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(5, 2))

        self.email_combo = ttk.Combobox(card, style="TCombobox")
        self.email_combo.pack(fill="x", pady=(0, 5))
        # 填充历史记录
        try:
            self.email_combo['values'] = config_mgr.get_history_users()
        except:
            pass

        tk.Label(card, text="密码:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 2))
        self.pwd_entry = ttk.Entry(card, show="•")
        self.pwd_entry.pack(fill="x", pady=(0, 10))

        self.verify_btn = ttk.Button(card, text="验证并获取角色", style="Primary.TButton", command=self._on_verify)
        self.verify_btn.pack(fill="x", pady=(0, 10))

        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=5)

        # --- C. 角色选择与信息 (关键修改区域) ---

        profile_box = ttk.Frame(card, style="Panel.TFrame")
        profile_box.pack(fill="x", pady=(5, 0))

        # 角色下拉框
        tk.Label(profile_box, text="选择游戏角色:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w")

        sel_row = ttk.Frame(profile_box, style="Panel.TFrame")
        sel_row.pack(fill="x", pady=(2, 0))

        # 角色列表 (ReadOnly, 但可选)
        self.profile_combo = ttk.Combobox(sel_row, state="disabled", style="TCombobox")
        self.profile_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_switched)

        # 复制 UUID 按钮
        self.btn_copy_uuid = ttk.Button(sel_row, text="复制 UUID", style="Secondary.TButton", command=self._copy_uuid,
                                        state="disabled")
        self.btn_copy_uuid.pack(side="right")

    def _ui_advanced_card(self):
        f = ttk.Frame(self.content, style="Bg.TFrame", padding=(20, 0))
        f.pack(fill="x")

        self.show_adv = tk.BooleanVar(value=False)
        self.adv_box = ttk.Frame(self.content, style="Bg.TFrame", padding=(20, 5, 20, 5))

        def toggle():
            if self.show_adv.get():
                self.adv_box.pack(fill="x")
            else:
                self.adv_box.pack_forget()

        ttk.Checkbutton(f, text="显示高级选项", variable=self.show_adv, command=toggle, style="Dark.TCheckbutton").pack(
            anchor="w")

        self.spoof_var = tk.StringVar(value=config_mgr.get_spoof_version())
        tk.Label(self.adv_box, text="伪装 Java 版本 (Spoof Version):", bg=COLOR_BG, fg=COLOR_TEXT).pack(anchor="w")
        ttk.Entry(self.adv_box, textvariable=self.spoof_var).pack(fill="x")
        tk.Label(self.adv_box, text="* 留空则默认。用于绕过启动器对 Java 版本号的正则检查。", bg=COLOR_BG,
                 fg=COLOR_TEXT_DIM, font=("Arial", 8)).pack(anchor="w")

    def _ui_footer(self):
        f = ttk.Frame(self.content, style="Bg.TFrame", padding=20)
        f.pack(fill="x", side="bottom")

        txt = "保存设置" if self.force_show_settings else "启动游戏"
        self.launch_btn = ttk.Button(f, text=txt, style="Primary.TButton", command=self._on_launch)
        self.launch_btn.pack(fill="x", ipady=8)

    # ================= 2. 逻辑控制 =================

    # --- Java 扫描 ---
    def _on_java_scan_finished(self, paths):
        # 合并当前配置中的路径，防止它不在扫描结果里
        curr = config_mgr.get_real_java_path()
        if curr and curr not in paths and os.path.exists(curr):
            paths.append(curr)

        paths = sorted(list(set(paths)))
        self.window.after(0, lambda: self._upd_java_list(paths))

    def _upd_java_list(self, paths):
        if not self.window.winfo_exists(): return
        self.java_combo['values'] = paths

        curr = self.java_path_var.get()
        if curr and curr in paths:
            self.java_combo.current(paths.index(curr))
        elif paths:
            self.java_combo.current(0)  # 默认选第一个
        else:
            self.java_combo.set("未找到有效 Java，请手动浏览")

    def _browse_java(self):
        ft = [("Java Executable", "java.exe;javaw.exe")] if platform.system() == "Windows" else []
        ft.append(("All Files", "*"))
        fn = filedialog.askopenfilename(filetypes=ft)
        if fn:
            self.java_path_var.set(fn)
            self.java_combo.set(fn)

    # --- API 管理 ---
    def _on_api_selected(self, e=None):
        idx = self.api_combo.current()
        apis = config_mgr.get_api_list()

        if 0 <= idx < len(apis):
            self.api_url_var.set(apis[idx]["base_url"])
            self.api_url_entry.config(state="readonly")
            self.save_api_btn.config(state="disabled")
            # 不允许删除默认项 (假设第一个是默认)
            self.del_api_btn.config(state="disabled" if idx == 0 else "normal")

        config_mgr.set_current_api_index(idx)

    def _new_api(self):
        self.api_combo.set("自定义 API")
        self.api_url_var.set("")
        self.api_url_entry.config(state="normal")
        self.api_url_entry.focus_set()
        self.save_api_btn.config(state="normal")
        self.del_api_btn.config(state="disabled")

    def _save_api(self):
        url = self.api_url_var.get().strip().rstrip('/')
        if not url.startswith("http"):
            return messagebox.showerror("错误", "API URL 必须以 http 或 https 开头")

        try:
            # 简单生成一个名字
            domain = url.split('//')[1].split('/')[0]
            apis = config_mgr.get_api_list()

            new_entry = {"name": f"自定义 ({domain})", "base_url": url}
            apis.append(new_entry)

            config_mgr.set_api_list(apis)

            # 刷新 UI
            self.api_combo['values'] = [x['name'] for x in apis]
            self.api_combo.current(len(apis) - 1)
            self._on_api_selected()
            config_mgr.save()

        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _del_api(self):
        idx = self.api_combo.current()
        if idx == 0: return  # 保护默认

        if messagebox.askyesno("确认删除", "确定要删除该 API 配置吗？"):
            apis = config_mgr.get_api_list()
            if 0 <= idx < len(apis):
                apis.pop(idx)
                config_mgr.set_api_list(apis)

                self.api_combo['values'] = [x['name'] for x in apis]
                self.api_combo.current(0)
                self._on_api_selected()
                config_mgr.save()

    # --- 账号核心逻辑 ---

    def _refresh_account_list(self):
        """加载 config 中的账号到下拉框"""
        accounts = config_mgr.get_all_accounts()
        self.saved_accounts_map = {}
        display_names = []

        default_uuid = config_mgr._config_data.get("default_account_uuid")
        sel_index = 0

        for acc in accounts:
            name = acc.get("name", "Unknown")
            uuid = acc.get("uuid", "???")
            # 格式: Name (UUID前8位)
            label = f"{name} ({uuid[:8]}...)"

            self.saved_accounts_map[label] = acc
            display_names.append(label)

            if uuid == default_uuid:
                sel_index = len(display_names) - 1

        self.saved_acc_combo['values'] = display_names

        if display_names:
            self.saved_acc_combo.current(sel_index)
            self._on_saved_acc_selected()  # 触发联动
        else:
            self.saved_acc_combo.set("无保存账号")

    def _on_saved_acc_selected(self, event=None):
        """当用户在顶部选择了已保存账号"""
        label = self.saved_acc_combo.get()
        auth_data = self.saved_accounts_map.get(label)

        if auth_data:
            self.current_auth_data = auth_data

            # 对于已保存账号，我们通常只有当前绑定的那个 profile 信息
            # 所以角色下拉框只显示当前这一个
            self.current_auth_response = None  # 清空 verify 缓存

            profile_name = auth_data.get("name", "Unknown")
            self.profile_combo.config(state="normal")
            self.profile_combo['values'] = [profile_name]
            self.profile_combo.current(0)
            self.profile_combo.config(state="readonly")

            self.btn_copy_uuid.config(state="normal")

            # 填充邮箱
            if "user_email" in auth_data:
                self.email_combo.set(auth_data["user_email"])

    def _copy_uuid(self):
        if self.current_auth_data:
            uuid = self.current_auth_data.get("uuid", "")
            self.window.clipboard_clear()
            self.window.clipboard_append(uuid)
            # 临时改变按钮文字提示成功
            orig_text = self.btn_copy_uuid['text']
            self.btn_copy_uuid.config(text="已复制!")
            self.window.after(1000, lambda: self.btn_copy_uuid.config(text=orig_text))

    def _on_verify(self):
        """点击验证按钮"""
        email = self.email_combo.get().strip()
        pwd = self.pwd_entry.get().strip()

        if not email or not pwd:
            return messagebox.showwarning("提示", "请输入账号和密码")

        api_cfg = config_mgr.get_current_api_config()
        if not api_cfg.get("base_url"):
            return messagebox.showerror("错误", "当前 API 配置无效")

        self.verify_btn.config(state="disabled", text="正在连接认证服务器...")

        # 异步线程认证
        auth_url = f"{api_cfg['base_url']}/authserver/authenticate"
        t = threading.Thread(target=self._do_verify_thread, args=(auth_url, email, pwd), daemon=True)
        t.start()

    def _do_verify_thread(self, url, email, pwd):
        try:
            # 调用 authAPI
            resp_data = authAPI.authenticate(url, email, pwd)
            self.window.after(0, lambda: self._on_verify_success(resp_data, email))
        except Exception as e:
            self.window.after(0, lambda: self._on_verify_fail(e))

    def _on_verify_success(self, data, email):
        self.verify_btn.config(state="normal", text="验证成功")

        # 1. 缓存完整响应 (包含所有 availableProfiles)
        self.current_auth_response = data
        self.current_email_cache = email

        # 2. 提取所有角色
        available_profiles = data.get("availableProfiles", [])
        selected_profile = data.get("selectedProfile")

        if not available_profiles:
            # 极端情况：没有角色
            if selected_profile:
                available_profiles = [selected_profile]
            else:
                return messagebox.showerror("失败", "该账号下没有任何 Minecraft 角色")

        # 3. 填充角色下拉框 (这里就是你要的“动手脚”)
        profile_names = [p['name'] for p in available_profiles]
        self.profile_combo.config(state="normal")
        self.profile_combo['values'] = profile_names

        # 4. 默认选中
        default_idx = 0
        if selected_profile:
            # 尝试找到 selectedProfile 在 availableProfiles 中的位置
            for i, p in enumerate(available_profiles):
                if p['id'] == selected_profile['id']:
                    default_idx = i
                    break

        self.profile_combo.current(default_idx)
        self.profile_combo.config(state="readonly")  # 只读但可选

        # 5. 触发选中逻辑 (生成 current_auth_data 并自动保存默认选中的那个)
        self._on_profile_switched()

        # 6. 清空密码，保存历史邮箱
        self.pwd_entry.delete(0, tk.END)
        config_mgr.add_history_user(email)

        # 7. 刷新顶部“已保存账号”列表
        # (因为 _on_profile_switched 会调用 add_or_update_account)
        self._refresh_account_list()

        # 自动定位到刚刚添加的这个账号
        if self.current_auth_data:
            target_label = f"{self.current_auth_data['name']} ({self.current_auth_data['uuid'][:8]}...)"
            if target_label in self.saved_acc_combo['values']:
                self.saved_acc_combo.set(target_label)

        self.btn_copy_uuid.config(state="normal")

    def _on_verify_fail(self, error):
        self.verify_btn.config(state="normal", text="验证并获取角色")
        msg = str(error)
        # 尝试提取 json 错误信息
        if isinstance(error, requests.exceptions.HTTPError):
            try:
                msg = error.response.json().get("errorMessage", msg)
            except:
                pass
        messagebox.showerror("认证失败", msg)

    def _on_profile_switched(self, event=None):
        """当用户在角色下拉框切换角色时 (或者登录成功自动调用)"""
        # 如果是“已保存账号”模式，response 是空的，下拉框只有一项，不需要动态查找
        if not self.current_auth_response:
            return

        # 获取当前选中的名字
        sel_name = self.profile_combo.get()
        if not sel_name: return

        # 在 response 中查找对应的 profile 数据
        target_profile = None
        for p in self.current_auth_response.get("availableProfiles", []):
            if p['name'] == sel_name:
                target_profile = p
                break

        if target_profile:
            # 构造要保存的数据
            self.current_auth_data = {
                "uuid": target_profile["id"],
                "name": target_profile["name"],
                "accessToken": self.current_auth_response["accessToken"],
                "clientToken": self.current_auth_response.get("clientToken"),
                "user_email": getattr(self, 'current_email_cache', "")
            }

            # 立即保存到配置，这样点“启动”时就是这个角色
            config_mgr.add_or_update_account(self.current_auth_data)

            # 更新按钮状态
            self.btn_copy_uuid.config(state="normal")

    def _on_launch(self):
        # 1. 验证 Java
        path = self.java_path_var.get()
        if not path:
            return messagebox.showerror("错误", "请选择有效的 Java 环境")
        config_mgr.set_real_java_path(path)

        # 2. 验证伪装版本
        sp = self.spoof_var.get().strip()
        config_mgr.set_spoof_version(sp if sp else constants.DEFAULT_SPOOF_VERSION)

        # 3. 验证账号
        if not self.current_auth_data:
            return messagebox.showerror("错误", "请先选择一个账号或登录")

        # 确保当前选中的账号被设为默认
        config_mgr.set_default_account(self.current_auth_data["uuid"])

        # 4. 保存并退出
        config_mgr.save()
        self.setup_success = True
        self.window.destroy()

    def run(self):
        self.window.mainloop()
        return self.setup_success


def show_wizard(is_relogin=False, force_show_settings=False):
    app = LoginWizard(force_show_settings)
    return app.run()