# YggdrasilProxy

---

🌍 English | [简体中文](./README.md)


YggdrasilProxy is a **launch-time middleware tool** for Minecraft.  
It is designed to centrally manage **third-party authentication accounts, Yggdrasil servers, and Java runtimes**,  
without replacing or modifying your existing launcher.

It works alongside almost all major launchers, including  
**HMCL, Prism Launcher, and the official Minecraft Launcher**.

---

## ✨ What does this tool do?

- Manage multiple Yggdrasil authentication accounts
- Bind different accounts to different Minecraft instances
- Automatically inject `authlib-injector` at launch time
- Adapt to different launcher argument structures
- Select or bind Java runtimes per instance
- Optional embedded Java for environment-free launching

---

## 🚀 Quick Start Guide

### 1️⃣ Download
Go to the **Releases** page and choose the version that fits your needs:

- **Lite version**: No bundled Java (recommended, smaller size)
- **Full version**: Includes an embedded Java runtime, ready to use

### 2️⃣ Use with your launcher
- Set **YggdrasilProxy** as the Java executable used by your launcher
- Add the ```--yggpro``` launch argument in your launcher to force the login/config UI

---

## 3️⃣ First Launch Configuration

On the first run, a configuration window will appear:

1. Add or select an account  
2. Choose an authentication server (LittleSkin is included by default) 
3. Select a Java runtime
4. Click Launch Game 

All settings are automatically saved per Minecraft instance.

---

## 🧩 Supported Launchers

- HMCL  
- Prism Launcher  
- MultiMC
- Official Minecraft Launcher
- And almost all other standard-compliant launchers !

---

## ⚠️ Usage Notes

- Your password is never stored 
- Access tokens are encrypted locally  
- Game files are never modified 
- Does not affect official server or online authentication rules  

---

## 🔧 Technical Overview

### System Architecture

YggdrasilProxy operates as a launch argument control layer:

1. Detects launcher type 
2. Extracts the real game launch arguments  
3. Injects authentication and runtime configuration  
4. Launches Minecraft in a controlled environment  

### Java Selection Priority

1. Java bound to the current instance   
2. Java detected on the system 
3. Embedded Java (if available)

### Authentication Logic

- Full support for the Yggdrasil protocol 
- Automatic token validation and refresh  
- Supports multiple profiles under a single account 

### Security Model

- Tokens are encrypted before being written to disk  
- Passwords are never written to disk  
- Network requests are restricted to the selected authentication server  

---

## 📦 Build Instructions
```bash
pyinstaller -F \
  --collect-all cryptography \
  # [Optional] YggProJRE.zip: bundled Java runtime archive
  --add-data "assets/YggProJRE.zip:assets" \
  --add-data "assets/fMcMain.jar:assets" \
  --add-data "assets/authlib-injector.jar:assets" \
  --name="YggdrasilProxy" \
  run.py
```

---

## 📄 License

- [[MPL-2.0]](LICENSE)