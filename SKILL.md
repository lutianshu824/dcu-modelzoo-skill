---
name: dcu-modelzoo
description: >-
  查询某模型是否在海光光合社区 ModelZoo 适配 DCU，并给出网页/clone 下载链接。
  触发：问"X 适配吗"、"DCU 支持 X 模型吗"、"X 有没有适配"、"ModelZoo 有 X 吗"、"海光适配了 X 吗"、
  "查模型适配"、"X 能在 DCU 跑吗"。也用于月度更新检查。
---

# DCU ModelZoo 模型适配查询

海光光合社区 ModelZoo（GitLab group `modelzoo`，id 831，public）收录 ~594 个模型在 DCU 上的适配仓库。
本技能：①查模型是否适配 + 给下载链接 + 硬件规格（卡型/精度/最低卡数/镜像）；②每月检查库更新。

数据：`data/modelzoo_snapshot.json`（仓库基线）+ `data/specs_snapshot.json`（README 解析的硬件规格）+ live GitLab API（最新）。

## 用途一：查模型适配（最常用）

用户问「<模型> 适配吗 / DCU 支持 <模型> 吗」时：

```
python3 ~/.claude/skills/dcu-modelzoo/scripts/query.py "<模型名或关键词>"
```

- 默认智能：本地 snapshot 新鲜(≤14天)则秒回；陈旧或缺失则**自动联网刷新**（首次安装即见当前数据，无需等月度任务）。
- `--live` 强制刷新；`--offline` 强制只用本地不联网。
- 输出已含：仓库名、框架、简介、**适配卡型 / 精度 / 最低卡数 / 镜像 tag / DTK**（来自 `specs_snapshot.json`）、更新日期、网页链接、`git clone` 链接。直接转述给用户。
- **回答适配时必带卡型 + 量化精度 + 最低卡数**（用户要求），不只说"适配/不适配"。FP8 模型仅 BW1100/BW1101；BW1000 无 FP8 硬件。

查询要点：
- 先用基座名查（`qwen` / `deepseek` / `llama` / `glm`），比全名召回高。
- 多关键词空格分隔（`qwen3 vl`）。
- 一个模型常有多框架版本（`_pytorch` / `_mmcv` / `_vllm`…），都列出。
- 命中 0 → 提示换关键词或 `--live`，并给社区浏览链接 https://developer.sourcefind.cn/codes/groups/modelzoo

## 用途二：月度更新检查

```
python3 scripts/check_update.py            # 只读，报告 新增/更新/删除
python3 scripts/check_update.py --apply    # 刷新 snapshot + 重生成清单
```

- 自动调度：`scripts/monthly_run.sh`，每月 1 号自动跑（macOS launchd / Linux cron，见 README）。
- 手动月检：先只读看 diff，再 `--apply` 落盘。
- `--apply` 重写输出目录下 `ModelZoo仓库清单.md`（输出目录 = `config.env` 的 `DCU_MODELZOO_OUT_DIR`，默认技能内 `output/`）。

## 用途三：硬件规格抓取（卡型/精度/最低卡数/镜像）

```
python3 scripts/harvest_specs.py                          # 全量 594 → data/specs_snapshot.json + 报告
python3 scripts/harvest_specs.py --sample glm-5.2,qwen3.6 # 指定 path 探测
python3 scripts/harvest_specs.py --limit 30               # 前 N 个
```

- 抓各仓库 README，解析「支持的DCU型号 / 数据类型(精度) / 最低卡数」表 + 镜像 tag(`harbor.sourcefind.cn…`) + DTK 版本。
- 594 仓库中约 **106 个带 BW 卡型信息**（其余为旧/非 LLM 仓库，README 未标型号列）。
- 卡型归一：**BW200 → BW1000**（BW200 = lsgpu 单卡名，BW1000 = 8 卡整机 SKU，同一产品）。
- 16 线程并发，全量 ~156s。⚠️ Py3.8 stderr 重定向到文件会块缓冲，跑后台用 `PYTHONUNBUFFERED=1` 才见进度。
- 报告 → `<DCU_MODELZOO_OUT_DIR>/ModelZoo卡型适配清单.md`（明细表 + 镜像速查）。
- query.py 自动读 `specs_snapshot.json` 注入规格，无需手动调本脚本即可在查询时看到卡型。

## 关联
- 输出清单：`<DCU_MODELZOO_OUT_DIR>/ModelZoo仓库清单.md`（可指向 Obsidian/笔记库）
- 部署：跑通模型需配 DTK/镜像，参见海光开发者社区文档
- clone：`git clone https://developer.sourcefind.cn/codes/modelzoo/<repo>.git`
