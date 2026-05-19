<div align="center">

# 🪟 WindowManager

**Windows 窗口透明度调节 & 后台自动点击 工具**
*Window opacity control & background auto-clicker for Windows*

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### 🌐 [🇨🇳 中文](#-中文文档) · [🇬🇧 English](#-english-documentation)

</div>

---

<a id="-中文文档"></a>

## 🇨🇳 中文文档

> [切换到 English →](#-english-documentation)

### 📖 简介

**WindowManager** 是一款专为 Windows 设计的桌面小工具，集成两大常用功能：

- 🪟 **窗口透明度管理** — 实时调节任意窗口的透明度
- 🖱 **后台自动点击器** — 在窗口失焦/最小化状态下也能持续点击
- ⌨ **全局快捷键** — 程序在后台也能响应
- 🔍 **窗口搜索 / 自动刷新** — 快速定位目标窗口

### ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 透明度滑块 | 1~255 范围连续调节，预设按钮一键切换 |
| 后台点击 | 通过 `PostMessage` 实现，目标窗口无需聚焦 |
| 子控件自动定位 | 自动找到坐标下真正接收点击的子窗口 |
| 倒计时记录坐标 | 按钮触发，倒计时后采样鼠标位置 |
| 即时记录坐标 | 快捷键触发，立即采样 |
| 全局快捷键 | 基于 `RegisterHotKey`，应用未聚焦也响应 |
| 自定义快捷键 | 弹窗可视化设置，保存到 `hotkeys.json` |
| 实时日志 | 终端风格彩色日志，记录每次点击 |

### 🖼 界面预览

```
┌─ 搜索 / 刷新 / 快捷键设置 ──────────────────────────────┐
├──────────────────────────┬──────────────────────────────┤
│                          │ 当前选中 (窗口信息)          │
│                          ├──────────────────────────────┤
│   窗口列表 (Treeview)    │ 🪟 透明度控制                │
│   - 标题                 │   滑块 / 数值 / 预设         │
│   - 进程                 ├──────────────────────────────┤
│   - HWND                 │ 🖱 后台点击                  │
│   - 当前透明度           │   X / Y / 间隔 / 倒计时      │
│                          │   记录坐标 / 开始 / 停止     │
│                          ├──────────────────────────────┤
│                          │ 快捷键提示                   │
├──────────────────────────┴──────────────────────────────┤
│ 日志输出 (深色终端风格)                                  │
├──────────────────────────────────────────────────────────┤
│ 状态栏：就绪 / 窗口数 / 运行状态                         │
└──────────────────────────────────────────────────────────┘
```

### 🚀 快速开始

#### 方式一：直接运行源码

```bash
# 1. 安装依赖
pip install pywin32 psutil

# 2. 运行（不弹控制台）
pythonw WindowManager.py
```

#### 方式二：使用打包好的 exe

从 [Releases](../../releases) 下载 `WindowManager.exe`，双击运行即可。

#### 方式三：自己打包

```bash
pip install pyinstaller
pyinstaller -F -w -i icon.ico --add-data "icon.ico;." WindowManager.py
```

生成的 exe 位于 `dist/WindowManager.exe`。

### ⌨ 默认快捷键

| 功能 | 快捷键 |
|------|--------|
| 记录鼠标坐标（立即） | `Ctrl + Shift + R` |
| 开始 / 停止点击 | `Ctrl + Shift + S` |
| 透明度 −10 | `Ctrl + Shift + -` |
| 透明度 +10 | `Ctrl + Shift + =` |
| 恢复完全不透明 | `Ctrl + Shift + 0` |
| 刷新窗口列表 | `F5` |
| 清空日志 | `Ctrl + L` |

> 所有快捷键均可在「⌨ 快捷键设置」弹窗中自定义，配置保存到 `hotkeys.json`。

### 📋 使用流程

#### 🔹 调节透明度

1. 在左侧列表中**选中目标窗口**
2. 拖动右侧滑块 / 输入数值 / 点击预设
3. 或使用快捷键 `Ctrl+Shift+-` / `Ctrl+Shift+=` 微调

#### 🔹 设置自动点击

1. 选中目标窗口
2. 把鼠标移到要点击的位置，按 `Ctrl+Shift+R` **立即记录坐标**
3. 设置间隔时间（秒）
4. 按 `Ctrl+Shift+S` 开始点击，再按一次停止

### 📂 项目结构

```
WindowManager/
├── WindowManager.py     # 主程序
├── icon.ico             # 应用图标
├── hotkeys.json         # 快捷键配置（首次运行后生成）
├── build.bat            # 打包脚本
├── README.md
└── LICENSE
```

### ⚙ 依赖

- Python 3.8+
- [pywin32](https://pypi.org/project/pywin32/)
- [psutil](https://pypi.org/project/psutil/)

```bash
pip install pywin32 psutil
```

### ❓ 常见问题

<details>
<summary><b>Q: 点击没反应？</b></summary>

A: 部分程序（如 DirectX 游戏、某些 Electron 应用）会拦截 `PostMessage`。这类程序需要前台真实输入，本工具暂不支持。
</details>

<details>
<summary><b>Q: 打包后启动很慢？</b></summary>

A: `-F` 单文件模式每次需要解压临时文件，慢 2~5 秒属正常。可改用 `-D` 文件夹模式加快启动。
</details>

<details>
<summary><b>Q: 任务栏图标和别的 Python 程序合并了？</b></summary>

A: 代码已通过 `SetCurrentProcessExplicitAppUserModelID` 隔离。若仍合并，建议打包成 exe 使用。
</details>

<details>
<summary><b>Q: 杀毒软件报毒？</b></summary>

A: PyInstaller 打包的 exe 常被误报，可加白名单或使用 Nuitka 重新打包。
</details>

### 📄 许可证

[MIT License](LICENSE)

### 🤝 贡献

欢迎 PR 和 Issue！

---

<a id="-english-documentation"></a>

## 🇬🇧 English Documentation

> [Switch to 中文 →](#-中文文档)

### 📖 Introduction

**WindowManager** is a lightweight desktop utility for Windows, combining two essential features:

- 🪟 **Window Opacity Manager** — Adjust transparency of any window in real-time
- 🖱 **Background Auto-Clicker** — Keeps clicking even when the target window is unfocused/minimized
- ⌨ **Global Hotkeys** — Works even when this app is in the background
- 🔍 **Search & Auto-refresh** — Quickly locate target windows

### ✨ Features

| Feature | Description |
|---------|-------------|
| Opacity Slider | Smooth 1~255 adjustment with preset buttons |
| Background Click | Uses `PostMessage`, no need to focus the target |
| Auto Child Locator | Automatically finds the actual child control under the coordinate |
| Delayed Position Recording | Button-triggered, captures cursor after countdown |
| Instant Position Recording | Hotkey-triggered, captures immediately |
| Global Hotkeys | Based on `RegisterHotKey`, responds even when unfocused |
| Customizable Hotkeys | GUI configuration, saved to `hotkeys.json` |
| Live Log | Terminal-style colored log for every action |

### 🖼 Interface Layout

```
┌─ Search / Refresh / Hotkey Settings ─────────────────────┐
├──────────────────────────┬───────────────────────────────┤
│                          │ Selected (window info)        │
│                          ├───────────────────────────────┤
│   Window List            │ 🪟 Opacity Control            │
│   - Title                │   Slider / Value / Presets    │
│   - Process              ├───────────────────────────────┤
│   - HWND                 │ 🖱 Background Clicker         │
│   - Current Opacity      │   X / Y / Interval / Delay    │
│                          │   Record / Start / Stop       │
│                          ├───────────────────────────────┤
│                          │ Hotkey Hints                  │
├──────────────────────────┴───────────────────────────────┤
│ Live Log (dark terminal style)                           │
├──────────────────────────────────────────────────────────┤
│ Status Bar: Ready / Window Count / Running State         │
└──────────────────────────────────────────────────────────┘
```

### 🚀 Getting Started

#### Option 1: Run from source

```bash
# 1. Install dependencies
pip install pywin32 psutil

# 2. Run (no console window)
pythonw WindowManager.py
```

#### Option 2: Use prebuilt exe

Download `WindowManager.exe` from [Releases](../../releases) and double-click to run.

#### Option 3: Build it yourself

```bash
pip install pyinstaller
pyinstaller -F -w -i icon.ico --add-data "icon.ico;." WindowManager.py
```

Output: `dist/WindowManager.exe`

### ⌨ Default Hotkeys

| Action | Shortcut |
|--------|----------|
| Record cursor position (instant) | `Ctrl + Shift + R` |
| Toggle clicker (start / stop) | `Ctrl + Shift + S` |
| Opacity −10 | `Ctrl + Shift + -` |
| Opacity +10 | `Ctrl + Shift + =` |
| Restore full opacity | `Ctrl + Shift + 0` |
| Refresh window list | `F5` |
| Clear log | `Ctrl + L` |

> All hotkeys can be customized via the "⌨ Hotkey Settings" dialog. Saved to `hotkeys.json`.

### 📋 Usage

#### 🔹 Adjust Opacity

1. Select target window in the left list
2. Drag slider / enter value / click presets
3. Or use `Ctrl+Shift+-` / `Ctrl+Shift+=` to fine-tune

#### 🔹 Configure Auto-Click

1. Select target window
2. Move cursor to target position, press `Ctrl+Shift+R` to **record instantly**
3. Set interval (seconds)
4. Press `Ctrl+Shift+S` to start; press again to stop

### 📂 Project Structure

```
WindowManager/
├── WindowManager.py     # Main script
├── icon.ico             # App icon
├── hotkeys.json         # Hotkey config (generated on first run)
├── build.bat            # Build script
├── README.md
└── LICENSE
```

### ⚙ Dependencies

- Python 3.8+
- [pywin32](https://pypi.org/project/pywin32/)
- [psutil](https://pypi.org/project/psutil/)

```bash
pip install pywin32 psutil
```

### ❓ FAQ

<details>
<summary><b>Q: Clicks don't work on some programs?</b></summary>

A: Programs like DirectX games or some Electron apps intercept `PostMessage`. These require real foreground input, which this tool doesn't support yet.
</details>

<details>
<summary><b>Q: Slow startup after packaging?</b></summary>

A: `-F` (one-file mode) extracts temp files on each launch (2~5s). Use `-D` (folder mode) for faster startup.
</details>

<details>
<summary><b>Q: Taskbar icon merged with other Python apps?</b></summary>

A: The code already isolates via `SetCurrentProcessExplicitAppUserModelID`. If still merged, build to exe.
</details>

<details>
<summary><b>Q: Antivirus false-positive?</b></summary>

A: PyInstaller-built exes are commonly flagged. Whitelist it, or rebuild with Nuitka.
</details>

### 📄 License

[MIT License](LICENSE)

### 🤝 Contributing

PRs and issues are welcome!

---

<div align="center">

**[⬆ Back to top](#-windowmanager)**

Made with ❤ for Windows users

</div>
