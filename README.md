# 海外投流素材内容工厂 / Content Factory

这是一个本地可运行的海外投流素材内容工厂 MVP。当前版本使用 `MockAIProvider`，不调用任何外部 API，也不需要 API key。它用于验证核心流程：输入素材需求，进行需求结构化、红线审核、多语言素材生成、100 分评分、投放分析，并把记录保存到 SQLite。

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
