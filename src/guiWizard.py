# src/guiWizard.py
import sys
import os
import threading
import tkinter
import customtkinter as ctk
from PIL import Image
from tkinter import messagebox

from src import constants, authAPI, javaScanner
from src.configMGR import config_mgr
from src.avatarMGR import AvatarManager
from src.i18n import I18n

# ================= 1. 外观配置 =================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# 配色方案
COLOR_SIDEBAR = "#2b2b2b"  # 左侧深色背景
COLOR_MAIN = "#363636"  # 右侧背景
COLOR_CARD_HOVER = "#3e3e3e"  # 列表项悬停
COLOR_CARD_SELECT = "#4a4a4a"  # 列表项选中
COLOR_ACCENT = "#E09F5E"  # 启动按钮橙色
COLOR_ACCENT_HOVER = "#D08E4C"
COLOR_TEXT_GRAY = "#AAAAAA"  # 灰色文字
COLOR_TEXT_DIM = "#777777"  # 更暗的提示文字
COLOR_BTN_GRAY = "#444444"  # 通用灰色按钮
COLOR_BTN_GRAY_HOVER = "#555555"


class AccountCard(ctk.CTkFrame):
    """左侧角色列表中的单个卡片"""

    def __init__(self, master, auth_data, is_selected, on_click, on_right_click):
        super().__init__(master, fg_color=COLOR_CARD_SELECT if is_selected else "transparent", corner_radius=6)

        self.auth_data = auth_data
        self.uuid = auth_data.get("uuid", "")
        self.name = auth_data.get("name", "Unknown")
        self.on_click = on_click

        self.grid_columnconfigure(1, weight=1)

        # ================= 头像初始化 (修复闪烁) =================
        # 1. 同步获取：尝试直接拿本地缓存或默认Steve图片
        # 这样创建时就直接显示图片，没有文字阶段
        initial_img = AvatarManager.get_local_cache_sync(self.uuid)
        ctk_img = ctk.CTkImage(light_image=initial_img, dark_image=initial_img, size=(32, 32))
        self._kept_image = ctk_img  # 防止回收

        self.avatar = ctk.CTkLabel(
            self, text="", image=ctk_img,  # 直接设置图片，text为空
            fg_color="transparent",
            width=32, height=32
        )
        self.avatar.grid(row=0, column=0, rowspan=2, padx=(10, 8), pady=8)
        # ========================================================

        # 2. 名字
        self.name_lbl = ctk.CTkLabel(
            self, text=self.name, font=("Microsoft YaHei UI", 13, "bold"), anchor="w"
        )
        self.name_lbl.grid(row=0, column=1, sticky="sw", padx=(0, 10), pady=(6, 0))

        # 3. 来源
        api_name = auth_data.get("api_name", I18n.t("account_source_default"))
        self.source_lbl = ctk.CTkLabel(
            self, text=api_name, font=("Microsoft YaHei UI", 11), text_color="gray", anchor="w"
        )
        self.source_lbl.grid(row=1, column=1, sticky="nw", padx=(0, 10), pady=(0, 6))

        # --- 事件绑定 ---
        def _left(e):
            if self.on_click: self.on_click(self.uuid)

        def _right(e):
            if on_right_click: on_right_click(e, self.uuid)

        self.bind("<Button-1>", _left)
        self.bind("<Button-3>", _right)
        self.bind("<Button-2>", _right)

        for widget in self.winfo_children():
            widget.bind("<Button-1>", _left)
            widget.bind("<Button-3>", _right)
            widget.bind("<Button-2>", _right)

            if not is_selected:
                widget.bind("<Enter>", self._on_enter)
                widget.bind("<Leave>", self._on_leave)

        if not is_selected:
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)

        # --- 启动异步更新 ---
        # 虽然已经显示了图片，但仍需后台检查是否有新皮肤
        self._start_avatar_update()

    def _on_enter(self, event):
        self.configure(fg_color=COLOR_CARD_HOVER)

    def _on_leave(self, event):
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        widget_x, widget_y = self.winfo_rootx(), self.winfo_rooty()
        width, height = self.winfo_width(), self.winfo_height()

        if widget_x <= x <= widget_x + width and widget_y <= y <= widget_y + height:
            return
        self.configure(fg_color="transparent")

    # ================== 后台检查更新 ==================

    def _start_avatar_update(self):
        api_url = None
        target_name = self.auth_data.get("api_name")

        if target_name:
            apis = config_mgr.get_api_list()
            for a in apis:
                if target_name in a["name"] or a["name"] in target_name:
                    api_url = a["base_url"]
                    break

        if not api_url:
            api_url = config_mgr.get_current_api_config()["base_url"]

        # 调用异步方法检查更新
        AvatarManager.get_avatar(self.uuid, api_url, self._on_avatar_updated)

    def _on_avatar_updated(self, pil_img):
        if not pil_img:
            return
        # 第一层保险：Card 已经不存在
        if not self.winfo_exists():
            return
        try:
            # 丢给主线程，真正更新放到 UI 线程
            self.after(0, lambda img=pil_img: self._safe_apply_avatar(img))
        except RuntimeError:
            # after 调用时窗口已经被销毁
            pass

    def _safe_apply_avatar(self, pil_img):
        # 第二层保险：after 执行时再次确认
        if not self.winfo_exists():
            return
        try:
            self._apply_avatar(pil_img)
        except RuntimeError:
            # Tk 已关闭 / Widget 已回收
            pass

    def _apply_avatar(self, pil_img):
        if not self.winfo_exists(): return

        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(32, 32))
        self._kept_image = ctk_img  # 防止回收
        self.avatar.configure(image=self._kept_image)


