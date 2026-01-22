# YggdrasilProxy

🌍 简体中文 | [English](./README.en.md)

---

YggdrasilProxy 是一个用于 Minecraft 的 **启动中间层工具**，  
用于统一管理 **第三方登录账号、认证服务器和 Java 运行环境**，  
无需替换你原本使用的启动器。

它可以与 **HMCL、Prism Launcher、官方启动器** 等几乎所有启动器配合使用。

---

## ✨ 这个工具能做什么？

- 管理多个 Yggdrasil 认证账号
- 将账号绑定到不同的 Minecraft 实例
- 启动时自动注入 authlib-injector
- 兼容不同启动器的启动参数结构
- 为不同实例选择或绑定 Java 运行时
- 可选内嵌 Java，实现“免环境启动”

---

## 🚀 快速使用指南

### 1️⃣ 下载程序
前往 **Releases** 页面，选择适合你的版本：

- **Lite 版**：不包含 Java（推荐，体积更小）
- **Full 版**：包含内嵌 Java，开箱即用

### 2️⃣ 在启动器中使用
- 将 **YggdrasilProxy** 设置为 Java 游戏即可
- 在启动器内添加启动参数```--yggpro```来强制打开账号登录页面

---

## 3️⃣ 首次启动配置

首次运行会弹出配置窗口：

1. 添加或选择账号  
2. 选择认证服务器（默认已包含 LittleSkin）  
3. 选择 Java 运行环境  
4. 点击「启动游戏」  

配置会按实例自动保存。

---

## 🧩 支持的启动器

- HMCL  
- Prism Launcher  
- MultiMC
- 官方 Minecraft 启动器
- 几乎所有启动器！

---

## ⚠️ 使用说明

- 不会记录或保存你的密码  
- AccessToken 仅本地加密存储  
- 不修改游戏文件  
- 不影响正版在线服务器规则  

---

## 🔧 技术说明

### 系统结构概览

YggdrasilProxy 作为 **启动参数控制层** 工作：

1. 识别启动器类型  
2. 提取真实启动参数  
3. 注入认证与运行时配置  
4. 在受控环境下启动 Minecraft  

### Java 选择优先级

1. 实例绑定的 Java   
2. 系统扫描到的 Java 
3. 内嵌 Java（如存在）

### 认证逻辑

- 完整支持 Yggdrasil 协议  
- 自动校验与刷新 Token  
- 支持一个账号多个角色  

### 安全模型

- Token 落盘前加密  
- 密码不写入磁盘  
- 网络请求仅限所选认证服务器  

---

## 📦 构建方式
```bash
pyinstaller -F \
  --collect-all cryptography \
  # [可选] YggProJRE.zip 是您想打包的 Java 压缩包
  --add-data "assets/YggProJRE.zip:assets" \
  --add-data "assets/fMcMain.jar:assets" \
  --add-data "assets/authlib-injector.jar:assets" \
  --name="YggdrasilProxy" \
  run.py
```

---

## 📄 开源协议

- [[MPL-2.0]](LICENSE)