# 零 Token 设计说明

> 依据：Lawted《Zero-Token Design》与《Zero Token Design after ChatGPT Work》
> https://www.ha7ch.com/writing/zero-token-design
> https://www.ha7ch.com/writing/zero-token-after-chatgpt-work

## 一句话

**让用户的 agent 干活，让产品接住结果。**

推理归用户的 agent；产品负责 schema、存储、版本、渲染和分发。
产品**不调用任何模型**，但这不等于产品没有后端——恰恰相反，零 token 的前提是有一个可靠的服务端。

## 分工

| 层 | 谁做 | 成本 |
|---|---|---|
| 理解意图（JD、截图、口语需求） | 用户的 agent | 用户自己的 token |
| 判断与写作（值不值得投、简历、招呼语） | 用户的 agent | 用户自己的 token |
| schema 校验、存储、版本、渲染、分享 | Compass 服务 | 0 |
| 抓取岗位（实习僧公开页） | Compass 服务（确定性脚本） | 0 |
| 展示 | Compass 的 URL 视图 | 0 |

## 对应课程的四件套

1. **清晰的数据结构** → `GET /schema` 发布 profile / self / explore / job / resume 的字段结构
2. **可靠的 server** → 本机 `127.0.0.1:8765`（可绑定公网），SQLite 持久化
3. **能被 agent 调用的 Skill/Plugin** → 单一 CLI `compass`；WorkBuddy skill 里只写命令
4. **真正值得独立存在的展示界面** → `/u/{handle}`、`/u/{handle}/explore`、简历版本 URL

## 一次典型调用

```
用户：「帮我把这个岗位记下来」
   ↓
agent：解析 JD → 调 compass jobs add --json '{...}'
   ↓
Compass：schema 校验 → 写入 jobs → 打分 → 返回 job id
   ↓
agent：compass open /u/{handle}
   ↓
用户：浏览器里看到看板
```

简历：

```
agent：compass resume --job job_xxx --style both
Compass：生成 visual + ats 两个版本，存进 resume_versions，返回两个 URL
agent：把 URL 给用户
```

分享：

```
compass share --kind resume --target res_xxx
→ /s/{slug}  只读、可撤销、不含 PAT
```

## 零 token 不等于零后端

这是最容易做错的地方。旧版把「不调模型」误做成了「没有服务端」，退化成
「脚本 + 本地 JSON + 静态 HTML」：没有 URL、没有版本、没有分享、没有身份，
别人拿到要先装 Python、记路径、跑脚本。那不是课程里的产品形态。

正确形态是：

- 产品有一个服务端，负责 schema / DB / 版本 / 渲染 / 分享
- 服务端**不跑推理**
- 用户只说话，agent 调 CLI，产品接住结果并展示

## PAT 是什么

`compass init` 生成的 `cmp_pat_...` 是**认账凭证**：它只用来授权写入这个服务，
不是 AI 额度，不产生任何推理费用，也不应该被发给别人。

## 分发

- 本机：`127.0.0.1`，数据不出本机
- 公网：`compass serve --host 0.0.0.0`，并在配置里设 `COMPASS_BASE_URL`
- 分享：只读链接 `/s/{slug}`，可撤销
- agent 发现：`/schema`、`/.well-known/compass.json`、`/llms.txt`

## Token 账本

- 扫 100 个实习僧岗位：0 token（服务端确定性脚本）
- 给 100 个岗位打分：0 token
- 生成看板/简历 URL：0 token
- 每天问「今天做什么」：0 token（CLI 直接取文本）
- 判断一个岗位 + 改一版简历 + 写招呼语：一次对话，由用户自己的 agent 承担

产品方运行时推理成本：**0**。
