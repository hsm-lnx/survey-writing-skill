# 检索界复核与补漏

> 对应 `survey-ops` §7.5。适用于「检索是否充分／有没有漏／检索界划在哪」一类请求。
> 脚本在 `scripts/search/`，逐项用法见该目录 `README.md`。
> 本节只定**查什么、怎么对账、怎么报告**；是否纳入由项目判据裁决。

## 0. 什么时候跑

- 案例集／证据集定稿前，需要说明「为什么这批文献够了」。
- 用户问「检索手段是否充分」「有没有漏掉的研究」。
- 换了数据库、检索式或时间窗，需要重新确认检索界。
- 某条新文献的发现路径无法归因：是关键词没命中、库没收录，还是根本没被看过。

不跑的情形：只补一条已知文献的著录、只改正文措辞、只做引用覆盖核对。

## 1. 先把检索方向拆开

同一个「检索」包含四种不同动作，漏检归因必须先分清是哪一种：

| 方向 | 做什么 | 补什么 | 典型盲区 |
|---|---|---|---|
| **主检索** | Crossref／OpenAlex／AMiner 按查询串抓记录 | 建立检索池 | 相关度排序的浅层捕获；Crossref 无摘要检索 |
| **复核检索** | Web of Science 等平台另跑一次 | 库覆盖缺口 | 平台导出滞后；不能替代主检索 |
| **后向引文** | 翻种子文献的参考文献表 | 更早的研究 | 种子选得窄就滚不出去 |
| **前向被引** | OpenAlex `cites:` 抓引用种子的记录 | 只写算法名、不写主题词的研究 | 种子必须有 DOI；新研究有引用滞后 |

> 关键区分：**引文追溯补的是主题词表述缺口，WoS 复核补的是库覆盖缺口，两者不是同一件事。** 报告里不得混写。

## 2. 数据库范围与已知边界

### 2.1 Crossref

- `query.bibliographic` 检索**题名／作者／容器**等著录字段，**不支持摘要检索**。摘要侧由 OpenAlex 的 `title_and_abstract.search` 承担。
- 主检索若按「相关度排序 + 整页无字面命中即停」操作化，实际只取前几页，是**浅层捕获**，不是 2015–2026 全量布尔命中。写检索界时必须按「相关度排序下的浅层捕获」表述，不能写成「全量命中」。
- `type:journal-article` 过滤只覆盖期刊部分。非期刊记录（会议论文、书章、预印本）经 OpenAlex、WoS 复核与引文追溯入池。类型过滤对查全的代价要用 `retrieval_boundary.py` 实测，不能凭感觉判断。

### 2.2 OpenAlex

- 摘要覆盖好，适合 `title_and_abstract.search` 与前向被引。
- 匿名池限流紧；大批量深翻时串行、页间退避，失败留痕即停，不得绕限。
- 当日额度耗尽（429）时，可改用 Crossref `works/{DOI}` 的 `abstract` 字段补摘要；仍无摘要的记为「未判」。

### 2.3 AMiner

- 用于中文文献、无 DOI 老文献；相似度 ≥ 0.85 才算命中。
- 端点失效时如实报告未验证条目，不得自创新端点或改用未经验证的镜像。

### 2.4 Web of Science

- 复核检索角色：查漏与完备性检验，著录权威仍按 Crossref 序。
- 平台导出件是手工产物，报告须登记执行日、检索式与导出文件。

### 2.5 引文追溯与前向被引

- 后向引文从核心案例与近邻综述的参考文献表滚雪球，能纳入 2015 年前研究。
- 前向被引用 OpenAlex `cites:` 对种子逐条抓取，能捕获「摘要只写算法名、不写主题词」的研究。
- 两者都依赖种子选择：种子不在引用集里，前向被引也无从发起。

## 3. 四类补漏实测

### 3.1 前向被引

```bash
python scripts/search/citation_chase.py --manuscript 正文.md --targets 9,25,44
python scripts/search/citation_screen.py --raw reports/_raw/citation_chase.json
python scripts/search/citation_abstracts.py --candidates reports/_raw/citation_chase_screen.json
```

对账口径：种子解析成功数／去重后被引记录数／题名含主题词数／与台账正文差集后的池外数／可得摘要数／信号命中数。**无摘要的条目单列，不得算作「已排除」。**

### 3.2 算法名扩展

```bash
python scripts/search/algo_name_search.py --ledger bib/verified.md --manuscript 正文.md
```

适用症状：主检索用「主题词 AND 方法词」，但部分研究全篇只写具体算法名或同义表述。把算法名／同义表述作为查询串，再与台账正文做差集。

### 3.3 整池筛查

```bash
python scripts/search/pool_screen.py --pool reports/_raw/pool.json \
  --ledger bib/verified.md --manuscript 正文.md \
  --out reports/_raw/pool_screen.json --digest reports/_raw/pool_digest.txt
```

前提：池必须能**复现**。先用原漏斗脚本重建 L2 存活池，逐项对账（L1 works／基准集／布尔核验剔除／同型重复剔除／存活池），数字一致才可整池判定。对不上就停，不得拿一个来源不明的池做判定。

输出三层：

| 层 | 含义 | 处置 |
|---|---|---|
| `known` | DOI 已在台账／正文 | 不再判 |
| `out` | 题名或摘要含信号词、且不在台账／正文 | 逐条判读 |
| `blind` | 无摘要且题名无信号词 | 只能按题名判，报告声明覆盖缺口 |

**整池筛查的价值**：目的性选样只判「反查引用集」找到的条目，池内未被反查到的合格研究可能从未被看过。整池判定补的就是这层。代价是池有多大就要逐条过一遍。

### 3.4 检索界实测

```bash
python scripts/search/retrieval_boundary.py types --manuscript 正文.md --targets 9,25,44
python scripts/search/retrieval_boundary.py depth --query 'welding "reinforcement learning"' --pages 30
python scripts/search/retrieval_boundary.py type-free --query 'welding AND "reinforcement learning"'
python scripts/search/retrieval_boundary.py non-journal --query 'welding AND "reinforcement learning"'
```

- `types`：量目标文献在 Crossref 的记录类型，回答「类型过滤把哪些案例挡在通道外」。
- `depth`：取消早停取满 N 页，回答「深翻是否还有相关记录」。若新增记录全是无关主题，说明早停规则是合理的操作化，应在方法节写实。
- `type-free`：摘掉类型过滤重跑，按记录类型统计池外新增。
- `non-journal`：定向枚举会议论文／书章／预印本，补 Crossref 期刊通道覆盖不到的部分。

## 4. 结论怎么写

报告至少分三句：

1. **池内完整性**：池能否复现；整池判定新增多少候选；其中多少纳入、多少未纳入以及理由。
2. **检索界写实**：每个通道实际是「浅层捕获」还是「穷尽布尔集」；Crossref 是否检索摘要；类型过滤的实测代价。
3. **残留缺口**：无摘要多少条、只按题名判多少条、哪类缺口由 WoS 复核补、哪类由引文追溯补。

禁用写法：

- 「已穷尽检索」——除非每个通道都做到全量且可复现。
- 「无遗漏」——无摘要条目只能写「未判」，不能写「无关」。
- 「检索手段充分」不带边界——应写成「对已覆盖部分充分，但受 X／Y 限制」。

## 5. 落盘与隐私

- 原始返回落 `reports/_raw/`，报告落 `reports/`；两者都应进入项目的版本管理或备份。
- 报告不得写入个人邮箱、密钥、本机绝对路径、未公开的项目内部信息。
- 脚本不读取 `.env`，不硬编码任何密钥；缺 key 时按匿名方式请求并如实留痕。
