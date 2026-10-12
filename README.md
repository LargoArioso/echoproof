# EchoProof

**给声音图表找出“数据不同、声音相同、问题答案不同”的可复验反例。**

这是一个零第三方运行依赖的研究原型，包含命令行工具、声音映射、有限域穷举、连续区间阈值分析、反例缩减、修复复验，以及带音频的离线中文报告。

**发布状态：早期研究原型（0.1.0）。** 本项目在仓库维护者提出的探索任务下，由 AI 编程助手主要完成实现、分析、测试与文档。自动检查和可复验记录支持这里声明的有限结论；尚未经过独立同行评审，也没有真人听觉实验结果。不声称全球首创、完整产品有效性或第三方工具存在普遍缺陷。

本项目代码按 MIT 许可发布，允许修改、分发和商业使用，但不提供保证。外部数据、软件和文献的权利不由本项目重新授予，详见 [来源与许可说明](NOTICE.md)。

新颖性候选是组合后的任务语义审计工作流。公开检索没有找到完全相同的成品，但不能证明全球无人开发；见 [调研记录](research/PRIOR_ART.md)。

本次运行的正确性证据、独立参考检查、性能记录和未验收事项见 [验证记录](research/VALIDATION.md)。

## 立即运行

需要 Python 3.9+。在本目录执行：

```sh
python3 -m echoproof demo --out artifacts/demo
python3 -m unittest discover -s tests -v
```

五个案例分别检查各自归一化、音高取整、缺失当零、漏采样与范围截断。每个案例输出 `index.html`、审计 JSON、修复 JSON、各任务反例 JSON，以及两组数据的 WAV。HTML 双击可离线打开，没有网络请求或自动播放。

## 自己定义检查范围

```sh
python3 -m echoproof audit --spec examples/per-series.json \
  --levels 1,2,3 --lengths 2,3 --tasks threshold,total \
  --threshold 2 --repair --out artifacts/custom
python3 -m echoproof verify artifacts/custom/threshold.witness.json
python3 -m echoproof verify artifacts/custom/audit.json
```

完整 `audit.json` 的复验会重跑声明输入范围，核对全部统计、原始与缩减反例、任务顺序和结论范围；仅复验 `*.witness.json` 则检查这一对反例。外部来源的真实性需要额外核对，不能由有限域重算单独认证。

`--include-missing` 将缺失加入输入字母表。所有长度、数值和任务均写进报告。穷举上限为 200,000 个序列；较大搜索应缩小范围。

支持任务：是否达到阈值、首尾已观测趋势、所有峰值位置、缺失数、已观测总和。只剩一个已观测值时趋势未定义；全缺失时总和未定义；阈值任务为 false。峰值下标从 0 开始。配置详见 [方法](research/METHOD.md)。

## 检查实际 CSV 数据

```sh
python3 -m echoproof probe examples/measurements.csv --column value \
  --spec examples/per-series.json --threshold 3 --out artifacts/csv-probe
```

此模式以 CSV 原始序列为起点，生成确定性的单位置变更与正仿射变换，检查保存的候选集合。报告带原文件 SHA-256、列名、原始序列、变换方法和全部候选，便于重跑。它不是对所有可能数据的穷举。输入上限为 64 行和 1 MiB，适合定位一段数据的问题。空值、NA、N/A、null、none、nan 作为缺失；其余字段必须为有限数值或有理数。

## 从有限网格推进到连续区间

同一种量化配置下，阈值 50 正好在音高边界上，阈值 51 却落在音高单元内部：

```sh
python3 -m echoproof threshold --spec examples/coarse-pitch.json \
  --threshold 50 --input-low 0 --input-high 100 --out artifacts/threshold50.json
python3 -m echoproof threshold --spec examples/coarse-pitch.json \
  --threshold 51 --input-low 0 --input-high 100 --out artifacts/threshold51.json
python3 -m echoproof verify artifacts/threshold50.json
python3 -m echoproof verify artifacts/threshold51.json
```

结果分别为 `preserved` 与 `collision_found`。解析结论覆盖闭实数区间，但只适用于固定映射、无缺失、stride=1 的声音事件通道。

## 重放缩减过程并核对输入来源

```sh
python3 -m echoproof verify artifacts/demo/normalization/threshold.trace.json
python3 -m echoproof verify artifacts/demo/normalization/threshold.trace.json \
  --audit artifacts/demo/normalization/audit.json
```

