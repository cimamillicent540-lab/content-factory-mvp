# 海外投流素材内容工厂 / Content Factory

这是一个本地可运行的海外投流素材内容工厂 MVP。当前版本使用 `MockAIProvider`，不调用任何外部 API，也不需要 API key。它用于验证核心流程：输入素材需求，进行需求结构化、红线审核、多语言素材生成、100 分评分、投放分析，并把记录保存到 SQLite。

## Internal MVP status

当前版本是内部 MVP release pack，用于内部投手、素材负责人、剪辑 / AI 视频制作人员和项目负责人演示、验收和培训。它不是客户自助 SaaS，不包含登录、客户权限、客户 Dashboard、部署配置、Supabase 或 Cloudflare 集成。

已覆盖核心内部工作流：Product Profile → 生成素材 → Creative ID → Creative Brief → Media Buyer Launch Brief → 广告上线命名 → CSV 复盘 → Saved Performance Report → Next Round Recommendations → Next Round Creative Brief Request。

## Quick start

Mock 模式适合本地演示和测试：

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock python3 -m content_factory.api --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

## Internal workflow routes

- `/`：Generate Creatives，本地素材生成工作台。
- `/history`：Generation History，查看生成记录和 BLOCKED 记录。
- `/performance`：Performance CSV Analyzer，粘贴广告 CSV 并保存复盘报告。
- `/performance/history`：Performance Reports，查看保存的 CSV 复盘。
- `/performance/history/{report_id}`：Performance Report Detail，查看 Next Round Recommendations 和 Next Round Creative Brief Request。

## Operator Guide

- [Internal Operator Guide](docs/internal_operator_guide.md)
- [MVP Smoke Test Checklist](docs/mvp_smoke_test_checklist.md)

## Testing commands

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m unittest discover -v

PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m compileall content_factory tests
```

## Real OpenAI mode warning

OpenAI 模式只用于真实 LLM 接入测试，需要本地环境变量 `OPENAI_API_KEY` 和可用模型配置。不要把真实 API key 写入代码、测试、README 或提交记录。自动化测试默认使用 mock / fake client，不访问真实 OpenAI API。

## 当前能力

- 需求结构化：把一组素材需求字段整理成结构化任务。
- 红线审核/阻断：命中禁用表达或素材合规问题时返回 `BLOCKED`，保存阻断原因，不生成正式素材内容。
- 多语言素材生成：正式广告脚本、字幕、旁白、广告文案、视频 Prompt 会根据 `language` 参数输出。
- 100 分评分报告：按产品事实、真实性、场景匹配、脚本质量、可执行性、合规风险、复用价值评分。
- 投放分析建议：根据 CTR、CPA、播放 3 秒、播放 50% 等数据输出下一轮迭代建议。
- SQLite 保存与按 id 查询：生成记录、审核记录、评分报告、投放反馈都会保存。
- CLI：支持命令行直接跑完整流程。
- HTTP API：支持外部系统通过接口调用。
- Web UI：支持浏览器填写素材需求并查看结构化 JSON 结果。

## 版本说明

当前是 mock provider 版本：

- 不调用 OpenAI、TikTok、Facebook、TikHub 或任何外部 API。
- 不读取真实 API key。
- 所有素材生成结果来自本地确定性规则，方便测试流程和数据结构。

后续替换真实 LLM Provider 时，建议新增一个 provider 类，实现与 `MockAIProvider` 相同的方法：

- `structure_demand(raw_input, product_context)`
- `deconstruct_benchmark(benchmark_input, product_context)`
- `audit_materials(product, demand, materials)`
- `generate_content(product, demand, materials, benchmarks, audit)`
- `evaluate_generation(product, demand, generation, audit)`
- `analyze_performance(generation, performance_log)`

再通过环境变量切换，例如：

```bash
CONTENT_FACTORY_PROVIDER=openai
OPENAI_API_KEY=你的真实密钥
```

不要把任何 API key 写死在代码里。

## 多语言素材逻辑

JSON 字段名、评分报告、投放分析建议、红线阻断原因可以继续使用中文，方便内部审核和运营查看。

正式素材内容字段统一为：

```json
{
  "素材内容": {}
}
```

其中正式广告脚本、字幕、旁白、广告文案、视频 Prompt 会根据 `language` 参数输出：

- `language=pt-BR` / `巴西葡萄牙语` / `Portuguese-BR`：输出巴西葡萄牙语素材。
- `language=es` / `西班牙语` / `Spanish`：输出西班牙语素材。
- `language=en` / `英语` / `English`：输出英语素材。
- `language=zh` / `中文` / `Chinese`：输出中文素材，用于测试或内部辅助。

红线阻断时返回 `BLOCKED`，不会返回正式 `素材内容`。

## Mock 输出结构

Mock 模式用于本地开发和测试，不调用真实 OpenAI API。正常生成时，`素材内容` 会返回稳定结构：

- `campaign_summary`：产品、国家、平台、目标人群、投放语言、核心卖点和风险提醒。
- `video_ad_concepts`：5 套短视频广告方案，每套包含 hook、15 秒脚本、旁白、字幕、Runway prompt、ElevenLabs prompt、Facebook primary text / headline / description 和合规说明。
- `scoring_report`：hook、清晰度、信任感、合规、本地化和转化潜力评分，以及总分和优化建议。
- `media_production_notes`：Runway、ElevenLabs、字幕节奏、首 3 秒和 A/B 测试建议。
- `launch_plan`：优先测试方案、受众角度和初始观察指标。
- `forbidden_claims_check`：禁用表达命中情况、风险说明和替代表达建议。

命中收益保证、无风险或快速致富类红线表达时，接口返回 `BLOCKED`，不生成 `video_ad_concepts`，并保存中文阻断原因和替代表达建议。

## CLI 运行

```bash
python3 -m content_factory.cli \
  --industry "交易所" \
  --product "加密货币跟单产品" \
  --platform "Facebook" \
  --country "巴西" \
  --language "pt-BR" \
  --audience "新用户" \
  --selling-points "注册奖励、跟单、快速开始" \
  --duration "15秒"
