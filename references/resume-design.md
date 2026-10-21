# 简历设计规范（视觉版 + ATS 版）

## 设计签名

这套版式来自一份实际投递过的简历，不是模板市场里的通用样式。特征是：

- **A4 单页**，页边距 12mm × 15mm
- **姓名居中、26pt、字距 3px**，下面一行定位（岗位 · 专业 · 年级）
- **联系方式一行**，城市 | 电话 | 邮箱 | 作品链接，细竖线分隔
- **概述居中**，2–3 行，不用「本人性格开朗」这类空话
- **双栏 3:2**：
  - 左栏：教育 → 当前方向 → 项目经历 → 业务接触
  - 右栏：核心能力 → 技能 → 工具链 → 作品链接 → 语言
- **章节标题**：小字号、大写、加字距、深蓝下划线
- **单一强调色**：深蓝 `#1b3a5c`，主文字 `#0d1b2a`，不用第二种颜色
- **标签**：当前方向用深色实心标签，核心能力用浅色标签
- **项目 bullet**：`▸` 前缀，动词开头，一条一行，不换行成三行
- **打印 CSS**：`@page A4`，去背景，保留颜色

## 两个版本，用途不同

| 版本 | 文件 | 用在哪儿 |
|---|---|---|
| **视觉版** | `resume_<id>_visual.html` | 发给 HR、微信附件、打印、面试带去 |
| **ATS 版** | `resume_<id>_ats.html` | 网申系统、招聘平台解析、需要机器读简历的地方 |

ATS 版故意做丑：单栏、无颜色、无标签、无图标、标准标题。**别拿 ATS 版发给 HR。**

## 生成

```bash
compass resume --job job_xxx            # 默认视觉版
compass resume --job job_xxx --style ats
compass resume --job job_xxx --style both
compass resume --job job_xxx --data resume_data.json --style both
```

服务会保存每一版（visual / ats 各自一个版本），返回可访问的 URL。
改内容：拿 `compass jobs show --id <id>` 的数据改好，用 `--data` 重新发布，会生成新版本。

## resume_data 结构

```json
{
  "job_id": "job_xxx",
  "lang": "zh",
  "headline": "产品实习生 · 市场营销 · 大二",
  "summary": "两到三行，讲清你是谁、做过什么、能到岗多久。",
  "education": {
    "school": "宁波工程学院",
    "college": "统计与数据科学学院",
    "period": "2025 – 2029",
    "major": "应用统计学",
    "note": "CET-6"
  },
  "focus": ["AI 产品", "内容运营", "数据分析"],
  "projects": [
    {
      "name": "校园二手交易小程序运营",
      "role": "课程项目 · 内容与用户运营",
      "bullets": [
        "调研 42 名同学，整理 5 类高频需求，写成 8 页需求文档",
        "运营小红书账号，18 篇笔记累计 1.2 万浏览，带来 60+ 试用"
      ]
    }
  ],
  "business_exposure": [],
  "competencies": ["用户调研", "内容策划", "Excel", "沟通"],
  "skill_groups": [
    {"category": "数据", "text": "Excel · SQL · Pandas"},
    {"category": "内容", "text": "小红书 · 文案 · 剪映"}
  ],
  "toolchain": ["Excel", "Figma", "剪映"],
  "links": {
    "title": "作品与链接",
    "items": ["小红书账号：..."],
    "url": "github.com/..."
  },
  "languages": [
    {"name": "English", "level": "CET-6"},
    {"name": "Español", "level": "A1 学习中"}
  ],
  "section_titles": {}
}
```

- `skill_groups` 为空时，右栏会把 `competencies` 显示成「技能」标签。
- `lang: "en"` 时章节标题自动切英文。
- `section_titles` 可以覆盖任何标题。
- 旧版 `experiences` / `skills` 结构会自动兼容。

## 一页纸纪律

- 项目最多 5 个；超过就合并或删。
- 每个项目最多 3 条 bullet；第 4 条通常是凑数。
- 一条 bullet 控制在 1–2 行；超过就拆成两条或删掉细节。
- 大二没有实习，就把课程项目、社团、比赛、兼职放在「项目经历」，不要硬编「实习经历」。
- 排完打开浏览器打印预览；出现第二页就删，不要缩字号到 7pt 以下。

## 内容红线

1. **不编造**。每个事实都要能在 `profile.json` / `stories.json` 里找到出处。
2. **不写「精通」**，除非能当场演示。
3. **不写空话**：性格开朗、学习能力强、吃苦耐劳——全部删掉。
4. **数字优先**：人数、篇数、阅读量、时长、金额、百分比。没有数字就写产出。
5. **动词开头**：调研、搭建、运营、整理、对接、分析、跑通。
6. **和 JD 对齐**：JD 里的关键词，能在经历里找到对应的就往前放；找不到就不硬塞。

## 打印成 PDF

浏览器打开 HTML → `Ctrl+P`：

- 纸张：A4
- 边距：默认（页面 CSS 已经设好）
- 缩放：100%
- 勾选「背景图形 / Background graphics」，否则标签底色会消失
- 另存为 PDF

## 参考过的 skill

| Skill | 借了什么 | 为什么没直接装 |
|---|---|---|
| `resume-modern` | 双栏 3:2、单 accent、print CSS | 版式不如这份成熟，且用 Tailwind 风格 |
| `chasen-liao/resume-skills@resume-builder` | **视觉版 + ATS 双输出**的思路、内容契约 | 依赖它的运行时和模板，会和现有版式冲突 |
| `paramchoudhary/resumeskills` | JD 关键词对齐、bullet 量化 | 面向英文 ATS，中文场景要重写 |
| `suzheng/k2f@k2f-resume` | 先写 content_and_design 再排版 | K2F 包太重，不适合一个 skill 内嵌 |
| `tw93/kami` | 纸张质感和排版克制 | 更适合报告/文档，不是简历 |

结论：**版式用这份，内容规则自己写，双输出模式借鉴。**
