# 视频生产流水线 · 代码与规范

本仓库是「普通人手搓 AI 电商」YouTube 频道（频道 B）视频产线的可下载副本：**机读契约 + 校验脚本 + 各环节规范**。
配套的成片、素材、配音、录屏等媒体文件不进仓库（见 `.gitignore`），这里只放能复跑、能对照的代码与规则。

## 目录结构

```
docs/                 各环节规范（写稿、分镜、配音、质检、交付）
  └ 频道B/            频道 B 专用：写稿规范、收稿检查单、选题卡、排期
  └ archive/          已被新版取代的旧版规范（留档，不再执行）
scripts/              产线脚本（分镜、切点、卡点、质检）
  └ render/           渲染与工程生成（montage、剪映/Studio 工程）
channelB/             频道 B 数字人/自动化相关代码
```

## 关键文档

| 文档 | 作用 |
| --- | --- |
| [视频生产流水线_SOP](docs/视频生产流水线_SOP.md) | 全流程唯一的执行口径：五环串行、四道闸门 |
| [分镜契约_v2](docs/分镜契约_v2.md) | `scene_plan.json` 机读契约与校验判据 |
| [质检清单_v1](docs/质检清单_v1.md) | 质检项与机检命令 |
| [剪映配音交付与验收规则_v1](docs/剪映配音交付与验收规则_v1.md) | 配音交付与验收口径 |
| [频道B_写稿规范_v1](docs/频道B/频道B_写稿规范_v1.md) | 频道 B 文风与口播写法 |

## 常用命令

```bash
# 分镜：生成 + 校验（全 PASS 才算交付）
python scripts/分镜导出.py <前缀>
python scripts/分镜校验.py <前缀>_scene_plan.json --txt <前缀>_纯口播.txt

# 切点表（每 ≤8 秒一个画面变化点）
python scripts/切点表.py <前缀>_scene_plan.json

# 逐句卡点对照表
python scripts/逐句卡点表.py <集号>_scene_plan.json --out <集号>_逐句卡点对照表.csv

# 质检机检（技术项全量出数，不手判）
python scripts/质检机检.py --mp4 成片.mp4 --srt 字幕.srt --txt 纯口播.txt --facts 事实核查表.csv --target-min 7

# 脚本自检 / 稿本同步
python scripts/脚本自检.py <纯口播.txt> [目标分钟]
python scripts/稿本同步检查.py
```

## 约定

- 脚本里的路径参数按命令行传入，不要写死本机绝对路径。
- 机检项必须**出数**：报告里的数字要能从脚本复跑出来。
- 旧版规范一律移入 `docs/archive/`，不在根目录堆放。
- 不提交：密钥（`keys/`、`*.pem`、`*.key`）、媒体（mp4/png/wav 等）、日志与备份、ERP 私有源码、单集产出数据。

## 环境

Windows + Python 3；本机 git 走 MinGit 并使用 `http.sslBackend=openssl`（系统 schannel 不可用）。