第一条只验证每一步删除仍保留冲突、最终无法再成对删点，输出 `TRACE_VERIFIED (domain membership not checked)`。第二条还完整重算父审计、核对输入成员与审计指纹，输出 `TRACE_AND_DOMAIN_VERIFIED`。它不认证外部数据提供方；真实观测来源另行逐年核对。

记录保留原位置索引，明确不同长度反例不执行成对删除。证书比较保留 JSON 类型：真假答案不能改为数字 0/1，整数事件字段不能被偷偷改为其他类型。

## 按任务合成补充提示

```sh
python3 -m echoproof cues artifacts/demo/quantization/audit.json \
  --out artifacts/cues-quantization
python3 -m echoproof verify artifacts/cues-quantization/plan.json
```

工具按原始声音类别，为不同的联合任务答案生成二进制提示。量化案例最大有 8 种联合答案，使用 3 位，达到给定原始声音后的固定长度二进制码下界。保存码本、原始/修复 WAV、示例事件和离线报告，并对全部声明输入验证机器解码答案。无歧义类别不加提示；域外输入拒绝。这不证明真人听觉表现，也不保证码字易学。

## 连续数据的其他任务

```sh
python3 -m echoproof interval-audit --input-low 0 --input-high 10 \
  --out artifacts/continuous-tasks
python3 -m echoproof verify artifacts/continuous-tasks/endpoint_trend.certificate.json
```

该命令检查五项任务，生成每项连续区间证书与可听反例。在任何非零宽度实数区间中，固定范围、有限量化步长的单音高映射，都有一小段相同音高的不同数值。交换其中两个数值可以反转趋势与峰位；单点总和也不同。即使步长缩小为 1 cent，仍能构造严格区间内的精确冲突。

因此，有限网格没有冲突不能推出连续数据全部保留；更细的步长可以缩小冲突区间，却不能完全修复这三项任务。阈值在切换边界上仍可保留。无缺失假设下缺失数恒为 0；单值输入区间则由时长确定序列长度并保留全部任务。这些结论不覆盖带额外答案通道、非量化音高或其他表示方式。

## 固定含义的提示与连续区间修复

```sh
python3 -m echoproof semantic-cues artifacts/demo/normalization/audit.json \
  --out artifacts/semantic-normalization
python3 -m echoproof verify artifacts/semantic-normalization/validation.json
python3 -m echoproof align-threshold --spec examples/coarse-pitch.json \
  --threshold 51 --input-low 0 --input-high 100 --out artifacts/threshold51-alignment.json
python3 -m echoproof align-thresholds --spec examples/coarse-pitch.json \
  --thresholds 50,51 --input-low 0 --input-high 100 --out artifacts/multi-threshold50-51.json
python3 -m echoproof verify artifacts/multi-threshold50-51.json
```

固定语义提示为“达到／未达到阈值”和“上升／下降／持平／未定义”提供全局一致的声音词汇，附在原始事件后。这里的两项任务合计增加 1,740 毫秒；36 个归一化案例输入全部解码正确。它直接编码原始数据的任务答案，支持原网格以外的有限序列；不同于按原始声音类别分配的短二进制码，本方案不宣称最短，也没有验证真人易学程度。

范围修复保持音域、音高步长与原始范围覆盖，改变一个端点并为所有候选生成连续区间证书。阈值 51 的最小单端点改动是把范围 0–100 调成 0–102，但这会失去原来保留的阈值 50。报告同时保存副作用和联合约束检查。

`align-thresholds` 对 2–16 个不同、非恒定阈值检查是否能同时保留，允许改变两个范围端点。固定音域与步长时，音高边界等距；两个阈值的边界索引决定整个范围，因此可以有限枚举，给出可行方案或模型内的不可行证书。50 与 51 的间距小于最小边界间距 100/3，证明在当前覆盖约束下不可能同时保留。搜索最多 200,000 个边界配对，超过上限会明确拒绝，不会报告“不可行”。

## 证据边界

- 相同事件在内置确定性播放器中生成相同 PCM 字节。
- 声音不同不代表人耳能区分；没有做听觉或无障碍用户实验。
- 网格上无反例只意味着这个网格没有冲突，不代表现实数据全都安全。
- 可选实验已直接调用 Erie 1.0.1 编译器，并保存“纯音相同、完整语音队列不同”的反向案例；见 [接入实验](integrations/erie/README.md)。核心映射仍是自己的模型；另已对 Highcharts 13.1.1 的原始内部映射函数做受控核对，未运行完整 Chart 或播放器，见 [第二后端核对](integrations/highcharts/README.md)。
- 语音标签、图形、时间戳、多声部与交互不在当前模型中。

