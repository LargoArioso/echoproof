# 来源、许可与研究状态

## 本项目

EchoProof 0.1.0 是维护者发起、由 AI 编程助手主要实现的早期研究原型。代码、方法分析、测试、合成声音、示意图和文档均有 AI 参与。维护者提出探索目标并授权发布；自动检查不代表维护者逐行人工审查、独立同行评审或真人有效性验证。

根目录 LICENSE 中的 MIT 许可适用于本项目编写的代码和文档，以及本项目生成且可许可的示例材料。MIT 允许修改、分发和商用，须保留许可与版权声明，软件按原样提供。该许可不重新授予第三方软件、观测数据、文献或商标的权利，也不作对生成内容权利状态的穷尽保证。

## NOAA / Scripps 观测数据

`research/data/noaa/co2_annmean_mlo.csv` 是未经修改的外部数据存档，不是 EchoProof 原创数据。数据来源：NOAA Global Monitoring Laboratory, Boulder, Colorado, USA；Xin Lan（NOAA/GML）与 Ralph Keeling（Scripps Institution of Oceanography）。早期观测来自 C. David Keeling/SIO。原文件的来源、引用要求和测站说明保留。

来源与产品引用：[年度数据页面](https://gml.noaa.gov/ccgg/trends/data.html)。使用条件：[GML 说明](https://gml.noaa.gov/about/disclaimer.html)。复用者应遵守数据自身的说明；不要把合成音频、图或工具结论当作 NOAA 的官方产品、认可或背书。涉及第三方贡献的数据权利不能仅凭项目 MIT 许可推定。

## 可选第三方后端

Erie 1.0.1 的下载源码遵循其自身 MIT 许可；Highcharts 13.1.1 受 Highsoft 自身许可和使用条件约束，不能因为源码可见就当作 MIT 软件。两个后端的源码和依赖不随本仓库或成果 ZIP 分发。这里的桥接脚本是本项目编写的实验工具，保存的输出是限定配置下的研究记录。

重跑外部后端前应自行阅读其许可：[Erie 项目](https://github.com/see-mike-out/erie-web)、[Highcharts 条款](https://shop.highcharts.com/license-eula)。本项目 MIT 许可不授权后端的下载、使用、修改或重新分发。默认离线复验与 CI 只检查存档记录，不下载或执行这些后端。

## 文献与结论

相关研究列于 `research/PRIOR_ART.md`。本仓库提供引用、链接和有限的概述，不分发论文全文，不宣称已有量化、决策理论或分区方法是本项目发明。公开检索未找到完全相同工作流，不能证明全球无人开发。

“保留”“冲突”“不可行”均受证书中声明的输入范围、任务和表示模型限制。机器事件相等及理想解码结论不等于人耳辨别能力；真人研究材料仅为准备材料，没有收集到的参与者成绩。第三方实验不构成对整个后端的故障判断。

## 公开日志

公开的复现与成果包检查日志替换了机器相关的绝对路径，并标明脱敏方式。检查的退出状态、计数、源文件哈希和所验证归档的 SHA-256 保留；脱敏日志不是逐字原始输出，也不认证作者身份。归档检查日志置于其所验证 ZIP 之外，避免自引用。
