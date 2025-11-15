# ZhiYUAI 用户端（Flutter）产品设计文档

## 1. 产品概述
- 名称：ZhiYUAI 用户端（Flutter）
- 目标：提供跨平台（iOS/Android）的一站式“即说即译/即输即译”体验，覆盖文本翻译、语音对话翻译、历史与多引擎可视化。
- 价值：低门槛、低延迟、多引擎高质量翻译；与现有微服务（语音交互、翻译、AI 路由等）无缝集成，支持企业级扩展与监控。

## 2. 用户与使用场景
- 目标用户：出境旅行者、跨国协作职场用户、跨语言客服与导购、语言学习者。
- 关键场景：
  - 快捷文本翻译：双语输入输出、复制/分享、术语表支持。
  - 语音同传：一键录音→识别→翻译→合成播放，支持自动语种检测。
  - 对话模式：按会话维度管理双向交互，记录历史、提供建议回复。
  - 引擎洞察：展示各翻译引擎可用性、响应时间、质量评分等，供用户选择。
  - 历史与收藏：会话维度查看翻译历史，标星、搜索、离线缓存。

## 3. 范围界定
- MVP：文本翻译、语音识别/翻译/合成、语言选择、引擎状态查看、历史列表、基础设置（语音、语言、质量与速度偏好）。
- 非 MVP（迭代）：账号体系（OAuth/JWT）、支付订阅、团队共享词库、图片/文档翻译、复杂场景识别联动。

## 4. 核心功能需求
### 4.1 文本翻译
- 输入文本、选择源/目标语（默认自动检测→默认目标语），展示译文、质量分、置信度、引擎信息与备选译文。
- 批量翻译（粘贴多段或选中文档片段）与进度反馈。

### 4.2 语音同传
- 一键录音（16k Linear PCM/WAV），上传识别→获取识别文本→翻译→TTS 播放，全链路可视化（进度/错误）。
- 上传本地音频文件识别；TTS 语速/音色/音调可调。

### 4.3 会话与历史
- 创建会话、会话内对话记录列表（气泡流），支持标星、搜索、再次复制/播放。
- 拉取服务端历史（按 `session_id`）并本地缓存。

### 4.4 引擎与语言
- 拉取支持语言列表；展示引擎状态与性能；可设首选引擎与模式（标准/专业/快速等）。

### 4.5 设置与偏好
- 默认目标语、语音播放偏好（音色/语速/音量）、缓存与离线策略、网络与超时策略。

### 4.6 错误与重试
- 请求超时/失败的反馈与重试；离线队列；回退策略（切换备用引擎/关闭质量评估）。

## 5. 非功能需求
- 性能：文本翻译平均 < 800ms，端到端语音 < 2.0s（网络良好）；主线程无卡顿。
- 兼容性：Android 7.0+/iOS 13+；中英日等主要语言良好展示。
- 安全：HTTPS、敏感日志脱敏；后续对接 JWT/OAuth；音频与翻译缓存受用户控制。
- 可观测性：基础使用埋点（本地可关），错误上报（用户同意后）与网络指标收集。
- 无障碍：字体缩放适配、语音播报、色彩对比。

## 6. 服务对接与接口映射（依据现有后端）
> 端口参考：默认配置 `host=0.0.0.0, port=8000`；翻译服务在 `8002`，AI 路由在 `8003`，语音交互在 `8000`（详见各服务 main.py）。

### 6.1 语音交互服务（Voice Interaction，:8000）
- 创建会话：`POST /session/create` → `{ session_id }`
- ASR（JSON/Base64）：`POST /voice/recognize`（`audio_data`, `audio_format`, `language?`, `session_id?`）
- ASR（文件上传）：`POST /voice/recognize/upload`（`UploadFile` + `language?` + `session_id?`）
- TTS：`POST /voice/synthesize`（`text`, `language`, `voice_type`, `speed`, `pitch`, `volume`, `audio_format`, `session_id?`）
- 对话处理：`POST /dialogue/process`（会话内意图解析与应答，MVP 可暂缓）

### 6.2 翻译服务（Translation，:8002）
- 文本翻译：`POST /translate`
- 批量翻译：`POST /translate/batch`
- 质量评估：`POST /quality/assess`
- 引擎选择：`POST /engine/select`
- 历史：`GET /history/{session_id}`
- 引擎状态：`GET /engines/status`
- 支持语言：`GET /languages/supported`

### 6.3 AI 路由（AI Router，:8003）
- 路由 ASR/翻译/TTS：`POST /route/*`（MVP 可不对接，后续切换为统一入口）

### 6.4 网关/端口与环境
- README 与代码端口存在差异，Flutter 端采用“API Gateway Base + 服务直连 Base URL 备选”的配置策略，通过环境切换；默认直连服务端口，未来接入网关时仅需改配置。

## 7. 客户端架构（Flutter）
### 7.1 分层与状态
- 表现层：Flutter UI（Material 3 + 自适应布局）
- 状态管理：Riverpod（或 Bloc，优先 Riverpod 简洁）
- 领域层：UseCase（翻译、ASR、TTS、会话管理）
- 数据层：Repository（TranslationRepo、VoiceRepo）+ 数据源（REST via Dio）

### 7.2 关键依赖
- 网络：`dio`（拦截器、重试、日志）
- 状态：`flutter_riverpod`
- 路由：`go_router`
- 模型：`freezed` + `json_serializable`
- 音频：录音 `record` 或 `flutter_sound`（16k WAV/PCM），播放 `just_audio`
- 权限：`permission_handler`
- 存储：`hive` 或 `isar`；偏好 `shared_preferences`
- 工具：`path_provider`、`file_picker`、`connectivity_plus`