## 审计真实编译记录的完整通道

可选 Erie 实验的 `corpus.cjs` 会对 27 个序列分别捕获自动数值范围和平均值汇总规范的原始队列。然后用 Python 检查录制结果：

```sh
node integrations/erie/corpus.cjs
python3 -m echoproof compiled artifacts/erie-corpus/aggregate-mean.corpus.json \
  --threshold 3 --out artifacts/erie-mean-full
python3 -m echoproof compiled artifacts/erie-corpus/auto-domain.corpus.json \
  --threshold 3 --out artifacts/erie-auto-full
python3 -m echoproof compiled artifacts/erie-corpus/auto-domain.corpus.json \
  --scope erie_tone_stream --threshold 3 --out artifacts/erie-auto-tone
```

默认完整队列范围保留语音；纯音范围必须显式选择。只删除原始数据元信息 `__datum`，不抹掉语音或未知声音项。任务针对变换前原始输入，因而平均值汇总可能与“原始输入是否出现尖峰”发生冲突。这是问题与汇总方式的兼容性检查，不自动意味着库的错误。

录制反例的复验只检查保存的队列相等与任务答案不同，显示 `RECORDING_VERIFIED (backend not rerun)`，不冒充重新运行外部编译器。重新捕获应运行 Node 脚本。

## 未修改的真实观测案例

```sh
python3 tools/real_data_case.py
```

本地保存 NOAA 原始年度 CO₂ CSV，来源注释与文件哈希保留。67 个年度观测组成全部 65 个连续三年窗口，未经改动；逐窗口归一化后有 15 个声音事件类别，400 ppm 阈值有 49 对冲突。一个完整反例是 1960–1962 与 2013–2015：前者均低于 400，后者包含 401.01，而声音事件完全相同。

实验采用相同相对时间，不编码或朗读绝对年份与 ppm；不把它当作完整气候图表的错误。完整窗口、缩减反例和来源分别保存，窗口年份和原值还会对存档逐项复核。数据提供者、原文件指纹与测站说明见 [来源记录](research/data/noaa/README.md)。

审计器现在同时保留 `original_witness` 和缩减后的 `witness`：前者确实属于声明输入集合，后者可能因删除点而离开该集合。报告明确展示这一区别。

## 第二后端：明确只检查映射函数

可选 Highcharts 核对锁定官方 13.1.1 源码，在内存中追加内部函数导出，调用原始函数及原始辅助模块；没有修改函数体，没有运行 Chart 或 AudioContext。手动提供 point、极值与捕获通道，保存全部乐器参数及事件时间。

27 个受控三点输入有 8 种映射输出。阈值 50 冲突 0 对，阈值 51 冲突 19 对；首尾趋势与峰值位置仍可能丢失。因此单一阈值正确不能推出其他任务正确。常数序列映射到最小音高，也与核心模型的中点规则不同。它不是完整图表验证；数据范围极值是人工测试输入。复现步骤与边界见 [接入说明](integrations/highcharts/README.md)。

## 隔离目录一键复现

```sh
python3 tools/reproduce.py --out /tmp/echoproof-reproduction --recordings --tests
```

目标目录必须不存在或为空；工具不会删除旧报告。它在隔离目录重建核心声音案例、CSV 检查、两种提示、单／多阈值修复，并检查全部生成证书、音频与链接。`--recordings` 只复验已保存的外部输出，不重新执行外部后端，也不联网；`--tests` 运行自动检查。阶段日志与核心源码指纹保存在 `reproduction.json`。本次 24 个阶段全部通过。

`python3 tools/package_snapshot.py` 生成带逐文件 SHA-256 清单的本地 ZIP，排除下载源码、第三方依赖与缓存。完整成果包仍可离线运行核心及保存记录的复验；重新捕获外部后端需另外按接入说明下载锁定源码。

## 为后续真人实验准备材料

```sh
python3 -m echoproof study-kit artifacts/demo/quantization/audit.json \
  --out /tmp/echoproof-listening-kit
python3 -m echoproof check-study /tmp/echoproof-listening-kit
```

