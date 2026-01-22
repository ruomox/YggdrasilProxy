# src/i18n.py
from src.configMGR import config_mgr

# 1. 定义支持的语言
SUPPORTED_LANGUAGES = {
    "zh_CN": "简体中文",
    "en_US": "English"
}

# 2. 定义翻译字典 (Key -> 多语言文本)
TRANSLATIONS = {
    "zh_CN": {
        "window_title": "配置向导",
        "sidebar_accounts": "账户",
        "account_source_default": "认证账户",
        "btn_launch": "启动游戏",
        "status_ready": "由 Mox 用 ♥ 制作",
        "sec_java": "Java 运行环境",
        "sec_api": "认证服务器 (API)",
        "sec_login": "登录新账号",
        "lbl_email": "邮箱 / 用户名:",
        "lbl_pwd": "密码:",
        "lbl_pwd_hint": "* YggdrasilProxy 不会记录您的密码",
        "btn_verify": "验证并添加",
        "java_scanning": "正在扫描...",
        "msg_select_acc": "请先选择一个账号",
        "copy_uuid": "复制 UUID",
        "del_account": "删除账号",
        "conform_yes": "确认",
        "conform_question": "确定删除该账号吗？",
        "api_info": "提示",
        "api_saved_info": "新 API 已保存",
        "api_del_ban": "禁止",
        "api_del_ban_info": "默认 API 不可删除",
        "api_del_info": "删除",
        "api_del_conform": "确定删除 API '{name}' 吗？",
        "now_conforming": "验证中...",
        "err_no_prof": "错误",
        "err_no_prof_info": "该账号没有游戏角色",
        "success_prof": "成功",
        "success_prof_info": "成功添加 {count} 个角色",
        "login_fail_info": "验证失败",
        "yggpro_in_java": "[YggdrasilProxy 内嵌]",
        "java_not_found": "未找到 Java",
        "browse_java_err": "错误",
        "browse_java_err_info": "无效的 Java 可执行文件",
        "show_java_dtl": "详情",
        "show_java_dtl_info": "请先选择一个有效的 Java 环境",
        "msg_java_details": "版本: {version}\n架构: {arch}\n路径: {path}\n\n原始输出: \n{raw}",
        "show_custom_dig_tit": "Java 详情",
        "show_custom_dig_close_btn": "关闭",
        "on_launch_acc_tit": "提示",
        "on_launch_select_acc": "请先选择一个账号",
        "on_launch_no_java_tit": "提示",
        "on_launch_no_java_info": "Java 路径为空",
    },
    "en_US": {
        "window_title": "Setup Wizard",
        "sidebar_accounts": "Accounts",
        "account_source_default": "Authentication Account",
        "btn_launch": "Launch Game",
        "status_ready": "Made with ♥ by Mox",
        "sec_java": "Java Runtime",
        "sec_api": "Authentication Server (API)",
        "sec_login": "Add New Account",
        "lbl_email": "Email / Username:",
        "lbl_pwd": "Password:",
        "lbl_pwd_hint": "* YggdrasilProxy never stores your password",
        "btn_verify": "Verify & Add",
        "java_scanning": "Scanning...",
        "msg_select_acc": "Please select an account first",
        "copy_uuid": "Copy UUID",
        "del_account": "Delete Account",
        "conform_yes": "Confirm",
        "conform_question": "Are you sure you want to delete this account?",
        "api_info": "Information",
        "api_saved_info": "New API has been saved",
        "api_del_ban": "Not Allowed",
        "api_del_ban_info": "The default API cannot be removed",
        "api_del_info": "Delete",
        "api_del_conform": "Are you sure you want to delete API '{name}'?",
        "now_conforming": "Verifying...",
        "err_no_prof": "Error",
        "err_no_prof_info": "This account has no available game profiles",
        "success_prof": "Success",
        "success_prof_info": "Successfully added {count} profile(s)",
        "login_fail_info": "Authentication failed",
        "yggpro_in_java": "[Bundled with YggdrasilProxy]",
        "java_not_found": "Java not found",
        "browse_java_err": "Error",
        "browse_java_err_info": "Invalid Java executable",
        "show_java_dtl": "Details",
        "show_java_dtl_info": "Please select a valid Java runtime first",
        "msg_java_details": "Version: {version}\nArchitecture: {arch}\nPath: {path}\n\nRaw Output: \n{raw}",
        "show_custom_dig_tit": "Java Details",
        "show_custom_dig_close_btn": "Close",
        "on_launch_acc_tit": "Notice",
        "on_launch_select_acc": "Please select an account before launching",
        "on_launch_no_java_tit": "Notice",
        "on_launch_no_java_info": "Java path is not set",
    }
}


class I18n:
    @staticmethod
    def get_languages():
        return SUPPORTED_LANGUAGES

    @staticmethod
    def get_current_language_code():
        return config_mgr.get_language()

    @staticmethod
    def t(key):
        """核心翻译方法：传入 key，返回当前语言的文本"""
        lang = config_mgr.get_language()

        # 获取对应语言包，如果不存在则回退到中文
        lang_data = TRANSLATIONS.get(lang, TRANSLATIONS["zh_CN"])

        # 获取 Key 对应的文本，如果 Key 不存在则直接返回 Key 自身方便调试
        return lang_data.get(key, key)