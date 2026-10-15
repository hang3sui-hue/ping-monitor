# Ping 网络监测器 / Ping Monitor

这是我学习 Python 时做的一个小项目。我想练习图形界面和网络命令，于是用 Tkinter 写了一个 Windows Ping 监测器。它可以选择常用网站或输入自己的主机名，查看每次 Ping 的结果、延迟和丢包率，并导出 CSV。

This is a small project I made while learning Python. I used Tkinter to build a bilingual Windows Ping monitor and practiced running network commands without freezing the interface.

## 我练习了什么

- 用 Tkinter 做一个可以点击操作的桌面界面，并加入中文和英文切换。
- 用后台线程运行 Windows 的 `ping` 命令，再用队列把结果交给界面显示。
- 检查用户输入，用 JSON 记住上次目标，并把结果保存为 CSV。
- 给几个不依赖网络的逻辑函数写单元测试。

## 怎么运行

安装 Python 3.10+ 后，在这个文件夹运行：

```powershell
python ping_gui.py
```

也可以双击 `start.bat`。本项目只需要 Python 标准库，不需要安装第三方包。

## 怎么使用

1. 在左侧“常用目标”中选择网站或“自定义”。预设目标的地址会锁定；只有“自定义”允许编辑。
2. 设置次数、间隔、超时和持续时间。数字输入框只接受数字。
3. 点击“开始监测”。达到次数或时间上限时，以先到者为准结束；也可以点击“停止”。
4. 表格展示每次结果，顶部展示已运行时间和统计。切换右上角语言不会清空结果。
5. 点击“导出 CSV”保存本次结果。程序会在同一文件夹的 `ping-monitor-settings.json` 中记住上次监测的目标。

限制：每次最多 100 次；间隔为 1000–60000 毫秒；持续时间为 1–300 秒。

## 代码怎么讲

主要代码都在 `ping_gui.py`，按下面的顺序阅读：

1. **预设与翻译**：`PRESETS` 保存目标地址，`WORDS` 每行写一对中文和英文。切换语言时，`translate_window()` 更新界面文字和已有结果。
2. **输入与记忆**：`read_inputs()` 检查目标和数字范围；`load_last_host()` / `save_last_host()` 用 JSON 记住上次目标。
3. **执行 Ping**：`monitor()` 在后台线程中循环，`ping_once()` 调用 Windows 自带的 `ping` 命令。这样网络等待不会卡住窗口。
4. **更新窗口**：后台线程把结果放进队列；Tkinter 主线程通过 `check_events()` 读取队列并更新表格和统计。这避免了直接从后台线程修改界面。

这个项目是我的 Python 练习作品，不是专业的网络诊断工具。目前只在 Windows 上运行，Ping 结果也会受到目标网站和本地网络是否允许 ICMP 的影响。

运行测试：

```powershell
python -m unittest discover -s tests -v
```

## 文件

```text
ping-monitor/
├── ping_gui.py             # 所有主要 Python 代码
├── start.bat               # Windows 双击启动源码
├── tests/test_ping_gui.py  # 小型逻辑测试
├── .gitignore              # 排除运行数据与打包文件
└── README.md
```

这个工具检查的是 **ICMP 连通性**。有些网站或网络会屏蔽 ICMP，因此 Ping 失败不一定表示网页无法打开。