材料按真实审计输入选择：4 个有歧义的原始声音组、10 个原始案例，每种答案等次数重复；两种 session 使用相同案例与顺序，分别播放原始事件与对应任务的固定语义提示。共 40 个试次 WAV 与 6 个训练图例。参与者表不含原始数值、答案或条件标签；提示能被听见，不宣称条件盲法。

一个参与者只使用一个条件，减少跨条件先听到答案的影响。研究者答案表与来源审计放在独立目录，配有空白响应表和 [研究协议](artifacts/study-kit/PROTOCOL.md)。输出必须为空目录，重复生成不会覆盖已填写响应；材料校验也不把未读取的响应冒充“零个真人结果”。没有招募、收集或生成真人成绩，不提供功效或有效性结论。

## 可导出的说明图

已保存 [阈值修复图](artifacts/figures/threshold-repair.png) 与 [真实窗口对照图](artifacts/figures/observed-windows.png)，并提供同名 SVG。独立图形已检查边界、数值和图例布局；这不等于离线 HTML 的浏览器视觉验收。

可选重新生成：`python3 tools/figures.py`，需要 Matplotlib。它只用于说明图，核心、证书和离线复现不需要 Matplotlib。

## 文件结构

`echoproof/` 为实现；`tests/` 为测试；`research/` 为调研及方法；`examples/` 为配置；`artifacts/` 为复现输出。

`integrations/erie/` 为可选 Node 接入实验，其依赖与核心 Python 工具分开。核心仍可完全离线、零第三方运行依赖执行。

许可：MIT，范围为本项目编写的代码及文档；第三方材料见 [NOTICE.md](NOTICE.md)。实现由 AI 辅助生成，没有有意复制相关工具的实现；这不是对所有代码来源或权利的穷尽鉴定。

## 用非均匀分区同时保留多个阈值

线性等距映射下，0–100 范围、1200 cents 步长无法同时保留 50 和 51 两个判断。允许改变数据区间的宽度后，可以用原有四个音高中的三个音：`[0,50)` → 4800 cents，`[50,51)` → 7200 cents，`[51,100]` → 8400 cents。每个采样仍只有一个音，时间槽与音符时长保持原设置。

```sh
python3 -m echoproof partition-thresholds --spec examples/coarse-pitch.json \
  --thresholds 50,51 --input-low 0 --input-high 100 --out artifacts/partition-thresholds
python3 -m echoproof verify artifacts/partition-thresholds/partition.json
```

[可听对照](artifacts/partition-thresholds/index.html)与证书覆盖区间内任意正长度、无缺失序列。声明区间必须覆盖原映射范围；固定映射、不漏采样。M 个不同的非恒定阈值产生 M+1 个单点答案向量，固定时间且每点只允许一个音时，至少需要 M+1 个音高符号。本构造达到这个特定下界；音高不够时返回容量不可行证书。它改变了线性映射假设，不与线性不可行结果矛盾；不恢复精确数值，也不证明真人易学。


分区还保留每项阈值的逐采样真假值，`PartitionEncoder.profiles(render)` 可返回达到阈值的位置、数量、any/all、首次与末次索引。它不推断连续暴露时间。

```sh
python3 tools/real_data_partition.py artifacts/noaa-partition
```

[真实窗口计数对照](artifacts/noaa-partition/index.html)：固定310–430 ppm范围，三个判断边界350/400/420 ppm，原始与分区表示都产生10个事件类别；65个原始窗口中，相同声音却位置/计数不同的输入对从179/53/9降至0/0/0。值、年份、全部事件和来源哈希保留，按存档逐项重算；没有人耳结果或风险结论。


## 理想解码上限与先验

```sh
python3 -m echoproof decision-bound artifacts/demo/quantization/audit.json --out artifacts/decision-base
python3 -m echoproof decision-bound artifacts/demo/quantization/audit.json \
  --representation conditional_task_cues --out artifacts/decision-cued
python3 -m echoproof verify artifacts/decision-base/decision.json
python3 tools/decision_comparison.py artifacts
```

有限声音类别内的最大答案权重，求和后除以总权重，得到只有精确事件与声明先验的理想解码器可达到的最优零一正确率。保存完整答案分布和预测查表，验证器重新枚举。默认每个不同输入等权；也可用 `--weights weights.json` 声明与规范化输入顺序一致的非负有理数权重，总权重必须为正。它们不是自然频率，零权重输入不影响正确率。