### 7.3 数据流
- 语音：录音→WAV/PCM(16k)→Base64→ASR→文本→翻译→TTS→播放
- 文本：文本输入→翻译→展示→可按需 TTS
- 会话：首次创建 `session_id` 并贯穿 ASR/TTS/翻译与历史查询

## 8. 信息架构与导航
- 入口/引导：选择默认目标语言与语音偏好（可跳过）
- 底部导航：翻译（文本）｜对话（语音）｜历史｜设置
- 页面：
  - 文本翻译页：输入、语种切换、译文卡片、复制分享、引擎与质量标签、批量入口
  - 语音对话页：录音按钮、实时报文卡片、进度/错误提示、合成播放
  - 历史页：按会话/时间展示、标星/搜索、详情页显示完整上下文
  - 设置页：语言/引擎/语音偏好、缓存与网络策略、关于/诊断

## 9. 数据模型（Dart 映射要点）
- TranslationRequest/Response、BatchTranslation、QualityAssessment、EngineSelection 与后端字段一致（语言/引擎枚举对齐）。
- ASRRequest/Response：`audio_data` Base64、`audio_format` 枚举、`sample_rate=16000`。
- TTSRequest/Response：兼容 `audio_url` 与 `audio_data`；优先 `audio_url`，无则解码 Base64 播放。
- 会话对象：保存 `session_id`，本地缓存与服务端历史打通。

## 10. 本地缓存与离线
- 缓存：成功翻译结果（hash-key）与会话历史元信息本地保存；容量/TTL 可配置。
- 离线队列：网络不可用时记录请求（文本/小音频），网络恢复后自动补发（提示用户可手动控制）。
- 隐私：音频缓存默认关闭；用户显式开启后仅在本机保留、可一键清空。

## 11. 错误与重试策略
- 网络错误/超时（如 >10s）分级提示；自动重试 1–2 次（指数退避）；必要时回退至备用引擎或关闭质量评估。
- ASR 上传失败提供“保存为文件并重试/切换上传接口（表单 vs JSON）”。

## 12. 安全与合规
- HTTPS 与证书校验；敏感参数仅内存持有；日志脱敏（隐藏 API Key、用户标识与音频内容）。
- 未来对接 JWT（对齐即将上线的用户管理服务）；支持匿名会话模式。

## 13. 配置与环境
- 构建风味：`dev/staging/prod`（不同 Base URL、日志级别与开关）
- 配置项：`VOICE_BASE_URL`、`TRANSLATION_BASE_URL`、`GATEWAY_BASE_URL?`、超时阈值、重试策略、是否允许离线缓存与音频缓存
- 后端对齐（本地开发示例）：
  - 语音交互：`http://localhost:8000`
  - 翻译服务：`http://localhost:8002`
  - AI 路由：`http://localhost:8003`

## 14. 测试计划
- 单元测试：模型序列化、Repository 与 UseCase（Mock 服务端）
- 组件测试：翻译页/对话页交互流程（假数据）
- 集成测试：录音→ASR→翻译→TTS 闭环（本地服务）
- 视觉回归：主要 UI 的 golden test
- 性能测试：首帧时间、录音到播放耗时、列表流畅度

## 15. 性能与体验优化
- 音频：录音端降噪参数、16k 采样直出避免转码；音频上传分片（后续）。
- 网络：Dio 连接池、HTTP/2、GZip；关键请求超时/重试拦截器。
- UI：骨架屏/占位、渐进加载、后台保持录音安全策略。

## 16. 可运维性
- 诊断页：展示健康检查结果（`/health`/`/ready`）、服务端延迟与错误比、当前引擎路由。
- 日志导出：本地日志打包（用户同意后），便于排障。
- 版本信息：与后端版本对齐（`shared/common/config.py` 中 `app_version` 可透传）。

## 17. 路线图
- MVP（2–3 周）：文本翻译、语音同传（ASR→翻译→TTS）、会话与历史、语言与引擎配置、基础缓存与错误处理。
- 迭代 1：账号体系与 JWT、同步收藏/偏好、统一网关接入、引擎智能路由（AI Router）。
- 迭代 2：图片/文档翻译、团队词库、场景识别联动、自定义工作流（批量/回调）。
- 迭代 3：性能专项、A/B 测试与质量闭环、端上个性化模型（VAD/关键词）。

## 18. 主要风险与对策
- 端口/网关不一致：以环境配置管理，支持服务直连与网关两套地址。
- iOS 音频权限与后台策略：完善权限文案与前后台切换逻辑。
- 大音频上传：提供表单上传与断点续传预留（后端准备后启用）。
- 引擎可用性波动：前端引擎状态缓存与自动降级/切换。

## 19. 验收标准（MVP）
- 文本翻译与语音同传闭环可用，失败可重试；平均耗时达标。
- 历史可拉取、可本地缓存与搜索；会话可创建和复用。
- 引擎状态可视化与语言列表正常展示；设置页面生效。
- 基础测试通过（单元/组件/集成），无明显 UI 卡顿与崩溃。

---

> 附：后端接口细节参考代码：
> - `services/voice-interaction/main.py`
> - `services/translation/main.py`
> - `services/ai-router/main.py`
> - 统一配置：`shared/common/config.py`

