# 海外投流素材内容工厂 Agent MVP 设计

## 背景与目标

本系统是一套围绕真实产品/SKU 的 AI Native 内容生产流水线，而不是单次脚本生成工具。MVP 需要先跑通从产品事实沉淀、需求结构化、素材审计、内容生成、最终评估到投放数据反馈的闭环。

第一版目标是可本地运行、可录入真实信息、可保存所有生成与评估记录。AI 能力先使用可运行的 mock provider 输出结构化结果，后续再替换为真实模型 provider。

## MVP 范围

### 包含

- 中文后台界面。
- 中文广告素材输出。
- 产品档案管理：产品基础信息、链接、国家、品类、平台、卖点、活动规则、禁用表达、合规红线。
- 产品资产上传：产品截图、logo、落地页截图、后台截图、历史素材。
- 一句话需求输入，并由 mock AI 转为结构化任务。
- Benchmark 输入与拆解：支持链接、截图说明、脚本文本。
- 素材库管理：真实素材、AI 可补素材、视频工具可生成素材、必须人工补充的红线素材。
- 内容生成流水线：每次生成前强制跑素材评估，每次生成后强制跑最终评估。
- 内容产物：素材方向、10 秒/15 秒/30 秒脚本、旁白、字幕、分镜、Runway Prompt、HeyGen Prompt、ElevenLabs Prompt、Facebook/TikTok 广告文案。
- 投放数据手动录入，并生成下一轮素材迭代建议。
- 所有生成记录、素材评估、最终评估、投放日志保存到数据库。
- README 说明环境变量、运行方式、后续接真实 AI provider 的位置。

### 不包含

- 不接 TikHub、TikTok API、Facebook API。
- 不做多语言输出；MVP 只输出中文，后台也不提供输出语言选择器。
- 不做真实视频生成或第三方视频工具调用，只生成 prompt/brief。
- 不做用户权限、多租户、团队协作。
- 不内置任何 API key。

国家、平台字段仍然保留，用于记录海外投放目标和后续扩展；但第一版所有脚本、旁白、字幕、prompt、广告文案和评估建议都用中文。

## 产品结构

采用「产品档案 + 任务流水线 + 资产/数据沉淀」结构。

### 1. 产品档案 Product Archive

用于沉淀 SKU 的事实和边界，作为所有生成任务的事实来源。

字段：
- 产品名称
- 产品链接
- 国家
- 品类
- 平台
- 卖点
- 活动规则
- 禁用表达
- 合规红线
- 备注

资产：
- 产品截图
- logo
- 落地页截图
- 后台截图
- 历史素材

### 2. 任务工厂 Content Pipeline

这是 MVP 的主工作台。

流程：
1. 用户选择产品。
2. 输入一句话需求。
3. mock AI 生成结构化 Demand Intake。
4. 用户可选择关联素材与 Benchmark。
5. 系统先跑 Material Audit。
6. 若状态为 `PASS` 或 `AUTO_REPAIR`，允许生成内容；若为 `HUMAN_REQUIRED` 或 `FATAL_FAILED`，生成按钮禁用并提示补充动作。
7. 生成内容后，系统自动跑 Evaluation Agent。
8. 内容生成记录、素材评估和最终评估全部保存。

### 3. Benchmark Deconstruction

支持输入视频链接、截图说明或脚本文本。mock AI 输出：
- 开头钩子
- 脚本节奏
- 镜头结构
- 情绪路径
- 卖点表达
- CTA
- 可复用结构

页面需要明确提示：只复刻内容逻辑，不复制具体产品和虚假事实。

### 4. Material Library

用于判断素材是否能支撑视频 brief。

素材字段：
- 类型
- 来源
- 适用产品
- 适用场景
- 是否可复用
- 是否合规
- 素材等级：真实素材、AI 可补素材、视频工具可生成素材、必须人工补充的红线素材
- 文件或外部链接
- 备注

### 5. Material Audit

生成前必须执行。状态包括：
- `PASS`：素材足够，可进入生成。
- `AUTO_REPAIR`：素材有小缺口，可用 AI 或工具补齐。
- `HUMAN_REQUIRED`：缺少包装、logo、界面、活动规则等红线素材，需要人工补充。
- `FATAL_FAILED`：产品事实冲突或存在严重合规风险，禁止生成。