原量化案例36个等权输入：阈值/趋势/峰位三个答案必须一起正确时，原事件最优上限1/3，有限条件提示为1。另一个[四表示比较](artifacts/decision-comparison/index.html)统一只问阈值与首尾趋势，原事件1/2，三种修复为1；分别平均660/1260/2400/660 ms，实际使用2/5/6/3种音高。

比较前沿使用三个明确方向：正确率最大、时长最短、使用音高数最少。任何输入域、先验、问题或来源映射不同的候选都会拒绝比较。这不是人的认知负担测量，也不推荐某种表示；分区在有限网格上保留趋势不证明连续区间也保留。声明输入上限5000，权重顺序来自去重后的输入顺序，可在证书每类 `input_indices` 追踪。

![有限先验下的理想决策能力](artifacts/figures/decision-tradeoffs.png)


## 验算特定快照

```sh
python3 tools/package_snapshot.py
python3 tools/smoke_snapshot.py --out ../echoproof-package-check --recordings
```

输出目录必须全新或为空。工具核对归档目录与清单，确认Python加载的是解压副本，再从该副本完整离线复现并运行检查；日志在输出目录的 `smoke.json`。清单说明字节一致性，不认证作者身份；日志只证明所记SHA-256的具体归档，不能沿用到之后重新打包的文件。实验响应文件不在此流程中覆盖。

生成的 ZIP 不纳入仓库版本控制。可使用 GitHub 的 Download ZIP 获取仓库，或运行上述打包命令生成成果包；新生成的包需要重新验算。已保存的脱敏检查日志对应其所记哈希的本地归档，不能当作 GitHub 下载包的验证记录。


## 检查报告值之外的实际阈值是否可确定

```sh
python3 -m echoproof uncertain-threshold examples/uncertain-report.json \
  --spec examples/coarse-pitch.json --out artifacts/observation-uncertainty/ambiguous
python3 -m echoproof verify artifacts/observation-uncertainty/ambiguous/observation.json
python3 tools/observation_cases.py artifacts/observation-uncertainty
```

输入明确包含 `reported`、`intervals`、`threshold` 三个字段。报告50、实际值允许49.9–50.1、阈值50时，报告值答案为true，允许实际答案为false/true，状态为 `not_identifiable`。即便原声音映射直接输入实际值时保留了阈值50，它也不能从相同的报告50判断究竟是哪种实际情况。

[四个合成案例](artifacts/observation-uncertainty/index.html)包含确定真、确定假、无法确定以及声明偏差。所有区间组合被调用方假定可行；无缺失、无其他相关约束，没有概率或覆盖率声明。不把NOAA标准不确定度列当作硬界。声音与固定答案提示仍对报告值正确；这一检查的问题是允许的实际值。方法与相关研究见[说明](research/OBSERVATION_METHOD.md)。

![不确定性可能出现在声音映射之前](artifacts/figures/observation-identifiability.png)


## 单入口阈值诊断

```sh
python3 -m echoproof diagnose examples/diagnosis-joint.json --out artifacts/diagnosis-cases/joint
python3 -m echoproof verify artifacts/diagnosis-cases/joint/diagnosis.json
python3 tools/diagnosis_cases.py artifacts/diagnosis-cases
```

[六个诊断案例](artifacts/diagnosis-cases/index.html)统一观测可确定性、原表示契约、共享标尺/全采样、单端点与联合范围搜索、非均匀分区及原有边界回归。输出只展示可核验的受约束设计，不自动应用，也不推荐全局最优方案。

输入字段为 `mapping`、`thresholds`（数组）、`reported_input_interval`；可另给 `reported`。`question=admissible_actual` 必须同时给 `reported` 和 `actual_intervals`。实际问题不可确定时，名义映射方案仍单独展示，不能当作实际答案恢复。缺失值及非阈值任务不在该入口的契约内。

数值阈值契约另补了两种全域反例：逐序列归一化的两份单点数据产生同一中点音高；固定标尺漏采样可在被跳过的第二点隐藏达到阈值的值。常量阈值答案与表示无关。旧固定标尺连续证书接口保持原范围；新契约单独验算。

“不可行”限定于覆盖范围的线性族或固定单音高容量；超出搜索上限标为 `not_searched`。分区构造若覆盖更大的原始范围，会明确列出该构造区间。所有受请求阈值会重新检查，额外失去的原有阈值也记录；其他数据任务没有因此得到保留保证。
