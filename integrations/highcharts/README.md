# Highcharts 原始映射函数核对

锁定官方 npm `highcharts@13.1.1`，包 SHA-512 在 `fetch_source.py` 中。只提取声音化、Core、Shared 及包声明相关文件，不安装包、不执行安装脚本。下载的第三方源码在 `research/vendor/`，不会进入本项目的 MIT 源码成果包；原源码保留其 Highsoft 许可声明。

```sh
python3 integrations/highcharts/fetch_source.py
node --experimental-vm-modules integrations/highcharts/check.cjs
python3 -m echoproof compiled artifacts/highcharts-mapping/corpus.json \
  --scope highcharts_mapped_instrument --threshold 51 --out artifacts/highcharts-threshold51
python3 -m echoproof compiled artifacts/highcharts-mapping/corpus.json \
  --scope highcharts_mapped_instrument --threshold 50 --out artifacts/highcharts-threshold50
```

需要支持 `vm.SourceTextModule` 的 Node；本次 Node 24.19.0。Node 提示这是实验接口，脚本仅用于本地研究复现。核心 Python 没有增加 Node 依赖。

## 精确的接入范围

从原始 `TimelineFromChart.js` 载入内部映射函数，在内存中追加 export，不修改下载文件或函数体；所需 18 个模块全部从原始文件加载。手动提供 point、series、propMetrics 和捕获 channel，调用实际 `getPointTime` 与 `addMappedInstrumentEvent`。记录完整 `instrumentEventOptions` 和 `time`，主动明确省略 `relatedPoint` 元信息。

没有构建 Chart，没有运行 `timelineFromChart` 主流程，没有构造 AudioContext 或播放器，也没有语音、上下文轨道、视觉标记或交互验证。本实验不能被称为完整 Highcharts 图表审计。记录携带源文件与采集脚本哈希，但记录复验本身不认证源码曾被执行。

## 结果

四项程序断言通过：

1. 每序列独立范围下，`[1,2,3]` 与 `[10,20,30]` 产生相同的乐器事件参数及时间。
2. 手动共享 propMetrics 的 0–30 范围后，两者不再相同。
3. 常数序列 `[5,5,5]` 映射到最小音高 48（Highcharts 的 C0 偏移），不是 EchoProof 核心的区间中点。不能直接把核心映射证书视为此库的证书。
4. 手动全局数值范围 0–100、音高 C0 偏移 48–84、`scale:[0]`，49、50、50.5、51 依次映射为 60、72、72、72。只有 C 类音、共四个音高；最近邻的平局向上使 50 位于边界。

完整 27 个三点序列（每个值属于 49、50、51）共 8 种乐器参数/时间输出。阈值 50 没有记录冲突；51 的冲突对数由 Python 保存的审计文件给出。其他任务也针对同一原始输入检查。

这里 0–100、0–30 是测试人工提供的数据极值，不是完整图表自动生成的结果；pitch 的 `min/max` 是输出音高界限，不等于数值输入范围。原库使用 C0 偏移音符数，本工具使用 MIDI cents，记录参数没有冒充 PCM。

公开原始说明：[Advanced Mapping](https://www.highcharts.com/docs/sonification/advanced-mapping)。这些函数说明了映射范围、音阶等实际行为；没有证明真人能听出差异或库存在错误。
