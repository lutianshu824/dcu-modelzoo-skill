#!/usr/bin/env python3
"""查询某模型是否在海光光合社区 ModelZoo 适配。
用法: python3 query.py "<模型名/关键词>" [--live] [--offline]
默认：本地 snapshot 若缺失或陈旧(>14天，按 snapshot_meta.json 的抓取日期)，自动拉 live 刷新；
否则用本地 snapshot（秒回）。--live 强制刷新；--offline 强制只用本地不联网。
首次安装即可见当前适配情况（自动联网拉取），无需等月度任务。
匹配: 大小写无关 + 去分隔符模糊 + 关键词分词全包含。
输出: 匹配仓库的 名称/框架/简介/更新日期/网页链接/clone链接。
"""
import json, sys, re, urllib.request, ssl, pathlib, datetime

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
SNAP = DATA / "modelzoo_snapshot.json"
META = DATA / "snapshot_meta.json"
SPECS = DATA / "specs_snapshot.json"
STALE_DAYS = 14
API = "https://developer.sourcefind.cn/codes/api/v4/groups/modelzoo/projects?per_page=100&include_subgroups=true&order_by=name&sort=asc&page="
_ctx = ssl.create_default_context(); _ctx.check_hostname=False; _ctx.verify_mode=ssl.CERT_NONE

def norm(s): return re.sub(r"[^a-z0-9一-鿿]", "", s.lower())

def _get(url):
    last=None
    for _ in range(4):
        try:
            req=urllib.request.Request(url, headers={"User-Agent":"curl/8"})
            return json.load(urllib.request.urlopen(req, timeout=60, context=_ctx))
        except Exception as e:
            last=e; import time; time.sleep(3)
    raise last

def load_live():
    out=[]
    for p in range(1,15):
        data=_get(API+str(p))
        if not data: break
        for r in data:
            out.append({"id":r["id"],"name":r["name"],"path":r["path"],"url":r["web_url"],
                        "desc":(r.get("description") or "").replace("\n"," ").strip(),
                        "updated":r["last_activity_at"][:10],
                        "clone":f'https://developer.sourcefind.cn/codes/{r["path_with_namespace"]}.git'})
        if len(data)<100: break
    out.sort(key=lambda x:x["name"].lower())
    return out

def save_snapshot(rows):
    try:
        json.dump(rows, open(SNAP,"w"), ensure_ascii=False, indent=0)
        json.dump({"fetched":datetime.date.today().isoformat(),"count":len(rows)},
                  open(META,"w"), ensure_ascii=False)
    except Exception:
        pass  # 只读环境下静默：本次仍用内存数据

def snapshot_age_days():
    try:
        f=json.load(open(META,encoding="utf-8"))["fetched"]
        return (datetime.date.today()-datetime.date.fromisoformat(f)).days
    except Exception:
        return None  # 无 meta = 视为陈旧

def get_rows(force_live=False, offline=False):
    age=snapshot_age_days()
    stale = (age is None) or (age > STALE_DAYS) or (not SNAP.exists())
    if not offline and (force_live or stale):
        try:
            rows=load_live(); save_snapshot(rows)
            why="强制刷新" if force_live else ("无本地数据，已联网获取" if age is None else f"本地数据 {age} 天前，已联网刷新")
            return rows, f"LIVE GitLab API（{why}，{len(rows)} 仓库）"
        except Exception as e:
            if SNAP.exists():
                return json.load(open(SNAP,encoding="utf-8")), f"本地 snapshot（联网失败回退：{str(e)[:50]}）"
            raise SystemExit(f"❌ 无本地 snapshot 且联网失败：{e}\n请联网后重试，或检查 {API}")
    rows=json.load(open(SNAP,encoding="utf-8"))
    tag=f"{age} 天前" if age is not None else "未知日期"
    return rows, f"本地 snapshot（{tag}，{len(rows)} 仓库）"

def framework(name):
    s=name.lower()
    for k,v in {"pytorch":"PyTorch","mmcv":"mmcv","paddle":"Paddle","oneflow":"OneFlow",
                "migraphx":"MIGraphX","onnxruntime":"ONNXRuntime","tensorflow":"TensorFlow",
                "bladedisc":"BladeDISC","fastertransformer":"FasterTransformer","vllm":"vLLM"}.items():
        if s.endswith("_"+k) or "_"+k+"_" in s or s.endswith("-"+k): return v
    return "—"

def load_specs():
    """path → 硬件规格（卡型/精度/最低卡数/镜像/DTK）。来自 harvest_specs.py。缺失返回空。"""
    try:
        return json.load(open(SPECS,encoding="utf-8")).get("repos",{})
    except Exception:
        return {}

def print_spec(spec):
    """转述硬件适配规格。spec = specs_snapshot 中某 path 的条目。"""
    if not spec: return
    cards=spec.get("cards") or []
    if cards: print(f"- 适配卡型：{' / '.join(cards)}")
    if spec.get("dtk"): print(f"- DTK：{spec['dtk']}")
    tbl=spec.get("table") or []
    for row in tbl:
        c=",".join(row.get("cards") or []) or row.get("card_raw","") or "—"
        parts=[p for p in [row.get("variant",""), row.get("size",""), row.get("precision",""),
                           f"{c}", (f"≥{row['min_cards']}卡" if row.get("min_cards") else "")] if p]
        print(f"  · {' | '.join(parts)}")
    for img in (spec.get("images") or [])[:2]:
        print(f"- 镜像：`{img}`")

def search(q, rows):
    nq=norm(q); toks=[norm(t) for t in re.split(r"[\s\-_/]+", q) if norm(t)]
    scored=[]
    for r in rows:
        nn=norm(r["name"]); nd=norm(r.get("desc",""))
        s=0
        if nq and nq in nn: s+=100
        if nq and nq==nn: s+=200
        if toks and all(t in nn for t in toks): s+=60
        if toks and all(t in (nn+nd) for t in toks): s+=20
        if nq and nq in nd: s+=10
        if s: scored.append((s,r))
    scored.sort(key=lambda x:(-x[0], x[1]["name"].lower()))
    return [r for _,r in scored]

def main():
    flags={"--live","--offline"}
    args=[a for a in sys.argv[1:] if a not in flags]
    live="--live" in sys.argv
    offline="--offline" in sys.argv
    if not args:
        print("用法: query.py \"<模型名>\" [--live|--offline]"); return
    q=" ".join(args)
    rows, src = get_rows(force_live=live, offline=offline)
    specs = load_specs()
    res=search(q, rows)
    print(f"# ModelZoo 适配查询：「{q}」")
    print(f"数据源：{src}\n")
    if not res:
        print(f"❌ 未找到「{q}」的适配仓库。")
        print("建议：换关键词（如基座名 qwen/deepseek/llama）；或 --live 查最新；或人工浏览 https://developer.sourcefind.cn/codes/groups/modelzoo")
        return
    print(f"✅ 命中 {len(res)} 个仓库：\n")
    for r in res[:25]:
        print(f"## {r['name']}  [{framework(r['name'])}]")
        if r.get("desc"): print(f"- 简介：{r['desc']}")
        print_spec(specs.get(r["path"]))
        print(f"- 更新：{r['updated']}")
        print(f"- 网页：{r['url']}")
        print(f"- clone：`git clone {r['clone']}`\n")
    if len(res)>25: print(f"... 另有 {len(res)-25} 个，缩小关键词。")

if __name__=="__main__": main()
