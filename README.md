# dcu-modelzoo — 海光 DCU 模型适配查询 Claude Code 技能

查一个模型是否在**海光光合社区 ModelZoo**（GitLab group `modelzoo`，public，~594 仓库）适配了 DCU，并直接给出**适配卡型 / 量化精度 / 最低卡数 / 镜像 tag** + 网页 / `git clone` 下载链接；附每月自动检查库更新。

适用：[Claude Code](https://claude.com/claude-code) 技能（skill）。也可纯命令行用脚本。

## 功能

- **查适配**：问「Qwen3 适配吗 / DCU 支持 X 吗」→ 模糊匹配仓库名+简介，列出多框架版本（`_pytorch`/`_vllm`/`_mmcv`…）+ 简介 + 更新日期 + clone 链接。
- **硬件规格**：查询自动带 **适配卡型（BW1000/BW1100/BW1101）/ 量化精度（FP8/BF16/INT4…）/ 最低卡数 / 镜像 tag / DTK 版本**，来自 `harvest_specs.py` 解析的各仓库 README（591 中约 103 仓库带卡型标注）。FP8 仅 BW1100/BW1101，BW1000 无 FP8 硬件。
- **离线优先**：内置 `data/modelzoo_snapshot.json`（仓库基线）+ `data/specs_snapshot.json`（硬件规格），秒回；`--live` 走 GitLab API 拿最新。
- **月度更新检查**：与 snapshot diff（新增/更新/删除），`--apply` 刷新 snapshot + 重生成清单表。
- **自动调度**：macOS launchd / Linux cron，每月 1 号自动跑，报告写你的笔记库。

## 安装（Claude Code 技能）

```bash
git clone https://github.com/lutianshu824/dcu-modelzoo-skill.git
cp -r dcu-modelzoo-skill ~/.claude/skills/dcu-modelzoo
```

技能随即可用——对 Claude 说「DeepSeek-R1 适配 DCU 了吗」即触发。

> 仅命令行用也行，无需 Claude Code。

## 配置（可选）

输出目录（清单表 + 更新日志落地处）默认写技能内 `output/`。要写进自己的笔记库（如 Obsidian）：

```bash
cd ~/.claude/skills/dcu-modelzoo
cp config.env.example config.env
# 编辑 config.env，设 DCU_MODELZOO_OUT_DIR 为你的笔记目录
```

`config.env` 已被 `.gitignore` 忽略，不会泄露个人路径。

## 用法（命令行）

```bash
# 查适配（智能：本地数据陈旧/缺失则自动联网刷新，首装即见当前数据）
python3 scripts/query.py "qwen3"
python3 scripts/query.py "deepseek r1"
python3 scripts/query.py "kimi" --live      # 强制联网刷新
python3 scripts/query.py "glm" --offline    # 强制只用本地，不联网

# 月度更新检查
python3 scripts/check_update.py            # 只读 diff
python3 scripts/check_update.py --apply     # 刷新 snapshot + 清单表

# 硬件规格抓取（卡型/精度/最低卡数/镜像）
python3 scripts/harvest_specs.py                          # 全量 → data/specs_snapshot.json + 卡型清单
python3 scripts/harvest_specs.py --sample glm-5.2,qwen3.6 # 指定仓库探测
```

> 首次安装会自带一份 snapshot（含抓取日期）。查询时若数据超过 14 天，自动联网拉取最新——
> 所以新用户当场就能看到 ModelZoo 当前的适配情况，不必等到下次月度任务。

依赖：Python 3.8+（仅标准库，无三方包）。联网回退另需系统 `openssl` CLI（见下「网络」）。

## 网络

抓取走 `scripts/sf_fetch.py`：**先试 `urllib` 直连**（用户本机 / 月度 cron 走自己网络通）；失败时**回退 `openssl s_client` 传输**。

原因：sourcefind.cn 前置中间盒按 TLS **ClientHello 指纹** reset 连接——`urllib` / 系统 `curl`（带 ALPN+多扩展）的握手在部分受限网络被杀（`SSL EOF` / `SSL_ERROR_SYSCALL`），而 `openssl s_client` 的极简 ClientHello 能通（实测 HTTP 200）。回退用系统 `openssl`，无需三方包。

## 自动调度

### macOS（launchd，推荐 — 睡眠错过会唤醒补跑）

```bash
# 1) 编辑 templates/launchd.plist：把 __USER__ 改成你的用户名、__SKILL_DIR__ 改成技能绝对路径
# 2) 安装
cp templates/launchd.plist ~/Library/LaunchAgents/com.dcu-modelzoo.monthly.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dcu-modelzoo.monthly.plist
# 3) 立即测试
launchctl kickstart -k gui/$(id -u)/com.dcu-modelzoo.monthly
```

⚠️ **TCC**：若输出目录在 `~/Documents`/`~/Desktop` 等受保护目录，launchd 需 **完全磁盘访问权限**（系统设置→隐私与安全性→完全磁盘访问，添加 `/bin/zsh` 与 `/usr/bin/python3`）。否则报告回退到技能内 `reports/`。
plist 已设 `LANG=en_US.UTF-8`，避免 launchd 无 locale 时中文路径写失败。

### Linux（cron）

```bash
crontab -e
# 每月 1 号 09:00：
0 9 1 * * /path/to/dcu-modelzoo/scripts/monthly_run.sh
```

## 数据来源

海光开发者社区 ModelZoo：https://developer.sourcefind.cn/codes/groups/modelzoo
（公开 GitLab，API `developer.sourcefind.cn/codes/api/v4/groups/modelzoo/projects`）

snapshot 仅含公开仓库元数据（名称/简介/链接/更新日期），无私密信息。

## License

MIT
