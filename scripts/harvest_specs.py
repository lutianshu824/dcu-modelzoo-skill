#!/usr/bin/env python3
"""抓取 ModelZoo 各仓库 README，解析硬件适配规格。

提取每仓库：
- 镜像 tag（harbor.sourcefind.cn 行，去重）
- DTK / vLLM / Torch 版本
- 适配表行：模型变体 | 权重大小 | 精度(数据类型) | 支持的DCU型号 | 最低卡数

用法:
  python3 harvest_specs.py --sample glm-5.2,qwen3.6,minimax-m3   # 指定 path 探测
  python3 harvest_specs.py --limit 30                            # 前 N 个
  python3 harvest_specs.py                                       # 全量 → specs_snapshot.json + 报告
并发抓取（默认 10 线程）。无适配表的仓库也记录（cards=[]）。
"""
import json, re, ssl, sys, pathlib, urllib.request, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
SNAP = DATA / "modelzoo_snapshot.json"
OUT_SPECS = DATA / "specs_snapshot.json"
RAW = "https://developer.sourcefind.cn/codes/modelzoo/{path}/-/raw/{br}/{f}"
BRANCHES = ("master", "main")
FILES = ("README.md", "readme.md")
TIMEOUT = 12
_ctx = ssl.create_default_context(); _ctx.check_hostname=False; _ctx.verify_mode=ssl.CERT_NONE

CARD_RE = re.compile(r"BW\s*1?\d{3,4}", re.I)          # BW150/BW1000/BW1100/BW1101 etc
IMG_RE  = re.compile(r"harbor\.sourcefind\.cn[^\s`'\"]+")
DTK_RE  = re.compile(r"DTK\D{0,8}(\d{2}\.\d{2}(?:\.\d+)?)", re.I)
# 卡型别名归一：BW200 = BW1000 单卡名(lsgpu 显示)，BW1000 = 8卡整机 SKU
CARD_ALIAS = {"BW200": "BW1000"}
def norm_card(c):
    c = c.upper().replace(" ", "")
    return CARD_ALIAS.get(c, c)


def fetch_readme(path):
    for br in BRANCHES:
        for f in FILES:
            url = RAW.format(path=path, br=br, f=f)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
                r = urllib.request.urlopen(req, timeout=TIMEOUT, context=_ctx)
                if r.status == 200:
                    return r.read().decode("utf-8", "replace")
            except Exception:
                continue
    return None


def parse_table(md):
    """找含『支持的DCU型号』(或『DCU型号』) 的 markdown 表，逐行抽 cells。"""
    lines = md.splitlines()
    rows = []
    hdr_idx = None
    cols = []
    for i, ln in enumerate(lines):
        if "|" in ln and ("支持的DCU型号" in ln or "DCU型号" in ln or ("型号" in ln and "精度" in ln)):
            cols = [c.strip() for c in ln.strip().strip("|").split("|")]
            hdr_idx = i
            break
    if hdr_idx is None:
        return rows
    # 列定位
    def col(key_opts):
        for j, c in enumerate(cols):
            if any(k in c for k in key_opts):
                return j
        return None
    ci_name = col(["模型名称", "模型", "名称"])
    ci_size = col(["权重大小", "参数", "大小"])
    ci_prec = col(["数据类型", "精度", "量化"])
    ci_card = col(["支持的DCU型号", "DCU型号", "型号"])
    ci_min  = col(["最低卡数", "卡数", "卡数需求"])
    for ln in lines[hdr_idx + 1:]:
        if "|" not in ln:
            break
        if re.match(r"^\s*\|?[\s:|-]+\|?\s*$", ln):  # 分隔行 :---:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if not any(cells):
            break
        def g(idx):
            return cells[idx] if idx is not None and idx < len(cells) else ""
        card_field = g(ci_card)
        cards = sorted(set(norm_card(c) for c in CARD_RE.findall(card_field)))
        rows.append({
            "variant": g(ci_name),
            "size": g(ci_size),
            "precision": g(ci_prec),
            "cards": cards,
            "card_raw": card_field,
            "min_cards": g(ci_min),
        })
    return rows


def parse_repo(md):
    images = sorted(set(IMG_RE.findall(md)))
    dtk = ""
    m = DTK_RE.search(md)
    if m:
        dtk = m.group(1)
    table = parse_table(md)
    # 整仓库聚合卡型（表里 + 全文 BW 提及）
    all_cards = sorted(set(norm_card(c) for r in table for c in r["cards"]))
    if not all_cards:
        all_cards = sorted(set(norm_card(c) for c in CARD_RE.findall(md)))
    return {"images": images, "dtk": dtk, "cards": all_cards, "table": table}


def main():
    args = sys.argv[1:]
    sample = None
    limit = None
    if "--sample" in args:
        sample = args[args.index("--sample") + 1].split(",")
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    repos = json.load(open(SNAP, encoding="utf-8"))
    if sample:
        sel = {s.lower() for s in sample}
        repos = [r for r in repos if r["path"].lower() in sel or r["name"].lower() in sel]
    elif limit:
        repos = repos[:limit]

    print(f"抓取 {len(repos)} 仓库 README …", file=sys.stderr)
    results = {}

    def work(r):
        md = fetch_readme(r["path"])
        if md is None:
            return r["path"], {"images": [], "dtk": "", "cards": [], "table": [], "no_readme": True}
        spec = parse_repo(md)
        spec["name"] = r["name"]
        spec["updated"] = r.get("updated", "")
        return r["path"], spec

    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(work, r): r for r in repos}
        for fut in as_completed(futs):
            path, spec = fut.result()
            results[path] = spec
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(repos)}", file=sys.stderr, flush=True)

    # 摘要
    with_card = {p: s for p, s in results.items() if s.get("cards")}
    no_readme = sum(1 for s in results.values() if s.get("no_readme"))
    print(f"\n完成。带BW卡型信息: {len(with_card)} / {len(results)}  (无README: {no_readme})", file=sys.stderr)

    if not sample:
        payload = {"fetched": datetime.date.today().isoformat(), "count": len(results), "repos": results}
        json.dump(payload, open(OUT_SPECS, "w"), ensure_ascii=False, indent=0)
        print(f"已写 {OUT_SPECS}", file=sys.stderr)

    # 打印带卡型的（便于探测/转述）
    for p, s in sorted(with_card.items()):
        cards = ",".join(s["cards"]) or "-"
        print(f"\n## {s.get('name', p)}  [{cards}]  DTK{s.get('dtk') or '?'}")
        for img in s["images"][:2]:
            print(f"   img: {img}")
        for row in s["table"]:
            if row["cards"] or row["precision"]:
                print(f"   - {row['variant']} | {row['size']} | {row['precision']} | {','.join(row['cards']) or row['card_raw']} | min {row['min_cards']}")


if __name__ == "__main__":
    main()
