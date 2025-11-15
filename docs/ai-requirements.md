# ZhiYUAI 2.0 — AI 能力与接口需求规范

## 概述
本规范用于对接外部 AI 提供商（API/SDK），指导提供哪些能力、接口形态、性能与可观测性要求，以及在本项目中的接入映射与配置方式。

## MVP 最小能力集（可立即联调）
- 语言检测（LID）：短文本语言码 + 置信度
- 文本机器翻译（NMT）：单条与小批量
- 语音识别（ASR）：文件或流式（二选一亦可先行）
- 语音合成（TTS）：文件或流式（二选一亦可先行）
- 可选：翻译质量评估（QE）若暂无，可先返回占位评分（0~1）以打通接口

## 能力清单（按模块）
- 翻译服务（services/translation）
  - 必需：NMT、LID
  - 建议：QE、Embedding（向量）用于缓存/检索与质量优化、文本增强（纠错/改写/风格）
- 语音交互服务（services/voice-interaction）
  - 必需：ASR、TTS
  - 建议：NLU（意图/实体）、VAD/降噪、说话人分离（Diarization）
- 场景识别服务（services/scene-recognition）
  - 建议：文本/音频场景分类、情感/主题分析
- AI 路由（services/ai-router）
  - 需要各提供商返回可度量的性能/成本指标，便于路由评分（时延/错误率/单次成本等）
- 可选能力
  - OCR/文档理解（截图/文档翻译）
  - 通用 LLM（对话管理/复杂指令/错误恢复建议）

> 已选视觉模型：Qwen3‑VL‑Plus（OpenAI 兼容接口）。参考 docs/providers/qwen3-vl-plus.md。

## 接口形态与协议
- 协议：REST/HTTP 或 gRPC；ASR/TTS 支持 WebSocket / HTTP/2 流式
- 认证：`Authorization: Bearer <token>` 或自定义 `X-API-Key`
- 版本化：建议 `Accept`/`Content-Type` 携带 `application/json; version=v1`
- 幂等性：支持 `Idempotency-Key` 头以防重试副作用（至少 NMT/支付相关）

## 质量、性能与 SLA（目标值）
- 平均响应：翻译/检测/QE < 2s；ASR/TTS 流式首包 < 300ms
- 可用性：≥ 99.9%
- 并发：≥ 1000 QPS（按需要可弹性扩展）
- 多语言：至少中/英/日/韩，后续可扩展

## 可观测性与计费（返回建议）
- Headers/Body 字段建议：
  - `x-request-id`（可回溯）
  - `x-provider-latency-ms`、`x-tokens-used`/`x-characters-used`、`x-cost`、`x-ratelimit-remaining`、`x-ratelimit-reset`
- 统计与错误日志：规范化错误码、重试建议

## 错误规范与重试
- 错误结构建议：
  - `error.code`（枚举：INVALID_ARGUMENT、UNAUTHORIZED、RATE_LIMITED、PROVIDER_UNAVAILABLE、INTERNAL 等）
  - `error.message`（面向开发者）
  - `error.details`（可选：字段/配额/提示）
- 重试策略：
  - 5xx/网络错误：指数退避重试
  - 429：依据 `Retry-After` 或 reset 时间重试

## 配置与环境变量（对齐本项目）
- 全局 AI Key（至少一种可用）
  - `AI_ALIBABA_API_KEY`、`AI_BAIDU_API_KEY`、`AI_AZURE_API_KEY`、`AI_GOOGLE_API_KEY`、`AI_SILICONFLOW_API_KEY`
  - 对应 Endpoint：`AI_ALIBABA_ENDPOINT`、`AI_BAIDU_ENDPOINT`、`AI_AZURE_ENDPOINT` ...
- 网关上游发现（已接入）
  - `VOICE_INTERACTION_URL`、`SCENE_RECOGNITION_URL`、`TRANSLATION_URL`、`AI_ROUTER_URL`、`USER_MANAGEMENT_URL`、`CONFIG_MANAGEMENT_URL`
  - 速率限制：`API_GATEWAY_RATE_LIMIT`

## 请求/响应示例（建议）
- 翻译（NMT）
  - 请求：`POST /translate`  {"text":"你好","source_language":"zh","target_language":"en","mode":"standard"}
  - 响应：{"translated_text":"Hello","confidence":0.98,"quality_score":0.92,"engine":"provider_a","processing_time":1500}
- 语言检测（LID）
  - 请求：`POST /detect-language`  {"text":"こんにちは"}
  - 响应：{"language":"ja","confidence":0.97}
- ASR（文件）
  - 请求：`POST /asr`  multipart/form-data（音频文件 + 采样率/语种）
  - 响应：{"text":"示例识别结果","confidence":0.95,"segments":[...]}
- TTS（文件）
  - 请求：`POST /tts`  {"text":"你好","language":"zh","voice":"female_1","speed":1.0}
  - 响应：{"audio_url":"https://.../audio.wav","duration":3.5}
- QE（可选）
  - 请求：`POST /qe`  {"source":"...","target":"...","source_language":"en","target_language":"zh"}
  - 响应：{"overall_score":0.88,"metrics":{"fluency":0.9,"accuracy":0.87,"adequacy":0.86}}

## 项目接入映射
- services/translation
  - 使用：`NMT`、`LID`、（可选 `QE`、`Embedding`、文本增强）
  - 关键接口：`/translate`、`/quality/assess`、`/engine/select`
- services/voice-interaction
  - 使用：`ASR`、`TTS`、（可选 `NLU`、`VAD/降噪`、`Diarization`）
- services/scene-recognition
  - 使用：文本/音频分类、情感/主题分析
- services/ai-router
  - 聚合：各提供商的延迟/错误率/成本/配额，输出路由决策
- web-app/backend（API 网关）
  - 代理路由：已接入 `/api/translation/translate`，后续补齐 ASR/TTS/场景/路由

## 验收与测试建议
- 健康检查：各服务 `GET /health`；网关 `GET /ready` 聚合上游地址
- 最小联调用例：
  - 翻译链路：`POST /api/translation/translate`（经网关）
  - ASR/TTS（任选其一）
- 压测与限流：提供 429 与剩余额度/重置时间 

## 提供商对接清单（Checklist）
- 能力范围：已覆盖哪些能力（NMT/LID/ASR/TTS/QE/NLU/Embedding/Moderation/...）
- 语种支持：源/目标语言列表；是否支持 AUTO
- 接口清单：路径、方法、字段、错误码、示例
- 性能与配额：延迟区间、QPS 限制、并发/速率、计费单位与成本
- 可观测性：请求 ID、计费/用量、限流头、故障上报
- 安全合规：认证、数据存储/加密、日志脱敏
- 回退与降级：备用模型或低配档；超时/失败重试策略

---

文档维护：由后端架构师与各服务负责人联合维护；能力和接口变化需同步更新。
