# Compass · 罗盘

**Sapphire Jan 为你们设计的一套职业探索与求职服务。**

零 token：推理发生在使用者自己的 agent 里；Compass 服务只负责 schema、存储、版本、URL 视图和分享，**服务端不调用任何模型**。

> 设计依据：Lawted《Zero-Token Design》——「让用户的 agent 干活，让产品接住结果。」
> 详见 [references/zero-token.md](references/zero-token.md)。

## 它是什么

不是脚本文件夹，是一个**服务**：

```
用户说一句话
   ↓
用户的 agent（WorkBuddy / Claude Code）——解析、判断、写作
   ↓ 调用唯一入口 compass ...
Compass 服务
   ├─ /schema                 字段结构（agent 先读）
   ├─ /api/*                  profile / self / explore / jobs / resume / share
   ├─ PAT 身份                认账凭证，不是 AI 额度
   ├─ SQLite                  数据 + 版本 + 事件
   ├─ /u/{handle}             URL 看板
   ├─ /u/{handle}/explore     探索页
   ├─ /u/{handle}/resume/...  简历版本
   └─ /s/{slug}               只读分享
```

对应课程的四个部件：清晰的数据结构、可靠的 server、agent 可调用的 Skill、值得独立存在的展示界面。

## 她怎么用（不需要部署）

1. 把整个 `compass` 文件夹给她。
2. **Windows：让她双击 `install.bat`，输入一个名字，看板会自动打开。**
3. 如果她用 WorkBuddy 打开文件夹，也可以说：**「装一下罗盘」**。
   agent 会读 `AGENTS.md`，自动完成安装和初始化。
4. 重启一次 WorkBuddy，让 `compass` skill 加载。
5. 之后全程说话：**「我不知道自己想做什么」**。

以后要重新打开看板：双击同目录的 `open-compass.bat`。

### 远程安装（推荐）

把仓库推到 GitHub 后，她不需要下载 zip，也不需要解压。给她 agent 一条指令即可：

```powershell
# agent 执行（示意）
$u = "https://cdn.jsdelivr.net/gh/<user>/compass@v1.0.0/compass-install.py"
$out = Join-Path $env:TEMP "compass-install.py"
Invoke-WebRequest -Uri $u -OutFile $out -UseBasicParsing
python $out --handle xiaoyu
```

完整的发布步骤、三条备用下载地址、可直接复制给 agent 的提示词，见 [`PUBLISH.md`](PUBLISH.md)。

服务跑在她自己的电脑上，数据只在本机。**不需要域名、不需要服务器、不需要 API key。**
只有「把链接发给别人、对方在自己设备上打开」才需要公网——那是可选能力，不是使用前提。

## 快速开始

**前提**：Windows + Python 3.9+（WorkBuddy 自带 Python 也可以）。

```powershell
cd compass
python install.py
```

安装后：

```
~/.compass/app/python/compass/    服务包
~/.compass/app/references/        内容参考
~/.compass/bin/compass.cmd        CLI（agent 的唯一入口）
~/.compass/compass.db             数据（首次运行创建）
~/.workbuddy/skills/compass/      WorkBuddy skill
```

然后：

```powershell
& "$env:USERPROFILE\.compass\bin\compass.cmd" init --handle your-name
& "$env:USERPROFILE\.compass\bin\compass.cmd" open
```

重启 WorkBuddy，让 `compass` skill 生效。之后用户只需说话，agent 调用 `compass ...`。

## 命令

| 目的 | 命令 |
|---|---|
| 一次看全状态 | `compass state` |
| 探索下一步 | `compass next`（返回 stage / question / record） |
| 交接提示词 | `compass handoff prompt` / `compass handoff interview` |
| 导入交接 | `compass handoff import <文件.md>` |
| 认领身份 | `compass init --handle your-name` |
| 写入速查 | `compass schema --brief` |
| 画像 | `compass profile --set name=... --set cities='["杭州"]'` |
| 自我认知 | `compass self --add-interest '{"name":"写作","evidence":"...","energy":"高"}'` |
| 素材库 | `compass stories --add '{"title":"...","bullets":["..."]}'` |
| 探索建议 | `compass explore --suggest` · `--add-suggested` · `--done m_001 --result ...` |
| 岗位雷达 | `compass jobs radar --keyword 产品实习 --city 杭州 --pages 2` |
| 记岗位 | `compass jobs add --json '{...}'` |
| 状态 | `compass jobs advance --id job_xxx --to applied` |
| 打分 | `compass score` |
| 今日待办 | `compass check` |
| 简历 | `compass resume --job job_xxx --style both` |
| 分享 | `compass share --kind dashboard|explore|resume` |
| 打开看板 | `compass open` |
| 导入旧数据 | `compass import --from <旧工作区/data>` |
| 导出 | `compass export` |

