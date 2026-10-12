# 观测可确定性：报告值与允许实际值分开

已实现独立的观测可确定性检查：在调用方声明的闭区间笛卡尔积假设下，给出阈值可能答案、确定状态、计数界与两个端点情况。不赋予概率或校准覆盖率。

对于N个同位置报告值，调用方另给N个闭区间 [Li,Hi]，并声明其笛卡尔积包含所有允许的实际值序列。问“实际值是否至少有一项≥t”：

- 只要某个Li≥t，则所有允许序列都为true。
- 若所有Hi<t，则所有允许序列都为false。
- 否则存在true与false两种允许序列，报告值本身不能决定该实际问题。

不确定情况下，所有低端点组成一份false序列；选择某个Hi≥t的位置并把该值置为t，其他保留低端点，得到一份true序列。这两种序列共享同一份已报告观测的可行集假设，不必在“把实际值直接送进声音映射”时产生相同事件。证明的是观测非可识别性，不是新的声音事件碰撞。

若声音及固定答案提示只依赖同一份报告观测，它们在两种允许世界中相同。提示能准确编码“报告值达到阈值”，不能据此证明“实际未知值达到阈值”。没有先验概率时不赋予50%、95%等数值。

不从NOAA不确定度列推导保证区间。标准不确定度、置信区间与硬界的含义不同；任何输入区间均须写明由调用方假定，不能称为实际来源的保证范围。暂只考虑无缺失、正长度、独立区间可行集，相关约束另行处理。

## 相关既有研究

检索日期2026-10-12，查询 `sonification uncertainty interval confidence sonification data uncertainty ICAD` 与 `sonification uncertain data threshold uncertainty visualization auditory graphs`。

已读 [Sounds Uncertain (2026) 作者摘要](https://arxiv.org/abs/2608.18680)及[官方活动页面](https://www.ieeevis.org/year/2026/program/paper/210639d8-d1a7-4e33-b61d-b1b74e17e6f1/)。论文使用共同设计研究探索声音表达不确定性情感，比较不确定/中性的声音性质；作者页面注明获IEEE Workshop on Uncertainty Visualization接收。没有阅读全文，不转用其人类结果，不把页面列出等同为会议已举办。

已读 [Batterman / Walker 2013论文](https://elektronicy.p.lodz.pl/projekty_i23/icad2013/paper/44_S9-10_Batterman.pdf)的摘要与导言。实际标题为 Auditory Graphs Need Error Bars: Validating Error-to-Sound Mappings and Scalings。论文研究听众对误差声音映射及缩放的选择验证；没有阅读全文，也不转用其真人结果。先前搜索中另一个“Displaying error”标题不能当作这篇PDF的正式题名。

不确定性声音表示已有研究，不能称这个广泛领域无人开发。当前实现的贡献仍是把明确的观测集合、反例、问题范围与声音审计流程联结；集合单调性判断和非可识别性论证不是新理论。
