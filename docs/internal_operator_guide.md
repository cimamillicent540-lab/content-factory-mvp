# Internal Operator Guide

## 1. 工具定位

Content Factory MVP 是内部投流团队和素材团队使用的 AI 投流素材生产工作台，不是客户自助 SaaS。主要使用者包括内部投手、素材负责人、剪辑 / AI 视频制作人员和项目负责人。

客户通常只看到我们导出的 Creative Brief、Media Buyer Launch Brief、Performance Report 或演示结果，不直接操作后台。

## 2. 标准工作流

1. 打开本地 Web UI。
2. 点击 `Use Spikex Brazil Profile` 或手动填写产品信息。
3. 点击生成素材，检查结果是否为 `GENERATED`。
4. 检查每套素材的 `Creative ID`。
5. 复制 `Creative Brief Markdown` 给素材团队。
6. 复制 `Media Buyer Launch Brief` 给投手。
7. 剪辑或 AI 视频生成时，把 Creative ID 放入视频文件名。
8. 广告上线时，把 Creative ID 放入广告名称、广告组备注或素材命名。
9. 从广告平台导出 CSV。
10. 打开 `/performance`，粘贴 CSV 并点击 Analyze Performance。
11. 查看并保存 Performance Report。
12. 打开 `/performance/history/{report_id}` 查看复盘详情。
13. 查看 `Next Round Creative Recommendations`。
14. 复制 `Next Round Creative Brief Request`。
15. 安排下一轮素材生产。

## 3. 命名规范

Creative ID 用于连接素材生产、广告上线和数据复盘。

用途：

- 视频文件名
- 广告名称
- 广告组备注
- CSV 数据匹配
- 复盘报告

示例：

```text
SPK-BR-FB-20260628-C001
SPK-BR-FB-20260628-C001-V2A
SPK-BR-FB-20260628-C002-RECUT-V2A
```

不要修改原始 Creative ID 规则。`V2A`、`V2B`、`RECUT-V2A` 是下一轮变体命名建议，不替代原始 Creative ID。

## 4. 投手上线前检查清单

- 产品事实是否和产品 Profile、落地页、实际后台一致。
- 落地页是否匹配广告承诺。
- 文案是否没有 `guaranteed profit`、`risk-free`、`no loss`。
- 视频文件名是否包含 Creative ID。
- 字幕是否和口播一致。
- Facebook 文案是否和 Brief 一致。
- Pixel / event 是否配置好。
- 素材命名是否能在广告平台 CSV 中被匹配。
- 风险提示是否保持 trading 产品所需的审慎表达。

## 5. 数据复盘说明

- `CTR`：点击率。低 CTR 通常说明 Hook、角度、主视觉或广告文案需要调整。
- `CPC`：单次点击成本。用于比较素材吸引点击的效率。
- `CPM`：千次展示成本。更多反映流量成本和受众竞争。
- `CPA registration`：注册成本。高点击低注册时，优先检查落地页、注册流程、事件追踪和承诺一致性。
- `CPA deposit`：充值 / 购买成本。注册有量但充值弱时，检查 onboarding、信任感、支付流程和后续教育。
- `3s rate`：前三秒观看率。低 3s rate 通常需要重剪开头。
- `50% retention`：中段留存。低中段留存通常说明节奏、信息密度或视觉变化不足。
- `95% retention`：接近完播率。可辅助判断视频结构是否完整、CTA 是否出现太晚。

## 6. 下一轮迭代说明

- `SCALE_CANDIDATE`：保留核心角度，做 2-3 个受控变体，不要一次改变太多变量。
- `KEEP_TESTING`：继续小预算测试，准备一个轻量 Hook / 字幕 / CTA 变体。
- `NEEDS_RECUT`：先重剪前三秒，再考虑重新上线。
- `CHECK_LANDING_PAGE`：先检查落地页 message match、注册流程、信任信号和 tracking。
- `PAUSE`：暂停当前版本，不要继续加预算；重做角度后再测试。

## 7. 不要做什么

- 不要承诺 ROI。
- 不要承诺稳赚、无风险、不亏钱。
- 不要把 `campaign_rules` 原样写进广告。
- 不要删除 Creative ID。
- 不要把客户不能确认的功能写进素材。
- 不要把未通过红线审核的内容当成交付 Brief。
- 不要在公开文案中暗示保证收益、快速致富或无风险交易。
