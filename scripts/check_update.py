#!/usr/bin/env python3
"""每月检查 ModelZoo 是否有更新：拉 live API，与 snapshot diff。
报告: 新增仓库、更新的仓库(last_activity 变化)、删除的仓库。
带 --apply: 刷新 snapshot + 重生成 Obsidian 清单表。
"""
import json, sys, re, urllib.request, ssl, pathlib, datetime

import os
ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT/"data"/"modelzoo_snapshot.json"
# 输出目录：环境变量 DCU_MODELZOO_OUT_DIR 优先，否则技能内 output/（便携默认）。
OUT_DIR = pathlib.Path(os.environ.get("DCU_MODELZOO_OUT_DIR", str(ROOT/"output"))).expanduser()
VAULT = OUT_DIR/"ModelZoo仓库清单.md"
API = "https://developer.sourcefind.cn/codes/api/v4/groups/modelzoo/projects?per_page=100&include_subgroups=true&order_by=name&sort=asc&page="
_ctx = ssl.create_default_context(); _ctx.check_hostname=False; _ctx.verify_mode=ssl.CERT_NONE

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

def cat(n):
    s=n.lower()
    pairs=[(("qwen","deepseek","llama","glm","chatglm","baichuan","yi-","internlm-","kimi","gemma","mistral","mixtral","phi-","ernie","falcon","bloom","gpt","codegeex","codestral","minimax","longcat","spark-x","llada","sensenova","moss","aquila","skywork","telechat"),"大语言模型LLM"),
        (("-vl","_vl","llava","internvl","minicpm-v","blip","florence","emu","bagel","cogvlm","janus","qwen-vl","glm-4v","deepseek-vl","paddleocr-vl"),"多模态VL"),
        (("stable","diffusion","controlnet","animatediff","comfyui","draggan","cogvideo","hunyuan","flashvideo","flux","sdxl","catvton","anytext","direct3d","wan","kolors","pixart","lumina"),"生图/视频"),
        (("yolo","detr","centernet","centerface","ssd","rtmdet","dino","co-detr","ddq"),"检测"),
        (("segment","sam","segformer","deeplab","unet","upernet","crf-rnn","mask2former"),"分割"),
        (("dbnet","crnn","ocr","deepsolo","abinet","svtr"),"OCR"),
        (("reid",),"ReID"),
        (("resnet","densenet","convnext","efficientnet","vit","swin","mobilenet","regnet","vgg","inception","repvgg","hrnet"),"图像分类/Backbone"),
        (("depth-anything","evtexture","flavr","cyclegan","codeformer","diffbir","esrgan","gfpgan","basicvsr"),"图像/视频增强"),
        (("whisper","funasr","cosyvoice","conformer","tts","asr","audiofly","fun-audio","fastspeech","vits","sensevoice","fish-speech"),"语音ASR/TTS"),
        (("bert","roberta","electra","embedding","bge","rerank","m3e","gte"),"NLP/Embedding"),
        (("deepmd","fastfold","openfold","alphafold","esm","unimol"),"科学计算AI4S"),
        (("clip","align","beit3"),"多模态对齐"),
        (("rag","db-gpt","agent"),"应用/Agent")]
    for keys,label in pairs:
        if any(k in s for k in keys): return label
    return "其他"

def framework(name):
    s=name.lower()
    for k,v in {"pytorch":"PyTorch","mmcv":"mmcv","paddle":"Paddle","oneflow":"OneFlow","migraphx":"MIGraphX","onnxruntime":"ONNXRuntime","tensorflow":"TensorFlow","bladedisc":"BladeDISC","fastertransformer":"FasterTransformer","vllm":"vLLM"}.items():
        if s.endswith("_"+k) or "_"+k+"_" in s or s.endswith("-"+k): return v
    return "—"

def write_vault(rows):
    import collections
    rows=sorted(rows,key=lambda r:(cat(r["name"]),r["name"].lower()))
    counts=collections.Counter(cat(r["name"]) for r in rows)
    fwc=collections.Counter(framework(r["name"]) for r in rows)
    d=datetime.date.today().isoformat()
    L=[f"# 海光光合社区 ModelZoo 仓库清单（{len(rows)}）\n",
       "> 来源：https://developer.sourcefind.cn/codes/groups/modelzoo （GitLab group id 831, public）",
       f"> 导出/刷新日期：{d}　|　共 {len(rows)} 个 DCU 模型适配仓库",
       "> 每仓库 = 一个模型在海光 DCU 上的适配代码，含 README(部署说明)/doc/model.properties。",
       "> 配套：[[DTK/DAS文档库]] · [[vLLM-DCU部署指南]]　|　自动刷新：dcu-modelzoo 技能 check_update.py\n",
       "## 分类统计\n","| 类别 | 数量 |","|---|---|"]
    for k,v in counts.most_common(): L.append(f"| {k} | {v} |")
    L+=["\n## 框架分布\n","| 框架 | 数量 |","|---|---|"]
    for k,v in fwc.most_common(): L.append(f"| {k} | {v} |")
    L.append("\n## 全量清单\n"); cur=None
    for r in rows:
        c=cat(r["name"])
        if c!=cur:
            cur=c; L+=[f"\n### {c}（{counts[c]}）\n","| 仓库 | 框架 | 简介 | 更新 |","|---|---|---|---|"]
        desc=(r.get("desc") or "").replace("|","/")[:70] or "—"
        L.append(f"| [{r['name']}]({r['url']}) | {framework(r['name'])} | {desc} | {r['updated']} |")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    VAULT.write_text("\n".join(L),encoding="utf-8")

def main():
    apply="--apply" in sys.argv
    old={r["id"]:r for r in json.load(open(SNAP,encoding="utf-8"))} if SNAP.exists() else {}
    try:
        live=load_live()
    except Exception as e:
        print(f"❌ API 拉取失败：{e}"); sys.exit(1)
    new={r["id"]:r for r in live}
    added=[r for i,r in new.items() if i not in old]
    removed=[r for i,r in old.items() if i not in new]
    changed=[r for i,r in new.items() if i in old and r["updated"]!=old[i].get("updated")]
    d=datetime.date.today().isoformat()
    print(f"# ModelZoo 月度更新检查　{d}")
    print(f"旧 {len(old)} → 新 {len(new)} 仓库\n")
    print(f"🆕 新增 {len(added)}：")
    for r in sorted(added,key=lambda x:x['updated'],reverse=True):
        print(f"  + {r['name']}  ({r['updated']})  {r.get('desc','')[:50]}")
    print(f"\n🔄 更新 {len(changed)}：")
    for r in sorted(changed,key=lambda x:x['updated'],reverse=True)[:40]:
        print(f"  ~ {r['name']}  {old[r['id']]['updated']}→{r['updated']}")
    if len(changed)>40: print(f"  ... 另 {len(changed)-40}")
    print(f"\n🗑️  删除 {len(removed)}：")
    for r in removed: print(f"  - {r['name']}")
    if not (added or changed or removed):
        print("\n✅ 无变化。")
    if apply:
        json.dump(live,open(SNAP,"w"),ensure_ascii=False,indent=0)
        json.dump({"fetched":d,"count":len(live)},open(SNAP.parent/"snapshot_meta.json","w"),ensure_ascii=False)
        write_vault(live)
        print(f"\n💾 已刷新 snapshot + Obsidian 清单（{VAULT}）")
    else:
        print("\n（只读检查。加 --apply 刷新 snapshot 与 Obsidian 清单）")

if __name__=="__main__": main()
