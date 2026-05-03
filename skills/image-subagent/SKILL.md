---
name: image-subagent
description: "Use when the user sends an image (via QQ/Telegram/Discord/file path) or asks to analyze/extract text from an image. Spawns a dedicated subagent with vision+file tools to analyze the image, then uses the result for further action."
version: 1.1.0
author: user
license: MIT
metadata:
  hermes:
    tags: [image, vision, subagent, ocr, analysis]
    related_skills: []
---

# Image Subagent

Spawn a dedicated subagent to handle image processing, freeing the main agent to focus on acting on the results.

## When to Use

- User sends an image attachment (QQ/Telegram/Discord/etc.)
- User provides a local image path (e.g. `/root/screenshot.png`)
- User says "帮我看看这张图" / "识别这张图" / "这张图里有什么"
- User says "帮我把图片上的文字提取出来"
- Any task that involves image analysis + follow-up action

## ⚠️ 重要：Hermes 有内置辅助视觉系统

如果主 agent 用非多模态模型（如 **DeepSeek V4 Flash**），Hermes 会自动在背后用另一个视觉模型把图片转成文字描述，塞进对话里给主 agent 看。

**问题：** 这个辅助视觉模型质量可能不高。
- 把百度地图导航识别为"卡通开车游戏"
- 把泡菜颜色说成"pinkish substance, possibly kimchi"
- 场景描述比较笼统，不适合精确任务

**所以你需要两条视觉通路：**

| | 内置辅助视觉（自动） | 专用图像 agent（手动） |
|--|-------------------|---------------------|
| 触发方式 | 自动，你发图就有 | 需要我主动调用 |
| 模型 | Hermes 内置（不可控） | **MiMo V2-Omni**（独立 key，Token Plan） |
| 质量 | 一般，适合粗看 | 高，适合精确识别 |
| 用途 | 快速判断"这是什么" | OCR、报错截图、细节分析 |

**我的策略：**
- 你随手发图 → 内置辅助视觉看个大概（免费自动的）
- 需要精确识别 → 我调 `analyze_image.sh` 走 MiMo 仔细看
- 重要任务（修 bug、填表、OCR）→ 自动走 MiMo，不依赖辅助视觉

## Flow

```
User sends image
    ↓
Main agent receives MEDIA:/path/image.png (or file path)
    ↓
Spawn subagent with:
  - toolsets=["vision", "file"]
  - context containing image path + what to analyze
    ↓
Subagent analyzes image (vision_analyze, read result)
    ↓
Returns text analysis (description, OCR text, findings)
    ↓
Main agent uses the analysis to act
```

## 两种模式

### 模式 A：原生 delegate_task（继承主 agent 的 API key）

子 agent 继承我的模型和 key，适合不需要换模型的场景。

```python
delegate_task(
    goal="分析这张图片，提取所有有用信息",
    context=f"图片路径: {image_path}\n用户要求: {user_request}\n\n" +
            "请使用 vision_analyze 工具仔细查看图片内容。\n" +
            "输出结构化的分析结果，包括：\n" +
            "1. 图片内容描述\n" +
            "2. 识别出的文字（如果有）\n" +
            "3. 关键元素的位置\n" +
            "4. 其他发现",
    toolsets=["vision", "file"]
)
```

### 模式 B：独立进程 + 单独 API key（推荐）

主 agent 用便宜模型（如 DeepSeek），图像 agent 用独立的高质量视觉模型（如 GPT-4o / Gemini / Claude），各走各的 key。

**脚本位置：** `scripts/analyze_image.sh`

用法：
```bash
# 设置视觉模型的 API key 和模型
export VISION_API_KEY=sk-xxx          # 你的视觉模型 API key
export VISION_PROVIDER=openai         # openai / openrouter / google / anthropic
export VISION_MODEL=gpt-4o            # 任意视觉模型

# 分析图片
bash /root/.hermes/skills/devops/image-subagent/scripts/analyze_image.sh \
  /root/screenshot.png \
  "分析这张图片里的错误信息"
```

或者在脚本里直接修改配置区（永久生效）：
```bash
# 编辑 ~/.hermes/skills/devops/image-subagent/scripts/analyze_image.sh
# 找到 "配置区" 部分，填入默认值
VISION_API_KEY=sk-xxx
VISION_PROVIDER=openai
VISION_MODEL=gpt-4o
```

**自动流程（我执行）：**
```
你发图 → 我调用 analyze_image.sh（走独立 key+模型）
       → 拿到分析结果
       → 用结果干活（修 bug / 搜方案 / 填表单）
```

### 使用结果

## Common Patterns

### OCR + 搜索
```
看图提取错误信息 → 搜解决方案 → 告诉用户怎么修
```

