# 放进 WorkBuddy

## 1. 安装服务

```powershell
cd compass
python install.py
```

装完：

| 东西 | 位置 |
|---|---|
| 服务包 | `~/.compass/app/python/compass/` |
| 参考文档 | `~/.compass/app/references/` |
| CLI | `~/.compass/bin/compass.cmd` |
| 数据 | `~/.compass/compass.db` |
| Skill | `~/.workbuddy/skills/compass/SKILL.md` |

## 2. 创建身份

```powershell
& "$env:USERPROFILE\.compass\bin\compass.cmd" init --handle your-name
& "$env:USERPROFILE\.compass\bin\compass.cmd" open
```

`handle` 会出现在看板 URL 里：`http://127.0.0.1:8766/u/your-name`。
PAT 只保存在 `~/.compass/config.json`，不用发给任何人。

## 3. 让 WorkBuddy 认出来

1. 完全退出 WorkBuddy（托盘也要退），再打开。
2. 新建会话。
3. 说「今天要做什么」。如果它去调 `compass check`，说明 skill 生效。

如果没反应：
- 检查 `~/.workbuddy/skills/compass/SKILL.md` 是否存在，frontmatter 的 `name` 是 `compass`。
- 检查里面的入口路径是否指向 `~/.compass/bin/compass.cmd`。
- 重启 WorkBuddy（技能列表有缓存）。

## 4. 服务生命周期

CLI 会自动检查服务；没起就后台拉起来。

```bash
compass status    # 看端口、健康状态、handle
compass start     # 手动启动
compass stop      # 停止
compass serve     # 前台运行（调试用）
```

端口默认 8765；被占用会自动换到 8766、8767……并写回 `~/.compass/config.json`。
**不要手动改端口**，除非你知道自己在做什么——`base_url` 和分享链接都依赖它。

## 5. 每天的自动化（可选）

在 WorkBuddy 里新建自动化，每天 09:00：

```
只执行下面这条命令，把 stdout 原样发给我。
不要分析、不要扩写。

"C:\Users\<你>\.compass\bin\compass.cmd" check
```

这样每天只有几百 token；真要 0 token，用 Windows 计划任务跑同一条命令，
再把输出 POST 到企业微信/钉钉/飞书机器人。

## 6. 公网分享（可选）

默认只监听 `127.0.0.1`，数据不出本机。要让别人打开看板：

```bash
compass serve --host 0.0.0.0 --port 8766
```

并设置环境变量：

```
COMPASS_BASE_URL=https://your-domain.com
```

分享链接才会是公网地址。公网部署前请加反向代理和 HTTPS，并限制写入接口的访问。
分享链接本身只读、不含 PAT，可撤销。

## 7. 常见问题

**python 找不到**
安装器用的是运行 `python install.py` 的那个解释器。WorkBuddy 自带：
`C:\Users\<你>\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
用它跑一次 `install.py` 即可。

**端口被别的程序占了**
CLI 会自动换端口；如果没换，说明那次启动失败，跑 `compass serve` 看报错。

**看板 401**
需要 PAT。用 `compass open` 打开，它会自动带 token 并种 cookie。
分享链接不需要 token。

**旧版（实习罗盘）数据怎么办**
```bash
compass import --from "C:/Users/<你>/Documents/实习罗盘/data"
```
导入画像、自我档案、探索、素材和岗位；岗位状态保留。

**想换 handle**
目前 handle 创建后不可改。换的话新建一个身份、重新导入数据即可。
