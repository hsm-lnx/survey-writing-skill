# 检索界复核与补漏脚本

这组脚本回答两个问题：

1. **检索界到底划在哪**——不是协议写了什么，而是每个数据库通道实际能捕到什么。
2. **池里有没有从未被看过的合格研究**——不是只看「反查引用集」选中的那些。

所有脚本只做检索、去重、初筛与落盘，**不作准入判定**。是否纳入案例集／证据集，仍由人按项目判据裁决。

## 数据库与检索方向

| 方向 | 接口 | 检索字段 | 能补什么 | 边界 |
|---|---|---|---|---|
| 主检索 | Crossref `query.bibliographic` | 题名／作者／容器等著录字段 | 著录权威、期刊覆盖 | 相关度排序下的浅层捕获；**不支持摘要检索** |
| 主检索 | OpenAlex `title_and_abstract.search` | 题名＋摘要 | 摘要侧查漏 | 匿名限流紧；有 key 更稳 |
| 主检索 | AMiner `publicationV2` | 题名／作者 | 中文文献、无 DOI 老文献 | 相似度阈值 ≥ 0.85 |
| 复核 | Web of Science 平台 | 平台检索式 | 库覆盖查漏、完备性检验 | 手工导出，不是 API |
| 后向引文 | 种子文献的参考文献表 | 参考文献条目 | 更早的研究 | 依赖种子选择 |
| **前向被引** | OpenAlex `cites:` | 引用种子的全部记录 | 只写算法名、不写主题词的研究 | 依赖种子有 DOI；有引用滞后 |
| **算法名扩展** | OpenAlex `title_and_abstract.search` | 算法名／同义表述 | 主题词写法不同造成的漏检 | 召回高，必须人工判读 |
| **整池筛查** | 本地 L2 存活池 | 题名＋摘要 | 目的性选样下从未被看过的池内条目 | 依赖池重建的可复现性 |

## 推荐流程

```
citation_chase.py        种子 DOI -> OpenAlex cites: -> 原始被引记录
        ↓
citation_screen.py       去重 + 主题词初筛 + 与台账/正文差集 -> 池外候选
        ↓
citation_abstracts.py    补摘要 + 信号词初判 -> 待人工判读清单
        ↓
（人工判读）              逐条看题名与摘要，按项目判据裁决，不作脚本判定
```

整池补漏另走一条：

```
pool_screen.py           存活池逐条过信号词 -> known / out / blind 三层
        ↓
（人工判读 out + blind）  blind 只能按题名判，报告须声明覆盖缺口
```

检索界实测：

```
retrieval_boundary.py types        目标文献在 Crossref 是什么记录类型
retrieval_boundary.py depth        取消早停取满 N 页，深翻还有没有相关记录
retrieval_boundary.py type-free    摘掉类型过滤重跑，按类型统计代价
retrieval_boundary.py non-journal  定向枚举会议论文/书章/预印本
```

## 命令示例

```bash
# 1. 前向被引：种子取自正文参考文献编号
python skills/survey-ops/scripts/search/citation_chase.py \
  --manuscript manuscript/正文.md --targets 9,25,44 \
  --out reports/_raw/citation_chase.json

# 2. 去重与主题词初筛
python skills/survey-ops/scripts/search/citation_screen.py \
  --raw reports/_raw/citation_chase.json \
  --ledger bib/verified.md --manuscript manuscript/正文.md \
  --out reports/_raw/citation_chase_screen.json

# 3. 补摘要并标信号
python skills/survey-ops/scripts/search/citation_abstracts.py \
  --candidates reports/_raw/citation_chase_screen.json \
  --out reports/_raw/citation_chase_abstracts.json

# 4. 算法名扩展检索
python skills/survey-ops/scripts/search/algo_name_search.py \
  --ledger bib/verified.md --manuscript manuscript/正文.md \
  --out reports/_raw/algo_name_search.json

# 5. 整池筛查
python skills/survey-ops/scripts/search/pool_screen.py \
  --pool reports/_raw/pool.json \
  --ledger bib/verified.md --manuscript manuscript/正文.md \
  --out reports/_raw/pool_screen.json --digest reports/_raw/pool_digest.txt

# 6. Crossref 检索界实测
python skills/survey-ops/scripts/search/retrieval_boundary.py types \
  --manuscript manuscript/正文.md --targets 9,25,44
python skills/survey-ops/scripts/search/retrieval_boundary.py depth \
  --query 'welding "reinforcement learning"' --pages 30
```

## 环境变量（均可选）

| 变量 | 用途 | 不给会怎样 |
|---|---|---|
| `OPENALEX_API_KEY` | OpenAlex 更高额度 | 匿名也能跑，但限流更紧，深翻大批量时可能 429 |
| `OPENALEX_MAILTO` / `CROSSREF_MAILTO` | 礼貌池标识 | 仍可请求，但礼貌池优先级较低 |

脚本不读 `.env`，不硬编码密钥；缺 key 时按匿名方式请求，失败如实留痕，不得伪造返回。

## 落盘与报告纪律

- 原始返回一律落 `reports/_raw/`；报告写清执行日、查询串、页数、去重数与差集口径。
- 「无摘要」只能记为「未判」，不能记成「已排除」；报告须声明覆盖缺口。
- 题名初筛只是粗筛，不能替代摘要或全文判读。
- 任何「池内没有遗漏」的结论，都必须先说明池是怎么重建的、与历史漏斗数字是否对得上。
