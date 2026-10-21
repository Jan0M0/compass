# 罗盘 Compass

这是 **Sapphire Jan 设计**的一套职业探索与求职工具。你现在所在的文件夹就是它。

## 如果你是 AI agent（第一次打开这个文件夹）

用户把文件夹交给你时，通常只会说一句：「装一下罗盘」「帮我用这个」。

按下面步骤做，**每步只做一次，不要重复安装**：

1. **检查是否已安装**

   ```bash
   ls ~/.compass/bin/compass.cmd    # Windows
   ls ~/.compass/bin/compass        # macOS / Linux
   ```

   存在就跳到第 4 步。

2. **安装**

   最简单：让用户双击本文件夹里的 `install.bat`，按提示输入一个名字。
   （Windows 上双击即可；它会自动找 Python、安装、建身份、打开看板。）

   或者由你来跑：

   ```bash
   python install.py
   ```

   如果 `python` 不是 3.9+ 或找不到，用 WorkBuddy 自带的：
   `C:\Users\<用户名>\.workbuddy\binaries\python\envs\default\Scripts\python.exe`

   或直接运行同目录的 `install.ps1`（Windows，会自动找 Python）。

3. **创建身份**

   ```bash
   ~/.compass/bin/compass.cmd init --handle <小写英文名>
   ```

   handle 会出现在看板网址里。不确定就用名字拼音。

4. **确认可用**

   ```bash
   ~/.compass/bin/compass.cmd status
   ~/.compass/bin/compass.cmd open
   ```

5. **告诉用户两件事**
   - 重启一次 WorkBuddy，`compass` 技能才会加载（之后就能全程用自然语言）。
   - 第一次对话可以从「我不知道自己想做什么」开始。

## 装好之后

完整的 agent 手册在 `~/.workbuddy/skills/compass/SKILL.md`（安装时生成）。
也可以直接读本文件夹的 `SKILL.md.in`。

核心分工：

- **你（agent）负责推理**：解析 JD、判断、写 bullet、写招呼语。
- **Compass 服务负责结果**：schema、存储、版本、URL 视图、分享。
- **用户只看 URL**：`compass open`。

## 不需要做的事

- 不需要部署到服务器
- 不需要配置 API key
- 不需要买任何服务
- 不需要联网（除了岗位雷达要访问实习僧）

服务跑在用户自己的电脑上，数据只在本机。

## 这份工具是谁的

Sapphire Jan 为使用者设计。修改、分发、二次开发都可以。