### OCR + 填表
```
看身份证照片 → 提取姓名/号码 → 打开网页填表
```

### 截图分析
```
看UI截图 → 描述布局 → 写对应的前端代码
```

### 多图对比
```
看两张截图 → 对比差异 → 报告不同之处
```

## 🔑 凭证管理：MiMo 的两种认证途径

当你发图时，Hermes 实际有 **两个独立使用 MiMo 的途径**，各自从不同位置读取 API key：

| 途径 | 触发方式 | 从哪读 key | 用途 |
|------|---------|-----------|------|
| **辅助视觉 (auxiliary vision)** | 你发图，自动触发 | `config.yaml` → `auxiliary.vision.api_key` | 幕后分析，结果自动塞进对话 |
| **独立进程** (`analyze_image.sh`) | 我手动调用脚本 | 脚本内 `VISION_API_KEY` 变量 | spawn 独立 Hermes 进程看细节 |

**更新 key 时必须同时更新所有位置：**
1. `config.yaml` → `auxiliary.vision.api_key` 字段（`hermes config edit` 或 patch）
2. `analyze_image.sh` → 脚本内 `VISION_API_KEY` 配置区
3. agent memory（`memory` tool 更新）

**辅助视觉 vs 独立进程的认证差异：**
- 辅助视觉读的是 `config.yaml` 里的 `auxiliary.vision.api_key`，不依赖环境变量
- `hermes chat --provider xiaomi` 读的是 `$XIAOMI_API_KEY` 环境变量（来自 `.env` 或 export），**不是** config 里的 auxiliary key
- 所以如果 `hermes chat --provider xiaomi` 报 401，检查 `.env` 里有没有 `XIAOMI_API_KEY` 或手动 export 环境变量

### ⚠️ MiMo Token Plan vs 标准 API 的区别

MiMo 有 **两套独立 API**，key 不能混用，endpoint 不同：

| | Token Plan（订阅制） | 标准 API（按量付费） |
|--|-------------------|-------------------|
| Key 前缀 | `tp-xxxxx` | `sk-xxxxx` |
| Base URL | `https://token-plan-cn.xiaomimimo.com/v1` | `https://api.xiaomimimo.com/v1` |
| Auth header | `Authorization: Bearer` 或 `api-key` | `Authorization: Bearer` 或 `api-key` |
| 可用模型 | `mimo-v2-omni`, `mimo-v2-pro`, `mimo-v2.5`, `mimo-v2.5-pro` | `mimo-v2.5-omni`, `mimo-v2.5-pro`, ... |

**必知：** 如果用 `tp-` 前缀的 Token Plan key 去调 `api.xiaomimimo.com/v1`，必返回 401。必须换成 Token Plan 专用 endpoint。

### 检查 key 是否有效

```bash
# Token Plan 测试（tp- 前缀 key）
curl -s -w "\n%{http_code}" https://token-plan-cn.xiaomimimo.com/v1/chat/completions \
  -H "Authorization: Bearer tp-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"mimo-v2-omni","messages":[{"role":"user","content":[{"type":"text","text":"hi"}]}]}'

# 标准 API 测试（sk- 前缀 key）
curl -s -w "\n%{http_code}" https://api.xiaomimimo.com/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"mimo-v2.5-omni","messages":[{"role":"user","content":[{"type":"text","text":"hi"}]}]}'
```

**401 排查流程：**
1. key 是 `tp-` 还是 `sk-` 开头？
2. endpoint 是否匹配 key 类型？（`tp-` → `token-plan-cn.*`，`sk-` → `api.*`）
3. 如果 key 类型和 endpoint 匹配但仍然 401 → 去 https://platform.xiaomimimo.com 后台检查 key 状态、订阅是否过期、余额是否充足
4. 后台需要登录小米账号，在"控制台→API Keys"查看

## Tips

- **模式 B 可以独立配任何模型+key**，主 agent 用 DeepSeek 省钱，视觉 agent 用 GPT-4o/Gemini 看图
- 脚本每次创建临时独立目录，不污染主 agent 的 session 和 config
- Subagent 只有 vision + file 工具，没有 terminal 权限，安全
- Subagent 结果可能不准确（自报告），重要信息我会 double-check
- 图片路径必须是本地可访问的绝对路径
- QQ 发来的 MEDIA 路径可直接用

## Example

User: "帮我看这个报错"
Image: [401 error screenshot]

→ spawn image-subagent
→ subagent: "图片显示 HTTP 401 Unauthorized, URL: /api/users, 时间: 2026-05-03"
→ main agent: 排查后端认证中间件，发现 token 过期，修复
→ 回复用户: "token过期了，已刷新，你再试试"