## 两个模式

- **探索**：不知道自己要什么 → `compass next` 引导 8 个阶段（能量→优势→反感→价值→约束→方向→实验→复盘），agent 只负责把问题说成人话
- **求职**：方向有了 → 找岗、判断、改简历、投递、跟进

方法论在 `references/`：`career-exploration.md`、`conversation-starters.md`、`missions.md`、`paths.md`、`tone.md`、`handoff-protocol.md`、`resume-design.md`、`resume-rules.md`。

## 交接（handoff）

如果她在别的 AI 里聊过，不需要重新讲一遍：

```bash
compass handoff prompt       # 打印提示词，复制给那个 AI
compass handoff interview    # 对话不多时：先访谈再整理
compass handoff import 交接.md
```

导入会：
- 合并 `profile` 和 `self`（只填空值，不覆盖已有值）
- 给每条打上 `source: handoff`；兴趣/优势默认标 `猜测`
- 报告 `conflicts`：已有值与交接值不同时，让用户决定
- 原始文档存到 `~/.compass/handoffs/`

导入后必须先复述 5 条并确认，不能把上一个 AI 的理解直接当事实。

## 架构细节

### Schema 先行

`compass schema --brief` 是给 agent 的写入速查；完整 schema 在 `compass schema`。
`compass state` 一次返回登录状态、画像缺口、self 计数、实验数、岗位数和看板 URL，避免 agent 连跑七八条命令。
服务端做最低限度的必填校验；未知字段会保留，但不会参与渲染。

### 身份

`compass init` 生成 `cmp_pat_...`，只存在 `~/.compass/config.json`（权限 600）。
它是认账凭证，不是 AI 额度；API 用 `Authorization: Bearer`，视图用 `?token=` 或 cookie。

### 版本

每次 `compass resume` 都会新增一个版本（visual / ats 各自一行）。
旧版本 URL 永久可访问，适合「给不同公司各存一版」。

### 分享

`compass share` 生成 `/s/{slug}`，只读、可撤销、不含 PAT。
分享页会隐藏导航，底部有「只读分享」标识。

### 本机 vs 公网

默认绑定 `127.0.0.1`，数据不出本机。
要给别人看：

```bash
compass serve --host 0.0.0.0 --port 8765
```

并设置 `COMPASS_BASE_URL=https://your-domain`，分享链接才会是公网地址。
公网部署前请加反向代理、HTTPS，并限制写入接口的访问。

## 从旧版迁移

旧版（`实习罗盘/`）的数据是本地 JSON。新服务可以直接导入：

```bash
compass import --from "C:/Users/JanEH/Documents/实习罗盘/data"
```

会导入 profile / self / explore / stories，并逐条导入 jobs（保留状态）。
旧版脚本不再使用，保留只作参考。

## 已验证（2026-10-21）

- 服务启动、健康检查、schema 输出、端口占用自动换端口
- `compass state` 一次返回登录/画像/self/explore/jobs 摘要；`compass next` 状态机按 8 个阶段推进
- PAT 认领、whoami、无 token 访问被拒
- profile / self / explore / stories 读写；schema 校验拒绝错误类型
- 岗位录入、去重、打分、状态流转
- 实习僧雷达（列表 + 详情）在服务内运行
- 今日待办文本
- 简历 visual + ats 双版本、版本号递增、旧版本可访问
- 只读分享链接、分享页隐藏导航
- 旧数据迁移（21 个岗位 + 画像 + 素材）
- 交接：`handoff prompt/interview` 输出提示词；`handoff import` 合并 profile/self、报告冲突、去重、存档原始文档
- 安装器 + `compass.cmd` shim + WorkBuddy skill 生成

## 安全与隐私

- 数据只在本机 `~/.compass/compass.db`
- 服务默认只监听 `127.0.0.1`
- 分享链接不含 PAT，可撤销
- 雷达只访问实习僧公开页面，不登录
- 不自动投递、不替用户给 HR 发消息

## 目录

```
compass/
├── install.py               安装服务、CLI shim、skill
├── SKILL.md.in              WorkBuddy skill 模板
├── python/compass/
│   ├── config.py            路径、端口、配置
│   ├── db.py                SQLite schema 与读写
│   ├── auth.py              PAT / handle / 分享 slug
│   ├── schema.py            对 agent 发布的 schema
│   ├── scoring.py           确定性打分
│   ├── resume.py            简历数据构建 + 视觉版/ATS 版渲染
│   ├── views.py             URL 视图
│   ├── radar.py             实习僧岗位采集
│   ├── server.py            HTTP 服务
│   ├── cli.py               单一 CLI 入口
│   └── templates/           看板、探索页
├── references/              方法论、题库、实验库、简历设计、语气
└── SKILL.md.in
```
