# YggdrasilProxy

🌍 简体中文 | [English](./README.md)

---

YggdrasilProxy 是一个用于 Minecraft 的 **启动中间层工具**，  
用于统一管理 **第三方登录账号、认证服务器和 Java 运行环境**，  
无需替换你原本使用的启动器。

它可以与 **HMCL、Prism Launcher、PCL2、官方启动器** 等 **几乎所有** 启动器配合使用。

![Main Window](readmePic/guiMain-zh-CN.png)

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
前往 **Releases** 页面，选择适合的版本：

- **标准版**：使用系统已有的 Java 环境
- **Java 版**：内置 Java ，开箱即用

### 2️⃣ 在启动器中使用
- 将 **YggdrasilProxy** 设置为游戏 Java 即可
- 在启动器内添加启动参数```--yggpro```来强制打开登录页面

### 3️⃣ 首次启动配置

首次运行会弹出配置窗口：

1. 添加或选择账号  
2. 选择认证服务器（默认已包含 LittleSkin）  
3. 选择 Java 运行环境  
4. 点击「启动游戏」即可，配置会按实例自动保存

### 4️⃣ 功能说明
- 双击程序可打开兼容模式设置  
- 右键 ? 支持切换界面语言  
- 右键账号可一键复制 UUID  

---

## 🧩 支持的启动器

- HMCL  
- Prism Launcher  
- MultiMC
- 官方 Minecraft 启动器
- 几乎所有启动器！

---

## ⚠️ 安全说明

- 不会修改您的游戏文件
- 不会记录或保存您的密码  
- AccessToken 本地加密存储
- 网络请求仅限所选认证服务器

---

## 📦 构建方式

#### 伪代码，详情可见 [pyCMD](pyCMD.md)

```bash
pyinstaller -F
  --collect-all cryptography
  # [可选] YggProJAVA.zip 是您想打包的 Java 压缩包
  --add-data "assets/YggProJAVA.zip:assets"
  --add-data "assets/fMcMain.jar:assets"
  --add-data "assets/authlib-injector.jar:assets"
  # [兼容] 为了部分 Windows 启动器的兼容 可选 
  --add-data "assets\javaw.exe;assets"
  --add-data "assets\javac.exe;assets"
  --name="YggdrasilProxy"
  run.py
```
本项目使用了 authlib-injector，由 [yushijinhun](https://github.com/yushijinhun/authlib-injector) 提供，特此感谢原作者。

---

## 📄 开源协议

- [[MPL-2.0]](LICENSE)