评估维度：
- 产品事实是否准确
- 红线素材是否缺失
- 包装、logo、界面、活动规则是否真实
- 是否存在违规或夸大承诺
- 是否需要人工补素材

### 6. Content Agent

生成内容必须绑定：
- 产品事实
- 结构化需求
- 关联素材
- Benchmark 可复用结构
- 当前 Material Audit 结论

输出：
- 素材方向
- 10 秒脚本
- 15 秒脚本
- 30 秒脚本
- 旁白
- 字幕
- 分镜
- Runway Prompt
- HeyGen Prompt
- ElevenLabs Prompt
- Facebook 广告文案
- TikTok 广告文案

### 7. Evaluation Agent

生成后必须执行，并输出总分 100 分。

评分维度：
- 产品事实准确性：20 分
- 真实性与红线素材：20 分
- 场景与人群匹配：15 分
- 脚本与分镜质量：15 分
- 视频 brief 可执行性：15 分
- 合规与风险：10 分
- 复用价值：5 分

输出：
- 总分
- 各维度得分
- 修改建议
- 失败原因
- 下一步动作

### 8. Ad Performance

第一版支持人工录入每条素材的投放数据。

字段：
- 花费
- 展示
- CPM
- 链接点击
- CTR
- 注册
- 充值
- CPA
- 播放 3 秒
- 播放 50%
- 播放 95%
- 播放 100%

mock AI 根据投放数据输出：
- 当前素材表现判断
- 可能问题
- 下一轮素材迭代方向
- 建议保留、放大、重剪或停用

## 数据模型

MVP 使用 SQLite。建议表：

- `products`
- `product_facts`
- `product_assets`
- `demand_intakes`
- `benchmark_videos`
- `benchmark_deconstructions`
- `material_assets`
- `content_generations`
- `material_audits`
- `evaluation_reports`
- `ad_performance_logs`
- `reusable_patterns`

所有主要表保留：
- `id`
- `created_at`
- `updated_at`

AI 输出字段使用 JSON 存储结构化内容，便于先快速迭代，后续再拆分为更细表结构。

## AI Provider 设计

第一版实现 `MockAIProvider`，提供以下能力：
- `structureDemand(input, productContext)`
- `deconstructBenchmark(input, productContext)`
- `auditMaterials(product, demand, materials)`
- `generateContent(product, demand, materials, benchmarks, audit)`
- `evaluateGeneration(product, demand, generation, audit)`
- `analyzePerformance(generation, performanceLog)`

provider 返回稳定 JSON，保证系统不依赖真实外部 API 也能完整运行。

后续接真实模型时新增 `OpenAIProvider` 或其他 provider，通过环境变量切换：
- `AI_PROVIDER=mock`
- `AI_PROVIDER=openai`
- `OPENAI_API_KEY=...`

代码中不得硬编码 API key。

## 技术建议

使用一个轻量全栈 Web 应用：
- 前端：中文后台 UI，桌面端优先。
- 后端：本地 API 路由处理 CRUD、上传、生成流水线。
- 数据库：SQLite。
- 文件：本地 `uploads/` 目录。
- 配置：`.env`，README 提供 `.env.example`。

具体框架在实现计划中确定，但应优先选择能快速交付 CRUD、上传和 API 路由的一体化方案。

## 错误处理

- 上传失败时保留表单输入并显示错误。
- 生成前若没有产品或需求，禁止执行。
- 素材评估为 `HUMAN_REQUIRED` 或 `FATAL_FAILED` 时禁止内容生成。
- mock provider 结果解析失败时保存失败状态和错误原因。
- 数据保存失败时不得显示为生成成功。

## 测试策略

MVP 至少覆盖：
- 数据库初始化与主要表存在。
- 产品创建。
- 需求结构化。
- 素材评估状态判定。
- `HUMAN_REQUIRED` / `FATAL_FAILED` 阻止内容生成。
- `PASS` / `AUTO_REPAIR` 允许内容生成并自动创建最终评估。
- 投放数据分析记录保存。

## 成功标准

- 用户能创建产品并上传资产。
- 用户能输入一句话需求并得到结构化任务。
- 用户能录入 Benchmark 并生成拆解结果。
- 用户能维护素材库。
- 每次内容生成前都有素材评估记录。
- 每次内容生成后都有最终评估记录。
- 所有记录可在后台查看。
- 用户能录入投放数据并看到下一轮迭代建议。
- 项目 README 能指导本地安装、配置和运行。