```

正常返回会包含：

- `generation_id`
- `结构化需求`
- `红线审核结果`
- `素材内容`
- `100分评分报告`
- `投放分析建议`

如果命中红线，例如需求中包含 `保证收益` 或 `稳赚`，会返回 `BLOCKED` 和 `阻断原因`，不会生成正式素材内容。

## HTTP API 运行

启动服务：

```bash
python3 -m content_factory.api --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl -i http://127.0.0.1:8000/health
```

生成素材：

```bash
curl -i -X POST http://127.0.0.1:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "行业": "交易所",
    "产品": "加密货币跟单产品",
    "投放平台": "Facebook",
    "国家": "巴西",
    "语言": "pt-BR",
    "目标人群": "新用户",
    "卖点": "注册奖励、跟单、快速开始",
    "活动规则": "新人完成注册可参与活动",
    "限制词": "稳赚，保证收益，官方背书",
    "需求": "给Facebook巴西新用户做一条15秒注册转化素材",
    "素材": [
      {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
      {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
      {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1}
    ]
  }'
```

查询生成记录：

```bash
curl -i http://127.0.0.1:8000/generations/1
```

录入投放反馈：

```bash
curl -i -X POST http://127.0.0.1:8000/generations/1/feedback \
  -H 'Content-Type: application/json' \
  -d '{"ctr": 0.8, "cpa": 20, "play_3s": 1000, "play_50": 300}'
```

## API 接口

- `GET /`：返回最小本地 Web UI。
- `GET /health`：返回服务健康状态。
- `POST /generate`：运行完整素材生成流程。
- `GET /generations/{id}`：按 id 查询生成结果。
- `POST /generations/{id}/feedback`：保存投放数据并返回分析建议。

## Web UI

启动 API 后，在浏览器打开：

```text
http://127.0.0.1:8000/
```

页面字段包括：

- 行业 `industry`
- 产品 `product`
- 平台 `platform`
- 国家 `country`
- 语言 `language`
- 人群 `audience`
- 卖点 `selling_points`
- 时长 `duration`
- 限制词/红线词 `restrictions`
- 自定义需求 `demand`

点击生成后，页面会调用 `POST /generate`，展示中文字段名的结构化 JSON；其中 `素材内容` 会按 `language` 输出对应语言。

## Creative Brief Export

当 Web UI 返回 `GENERATED` 结果时，页面会在素材卡片、Prompt、Facebook Ads 文案和评估区之后展示 `Creative Brief Markdown` 区域。

这个区域会把当前生成结果整理成可复制的 Markdown Brief，包含 campaign summary、5 套 creative concepts、scoring report、media production notes、launch plan 和 forbidden claims check。它可以直接分享给素材制作团队、media buyer 或客户，用于后续剪辑、配音、视频工具生成和投放沟通。

页面提供 `Copy Full Brief` 按钮；如果浏览器复制权限不可用，也可以在 textarea 中手动全选复制。

当结果为 `BLOCKED` 时，页面不会生成 Creative Brief。BLOCKED 页面只展示阻断原因、风险、替代表达、下一步动作、结构化需求和 Raw JSON，避免把未通过红线审核的内容包装成交付 Brief。

Raw JSON 仍然保留在页面底部，方便调试、对接和复核完整结构。

## Generation History

本地 Web UI 会把生成结果保存到 SQLite。打开 `/history` 可以查看最近的本地 generation 记录，包括 GENERATED 素材包和 BLOCKED 红线阻断记录。

列表页会展示 generation id、状态、创建时间、行业、产品、平台、国家、语言、素材概念数量和是否 BLOCKED。每条记录都提供 View 链接进入详情页。

GENERATED 详情页会展示可复制的 `Creative Brief Markdown`、`Copy Full Brief` 按钮、素材概念摘要和 Raw JSON，方便复用给素材团队、media buyer 或客户。

BLOCKED 详情页只展示阻断原因、risks、risk_explanation、safer_alternatives、next_actions 和 Raw JSON，不生成 Creative Brief，避免把未通过红线审核的内容误作为交付素材。

这是本地 MVP history，用于单机演示、复盘和交付辅助，不是多用户 SaaS 存储，也没有登录、权限隔离或云端同步。

## Product Profiles

Product profiles provide reusable client/product context for local generation. The first MVP profile is `spikex_brazil`, which fills Spikex product, industry, country, language, audience, selling points, campaign rules, forbidden claims and product facts.

On the Web UI home page, use `Use Spikex Brazil Profile` to fill the existing generation form without auto-submitting it. The original `Spikex Brazil Demo`, `BLOCKED Risk Demo` and `Clear Form` buttons remain available.

Profiles help ground generation in reusable product facts, reduce manual input, and improve Creative Brief quality. When a profile includes `product_facts`, the facts are passed into the generation request, included in OpenAIProvider prompts as factual grounding, saved with the local generation record, and shown in Creative Brief Markdown under `Product Facts`.

This is local static profile storage for MVP demos and repeatable client briefs. It is not a multi-user SaaS CRM, does not provide login, permissions, cloud sync, or account-level profile management.

## Internal Media Buyer Workflow

This tool is primarily for internal media buyers and creative teams, not customer self-service. Internal users can prepare ad creatives, review product facts, export briefs, and hand off launch-ready notes before ads go live.

Creative IDs are derived by the application, not by the LLM. The current format is `{PRODUCT_CODE}-{COUNTRY_CODE}-{PLATFORM_CODE}-{YYYYMMDD}-{CONCEPT_CODE}`, for example `SPK-BR-FB-20260628-C001`. These IDs help track creative concepts across briefs, video file names, ad launches, and performance reports.

Generated results include a `Media Buyer Launch Brief` with campaign setup, a creative launch table, metrics to watch, launch checklist, and decision rules. It is written for internal launch preparation and avoids ROI promises, guaranteed profit claims, or customer-facing performance commitments.

Customers may see exported Creative Briefs, reports, or selected presentation outputs, but internal teams are the primary users of this MVP.

## Performance CSV Analyzer

The local Web UI includes a `Performance CSV Analyzer` page at `/performance` for internal media buyers and creative teams. It does not call any ad platform API. Each pasted CSV analysis is saved locally as a Performance Report for internal review.

Supported Creative ID matching:

- Direct columns: `creative_id`, `Creative ID`, `creative id`
- Name extraction from: `ad_name`, `Ad Name`, `campaign_name`, `Campaign Name`, `adset_name`, `Ad Set Name`
- Example ID format: `SPK-BR-FB-20260628-C001`

Supported metrics include spend, impressions, clicks, link clicks, registrations, deposits or purchases, 3-second video views, 50% video views, and 95% video views. The analyzer calculates CTR, link CTR, CPC, CPM, registration CPA, deposit CPA, 3s view rate, 50% retention, and 95% retention.

The result page shows a summary, Creative Performance Table, unmatched row warning, internal action notes, and a copyable `Performance Summary` Markdown textarea. Recommendations are rule-based for MVP use, including `SCALE_CANDIDATE`, `KEEP_TESTING`, `NEEDS_RECUT`, `PAUSE`, `CHECK_LANDING_PAGE`, `CHECK_ONBOARDING_OR_TRUST`, `NEEDS_COPY_OR_CTA_TEST`, and `INSUFFICIENT_DATA`.

Example CSV:

```csv
creative_id,spend,impressions,clicks,link_clicks,registrations,deposits,video_3s_views,video_50_views,video_95_views
SPK-BR-FB-20260628-C001,30,5000,80,65,5,1,1200,500,220
SPK-BR-FB-20260628-C002,25,4500,35,28,1,0,600,180,60
```

## Saved Performance Reports

Each `/performance` CSV analysis is saved locally as a Performance Report. The result page shows `Saved Performance Report` with links to the saved report detail and the report history.

Open `/performance/history` to review recent saved reports. Each row shows report id, created time, total spend, matched creative count, unmatched row count, and counts for `SCALE_CANDIDATE`, `NEEDS_RECUT`, `PAUSE`, and `CHECK_LANDING_PAGE`.

Open `/performance/history/{report_id}` to view the saved analysis, including Summary, Creative Performance Table, Internal Action Notes, Unmatched Rows, Copy Performance Summary Markdown, and Raw CSV preview.

This feature is for internal media buyers, creative teams, and project review. V1 does not sync with Facebook/TikTok APIs, does not require customer login, and does not provide a customer dashboard. Future versions can link saved performance reports to generated Creative IDs, client weekly reports, and next-round creative generation suggestions.

## Next Round Creative Recommendations

Saved Performance Reports can produce `Next Round Creative Recommendations` on `/performance/history/{report_id}`. These recommendations are for internal media buyers, creative teams, editors, and project owners.

The system groups creatives into scale candidates, keep testing, needs recut, copy/CTA tests, landing page checks, and pause. It also produces next-round angles and `creative_brief_requests` that can be copied into Notion, Feishu, Slack, or a client weekly report draft.

This V1 only recommends what to test next. It does not automatically generate new creatives, does not call MockAIProvider or OpenAIProvider for new assets, and does not promise ROI, CPA improvement, deposits, or performance outcomes.

## Next Round Creative Brief Request

Saved Performance Reports can also produce a copyable `Next Round Creative Brief Request` on `/performance/history/{report_id}`. This is for internal media buyers and creative producers before the next production round.

The request converts performance recommendations into a production-ready brief with priority actions, next-round generation requests, do-not-repeat notes, internal production notes, and suggested variant naming such as `SPK-BR-FB-20260628-C001-V2A`.

This V1 does not automatically generate new creatives, does not call OpenAI or any ad platform API, and does not promise ROI or performance outcomes. It is a structured internal request that can be copied into Notion, Feishu, Slack, or a production handoff.

## 本地 Web Demo

进入项目目录：

```bash
cd /Users/zeipiaoliang/Documents/content-factory-mvp
```

使用 mock 模式启动本地 Web Demo：

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock python3 -m content_factory.api --host 127.0.0.1 --port 8000
```

本地访问地址：

```text
http://127.0.0.1:8000/
```

运行测试：

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock python3 -m unittest discover -v
python3 -m compileall content_factory tests
```

## 本地数据

默认配置来自环境变量或内置默认值：

- `DATABASE_PATH=data/content_factory.sqlite3`
- `UPLOAD_DIR=uploads`
- `AI_PROVIDER=mock`
- `HOST=127.0.0.1`
- `PORT=8000`

SQLite 数据库会在服务或 CLI 启动时自动初始化。

## 测试

当前环境没有依赖 pytest，使用 Python 标准库 unittest：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m unittest \
  tests.test_config \
  tests.test_db \
  tests.test_ai_provider \
  tests.test_services \
  tests.test_cli \
  tests.test_api \
  tests.test_web_ui \
  -v
```

编译检查：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m compileall content_factory tests
```

## 后续计划

- 替换真实 LLM Provider。
- 接完整前端后台。
- 接产品库、素材库、Benchmark 拆解库的更完整管理能力。
- 接投放数据回传。
- 接自动评分、素材复用和下一轮迭代策略。

## Industry templates

当前版本内置 `Crypto Exchange / Trading V1` 行业模板，用于加密货币交易所、交易、crypto exchange、trading、crypto 等投流场景。模板会影响两类输出：

- `MockAIProvider`：当产品行业/品类或需求文本命中 crypto exchange / exchange / trading / crypto 时，Spikex Brazil Demo 会生成更贴近交易所行业的 5 套素材角度。
- `OpenAIProvider`：命中模板时，会把行业角度、禁用表达、替代表达、巴西葡语术语、视频风格和文案规则写入 LLM prompt，但仍要求返回与 mock 兼容的结构化 JSON。

模板允许的方向包括：新手教育、AI copy trading 发现、平台 walkthrough、market access、risk-aware trading、app onboarding、daily check habit、feature comparison。

高风险表达包括：`guaranteed profit`、`risk-free`、`no loss`、`稳赚`、`保证收益`、`不亏钱`、`100% win`、`get rich quick`、`financial freedom guaranteed`、`easy money`、`profit promise`、`win every trade`。

建议替代表达包括：`explore market tools`、`understand platform features`、`review trading rules`、`trade with risk awareness`、`learn before trading`、`compare market information`、`manage your own trading decisions`、`educational and informational use`。

巴西葡语术语示例：

- `AI copy trading` → `copy trading com IA`
- `crypto trading` → `negociação de criptomoedas`
- `US stocks trading` → `negociação de ações dos EUA`
- `fast onboarding` → `cadastro rápido`
- `beginner-friendly trading experience` → `experiência simples para iniciantes`
- `trading tools` → `ferramentas de negociação`
- `market access` → `acesso ao mercado`
- `risk-aware trading` → `negociação com consciência de risco`
- `platform walkthrough` → `demonstração da plataforma`
- `educational content` → `conteúdo educativo`

红线规则仍保持原有边界：如果高风险表达出现在正式需求、产品名或卖点中，会返回 `BLOCKED` 或素材审核失败；如果只出现在 `forbidden_claims`、`campaign_rules`、合规规则说明中，只作为审核参考，不会自动阻断。

## Real LLM mode

系统默认仍然使用 `MockAIProvider`，适合本地演示、自动化测试和无密钥环境，不会调用真实 OpenAI API。

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock python3 -m content_factory.api --host 127.0.0.1 --port 8000
```

OpenAI 模式会使用 `OpenAIProvider` 调用真实 OpenAI API，需要配置 `OPENAI_API_KEY`。不要把 `OPENAI_API_KEY` 提交到 Git，也不要写入代码、测试或文档示例中的真实值。

```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_MODEL="gpt-4.1-mini"
CONTENT_FACTORY_PROVIDER=openai python3 -m content_factory.api --host 127.0.0.1 --port 8000
```

如果 `CONTENT_FACTORY_PROVIDER=openai` 但缺少 `OPENAI_API_KEY`，系统不会静默回退到 mock，而是返回清晰配置错误。

OpenAIProvider 会要求 LLM 返回结构化 JSON，生成结果必须保持与 mock 输出兼容：`campaign_summary`、5 套 `video_ad_concepts`、`scoring_report`、`media_production_notes`、`launch_plan`、`forbidden_claims_check`。正式素材语言仍支持 `pt-BR` / `es` / `en` / `zh`，红线命中时仍返回 `BLOCKED`，不生成正式素材内容。

自动化测试仍使用 mock 或 fake client，不调用真实 OpenAI API：

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock python3 -m unittest discover -v

python3 -m compileall content_factory tests
```
