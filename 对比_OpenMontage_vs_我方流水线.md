# OpenMontage vs 我方流水线 · 对比笔记（只对比，不动技能）

> 来源：GitHub `calesthio/OpenMontage`（AGPL-3.0，约 7.0 万 star，2026-10-16 仍在更新）的 README、AGENT_GUIDE、`pipeline_defs/documentary-montage.yaml`、`skills/pipelines/documentary-montage/edit-director.md`。
> 知乎那篇使用指南我这边打不开（知乎 403、Jina Reader 也被拦），下面**不含**该文内容；如那篇有额外玩法，以管理员读到的为准。
> 日期：2026-10-20 ｜ 结论：形态可学，代码不建议直接并用。

## 一、它是什么

- **定位**：开源、agent 驱动的视频生产系统。「12 条 pipeline + 100+ 工具 + 700+ skill/知识文件」。
- **12 条 pipeline**（`pipeline_defs/*.yaml`）：animated-explainer、animation、avatar-spokesperson、character-animation、cinematic、clip-factory、**documentary-montage**、framework-smoke、hybrid、localization-dub、podcast-repurpose、screen-demo、talking-head。
- **架构**：YAML pipeline manifest（stages、`review_focus`、`success_criteria`、`checkpoint_required`、`human_approval_default`、`max_revisions_per_stage`、`budget_default_usd`）+ 每阶段一个 director skill（md，1 万～2 万字级）+ Python 工具层 + 20+ JSON Schema + 状态 checkpoint。
- **明确禁令**（AGENT_GUIDE Rule Zero）：不许绕过 pipeline、不许临时写脚本直接调工具、不许跳过 preflight/checkpoint/review。

## 二、和我们最像的那条：documentary-montage

检索式素材拼接：从 Pexels / Archive.org / NASA / Wikimedia / Unsplash 建语义语料，用 CLIP 检索按 slot 描述填片，按叙事节拍排序 + 音乐同步 + 统一调色。风格参考 Adam Curtis / Chris Marker。

它的 `review_focus` 具体到可以机判：
- 每个 slot 恰好一条片、同一 clip 不许复用到两个 slot；
- 每条素材必须带 `provider / original_url / license`；
- 标准路径语料 ≥8×slot 数、检索分 ≥0.22；
- 相邻两刀不许同主体又同景别；转场词表 ≤4 种；每刀必须有理由；
- 总时长与 brief 差 ≤10%；成片时长误差 ≤1s。

## 三、质量体系（它最强的地方）

| 层 | 它的做法 | 我们现状 |
|---|---|---|
| 人工签收门 | proposal / script / scene plan / assets / publish 五处**强制**暂停签收；checkpoint writer 拒绝「未签收却标记完成」的阶段，被替代的 checkpoint 归档 | SOP 写了「上一步交付完整才开工」，但没有机器强制的签收记录 |
| 渲染前校验 | delivery promise（承诺「motion-led」却 80% 静图=阻断）、slideshow risk、渲染器缺失 → 直接不许渲染 | 没有渲染前门，v3 是渲染后才知道坏块 |
| 渲染后自检 | ffprobe + 4 固定位置抽帧查黑帧/坏覆盖 + 音频电平查静音与削波 + promise 复核 + 字幕存在性；不过不呈现 | 机检有字幕逐字/CER/响度/坏块，但**不验黑帧、不验「不是 PPT」** |
| slideshow 风险 | 6 维评分：重复、装饰性画面、弱运动、镜头意图、字体依赖、无依据的电影感声明 | 无 |
| 素材体检 | 用户给素材先 probe（分辨率/编码/声道/时长）再谈创作，不按文件名瞎猜内容 | 找素材有台账七列，但无逐文件 probe |
| 审计 | 每个决策记 alternatives + confidence + 理由；provider 7 维打分留决策链 | 有改稿记录和台账，无「为什么选这条素材/这个音色」的理由账 |
| 预算 | estimate / reserve / reconcile；默认单次 >$0.50 要批、总帽 $10 | 有单条时间预算，无成本账（我们本来就是零成本线） |
| 断点续做 | checkpoint JSON + superseded 归档，可续跑 | 靠「挂账参数」文字记录 |

## 四、差距的本质

它是**把流水线写成了可校验的程序**（manifest + schema + success_criteria），我们**把流水线写成了可读的规范**（SOP.md + 各环节 skill）。所以它能在阶段边界自动判定「这一步做完没有」，我们只能靠人和 agent 自觉。

但我们的强项它没有：
- 中文口播的**逐字一致性**（B1）和**分块 ASR 回读 + CER 分档**，它没有等价的配音质量门；
- **版权台账七列 + 红线素材**的硬校验（它只要求 provenance/license 字段，不判类型红线）；
- 事实口径与点名边界（D4–D6）、文风人判——它这条线几乎不涉及新闻/时事内容合规。

## 五、可借鉴的候选动作（按风险分档，**今天都不动**）

**A. 低风险、下次开片就能上（纯文档/脚本，不改现有 skill）**
1. 每环节交付卡 JSON 化：编剧/素材/成片各一份 schema，机器验「字段齐不齐、值合不合法」，比散文承诺可靠。
2. 渲染前预检清单（10 条：时长/字数口径/字幕条数/花字时间轴在 manifest 内/素材覆盖 100%/无空 slot/配音时长差/响度预算/镜头数与平均镜长/渲染器与输出规格）。
3. 项目状态.json：阶段、版本、未清阻断、恢复参数（替代「挂账文字」）。

**B. 中期（要改工具，得单独评估）**
4. 机检加 C10：黑帧检测、静态画面占比、镜头时长分布（对「素材拼接」这条线，这是防 PPT 化的最有效指标）。
5. 简化版 slideshow 风险分：镜头数 / 平均镜长 / 静态帧比例 / 重复画面率。
6. decisions.md：每条素材、音色、渲染器选择写一句理由，便于复盘和追责。

**C. 不建议**
7. 抄 12 条 pipeline：我们只有一条时事/社会拼接线，先把这一条做到 manifest 级。
8. provider 7 维打分/预算系统：我们配音免费、素材多为公版，收益极低。
9. **直接并代码**：AGPL-3.0，本地自用没问题，但并进我们的产品或对外提供服务会触发开源义务；借鉴方法论与文档结构即可。

## 六、一句话结论

它的启发不是「换工具」，而是「把验收标准写成机器能判的字段」——这正是我们 SOP 下一步该补的：不是更多文字，而是每道门的 `success_criteria`。
