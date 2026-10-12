# EchoProof 调研记录

检索日期：2026-10-11（Asia/Shanghai）。这是一份可追踪的公开资料检索，不是全球不存在证明，也不是专利检索。

## 问题与拟贡献

声音图表把数值映射为音高、时长等声音参数。这里关注一个较窄的软件问题：**输出相同，但数据问题的答案不同**。拟实现的贡献是把有限域穷举、任务相关冲突、可携带反例证书、反例缩减、修复配置复验和离线可听报告结合成一个小工具，并对特定阈值映射提供连续区间分析。

信息丢失、量化、归一化和测试本身均不是新发现。新颖性候选是这套面向声音图表的数据语义检查工作流。不能仅凭检索结果称“世界首创”。

## 最接近的公开工作

| 来源 | 已有能力 | 与本原型的关系 |
| --- | --- | --- |
| [Erie 原作者网页论文](https://see-mike-out.github.io/erie-editor/paper/) / [实现仓库](https://github.com/see-mike-out/erie-web) | 声音图表声明语法、声音队列、编码通道、图例和组合 | 说明可以把映射与播放器分开。本文检索到的页面未展示自动搜索任务答案冲突并生成反例证书的功能；没有完整审计其所有代码。 |
| [Highcharts Advanced Mapping](https://www.highcharts.com/docs/sonification/advanced-mapping) | 按系列、图表或坐标轴选择映射范围，使用音阶，定制映射 | 说明共享范围与各系列独立范围是现实存在的设计选择。本原型没有复刻 Highcharts 的全部行为，也不声称发现其具体缺陷。 |
| [Highcharts Audio Charts](https://www.highcharts.com/docs/sonification/getting-started) | 多声音轨、语音、上下文提示、导航、MIDI 导出 | 实际应用可能通过语音或互动恢复信息。EchoProof 第一版只审计自己的纯离散声音通道。 |
| [Sonification Sandbox 原始会议报告](https://www.resna.org/sites/default/files/legacy/conference/proceedings/2004/Papers/Research/TCS/Sonification.html) | 创建声音图表、控制参数、上下文提示 | 不能把“创建声音图表”作为本项目的原创点。 |
| [Sahyun 学位研究结论](https://sahyun.net/phd/chapter10.html) | 听觉与视觉图表比较、曲率和斜率提示、听觉偏好测试 | 证明听觉评估和辅助通道已有长期研究。软件证书不能替代真人研究。 |
| [Ramakrishnan, Sonification and Information Theory，出版方页面](https://link.springer.com/chapter/10.1007/978-3-642-12439-6_7) | CMMR/ICAD 2009、2010 年出版；将信息论用于声音化设计，提出熵声音化及分析框架 | 明确排除“首次把信息论用于声音化”的说法。页面摘要已读取，付费正文未读取；作者公开稿检索片段显示对声音图表上下文和通信信息量的讨论。 |
| [Higher-order sonification of the human brain](https://pmc.ncbi.nlm.nih.gov/articles/PMC12660788/) / [作者预印本](https://assets-eu.researchsquare.com/files/rs-6623643/v1_covered_3ccb14ab-893e-4cd9-a3e7-683e35daff65.pdf?c=1764605668) | 检索摘要明确提及反向映射、NMSE 等信息丢失指标 | 信息丢失度量已有工作。本项目关注某个问题的不同答案是否坍缩到相同输出，而非把一般重建误差当作任务失败。PMC 正文访问遇到验证码；本条依据检索返回摘要与预印本片段，不能声称已通读。 |

## 检索式与结果边界

实际使用的检索式包括：

- `sonification "metamorphic testing"`
- `sonification "information loss" testing tool`
- `"sonification" "collision detection" software`
- `"sonification" "automated" "verification"`
- `"sonification" "counterexample"`
- `"sonification" "property-based"`
- `"auditory graphs" "testing" github`
- `"sonification" "injectivity"`
- `site.github.com sonification audit testing information loss`
- `"sonification" "semantic" "testing" software`
- `sonification "automated" "repair"`
- `sonification "task" "information preserving"`
- `sonification "minimum" "bits" auditory graphs`
- `"sonification" "counterexample" "verification"`
- `"Sonification and Information Theory" authors 2009 pdf`

结果包含数据声音化平台、听觉实验、其他音频测试，以及与空间碰撞或粒子碰撞有关的项目。在这批检索返回结果中，没有识别出与“自动生成数据任务冲突证书并复验修复”完全对应的成品。搜索引擎覆盖有限，未索引项目、其他术语、私人项目和未发表研究都可能存在。

## 可成立与不可成立的结论

可成立：在本次检索范围内，找到一个值得做的具体软件切口，并实现一套独立编写的原型。已有资料支持所选映射机制与评估问题的现实性。

不可成立：证明全球无人开发、证明所有相关工作不存在、宣称新的信息论定理、宣称对盲人用户已验证有效、宣称对 Erie 或 Highcharts 所有功能已经完成审计。

下一步应扩大 ICAD/CHI/ASSETS 论文和仓库覆盖，接入真实声音队列，并与声音图表作者及潜在使用者共同验证任务定义。

后续进展：已直接下载并验证官方 Erie 1.0.1 npm 包，调用其编译器跑四个具体规范。自动范围的纯音部分出现仿射冲突，但完整队列的语音图例不同。该观察缩小了可成立的冲突范围；结果和复验步骤见 [接入实验](../integrations/erie/README.md)。这不支持“Erie 整体丢失这些答案”的结论。

## 调研后新增功能的定位

已实现任务相关二进制提示合成：保持原始事件，只向有多种联合任务答案的类别增加分隔符与码字。最坏固定长度为 `ceil(log2 M)`，M 为单一声音类别中最大的联合答案数。这是标准计数下界的程序化应用，不是新编码理论，也没有证明对人类听觉最优。新增功能使工具可以从反例走向可机读验证的构造性修复。

## 2026-10-12 补充检索：缩小原创声明

补充检索式：`sonification "verification" "threshold"`、`sonification "information loss" quantization`、`"auditory display" "formal verification"`、`sonification "counterexample"`、`"sonification" "property-based"`、`"sonification" "metamorphic"`、`"sonification" "task" "quantization" "threshold"`。宽检索含大量无关命中；不能把没有搜索到完全匹配解读为不存在。

- [Tsuchiya 与 Freeman，ICAD 2018 原始论文](https://icad2018.icad.org/wp-content/uploads/2018/06/ICAD2018_paper_31.pdf)：读取了会议 PDF 的摘要及实验设计。研究为听者提供时间与音高分辨率控制，并记录分析行为。说明“任务与量化参数的关系”已有明确研究；EchoProof 没有做此类真人实验。
- [Elmquist 等，Parallel Chords，2024，出版方原文](https://link.springer.com/article/10.1007/s00779-024-01795-8)：出版方检索返回了原始论文全文片段，包括量化影响的检查。该工作比较了 36 步 MIDI 量化前后的 Pearson 相关系数，并有真人相关性分辨实验。这是对“量化影响可忽略”的具体数据／任务观察，不能外推到所有阈值任务。EchoProof 的精确反例方法与该感知实验互补；不能宣称首次检查声音图表的量化影响。
- [Soniccup，Sensors 2024，原始论文](https://www.mdpi.com/1424-8220/24/19/6279)：原始论文检索片段明确展示步长可调的 MIDI 音高取整，用于减少声音波动。正文访问失败，未通读。其取整方法为 floor，本工具为最近邻且平局向上；本工具的解析边界证书不能直接当作该实现的证书。

范围修复把指定阈值对齐量化边界，固定语义提示直接附加答案词汇，均可用已知数学与声音提示原则解释。新增贡献仍定位为独立实现的完整软件工作流与可重放研究案例，而非声称全新的原理或全球首创。

第二后端后续进展：锁定官方 Highcharts 13.1.1 npm 包并读取原始内部映射源码。函数核对通过在内存中追加 export 实现，18 个原始模块被加载，函数体未修改；手工 point/metrics/channel，未构建 Chart、完整时间线或播放器。结果区分了核心中点规则与 Highcharts 常数序列下限规则，进一步限制了模型证书向第三方外推。见 [核对方法](../integrations/highcharts/README.md)。


## 非均匀分区补查（2026-10-12）

新增检索 `sonification task aligned quantization threshold nonuniform pitch mapping` 和 `sonification threshold boundaries data categorization pitch bins audification`。检索范围有限，不能确认世界上无人实现过阈值分桶。

- [Vickers / Höldrich, Direct Segmented Sonification (2017)](https://arxiv.org/abs/1711.11368)：作者摘要说明使用领域知识，将时间数据分为具有意义的片段并形成声音事件。只核对摘要；它的时间分段与本项目的数值阈值区间不是同一个对象，但已经表明“按领域信息改变分段”不是全新理念。
- [Liu et al., Nonuniform-to-Uniform Quantization (CVPR 2022)](https://arxiv.org/abs/2111.14826)：作者摘要明确描述不等距输入阈值与等距输出等级。研究对象是神经网络压缩；不能据此推断其开发了声音图表证明工具，但不能声称非均匀输入分区本身为新方法。
- [Liu et al., Accessible Fine-grained Data Representation via Spatial Audio (2026)](https://arxiv.org/abs/2604.08979)：作者摘要报告26人、含10位BLV参与者的空间声音数据任务研究。只核对摘要，不转用其结果为EchoProof的人耳效果；它是细粒度数据表达的相关既有研究，说明多通道与人的识别能力应另行验证。

这三项摘要没有提供“从等距映射不可行证书自动切换为非均匀阈值构造、达到限定符号下界并可验算”的直接证据；这只是检索观察，不是全球首创证明。新的本地成果仍按独立实现与工程组合描述。


## 决策上限补查（2026-10-12）

检索 `sonification information loss Bayes error task accuracy bound quantization` 和 `auditory graph sonification task optimal decoder conditional entropy information loss`。

- [Silva / Tobar, AISTATS 2022](https://proceedings.mlr.press/v151/silva22b.html)：已读官方摘要。讨论信息损失与最小分类错误之间的关系，涉及有损连续表示和量化。这是相关分类理论，本项目有限类多数答案计数并非新理论；不把其渐近结论套到本地有限数据。
- [Jahromi et al., Information Loss in the Human Auditory System (2018)](https://arxiv.org/abs/1805.00698)：已读作者摘要。用噪声语音和封闭词汇测试研究信息损失、识别率并与最优分类器比较。对象为特定语音通信设置，不能据此声称本工具测量了人耳或从该研究借用人的效果。

本地新功能仅给出声明有限输入与先验下、精确事件解码的可达到上限；默认输入等权是选择，不是观测频率。不能把它当作学术首创、人耳实验或新输入泛化证明。


## 观测不确定性补查

[观测说明](OBSERVATION_METHOD.md)保存检索词与范围。已读2026作者/活动摘要以及[Batterman / Walker 2013](https://elektronicy.p.lodz.pl/projekty_i23/icad2013/paper/44_S9-10_Batterman.pdf)的摘要/导言：声音表达不确定性及其真人缩放验证已有研究。当前工具按声明可行集给出问题是否可确定的端点证据，不声称创立了不确定性声音表示，也不转用这些人的实验效果。