class ModernWizard(ctk.CTk):
    def __init__(self, force_show=False, game_dir=None):
        super().__init__()
        self.setup_success = False
        self.game_dir = game_dir  # 【新增】保存实例路径

        self.title(f"{constants.PROXY_NAME} {I18n.t('window_title')}")
        # --- 窗口居中 & 置顶 (修复) ---
        w, h = 820, 500
        self.minsize(800, 500)

        # 获取屏幕宽高
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()

        # 计算居中坐标 (X和Y都居中)
        x = int((ws - w) / 2)
        y = int((hs - h) / 2)

        self.geometry(f"{w}x{h}+{x}+{y}")

        # 【关键修复】强制将窗口置于所有窗口的最顶层 (Z轴)
        self.attributes("-topmost", True)

        # 可选：为了不影响后续切换窗口，可以在 1秒后取消强制置顶，或者就这样保留
        self.after(1000, lambda: self.attributes("-topmost", False))

        self.lift()  # 提升窗口层级
        self.focus_force()  # 强制获取焦点

        config_mgr.load()
        self.current_auth_data = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._init_sidebar()
        self._init_main_panel()

        self._refresh_account_list()
        javaScanner.start_scan(self._on_java_scan_finished)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.setup_success = False
        self.destroy()

    # 自定义弹窗
    def _show_custom_dialog(self, title, content, width=600, height=371):
        """自定义大小的弹窗"""
        top = ctk.CTkToplevel(self)
        top.title(title)
        top.geometry(f"{width}x{height}")

        top.minsize(width, height)

        # 强制置顶并模态
        top.attributes("-topmost", True)
        top.transient(self)
        top.grab_set()

        # 居中计算
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        top.geometry(f"+{x}+{y}")

        # 文本框
        textbox = ctk.CTkTextbox(top, wrap="word", font=("Consolas", 12))
        textbox.pack(fill="both", expand=True, padx=20, pady=20)
        textbox.insert("0.0", content)
        textbox.configure(state="disabled")  # 只读

        # 关闭按钮
        ctk.CTkButton(top, text=I18n.t("show_custom_dig_close_btn"), command=top.destroy).pack(pady=(0, 20))

    # ================= UI 构建 =================

    def _init_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(1, weight=1)

        # 滚轮事件绑定辅助函数 (绑定整个 Sidebar 区域)
        def _scroll_handler(event):
            self.scroll_frame._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.sidebar.bind("<MouseWheel>", _scroll_handler)

        # 标题
        title_lbl = ctk.CTkLabel(
            self.sidebar, text=I18n.t("sidebar_accounts"), font=("Microsoft YaHei UI", 16, "bold"), anchor="w"
        )
        title_lbl.grid(row=0, column=0, sticky="ew", padx=20, pady=(25, 10))
        title_lbl.bind("<MouseWheel>", _scroll_handler)  # 标题也支持滚轮

        # 列表
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            width=220,
            scrollbar_button_color=COLOR_SIDEBAR,
            scrollbar_button_hover_color=COLOR_SIDEBAR
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # 底部启动区
        self.launch_area = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.launch_area.grid(row=2, column=0, sticky="ew", padx=15, pady=(37, 20))
        self.launch_area.bind("<MouseWheel>", _scroll_handler)  # 底部区域也支持滚轮

        self.launch_btn = ctk.CTkButton(
            self.launch_area,
            text=I18n.t("btn_launch"),
            font=("Microsoft YaHei UI", 16, "bold"),
            height=45,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._on_launch
        )
        self.launch_btn.pack(fill="x")

        self.ver_lbl = ctk.CTkLabel(self.launch_area, text=I18n.t("status_ready"), font=("Arial", 10), text_color="gray")
        self.ver_lbl.pack(pady=(5, 0))

    def _init_main_panel(self):
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=COLOR_MAIN)
        self.main.grid(row=0, column=1, sticky="nsew")

        # 顶部留白 (调整此处高度以对齐左侧“账户”标题)
        # 左侧“账户”是 pady=(25, 10)，这里设为 25 左右可以 visually aligned
        ctk.CTkFrame(self.main, height=25, fg_color="transparent").pack()

        # --- 1. Java 环境板块 (UI 重构) ---
        self._create_section_container(I18n.t("sec_java"))

        java_row = ctk.CTkFrame(self.current_section, fg_color="transparent")
        java_row.pack(fill="x", pady=(5, 0))

        # 1. 下拉框 (显示精简信息)
        self.java_map = {}  # 存储 "显示名" -> "详细信息Dict" 的映射
        self.java_var = tkinter.StringVar(value=I18n.t("java_scanning"))

        self.java_combo = ctk.CTkComboBox(
            java_row, variable=self.java_var, height=32,
            command=self._on_java_change  # 绑定变更事件
        )
        self.java_combo.pack(side="left", fill="x", expand=True)

        # 间距
        ctk.CTkFrame(java_row, width=10, height=1, fg_color="transparent").pack(side="left")

        # 2. 按钮容器 (总宽 80 = 35 + 10 + 35)
        # [+] 浏览按钮
        ctk.CTkButton(
            java_row, text="+", width=35, height=32,
            fg_color=COLOR_BTN_GRAY, hover_color=COLOR_BTN_GRAY_HOVER,
            font=("Arial", 16),
            command=self._browse_java
        ).pack(side="left")

        ctk.CTkFrame(java_row, width=10, height=1, fg_color="transparent").pack(side="left")

        # [?] 详情按钮
        ctk.CTkButton(
            java_row, text="?", width=35, height=32,
            fg_color=COLOR_BTN_GRAY, hover_color=COLOR_BTN_GRAY_HOVER,
            font=("Arial", 14, "bold"),
            command=self._show_java_details
        ).pack(side="left")

        # --- 2. 认证服务器板块 ---
        self._create_section_container(I18n.t("sec_api"))

        api_row = ctk.CTkFrame(self.current_section, fg_color="transparent")
        api_row.pack(fill="x", pady=(5, 0))

        # API 下拉框
        self.api_combo = ctk.CTkComboBox(
            api_row, height=32,
            command=self._on_api_change
        )
        self.api_combo.pack(side="left", fill="x", expand=True)

        # 占位符 (间距)
        ctk.CTkFrame(api_row, width=10, height=1, fg_color="transparent").pack(side="left")

        # 按钮容器 (总宽 80)
        # + 按钮 (宽 35)
        ctk.CTkButton(
            api_row, text="+", width=35, height=32,
            fg_color=COLOR_BTN_GRAY, hover_color=COLOR_BTN_GRAY_HOVER,
            font=("Arial", 16),
            command=self._save_custom_api_from_input
        ).pack(side="left")

        # 按钮间距 (宽 10)
        ctk.CTkFrame(api_row, width=10, height=1, fg_color="transparent").pack(side="left")

        # - 按钮 (宽 35)
        ctk.CTkButton(
            api_row, text="-", width=35, height=32,
            fg_color="#8B0000", hover_color="#B00000",
            font=("Arial", 16),
            command=self._del_api
        ).pack(side="left")

        # --- 3. 登录板块 ---
        self._create_section_container(I18n.t("sec_login"))

        # 邮箱
        ctk.CTkLabel(
            self.current_section, text=I18n.t("lbl_email"),
            font=("Microsoft YaHei UI", 10), text_color=COLOR_TEXT_GRAY
        ).pack(anchor="w", pady=(3, 1))

        self.email_entry = ctk.CTkComboBox(
            self.current_section, height=32,
            values=config_mgr.get_history_users()
        )
        self.email_entry.pack(fill="x", pady=(0, 4))

        # 密码
        ctk.CTkLabel(
            self.current_section, text=I18n.t("lbl_pwd"),
            font=("Microsoft YaHei UI", 10), text_color=COLOR_TEXT_GRAY
        ).pack(anchor="w", pady=(0, 1))

        self.pwd_entry = ctk.CTkEntry(self.current_section, height=32, show="•")
        self.pwd_entry.pack(fill="x", pady=(0, 0))

        # 密码提示语
        ctk.CTkLabel(
            self.current_section, text=I18n.t("lbl_pwd_hint"),
            font=("Microsoft YaHei UI", 10), text_color=COLOR_TEXT_DIM
        ).pack(anchor="w", pady=(0, 0))

        # --- 底部验证按钮 ---
        # 放在 main 的最底部，与左侧 Launch 按钮对齐
        # 左侧 Padding 是 (15, 20)，这里我们也给类似的 Padding
        bottom_area = ctk.CTkFrame(self.main, fg_color="transparent")
        bottom_area.pack(fill="x", padx=30, pady=(0, 53), side="bottom")

        self.login_btn = ctk.CTkButton(
            bottom_area, text=I18n.t("btn_verify"), height=45,  # 高度与启动按钮一致
            font=("Microsoft YaHei UI", 14, "bold"),
            command=self._on_verify
        )
        self.login_btn.pack(fill="x")

        # 初始化数据
        self._refresh_api_ui()
        self.api_combo.bind("<Return>", lambda e: self._save_custom_api_from_input())
        self._init_language_button()

    def _init_language_button(self):
        """在右上角初始化圆形语言切换按钮 (静默模式)"""
        # 创建圆形按钮
        self.lang_btn = ctk.CTkButton(
            self.main,  # 父容器：右侧面板
            text="文",  # 显示文字，可改为图标
            width=30, height=30,
            corner_radius=15,  # 圆形
            fg_color="#555555",
            hover_color="#666666",
            font=("Microsoft YaHei UI", 12, "bold"),
            command=self._show_language_menu
        )

        # 绝对定位到右上角 (右偏移15，下偏移15)
        self.lang_btn.place(relx=1.0, x=-15, y=15, anchor="ne")

    def _show_language_menu(self):
        """显示下拉菜单"""
        menu = tkinter.Menu(self, tearoff=0)

        current_code = I18n.get_current_language_code()
        langs = I18n.get_languages()

        for code, name in langs.items():
            # 视觉反馈：当前语言前打勾
            label_text = f"✓ {name}" if code == current_code else f"   {name}"

            menu.add_command(
                label=label_text,
                command=lambda c=code: self._change_language_quietly(c)
            )

        # 在按钮正下方弹出
        x = self.lang_btn.winfo_rootx()
        y = self.lang_btn.winfo_rooty() + self.lang_btn.winfo_height() + 5
        menu.tk_popup(x, y)

    def _change_language_quietly(self, lang_code):
        """切换语言并保存，不重启，不弹窗"""
        if I18n.get_current_language_code() == lang_code:
            return

        # 仅保存配置
        config_mgr.set_language(lang_code)
        print(f"Language switched to {lang_code}. Restart required to take effect.")

    def _create_section_container(self, title):
        container = ctk.CTkFrame(self.main, fg_color="transparent")
        container.pack(fill="x", padx=30, pady=(0, 20))  # 减小板块间距

        ctk.CTkLabel(
            container, text=title,
            font=("Microsoft YaHei UI", 13, "bold"), text_color=COLOR_ACCENT
        ).pack(anchor="w")

        self.current_section = container

    # ================= 逻辑处理 =================

    def _refresh_account_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        accounts = config_mgr.get_all_accounts()
        default_uuid = config_mgr._config_data.get("default_account_uuid")

        for acc in accounts:
            is_sel = (acc["uuid"] == default_uuid)
            if is_sel: self.current_auth_data = acc
            AccountCard(
                self.scroll_frame,
                acc,
                is_sel,
                self._select_account,
                self._show_context_menu
            ).pack(fill="x", pady=2, padx=(10, 0))

        if not self.current_auth_data and accounts:
            self._select_account(accounts[0]["uuid"])

    def _select_account(self, uuid):
        config_mgr.set_default_account(uuid)
        self._refresh_account_list()

    def _show_context_menu(self, event, uuid):
        m = tkinter.Menu(self, tearoff=0)
        m.add_command(label=I18n.t("copy_uuid"), command=lambda: self._copy_uuid(uuid))
        m.add_separator()
        m.add_command(label=I18n.t("del_account"), command=lambda: self._del_account(uuid))
        m.tk_popup(event.x_root, event.y_root)

    def _copy_uuid(self, uuid):
        self.clipboard_clear()
        self.clipboard_append(uuid)

    def _del_account(self, uuid):
        if messagebox.askyesno(I18n.t("conform_yes"), I18n.t("conform_question")):
            config_mgr.remove_account(uuid)
            self._refresh_account_list()

    # --- API 逻辑 ---
    def _refresh_api_ui(self):
        apis = config_mgr.get_api_list()
        names = [a["name"] for a in apis]
        self.api_combo.configure(values=names)

        idx = config_mgr.get_current_api_index()
        if 0 <= idx < len(names):
            self.api_combo.set(names[idx])
        else:
            self.api_combo.set(names[0])

    def _on_api_change(self, choice):
        apis = config_mgr.get_api_list()
        for i, a in enumerate(apis):
            if a["name"] == choice:
                config_mgr.set_current_api_index(i)
                break

    def _save_custom_api_from_input(self):
        text = self.api_combo.get().strip()
        if not text: return None

        apis = config_mgr.get_api_list()
        for i, a in enumerate(apis):
            if a["name"] == text or a["base_url"] == text:
                config_mgr.set_current_api_index(i)
                return a

        if text.startswith("http"):
            url = text.rstrip('/')
            try:
                domain = url.split('//')[1].split('/')[0]
                name = f"Custom ({domain})"
            except:
                name = f"Custom ({len(apis)})"

            new_api = {"name": name, "base_url": url}
            apis.append(new_api)
            config_mgr.set_api_list(apis)
            config_mgr.set_current_api_index(len(apis) - 1)
            config_mgr.save()

            self._refresh_api_ui()
            self.api_combo.set(name)
            messagebox.showinfo(I18n.t("api_info"), I18n.t("api_saved_info"))
            return new_api

        return None

    def _del_api(self):
        idx = config_mgr.get_current_api_index()
        if idx == 0: return messagebox.showwarning(I18n.t("api_del_ban"), I18n.t("api_del_ban_info"))

        l = config_mgr.get_api_list()
        name = l[idx]["name"]

        if messagebox.askyesno(I18n.t("api_del_info"), I18n.t("api_del_conform").format(name=name)):
            l.pop(idx)
            config_mgr.set_api_list(l)
            config_mgr.set_current_api_index(0)
            config_mgr.save()
            self._refresh_api_ui()

    # --- 登录逻辑 ---
    def _on_verify(self):
        email = self.email_entry.get().strip()
        pwd = self.pwd_entry.get().strip()
        if not email or not pwd: return

        current_text = self.api_combo.get()
        if current_text.startswith("http"):
            self._save_custom_api_from_input()

        api = config_mgr.get_current_api_config()
        url = f"{api['base_url']}/authserver/authenticate"

        self.login_btn.configure(text=I18n.t("now_conforming"), state="disabled")
        threading.Thread(target=self._do_verify, args=(url, email, pwd), daemon=True).start()

    def _do_verify(self, u, e, p):
        try:
            data = authAPI.authenticate(u, e, p)
            self.after(0, lambda: self._on_login_success(data, e))
        except Exception as err:
            self.after(0, lambda: self._on_login_fail(err))

    def _on_login_success(self, data, email):
        self.login_btn.configure(text=I18n.t("btn_verify"), state="normal")

        profiles = data.get("availableProfiles", [])
        if not profiles and data.get("selectedProfile"):
            profiles = [data["selectedProfile"]]

        if not profiles:
            return messagebox.showerror(I18n.t("err_no_prof"), I18n.t("err_no_prof_info"))

        api_cfg = config_mgr.get_current_api_config()
        api_name_short = api_cfg["name"]
        if "(" in api_name_short:
            api_name_short = api_name_short.split('(')[0].strip()

        for p in profiles:
            acc = {
                "uuid": p["id"],
                "name": p["name"],
                "accessToken": data["accessToken"],
                "clientToken": data.get("clientToken"),
                "user_email": email,
                "api_name": api_name_short
            }
            config_mgr.add_or_update_account(acc)

        config_mgr.add_history_user(email)
        self.pwd_entry.delete(0, "end")
        self._refresh_account_list()
        messagebox.showinfo(
            I18n.t("success_prof"),
            I18n.t("success_prof_info").format(count=len(profiles))
        )

    def _on_login_fail(self, e):
        self.login_btn.configure(text=I18n.t("btn_verify"), state="normal")
        messagebox.showerror(I18n.t("login_fail_info"), str(e))

    # --- Java ---
    def _on_java_scan_finished(self, infos):
        if not self.winfo_exists(): return

        self.java_map = {}
        display_list = []  # 下拉框列表 (存长名字)

        current_path = config_mgr.get_real_java_path()
        target_display = None

        for info in infos:
            path = info["path"]
            # 检测路径中是否包含 .YggProxy (或者 constants.DATA_DIR_NAME)
            # 只要包含这个关键字，就认为是内嵌版，隐藏长路径
            if constants.DATA_DIR_NAME in path or ".YggProxy" in path:
                suffix = I18n.t("yggpro_in_java")
            else:
                suffix = path
            # 构造长名字：版本 (架构) - 路径
            long_display = f"Java {info['version']} ({info['arch']}) - {suffix}"

            self.java_map[long_display] = info
            display_list.append(long_display)

            if current_path and os.path.normpath(path) == os.path.normpath(current_path):
                target_display = long_display

        # 处理当前 Config 中的路径
        if current_path and not target_display:
            manual_info = javaScanner.get_java_info(current_path)
            if not manual_info:
                manual_info = {"path": current_path, "version": "?", "arch": "?"}
            # 对 Config 里的路径也做同样的判断
            if constants.DATA_DIR_NAME in current_path or ".YggProxy" in current_path:
                suf = I18n.t("yggpro_in_java")
            else:
                suf = current_path

            long_display = f"Java {manual_info['version']} ({manual_info['arch']}) - {suf}"
            self.java_map[long_display] = manual_info
            display_list.insert(0, long_display)
            target_display = long_display

        # 更新 UI
        if display_list:
            self.java_combo.configure(values=display_list)
            # 如果有目标，选中它；否则选中第一个
            # 注意：这里调用 _on_java_change 会自动把长名字截断为短名字显示
            self._on_java_change(target_display if target_display else display_list[0])
        else:
            self.java_combo.set(I18n.t("java_not_found"))

    def _on_java_change(self, long_display_name):
        """
        用户点击下拉项时触发。
        入参是下拉列表里的长字符串: "Java 17 (x64) - /path/to/java"
        """
        info = self.java_map.get(long_display_name)

        if info:
            # 1. 保存真实路径和信息对象 (供启动和详情页使用)
            self.selected_java_path = info["path"]
            self.current_java_info = info  # 缓存信息对象给 ? 按钮用

            # 2. 【核心】将显示文本篡改为短格式 (不含路径)
            short_display = f"Java {info['version']} ({info['arch']})"
            self.java_combo.set(short_display)
        else:
            # 异常情况兜底
            self.selected_java_path = long_display_name

    def _browse_java(self):
        f = tkinter.filedialog.askopenfilename(filetypes=[("Java Executable", "*.exe;java")])
        if f:
            info = javaScanner.get_java_info(f)
            if info:
                # 构造长名字
                long_display = f"Java {info['version']} ({info['arch']}) - {f}"
                self.java_map[long_display] = info

                # 更新列表
                vals = self.java_combo.cget("values")
                if not vals: vals = []
                if long_display not in vals: vals.insert(0, long_display)
                self.java_combo.configure(values=vals)

                # 触发选中逻辑 (会自动变短)
                self._on_java_change(long_display)
            else:
                messagebox.showerror(I18n.t("browse_java_err"), I18n.t("browse_java_err_info"))

    def _show_java_details(self):
        info = getattr(self, "current_java_info", None)

        if not info:
            # 尝试通过 map 反查
            path = self.java_combo.get()
            # 如果 map 里存的是长名字，尝试直接 get；如果是短名字，无法反查，只能提示
            # 由于我们现在的逻辑是选中后变短名字，所以这里大概率依赖 current_java_info
            # 如果没有，尝试重新获取一下
            for k, v in self.java_map.items():
                if v["path"] == getattr(self, "selected_java_path", ""):
                    info = v
                    break

        if not info:
            return messagebox.showinfo(I18n.t("show_java_dtl"), I18n.t("show_java_dtl_info"))

        template = I18n.t("msg_java_details")
        msg = template.format(
            version=info.get('version'),
            arch=info.get('arch'),
            path=info.get('path'),
            raw=info.get('raw_info')
        )

        # 【修改】使用自定义弹窗，宽600，高371
        self._show_custom_dialog(I18n.t("show_custom_dig_tit"), msg, 600, 371)

    # --- 启动 ---
    def _on_launch(self):
        if self.api_combo.get().startswith("http"):
            self._save_custom_api_from_input()

        if not self.current_auth_data:
            return messagebox.showwarning(I18n.t("on_launch_acc_tit"), I18n.t("on_launch_select_acc"))

        # 【核心修复】直接使用内存中保存的真实路径
        # 因为现在输入框里显示的是 "Java 17 (x64)" 这种短名字，不能直接用来启动
        final_path = getattr(self, "selected_java_path", None)

        # 兜底：如果还没触发过选择事件，尝试用 config 里的
        if not final_path:
            final_path = config_mgr.get_real_java_path()

        if not final_path: return messagebox.showwarning(
            I18n.t("on_launch_no_java_tit"), I18n.t("on_launch_no_java_info"))

        # 如果传入了游戏目录，则进行绑定；否则只设置全局默认
        if self.game_dir:
            # 这一步会同时更新 global real_java_path (取决于你在 configMGR 里的实现)
            config_mgr.set_instance_java_binding(self.game_dir, final_path)
            print(f"Java bound to instance: {self.game_dir}")
        else:
            config_mgr.set_real_java_path(final_path)

        # 4. Token 刷新逻辑 (保持不变)
        api = config_mgr.get_current_api_config()

        try:
            profile = {"id": self.current_auth_data["uuid"], "name": self.current_auth_data["name"]}
            new_data = authAPI.refresh(
                f"{api['base_url']}/authserver/refresh",
                self.current_auth_data["accessToken"],
                self.current_auth_data.get("clientToken"),
                selected_profile=profile
            )
            self.current_auth_data["accessToken"] = new_data["accessToken"]
            config_mgr.add_or_update_account(self.current_auth_data)
        except Exception as e:
            print(f"Refresh warning: {e}")
            pass

        config_mgr.save()
        self.setup_success = True
        self.destroy()

    def run(self):
        self.mainloop()
        return self.setup_success


def show_wizard(force_show_settings=False, game_dir=None):
    app = ModernWizard(force_show_settings, game_dir=game_dir)
    return app.run()