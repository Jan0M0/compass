# 发布到 GitHub，然后给她一条指令

## 1. 仓库放什么

把 `compass/` 这个文件夹作为仓库根目录，推到 GitHub。结构应该是：

```
compass/                     ← 仓库根
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── 使用说明.md
├── compass-install.py       ← 单文件安装器（最重要）
├── install.py / install.ps1 / install.bat / open-compass.bat
├── SKILL.md.in
├── python/
├── references/
└── .gitignore
```

`compass-install.py` 已经内嵌了整个包，**她只需要下载这一个文件**，不需要 clone、不需要解压。

## 2. 发布

```bash
cd compass
git init
git add .
git commit -m "Compass v1.0.0"
git tag v1.0.0
git branch -M main
git remote add origin https://github.com/<你的用户名>/compass.git
git push -u origin main --tags
```

**用 tag（`v1.0.0`）而不是 `main` 生成链接**：jsDelivr 和 GitHub 都会缓存，tag 是不可变的，不会因为后续改动导致她装到半成品。

## 3. 发给她 agent 的指令

把下面整段复制给她的 WorkBuddy。**把 `<你的用户名>` 换成你的 GitHub 用户名。**

```text
帮我装一个叫「罗盘 Compass」的本地工具。它不花钱、不联网存我的数据，只在我自己的电脑上跑。

步骤：

1. 先问我一个问题，只问这一个，不要列选项：
   「看板网址用哪个名字？小写英文，比如 xiaoyu。」

2. 用我回答的名字（下面用 xiaoyu 代替），执行这段 PowerShell：

$name = "xiaoyu"
$py = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  $py = "$env:USERPROFILE\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
}
$urls = @(
  "https://ghproxy.net/https://raw.githubusercontent.com/Jan0M0/compass/v1.0.0/compass-install.py",
  "https://cdn.jsdelivr.net/gh/Jan0M0/compass@v1.0.0/compass-install.py",
  "https://raw.githubusercontent.com/Jan0M0/compass/v1.0.0/compass-install.py"
)
$expected = "ea88ec518c98ac84e6500c6515d41fcc4ad4a34757c9d354a8c15042579f3605"
$out = Join-Path $env:TEMP "compass-install.py"
$ok = $false
foreach ($round in 1..2) {
  foreach ($u in $urls) {
    try {
      Invoke-WebRequest -Uri $u -OutFile $out -UseBasicParsing -TimeoutSec 15
      if ((Test-Path $out) -and (Get-Item $out).Length -eq 139890) {
        if ((Get-FileHash $out -Algorithm SHA256).Hash.ToLower() -eq $expected) {
          $ok = $true
          break
        }
      }
    } catch {}
  }
  if ($ok) { break }
}
if (-not $ok) { throw "安装包下载或校验失败，请检查网络后重试" }
& $py $out --handle $name

3. 装完告诉我两件事：看板网址；是否需要重启 WorkBuddy。
4. 重启后我会说「我不知道自己想做什么」。到时候不要列功能菜单，只问我一个具体的问题。
```

## 4. 三个下载地址为什么要都放

国内网络对 GitHub 的可用性不稳定，这三个按顺序试：

| 顺序 | 地址 | 说明 |
|---|---|---|
| 1 | `cdn.jsdelivr.net/gh/...` | 国内通常最快 |
| 2 | `raw.githubusercontent.com/...` | 直连 GitHub |
| 3 | `ghproxy.net/...` | 前两个都失败时的镜像 |

代码里已经判断 `> 50000` 字节才算下载成功，避免把 404 页面当安装包执行。

如果她那边三个都不通（没有代理、GitHub 和 jsDelivr 都被限），再加一个 Gitee 镜像：

```bash
# 在 Gitee 新建仓库后
git remote add gitee https://gitee.com/<你的Gitee用户名>/compass.git
git push gitee main --tags
```

下载地址：

```
https://gitee.com/<你的Gitee用户名>/compass/raw/v1.0.0/compass-install.py
```

把这条加到 `$urls` 的最后即可。

## 5. 验证过什么

- 单文件安装器在干净目录完整跑通：解包 → 安装 → 建身份 → `compass next`
- 三个下载地址当前都可访问（2026-10-22 实测）
- 安装后 skill 写入 `~/.workbuddy/skills/compass/SKILL.md`
- 数据写在 `~/.compass/compass.db`，不经过 GitHub

## 6. 她需要什么

- Windows + WorkBuddy
- 不需要 Python（用 WorkBuddy 自带的）
- 不需要 git、不需要解压、不需要 Node
- 不需要 API key

## 7. 更新版本时

1. 改代码
2. 重新生成单文件：`python build_single.py`
3. 打新 tag：`git tag v1.0.1 && git push origin v1.0.1`
4. 把给她的指令里的 `@v1.0.0` 改成 `@v1.0.1`

不要复用旧 tag。

## 8. 安全说明

- 仓库是公开的，任何人可以看代码；安装器只做解包和写本地文件，不发网络请求、不调模型。
- 她的数据只存在她本机 `~/.compass/`，不会回传到 GitHub 或你的机器。
- 首次安装会从 GitHub/jsDelivr 下载一次代码；之后运行不再联网（岗位雷达除外）。
