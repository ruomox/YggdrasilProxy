# src/preSetup.py
import sys
import webbrowser
import customtkinter as ctk
from src import launcherCompat

# ================= 配置与外观 =================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# 配色方案
COLOR_BG = "#2b2b2b"
COLOR_CARD = "#363636"

# 主按钮 (Settings)
COLOR_BTN_MAIN = "#A07040"
COLOR_BTN_MAIN_HOVER = "#B38050"

COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_SUB = "#999999"
COLOR_LINK_IDLE = "#999999"
COLOR_LINK_HOVER = "#FFFFFF"

# 关闭按钮
COLOR_BTN_CLOSE_BG = "#2f2f2f"        # 比背景亮一点
COLOR_BTN_CLOSE_BORDER = "#4a4a4a"    # 稳定的灰边框
COLOR_BTN_CLOSE_HOVER = "#3a3a3a"     # 悬停略提亮
COLOR_BTN_CLOSE_TEXT = "#b0b0b0"
COLOR_BTN_CLOSE_TEXT_HOVER = "#e0e0e0"

REG_URL = "https://littleskin.cn/auth/register"


class PreSetupApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.attributes("-topmost", True)
        self.title("YggdrasilProxy")

        # 窗口尺寸
        w, h = 300, 485
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = int((ws - w) / 2)
        y = int((hs - h) / 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        # 卡片容器
        self.card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        self.card.pack(fill="both", expand=True, padx=15, pady=15)

        # 1. 标题
        self.title_lbl = ctk.CTkLabel(
            self.card,
            text="Yggdrasil Proxy",
            font=("Microsoft YaHei UI", 23, "bold"),
            text_color=COLOR_TEXT_MAIN
        )
        self.title_lbl.pack(pady=(50, 5))

        # 2. 提示文案
        self.sub_lbl = ctk.CTkLabel(
            self.card,
            text="请在您的启动器内选择本应用为 Java 以使用\n"
                 "Select this app as Java in your launcher",
            font=("Microsoft YaHei UI", 10),
            text_color=COLOR_TEXT_SUB,
            justify="center",
            height=30
        )
        self.sub_lbl.pack(pady=(20, 0))

        # 3. 按钮: 账号设置
        self.btn_settings = ctk.CTkButton(
            self.card,
            text="账号设置 / Settings",
            font=("Microsoft YaHei UI", 12, "bold"),
            height=57,
            width=186,
            fg_color=COLOR_BTN_MAIN,
            hover_color=COLOR_BTN_MAIN_HOVER,
            corner_radius=6,
            command=self._open_main_wizard
        )
        self.btn_settings.pack(pady=(30, 0))

        # 4. 按钮: 兼容模式
        self.btn_compat = ctk.CTkButton(
            self.card,
            text="兼容模式 / Compatibility",
            font=("Microsoft YaHei UI", 12, "bold"),
            height=57,
            width=186,
            fg_color=COLOR_BTN_MAIN,
            hover_color=COLOR_BTN_MAIN_HOVER,
            corner_radius=6,
            command=self._run_compatibility_mode
        )
        self.btn_compat.pack(pady=(30, 0))

        # 5. 注册链接
        self.link_lbl = ctk.CTkLabel(
            self.card,
            text="🔗 前往 LittleSkin 注册",
            font=("Microsoft YaHei UI", 9, "underline"),
            text_color=COLOR_LINK_IDLE,
            cursor="hand2"
        )
        self.link_lbl.pack(pady=0)

        self.link_lbl.bind("<Button-1>", lambda e: self._open_register())
        self.link_lbl.bind("<Enter>", lambda e: self.link_lbl.configure(text_color=COLOR_LINK_HOVER))
        self.link_lbl.bind("<Leave>", lambda e: self.link_lbl.configure(text_color=COLOR_LINK_IDLE))

        # 6. 关闭按钮
        self.btn_close = ctk.CTkButton(
            self.card,
            text="关闭 / Close",
            font=("Microsoft YaHei UI", 12),
            height=36,
            width=115,

            fg_color=COLOR_BTN_CLOSE_BG,
            hover_color=COLOR_BTN_CLOSE_HOVER,

            border_width=1,
            border_color=COLOR_BTN_CLOSE_BORDER,

            text_color=COLOR_BTN_CLOSE_TEXT,
            corner_radius=8,

            command=self._close_app
        )
        self.btn_close.pack(side="bottom", pady=(0, 50))

        self.btn_close.bind(
            "<Enter>",
            lambda e: self.btn_close.configure(text_color=COLOR_BTN_CLOSE_TEXT_HOVER)
        )
        self.btn_close.bind(
            "<Leave>",
            lambda e: self.btn_close.configure(text_color=COLOR_BTN_CLOSE_TEXT)
        )

    def _open_main_wizard(self):
        self.destroy()
        try:
            from src import guiWizard
            guiWizard.show_wizard(force_show_settings=True)
        except Exception as e:
            print(f"Error: {e}")

    def _run_compatibility_mode(self):
        launcherCompat.show_compatibility_gui(self)

    def _open_register(self):
        webbrowser.open(REG_URL)

    def _close_app(self):
        sys.exit(0)


def check_entry_mode():
    if len(sys.argv) > 1: return
    try:
        app = PreSetupApp()
        app.mainloop()
        sys.exit(0)
    except:
        sys.exit(1)