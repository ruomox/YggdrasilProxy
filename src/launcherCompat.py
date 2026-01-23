# src/launcherCompat.py
import sys
import os
import shutil
import platform
import tkinter.messagebox


# ================= 对外接口 =================

def show_compatibility_gui(parent_window=None):
    """
    [主入口]
    执行兼容性逻辑，并调用系统原生弹窗显示结果。
    """
    system = platform.system()

    try:
        # --- 分支 1: Windows (执行实际操作) ---
        if system == "Windows":
            success, msg = _install_windows_logic()

            if success:
                tkinter.messagebox.showinfo("操作成功", msg, parent=parent_window)
            else:
                tkinter.messagebox.showerror("操作失败", msg, parent=parent_window)

        # --- 分支 2: macOS / Linux (提示无需操作) ---
        else:
            msg = (
                "当前系统无需使用兼容模式。\n"
                "Compatibility not required."
            )
            tkinter.messagebox.showinfo("提示", msg, parent=parent_window)

    except Exception as e:
        tkinter.messagebox.showerror("未知错误", str(e), parent=parent_window)


# ================= 内部业务逻辑 (Windows) =================

def _install_windows_logic():
    """Windows 具体干活的代码"""
    try:
        executable_path = sys.executable
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(executable_path)
            assets_dir = os.path.join(sys._MEIPASS, "assets")
        else:
            base_dir = os.getcwd()
            assets_dir = os.path.join(base_dir, "assets")

        # 1. java.exe (硬链接)
        target_java = os.path.join(base_dir, "java.exe")
        _create_hard_link(executable_path, target_java)

        # 2. 资源释放
        for filename in ["javaw.exe", "javac.exe"]:
            src = os.path.join(assets_dir, filename)
            dst = os.path.join(base_dir, filename)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dst)
                except:
                    pass  # 忽略覆盖错误
            else:
                return False, f"资源缺失: {filename}"

        msg = (
            "兼容文件已生成！\n\n"
            "请在启动器中选择同目录下的:\n"
            f"-> [ javaw.exe ]\n\n"
            "选择此文件可解决部分启动器无法识别的问题。"
        )
        return True, msg
    except Exception as e:
        return False, f"文件生成出错: {str(e)}"


def _create_hard_link(src, dst):
    if os.path.exists(dst):
        try:
            if os.path.getsize(src) != os.path.getsize(dst):
                os.remove(dst)
            else:
                return
        except:
            pass
    try:
        os.link(src, dst)
    except:
        shutil.copy2(src, dst)