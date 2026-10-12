"""Present the direct compiler observations, without treating projections as audio."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from echoproof.report import STYLE, esc, data_table


def main():
    directory = Path(__file__).resolve().parents[1] / 'artifacts/erie-direct'
    record = json.loads((directory / 'observation.json').read_text(encoding='utf-8'))
    observations = record['observations']
    rows = [
        ('自动数值范围 / 纯音流', observations['auto_domain_tone_streams_equal']),
        ('自动数值范围 / 完整队列', observations['auto_domain_full_queues_equal']),
        ('共享显式范围 / 纯音流', observations['shared_domain_tone_streams_equal']),
    ]
    table = '<table><caption>原始 Erie 编译器输出比较</caption><thead><tr><th>检查对象</th><th>两个输入的输出是否相同</th></tr></thead><tbody>'
    table += ''.join('<tr><th scope="row">%s</th><td>%s</td></tr>' % (esc(label), '相同' if equal else '不同') for label, equal in rows)
    table += '</tbody></table>'
    legend_left = esc('\n'.join(observations['speech_left']))
    legend_right = esc('\n'.join(observations['speech_right']))
    output = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 真实编译器的反向检验</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / ERIE 1.0.1 DIRECT EXPERIMENT</div><h1>音高相同，完整输出仍可不同。</h1><p class="lead">直接调用已有声音图表编译器，检验原型的结论边界：语音图例可以保留纯音通道丢掉的信息。</p></header>
<p class="note">这里没有证明 Erie 的完整输出发生信息丢失。实际编译结果显示，语音图例区分了两组数据。保留这个反向案例，有助于避免误报。</p>
<article><h2>相差十倍的两份数据</h2>%s<p>是否存在 ≥5 的数值：数据 A 为 false，数据 B 为 true。总和分别为 6 与 60。</p>%s</article>
<h2>语音图例提供了不同的数值范围</h2><div class="pair"><article><h3>数据 A 的语音</h3><pre>%s</pre></article><article><h3>数据 B 的语音</h3><pre>%s</pre></article></div>
<h2>这个结果说明什么</h2><p>信息是否保留，取决于被检查的完整通道。对纯音流成立的冲突，不自动适用于包含语音、图例和交互的整套声音图表。共享显式范围则可以让纯音事件本身不同。</p>
<p>后端：%s。运行时：%s。源码包和依赖均固定版本并记录哈希。比较只剔除非声音的原始数据字段 __datum，完整队列比较保留语音。</p>
<p><a href="observation.json">完整规范、原始队列和比较记录</a> · <a href="../../integrations/erie/README.md">重跑方法与范围</a> · <a href="../demo/index.html">返回实验总览</a></p>
<p class="muted">仅执行编译与预渲染队列生成；未运行 Web Audio 播放器，未进行真人听觉测试。</p></main></body></html>''' % (
        STYLE, data_table(record['inputs']['left'], record['inputs']['right']), table,
        legend_left, legend_right, esc(record['backend']), esc(record['runtime']))
    (directory / 'index.html').write_text(output, encoding='utf-8')
    print(directory / 'index.html')


if __name__ == '__main__':
    main()
