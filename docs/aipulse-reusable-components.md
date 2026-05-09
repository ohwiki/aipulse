# AIpulse 可复用组件 — 从 msgflow 继承

> 以下组件可以直接从 msgflow 仓库复制到 aipulse，保持两个项目的一致性。

## 1. 结构化日志 — logger.py

**来源：** `msgflow/tools/capabilities/logger.py`

**作用：** 统一的 JSON 格式日志，方便 GitHub Actions 中排查问题。

**复制到：** `aipulse/tools/logger.py`

**使用方式：**
```python
from logger import get_logger
log = get_logger("fetch")
log.info("source fetched", extra={"name": "OpenAI Blog", "count": 12})
log.error("fetch failed", extra={"url": "...", "status": 403})
```

## 2. 内容抓取链 — content_fetcher.py

**来源：** `msgflow/tools/capabilities/content_fetcher.py`

**作用：** 当 RSS 的 summary 太短需要抓全文时，用 Jina/Defuddle 获取完整内容。

**复制到：** `aipulse/tools/content_fetcher.py`

**AIpulse 场景：** 打分时如果 RSS description 太短（<100 字），可以调 `fetch(url)` 拿全文再打分，提高打分准确度。

## 3. LLM 调用模式

**来源：** `msgflow/tools/capabilities/ai_runner.py` 的调用模式

**作用：** 调用 MiMo API（OpenAI 兼容格式）进行打分和摘要生成。

**AIpulse 建议实现：**
```python
import requests

def call_llm(prompt: str, model: str = None) -> str:
    """调用 LLM，返回文本响应"""
    api_key = os.environ.get("NULLCLAW_API_KEY")
    base_url = os.environ.get("NULLCLAW_BASE_URL", "https://platform.xiaomimimo.com/v1")
    model = model or os.environ.get("NULLCLAW_MODEL", "mimo-v2.5-pro")

    resp = requests.post(f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1, "max_tokens": 200})
    return resp.json()["choices"][0]["message"]["content"].strip()
```

**注意：** 打分用 `temperature: 0.1`（要稳定），摘要用 `temperature: 0.3`（要自然）。

## 4. GitHub Actions 配置模式

**来源：** `msgflow/.github/workflows/feishu-task.yml` 的 secrets/vars 用法

**AIpulse 需要的 Secrets：**

| Name | 用途 |
|------|------|
| `NULLCLAW_API_KEY` | MiMo API Key（打分+摘要） |
| `NULLCLAW_BASE_URL` | MiMo API 地址 |

**Variables：**

| Name | 用途 | 默认值 |
|------|------|--------|
| `NULLCLAW_MODEL` | 模型名 | `mimo-v2.5-pro` |

可以和 msgflow 共用同一个 MiMo API Key。

## 5. Worker + KV 配置管理（P3 用）

**来源：** `msgflow/worker/` 整套架构

**AIpulse P3 做 API 时：**
- 复用 `lib/config.js` 的 KV 读写 + 脱敏逻辑
- 复用 `lib/log.js` 的结构化日志
- Admin 页面可以简化（AIpulse 配置项少）

**建议：** P3 时直接从 msgflow worker 复制骨架，删掉消息处理相关的 handler，保留 config + admin。

## 6. 日志格式约定（两个项目统一）

```json
{"ts": "2026-05-09T07:00:01Z", "level": "info", "module": "fetch", "msg": "source fetched", "name": "OpenAI Blog", "count": 12}
{"ts": "2026-05-09T07:00:05Z", "level": "error", "module": "score", "msg": "llm call failed", "url": "...", "status": 429}
```

字段：`ts`（ISO 8601）、`level`（info/warning/error）、`module`（哪个脚本）、`msg`（事件描述）、其余为 extra。

## 不需要复用的

| msgflow 组件 | 原因 |
|---|---|
| `pipelines/` 编排层 | AIpulse 流程不同，自己写 |
| `worker/handlers/` 消息处理 | AIpulse 没有聊天消息入口 |
| `skills/` | AIpulse 不用 NullClaw Agent |
| `content-fetch/fetch_weixin.py` | AIpulse 不抓公众号网页 |
