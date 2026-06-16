---
name: dcu-modelzoo
description: >-
  查询某模型是否在海光光合社区 ModelZoo 适配 DCU，并给出网页/clone 下载链接。
  触发：问"X 适配吗"、"DCU 支持 X 模型吗"、"X 有没有适配"、"ModelZoo 有 X 吗"、"海光适配了 X 吗"、
  "查模型适配"、"X 能在 DCU 跑吗"。也用于月度更新检查。
---

# DCU ModelZoo 模型适配查询

海光光合社区 ModelZoo（GitLab group `modelzoo`，id 831，public）收录 ~589 个模型在 DCU 上的适配仓库。
本技能：①查模型是否适配 + 给下载链接；②每月检查库更新。

数据：`scripts/data/modelzoo_snapshot.json`（离线基线）+ live GitLab API（最新）。

## 用途一：查模型适配（最常用）

用户问「<模型> 适配吗 / DCU 支持 <模型> 吗」时：

```
python3 ~/.claude/skills/dcu-modelzoo/scripts/query.py "<模型名或关键词>"
```

- 默认智能：本地 snapshot 新鲜(≤14天)则秒回；陈旧或缺失则**自动联网刷新**（首次安装即见当前数据，无需等月度任务）。
- `--live` 强制刷新；`--offline` 强制只用本地不联网。
- 输出已含：仓库名、框架、简介、更新日期、网页链接、`git clone` 链接。直接转述给用户。

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

## 关联
- 输出清单：`<DCU_MODELZOO_OUT_DIR>/ModelZoo仓库清单.md`（可指向 Obsidian/笔记库）
- 部署：跑通模型需配 DTK/镜像，参见海光开发者社区文档
- clone：`git clone https://developer.sourcefind.cn/codes/modelzoo/<repo>.git`
