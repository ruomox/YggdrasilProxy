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

# ================= 暗色主题配置 =================
SYSTEM = platform.system()
FONT_FAMILY = "Microsoft YaHei UI" if SYSTEM == "Windows" else "PingFang SC"
if SYSTEM == "Linux": FONT_FAMILY = "DejaVu Sans"

COLOR_BG = "#1E1E1E";
COLOR_PANEL = "#252526";
COLOR_BORDER = "#3E3E42"
COLOR_TEXT = "#CCCCCC";
COLOR_TEXT_DIM = "#858585"
COLOR_ACCENT = "#007ACC";
COLOR_ACCENT_HOVER = "#0098FF"
COLOR_INPUT_BG = "#3C3C3C";
COLOR_ERROR = "#F48771"


class LoginWizard:
    def __init__(self, force_show_settings=False):
        # 仅保留 force_show_settings，用于区分是“强制设置”还是“启动前检查”
        self.force_show_settings = force_show_settings
        self.setup_success = False
        self.temp_auth_data = None
        self.temp_available_profiles = []

        self.window = tk.Tk()
        self._init_styles()
        self._setup_window()
        self._build_layout()

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
        style.configure("Dark.TCheckbutton", background=COLOR_BG, foreground=COLOR_TEXT_DIM)
        style.map("Dark.TCheckbutton", background=[('active', COLOR_BG)])
        style.configure("Header.TLabel", background=COLOR_BG, foreground="white", font=(FONT_FAMILY, 16, "bold"))
        style.configure("SubHeader.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_DIM)
        style.configure("CardHeader.TLabel", background=COLOR_PANEL, foreground=COLOR_ACCENT,
                        font=(FONT_FAMILY, 10, "bold"))

    def _setup_window(self):
        self.window.title(f"{constants.PROXY_NAME} 配置")
        self.window.config(bg=COLOR_BG)
        w, h = 520, 750
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.window.minsize(450, 600)
        self.window.protocol("WM_DELETE_WINDOW", sys.exit)

    def _build_layout(self):
        canvas = tk.Canvas(self.window, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        self.content = ttk.Frame(canvas, style="Bg.TFrame")

        self.content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.win_id = canvas.create_window((0, 0), window=self.content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.window.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self._ui_header()
        self.java_path_var = tk.StringVar(value=config_mgr.get_real_java_path() or "")
        self._ui_java_card()
        self._ui_api_card()
        self._ui_login_card()
        self._ui_advanced_card()
        self._ui_footer()

    def _ui_header(self):
        f = ttk.Frame(self.content, style="Bg.TFrame", padding=(25, 30, 25, 10))
        f.pack(fill="x")
        title_txt = "环境设置" if self.force_show_settings else "欢迎使用"
        ttk.Label(f, text=title_txt, style="Header.TLabel").pack(anchor="w")
        ttk.Label(f, text="配置 Java 环境与 Yggdrasil 账号。", style="SubHeader.TLabel").pack(anchor="w", pady=(5, 0))

    def _ui_java_card(self):
        card = ttk.LabelFrame(self.content, style="Card.TLabelframe", padding=15)
        card.pack(fill="x", padx=20, pady=10)
        ttk.Label(card, text="Java 运行环境", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        box = ttk.Frame(card, style="Panel.TFrame")
        box.pack(fill="x")
        self.java_combo = ttk.Combobox(box, textvariable=self.java_path_var, style="TCombobox")
        self.java_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.java_combo.set("扫描中...")
        ttk.Button(box, text="浏览", style="Secondary.TButton", width=6, command=self._browse_java).pack(side="right")

        tk.Label(card, text="* 必填，请选择本机安装的 Java 17 或更高版本。", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Arial", 8), anchor="w").pack(fill="x", pady=(5, 0))
        javaScanner.start_scan(self._on_java_scan_finished)

    def _ui_api_card(self):
        card = ttk.LabelFrame(self.content, style="Card.TLabelframe", padding=15)
        card.pack(fill="x", padx=20, pady=10)

        ttk.Label(card, text="认证服务器 (API)", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        # API 列表
        apis = config_mgr.get_api_list()
        names = [a['name'] for a in apis]
        self.api_combo = ttk.Combobox(card, values=names, state="readonly", style="TCombobox")
        self.api_combo.current(config_mgr.get_current_api_index())
        self.api_combo.pack(fill="x", pady=(0, 8))
        self.api_combo.bind("<<ComboboxSelected>>", self._on_api_selected)

        # URL 框
        self.api_url_var = tk.StringVar()
        # 【关键修复】这里必须赋值给 self 变量，否则后面 _on_api_selected 会报错
        self.api_url_entry = ttk.Entry(card, textvariable=self.api_url_var, state="readonly")
        self.api_url_entry.pack(fill="x", pady=(0, 8))

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

        self._on_api_selected()

    def _ui_login_card(self):
        card = ttk.LabelFrame(self.content, style="Card.TLabelframe", padding=15)
        card.pack(fill="x", padx=20, pady=10)
        ttk.Label(card, text="账号验证", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        tk.Label(card, text="账号 / 邮箱:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 2))
        self.email_combo = ttk.Combobox(card, style="TCombobox")
        self.email_combo.pack(fill="x", pady=(0, 10))

        try:
            if hasattr(config_mgr, 'get_history_users'):
                history = config_mgr.get_history_users()
                if history:
                    self.email_combo['values'] = history
                    self.email_combo.current(0)
        except:
            pass
        if not self.email_combo.get():
            curr = config_mgr.get_auth_data()
            if curr and curr.get("name"): self.email_combo.set(curr["name"])

        tk.Label(card, text="密码:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 2))
        self.pwd_entry = ttk.Entry(card, show="•")
        self.pwd_entry.pack(fill="x", pady=(0, 15))

        self.verify_btn = ttk.Button(card, text="验证账号", style="Primary.TButton", command=self._on_verify)
        self.verify_btn.pack(fill="x", pady=(0, 15))

        self.profile_frame = ttk.Frame(card, style="Panel.TFrame")
        self.profile_frame.pack(fill="x")
        tk.Label(self.profile_frame, text="选择角色:", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 2))
        self.profile_combo = ttk.Combobox(self.profile_frame, state="disabled", style="TCombobox")
        self.profile_combo.set("请先验证账号")
        self.profile_combo.pack(fill="x")

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
        tk.Label(self.adv_box, text="伪装 Java 版本:", bg=COLOR_BG, fg=COLOR_TEXT).pack(anchor="w")
        ttk.Entry(self.adv_box, textvariable=self.spoof_var).pack(fill="x")
        tk.Label(self.adv_box, text="* 留空默认。用于绕过启动器版本检查。", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                 font=("Arial", 8)).pack(anchor="w")

    def _ui_footer(self):
        f = ttk.Frame(self.content, style="Bg.TFrame", padding=20)
        f.pack(fill="x", side="bottom")
        txt = "保存设置" if self.force_show_settings else "启动游戏"
        self.launch_btn = ttk.Button(f, text=txt, style="Primary.TButton", command=self._on_launch)
        self.launch_btn.pack(fill="x", ipady=8)

    # 逻辑部分
    def _on_java_scan_finished(self, paths):
        curr = config_mgr.get_real_java_path()
        if curr and curr not in paths and os.path.exists(curr): paths.append(curr)
        paths = sorted(list(set(paths)))
        self.window.after(0, lambda: self._upd_java(paths))

    def _upd_java(self, paths):
        if not self.window.winfo_exists(): return
        self.java_combo['values'] = paths
        curr = self.java_path_var.get()
        if curr and curr in paths:
            self.java_combo.current(paths.index(curr))
        elif paths:
            self.java_combo.current(0)
        else:
            self.java_combo.set("未找到 Java")

    def _browse_java(self):
        ft = [("Java", "java.exe"), ("All", "*")] if platform.system() == "Windows" else [("All", "*")]
        fn = filedialog.askopenfilename(filetypes=ft)
        if fn:
            self.java_path_var.set(fn)
            self.java_combo.set(fn)

    def _on_api_selected(self, e=None):
        idx = self.api_combo.current()
        l = config_mgr.get_api_list()
        if 0 <= idx < len(l):
            self.api_url_var.set(l[idx]["base_url"])
            self.api_url_entry.config(state="readonly")
            self.save_api_btn.config(state="disabled")
            self.del_api_btn.config(state="disabled" if idx == 0 else "normal")
        config_mgr.set_current_api_index(idx)

    def _new_api(self):
        self.api_combo.set("自定义")
        self.api_url_var.set("")
        self.api_url_entry.config(state="normal")
        self.api_url_entry.focus_set()
        self.save_api_btn.config(state="normal")
        self.del_api_btn.config(state="disabled")

    def _save_api(self):
        u = self.api_url_var.get().strip().rstrip('/')
        if not u.startswith("http"): return messagebox.showerror("错误", "API 格式错误")
        try:
            d = u.split('//')[1].split('/')[0]
            l = config_mgr.get_api_list()
            l.append({"name": f"自定义 ({d})", "base_url": u})
            config_mgr.set_api_list(l)
            self.api_combo['values'] = [x['name'] for x in l]
            self.api_combo.current(len(l) - 1)
            self._on_api_selected()
            config_mgr.save()
        except:
            messagebox.showerror("错误", "URL 无效")

    def _del_api(self):
        idx = self.api_combo.current()
        if idx == 0: return
        if messagebox.askyesno("删除", "确定删除？"):
            l = config_mgr.get_api_list()
            l.pop(idx)
            config_mgr.set_api_list(l)
            self.api_combo['values'] = [x['name'] for x in l]
            self.api_combo.current(0)
            self._on_api_selected()
            config_mgr.save()

    def _on_verify(self):
        email = self.email_combo.get().strip()
        pwd = self.pwd_entry.get().strip()
        if not email or not pwd: return messagebox.showwarning("提示", "请输入账号密码")
        cfg = config_mgr.get_current_api_config()
        if not cfg.get("base_url"): return
        self.verify_btn.config(state="disabled", text="验证中...")
        self.profile_combo.set("验证中...")
        threading.Thread(target=self._do_verify, args=(email, pwd, f"{cfg['base_url']}/authserver/authenticate"),
                         daemon=True).start()

    def _do_verify(self, e, p, u):
        try:
            d = authAPI.authenticate(u, e, p)
            self.window.after(0, lambda: self._ver_ok(d, e))
        except Exception as x:
            self.window.after(0, lambda: self._ver_fail(x))

    def _ver_ok(self, data, email):
        self.verify_btn.config(state="normal", text="✔ 验证成功")
        self.temp_auth_data = data
        self.temp_available_profiles = data.get("availableProfiles", [])
        if hasattr(config_mgr, 'add_history_user'):
            config_mgr.add_history_user(email)
            self.email_combo['values'] = config_mgr.get_history_users()

        if not self.temp_available_profiles:
            self.profile_combo.set("无角色")
            return messagebox.showerror("失败", "无游戏角色")

        names = [x["name"] for x in self.temp_available_profiles]
        self.profile_combo['values'] = names
        self.profile_combo.config(state="readonly")
        sel = data.get("selectedProfile")
        if sel:
            for i, prof in enumerate(self.temp_available_profiles):
                if prof["id"] == sel["id"]:
                    self.profile_combo.current(i)
                    break
        else:
            self.profile_combo.current(0)

    def _ver_fail(self, e):
        self.verify_btn.config(state="normal", text="验证账号")
        self.profile_combo.set("验证失败")
        msg = str(e)
        if isinstance(e, requests.exceptions.HTTPError):
            try:
                msg = e.response.json().get("errorMessage", msg)
            except:
                pass
        messagebox.showerror("验证失败", msg)

    def _on_launch(self):
        path = self.java_path_var.get()
        if not path: return messagebox.showerror("错误", "请设置 Java")
        config_mgr.set_real_java_path(path)

        sp = self.spoof_var.get().strip()
        config_mgr.set_spoof_version(sp if sp else constants.DEFAULT_SPOOF_VERSION)

        if self.force_show_settings:
            config_mgr.save()
            self.setup_success = True
            self.window.destroy()
            return

        if self.temp_auth_data:
            idx = self.profile_combo.current()
            if idx < 0: return messagebox.showerror("错误", "请选择角色")
            prof = self.temp_available_profiles[idx]
            payload = {
                "accessToken": self.temp_auth_data["accessToken"],
                "uuid": prof["id"],
                "name": prof["name"]
            }
            if self.temp_auth_data.get("clientToken"):
                payload["clientToken"] = self.temp_auth_data.get("clientToken")
            config_mgr.set_auth_data(payload)
        elif not config_mgr.get_auth_data():
            return messagebox.showerror("错误", "请先验证账号")

        try:
            config_mgr.save()
            self.setup_success = True
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def run(self):
        self.window.mainloop()
        return self.setup_success


def show_wizard(is_relogin=False, force_show_settings=False):
    # is_relogin 参数虽然保留了接口，但在内部已经不产生逻辑影响
    return LoginWizard(force_show_settings=force_show_settings).run()