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
COLOR_BG = "#1E1E1E"
COLOR_PANEL = "#252526"
COLOR_BORDER = "#3E3E42"
COLOR_TEXT = "#CCCCCC"
COLOR_TEXT_DIM = "#858585"
COLOR_ACCENT = "#007ACC"
COLOR_ACCENT_HOVER = "#0098FF"
COLOR_INPUT_BG = "#3C3C3C"
COLOR_SUCCESS = "#4EC9B0"
COLOR_DANGER = "#F44336"  # 删除按钮红色


class LoginWizard:
    def __init__(self, force_show_settings=False):
        # force_show_settings 仅影响是否默认展开高级选项
        self.show_advanced_default = force_show_settings
        self.setup_success = False

        self.current_auth_data = None
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

        style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=(FONT_FAMILY, 9), borderwidth=0)
        style.configure("Bg.TFrame", background=COLOR_BG)
        style.configure("Panel.TFrame", background=COLOR_PANEL)
        style.configure("Card.TLabelframe", background=COLOR_PANEL, bordercolor=COLOR_BORDER, relief="solid",
                        borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=COLOR_PANEL, foreground=COLOR_ACCENT,
                        font=(FONT_FAMILY, 10, "bold"))
        style.configure("TEntry", fieldbackground=COLOR_INPUT_BG, foreground="white", bordercolor=COLOR_BORDER,
                        padding=5)
        style.map("TEntry", bordercolor=[("focus", COLOR_ACCENT)])
        style.configure("TCombobox", fieldbackground=COLOR_INPUT_BG, background=COLOR_PANEL, foreground="white",
                        arrowcolor=COLOR_TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", COLOR_INPUT_BG)],
                  selectbackground=[("readonly", COLOR_ACCENT)])

        style.configure("Primary.TButton", background=COLOR_ACCENT, foreground="white", borderwidth=0,
                        font=("Arial", 9, "bold"), padding=6)
        style.map("Primary.TButton", background=[('active', COLOR_ACCENT_HOVER), ('disabled', '#333333')],
                  foreground=[('disabled', '#888888')])

        style.configure("Secondary.TButton", background="#3E3E42", foreground="white", borderwidth=0, padding=4)
        style.map("Secondary.TButton", background=[('active', '#505050')])

        # 红色删除按钮
        style.configure("Danger.TButton", background="#8B0000", foreground="white", borderwidth=0, padding=4)
        style.map("Danger.TButton", background=[('active', COLOR_DANGER)])

        style.configure("Dark.TCheckbutton", background=COLOR_BG, foreground=COLOR_TEXT_DIM)
        style.map("Dark.TCheckbutton", background=[('active', COLOR_BG)])
        style.configure("Header.TLabel", background=COLOR_BG, foreground="white", font=(FONT_FAMILY, 16, "bold"))
        style.configure("SubHeader.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_DIM)
        style.configure("CardHeader.TLabel", background=COLOR_PANEL, foreground=COLOR_ACCENT,
                        font=(FONT_FAMILY, 10, "bold"))

    def _setup_window(self):
        self.window.title(f"{constants.PROXY_NAME} 配置向导")
        self.window.config(bg=COLOR_BG)
        w, h = 540, 700
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.window.minsize(450, 600)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.setup_success = False
        self.window.destroy()

    def _build_layout(self):
        canvas = tk.Canvas(self.window, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        self.content = ttk.Frame(canvas, style="Bg.TFrame")

        self.content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.win_id = canvas.create_window((0, 0), window=self.content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.window.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._ui_header()
        self._ui_java_card()
        self._ui_api_card()
        self._ui_account_card()
        self._ui_advanced_card()
        self._ui_footer()

    def _ui_header(self):
        f = ttk.Frame(self.content, style="Bg.TFrame", padding=(25, 25, 25, 5))
        f.pack(fill="x")
        ttk.Label(f, text="启动环境配置", style="Header.TLabel").pack(anchor="w")
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
        self.java_combo.set("扫描中...")
        ttk.Button(box, text="浏览", style="Secondary.TButton", width=6, command=self._browse_java).pack(side="right")
        tk.Label(card, text="* 推荐使用 Java 17 或更高版本。", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Arial", 8),
                 anchor="w").pack(fill="x", pady=(5, 0))
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

        self.api_url_var = tk.StringVar()
        self.api_url_entry = ttk.Entry(card, textvariable=self.api_url_var, state="readonly")
        self.api_url_entry.pack(fill="x", pady=(0, 10))

        btn_box = ttk.Frame(card, style="Panel.TFrame")
        btn_box.pack(fill="x")
        ttk.Button(btn_box, text="新建", style="Secondary.TButton", width=5, command=self._new_api).pack(side="left",
                                                                                                         padx=(0, 5))
        self.save_api_btn = ttk.Button(btn_box, text="保存", style="Secondary.TButton", width=5, command=self._save_api,
                                       state="disabled")
        self.save_api_btn.pack(side="left", padx=(0, 5))
        self.del_api_btn = ttk.Button(btn_box, text="删除", style="Secondary.TButton", width=5, command=self._del_api)
        self.del_api_btn.pack(side="right")

        self.api_combo.current(config_mgr.get_current_api_index())
        self._on_api_selected()

    def _ui_account_card(self):
        """
        合并后的账号卡片
        上部：账号选择 + 删除 + 复制UUID
        中部：分割线
        下部：登录新账号
        """
        card = ttk.LabelFrame(self.content, style="Card.TLabelframe", padding=15)
        card.pack(fill="x", padx=20, pady=10)
        ttk.Label(card, text="账号与角色", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        # --- A. 账号选择区 (合并了原来的 saved 和 profile) ---
        tk.Label(card, text="选择要使用的角色:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 2))

        sel_box = ttk.Frame(card, style="Panel.TFrame")
        sel_box.pack(fill="x", pady=(0, 10))

        self.account_combo = ttk.Combobox(sel_box, state="readonly", style="TCombobox")
        self.account_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.account_combo.bind("<<ComboboxSelected>>", self._on_account_selected)

        # 按钮组
        self.btn_copy_uuid = ttk.Button(sel_box, text="复制 UUID", style="Secondary.TButton", command=self._copy_uuid,
                                        state="disabled")
        self.btn_copy_uuid.pack(side="left", padx=(0, 5))

        self.btn_del_acc = ttk.Button(sel_box, text="删除", style="Danger.TButton", command=self._del_account,
                                      state="disabled")
        self.btn_del_acc.pack(side="right")

        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=5)

        # --- B. 登录表单 ---
        tk.Label(card, text="登录新账号 (验证后自动添加到上方列表):", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM).pack(
            anchor="w", pady=(5, 5))

        tk.Label(card, text="邮箱 / 用户名:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 2))
        self.email_combo = ttk.Combobox(card, style="TCombobox")
        self.email_combo.pack(fill="x", pady=(0, 5))
        try:
            self.email_combo['values'] = config_mgr.get_history_users()
        except:
            pass

        tk.Label(card, text="密码:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 2))
        self.pwd_entry = ttk.Entry(card, show="•")
        self.pwd_entry.pack(fill="x", pady=(0, 10))

        self.verify_btn = ttk.Button(card, text="验证并添加", style="Primary.TButton", command=self._on_verify)
        self.verify_btn.pack(fill="x", pady=(0, 5))

    def _ui_footer(self):
        f = ttk.Frame(self.content, style="Bg.TFrame", padding=20)
        f.pack(fill="x", side="bottom")
        # 统一按钮为“启动游戏”，哪怕是配置模式，也是“保存并准备启动”
        self.launch_btn = ttk.Button(f, text="启动游戏", style="Primary.TButton", command=self._on_launch)
        self.launch_btn.pack(fill="x", ipady=8)

    # ================= 2. 逻辑控制 =================

    # --- 账号列表管理 (核心修改) ---

    def _refresh_account_list(self):
        """刷新下拉框，列出 config 中所有已保存的角色"""
        accounts = config_mgr.get_all_accounts()  # [{'uuid':..., 'name':...}, ...]
        self.saved_accounts_map = {}
        display_names = []

        # 获取当前“默认/选中”的UUID，用于回显
        # 注意：main.py 会根据 instance_map 找，找不到才找 default
        # 这里我们主要回显 default，或者用户刚刚添加的那个
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

        self.account_combo['values'] = display_names

        if display_names:
            if sel_index >= len(display_names): sel_index = 0
            self.account_combo.current(sel_index)
            self._on_account_selected()  # 触发联动
        else:
            self.account_combo.set("请先登录添加账号...")
            self.btn_copy_uuid.config(state="disabled")
            self.btn_del_acc.config(state="disabled")
            self.current_auth_data = None

    def _on_account_selected(self, event=None):
        label = self.account_combo.get()
        auth = self.saved_accounts_map.get(label)
        if auth:
            self.current_auth_data = auth
            self.btn_copy_uuid.config(state="normal")
            self.btn_del_acc.config(state="normal")
            # 自动填入邮箱到登录框（方便重新验证）
            if "user_email" in auth:
                self.email_combo.set(auth["user_email"])

    def _copy_uuid(self):
        if self.current_auth_data:
            uuid = self.current_auth_data.get("uuid", "")
            self.window.clipboard_clear()
            self.window.clipboard_append(uuid)
            orig = self.btn_copy_uuid['text']
            self.btn_copy_uuid.config(text="已复制")
            self.window.after(1000, lambda: self.btn_copy_uuid.config(text=orig))

    def _del_account(self):
        """删除当前选中的账号"""
        if not self.current_auth_data: return
        name = self.current_auth_data.get("name")
        uuid = self.current_auth_data.get("uuid")

        if messagebox.askyesno("删除账号", f"确定要删除角色 '{name}' 吗？\n该操作无法撤销。"):
            config_mgr.remove_account(uuid)
            self._refresh_account_list()

    # --- 登录验证 (修改后支持一次添加多个角色) ---

    def _on_verify(self):
        email = self.email_combo.get().strip()
        pwd = self.pwd_entry.get().strip()
        if not email or not pwd: return messagebox.showwarning("提示", "请输入账号密码")

        api = config_mgr.get_current_api_config()
        if not api.get("base_url"): return messagebox.showerror("错误", "API 无效")

        self.verify_btn.config(state="disabled", text="验证中...")
        threading.Thread(target=self._do_verify, args=(f"{api['base_url']}/authserver/authenticate", email, pwd),
                         daemon=True).start()

    def _do_verify(self, u, e, p):
        try:
            d = authAPI.authenticate(u, e, p)
            self.window.after(0, lambda: self._on_verify_success(d, e))
        except Exception as x:
            self.window.after(0, lambda: self._on_verify_fail(x))

    def _on_verify_success(self, data, email):
        self.verify_btn.config(state="normal", text="验证并添加")

        # 获取所有可用角色
        profiles = data.get("availableProfiles", [])
        selected = data.get("selectedProfile")

        if not profiles:
            if selected:
                profiles = [selected]
            else:
                return messagebox.showerror("失败", "该账号无游戏角色")

        # 将所有角色都存入 config
        # 注意：所有角色共享同一个 accessToken (Yggdrasil 机制)
        count = 0
        target_uuid = None  # 用于选中最后默认的那个

        for p in profiles:
            auth_data = {
                "uuid": p["id"],
                "name": p["name"],
                "accessToken": data["accessToken"],
                "clientToken": data.get("clientToken"),
                "user_email": email
            }
            config_mgr.add_or_update_account(auth_data)
            count += 1
            # 优先选中 selectedProfile，否则选中列表里最后一个
            if selected and p["id"] == selected["id"]:
                target_uuid = p["id"]
            elif not target_uuid:
                target_uuid = p["id"]

        # 保存历史并刷新 UI
        config_mgr.add_history_user(email)
        self.pwd_entry.delete(0, tk.END)

        # 刷新下拉框
        self._refresh_account_list()

        # 自动选中刚添加的
        if target_uuid:
            # 设为默认，这样 _refresh_account_list 会自动选中它
            config_mgr._config_data["default_account_uuid"] = target_uuid
            self._refresh_account_list()

        messagebox.showinfo("成功", f"验证成功！已添加 {count} 个角色到列表。")

    def _on_verify_fail(self, e):
        self.verify_btn.config(state="normal", text="验证并添加")
        msg = str(e)
        if isinstance(e, requests.exceptions.HTTPError):
            try:
                msg = e.response.json().get("errorMessage", msg)
            except:
                pass
        messagebox.showerror("验证失败", msg)

    # --- 其他辅助逻辑 (Java/API) ---
    # (保持原样，略微精简代码以适配上下文)
    def _on_java_scan_finished(self, paths):
        curr = config_mgr.get_real_java_path()
        if curr and curr not in paths and os.path.exists(curr): paths.append(curr)
        paths = sorted(list(set(paths)))
        self.window.after(0, lambda: self._upd_j(paths))

    def _upd_j(self, p):
        if self.window.winfo_exists():
            self.java_combo['values'] = p
            if self.java_path_var.get() in p:
                self.java_combo.current(p.index(self.java_path_var.get()))
            elif p:
                self.java_combo.current(0)

    def _browse_java(self):
        fn = filedialog.askopenfilename()
        if fn:
            self.java_path_var.set(fn)
            self.java_combo.set(fn)

    def _on_api_selected(self, e=None):
        idx = self.api_combo.current()
        apis = config_mgr.get_api_list()
        if 0 <= idx < len(apis):
            self.api_url_var.set(apis[idx]["base_url"])
            self.api_url_entry.config(state="readonly")
            self.save_api_btn.config(state="disabled")
            self.del_api_btn.config(state="disabled" if idx == 0 else "normal")
        config_mgr.set_current_api_index(idx)

    def _new_api(self):
        self.api_combo.set("New API");
        self.api_url_entry.config(state="normal");
        self.api_url_entry.focus_set()
        self.save_api_btn.config(state="normal");
        self.del_api_btn.config(state="disabled")

    def _save_api(self):
        u = self.api_url_var.get().strip().rstrip('/')
        if not u.startswith("http"): return messagebox.showerror("错误", "URL无效")
        try:
            l = config_mgr.get_api_list()
            l.append({"name": f"自定义 ({u.split('//')[1].split('/')[0]})", "base_url": u})
            config_mgr.set_api_list(l)
            self.api_combo['values'] = [x['name'] for x in l]
            self.api_combo.current(len(l) - 1)
            self._on_api_selected()
            config_mgr.save()
        except:
            messagebox.showerror("错误", "保存失败")

    def _del_api(self):
        idx = self.api_combo.current()
        if idx == 0: return
        if messagebox.askyesno("删除", "确定删除？"):
            l = config_mgr.get_api_list()
            l.pop(idx)
            config_mgr.set_api_list(l)
            self.api_combo['values'] = [x['name'] for x in l]
            self.api_combo.current(0);
            self._on_api_selected();
            config_mgr.save()

    # --- 启动 ---

    def _on_launch(self):
        # 1. 验证 Java
        path = self.java_path_var.get()
        if not path: return messagebox.showerror("错误", "请选择 Java")
        config_mgr.set_real_java_path(path)

        if not self.current_auth_data:
            return messagebox.showerror("错误", "请选择一个账号")

        # 2. 【核心修复】执行角色绑定 (Profile Binding)
        # 我们手里的 Token 可能是“无主”的，必须通过 Refresh + SelectedProfile 把它变成“有主”的
        # 只有“有主”的 Token 才能通过 validate

        api = config_mgr.get_current_api_config()
        base_url = api.get("base_url", "").rstrip('/')

        # 构造 Profile 对象
        target_profile = {
            "id": self.current_auth_data["uuid"],
            "name": self.current_auth_data["name"]
        }

        try:
            # 尝试绑定 (Refresh with Profile)
            # 注意：即便 Token 已经是绑定的，再次绑定通常也是安全的（刷新有效期）
            print(f"Binding token to profile: {target_profile['name']}")

            new_data = authAPI.refresh(
                f"{base_url}/authserver/refresh",
                self.current_auth_data["accessToken"],
                self.current_auth_data.get("clientToken"),
                selected_profile=target_profile
            )

            # 更新内存中的数据为“已绑定”的新 Token
            self.current_auth_data["accessToken"] = new_data["accessToken"]
            # clientToken 通常不变，但以防万一
            if "clientToken" in new_data:
                self.current_auth_data["clientToken"] = new_data["clientToken"]

            # 保存到 Config
            config_mgr.add_or_update_account(self.current_auth_data)

        except Exception as e:
            # 如果绑定失败，可能是网络问题，也可能是 Token 彻底过期
            # 这里我们提示错误，不强行关闭，让用户决定是否重试登录
            return messagebox.showerror("绑定角色失败", f"无法绑定角色，请尝试重新登录。\n{e}")

        # 3. 设置默认并退出
        config_mgr._config_data["default_account_uuid"] = self.current_auth_data["uuid"]
        config_mgr.save()

        self.setup_success = True
        self.window.destroy()

    def run(self):
        self.window.mainloop()
        return self.setup_success


def show_wizard(force_show_settings=False):
    app = LoginWizard(force_show_settings)
    return app.run()