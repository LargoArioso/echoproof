"""Portable HTML report with data tables and opt-in sound playback."""
import base64
import html
import json
from pathlib import Path
from .audio import wav_bytes
from .audit import verify_witness
from .model import Mapping, Render, Event, encode

STYLE = """
:root{color-scheme:light;--ink:#162a38;--muted:#536775;--line:#c8d4d9;--accent:#036655}
*{box-sizing:border-box}body{margin:0;background:#f3f6f5;color:var(--ink);font:16px/1.65 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:48px 24px}header{border-bottom:2px solid var(--ink);padding-bottom:28px}
h1{font-size:clamp(2rem,5vw,3.4rem);line-height:1.1;letter-spacing:-.035em}h2{font-size:1.6rem}h3{margin-top:0}
.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.12em}.lead{font-size:1.2rem;max-width:820px}
.metrics{display:flex;flex-wrap:wrap;gap:16px;margin:28px 0}.metric{background:white;border:1px solid var(--line);padding:18px 24px;flex:1;min-width:170px}
.metric strong{font-size:2rem;display:block}.note{border-left:4px solid var(--accent);padding:12px 20px;background:#e4eee9}
article{background:white;border:1px solid var(--line);border-radius:10px;padding:26px;margin:24px 0}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:22px}table{border-collapse:collapse;width:100%;margin:14px 0;overflow-wrap:anywhere}
th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line)}th{font-weight:650}caption{text-align:left;font-weight:600}
.scroll{overflow-x:auto}pre{background:#edf1f1;padding:16px;overflow:auto;font-size:.85rem}audio{max-width:100%;width:100%}
.badge{display:inline-block;border-radius:4px;background:#f9e7dd;color:#7c330c;padding:3px 8px;font-size:.85rem;font-weight:650}
.ok{background:#e4eee9;color:#036655}a{color:#036655}button:focus-visible,a:focus-visible,audio:focus-visible{outline:3px solid #bc5b12;outline-offset:4px}
.muted{color:var(--muted)}@media(max-width:680px){.pair{grid-template-columns:1fr}main{padding:28px 16px}article{padding:20px}}
"""

TASK_NAMES = {"threshold": "是否达到阈值", "endpoint_trend": "首尾趋势", "peak_indices": "峰值所在位置", "missing_count": "缺失数量", "total": "观测值总和"}


def esc(value):
    return html.escape(str(value), quote=True)


def sound(render, label):
    payload = base64.b64encode(wav_bytes(render)).decode("ascii")
    return '<p>%s</p><audio controls preload="none" aria-label="%s"><source src="data:audio/wav;base64,%s" type="audio/wav">浏览器不支持音频。</audio>' % (esc(label), esc(label), payload)


def data_table(left, right):
    rows = []
    for i in range(max(len(left), len(right))):
        values = []
        for sequence in (left, right):
            values.append("—" if i >= len(sequence) else "缺失" if sequence[i] is None else sequence[i])
        rows.append("<tr><th scope=\"row\">%d</th><td>%s</td><td>%s</td></tr>" % (i, esc(values[0]), esc(values[1])))
    return '<table><caption>原始数据（位置从 0 开始）</caption><thead><tr><th scope="col">位置</th><th scope="col">数据 A</th><th scope="col">数据 B</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def report_html(result, title="EchoProof · 声音图表的信息丢失审计", repairs=None):
    metrics = result["search"]
    cards = []
    for task, details in result["tasks"].items():
        record = details["witness"]
        if not record:
            cards.append('<article><h3>%s</h3><span class="badge ok">当前搜索范围未发现冲突</span><p>这项结论仅覆盖下面列出的有限搜索范围。</p></article>' % esc(TASK_NAMES[task]))
            continue
        if not verify_witness(record):
            raise ValueError("Refusing to publish an invalid witness")
        original = details.get("original_witness")
        original_details = ""
        if original:
            if not verify_witness(original):
                raise ValueError("Invalid original corpus witness")
            original_details = '<details><summary>查看缩减前、确实属于搜索输入集合的完整反例</summary><pre>%s</pre></details>' % esc(json.dumps(original, ensure_ascii=False, indent=2))
        trace = details.get("minimization_trace")
        if trace:
            original_details += '<p>保留的原位置：A %s，B %s；依次删去的位置：%s。<a href="%s.trace.json">可重放的缩减记录</a>。</p>' % (esc(trace["retained_left_indices"]), esc(trace["retained_right_indices"]), esc(trace["removed_original_indices"]), esc(task))
        audio = encode(record["left"], Mapping(**record["mapping"]))
        reduction_note = "反例经过成对删除缩减；不宣称全局最短。" if record.get("minimization") == "paired-deletion 1-minimal" else "两侧原始长度不同，本例不执行成对删除，也不宣称最短。"
        cards.append('''<article><h3>%s</h3><span class="badge">声音事件完全相同，答案不同</span>
<p>数据 A 的答案：<strong>%s</strong>；数据 B 的答案：<strong>%s</strong>。</p>
%s<div class="pair"><div>%s</div><div>%s</div></div>
<p class="muted">相同事件在内置确定性播放器中生成相同 PCM 字节。%s</p>
<details><summary>查看可复验的缩减反例</summary><pre>%s</pre></details>%s</article>''' % (
            esc(TASK_NAMES[task]), esc(record["left_answer"]), esc(record["right_answer"]),
            data_table(record["left"], record["right"]), sound(audio, "播放数据 A"), sound(audio, "播放数据 B"), esc(reduction_note), esc(json.dumps(record, indent=2, ensure_ascii=False)), original_details))
    repairs_html = ""
    if repairs:
        rows = []
        for label, candidate in repairs:
            rows.append('<tr><th scope="row">%s</th><td>%s</td><td>%s</td></tr>' % (
                esc(label), esc(candidate["search"]["render_classes"]),
                esc(" / ".join("%s: %d" % (TASK_NAMES[t], v["disagreeing_pairs"]) for t, v in candidate["tasks"].items()))))
        repairs_html = '<h2>修复候选：同一搜索网格重新验证</h2><p>数字是声音相同而答案不同的数据对数。0 只表示当前网格没有反例。修复可能改变声音风格和所需训练。</p><div class="scroll"><table><thead><tr><th>候选</th><th>声音类别</th><th>冲突数据对</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    count = sum(d["status"] == "collision_found" for d in result["tasks"].values())
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>%s</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / REPRODUCIBLE AUDIT</div><h1>数据不同，声音一样。</h1><p class="lead">用可复验的反例，找到声音图表丢掉的关键信息。</p><p>%s</p></header>
<div class="metrics"><div class="metric"><strong>%s</strong>已检查的数据序列</div><div class="metric"><strong>%s</strong>不同声音事件类别</div><div class="metric"><strong>%s / %s</strong>存在冲突的问题</div></div>
<p class="note">证据边界：这里只检查离散声音事件是否完全相同。没有做真人听觉实验；声音不同也不代表人一定听得出。语音标签、图形和外部播放器不在证明范围内。</p>
<h2>发现与反例</h2>%s%s<h2>搜索范围与映射</h2><details open><summary>完整配置</summary><pre>%s</pre></details>
<p class="muted">离线报告 · 音频仅在点击后播放 · 无网络依赖 · EchoProof 0.1.0</p></main></body></html>''' % (
        esc(title), STYLE, esc(title), metrics["series_count"], metrics["render_classes"], count, len(result["tasks"]),
        "".join(cards), repairs_html, esc(json.dumps({"domain": result["domain"], "mapping": result["mapping"], "search": metrics}, ensure_ascii=False, indent=2)))


def write_report(result, directory, title=None, repairs=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for task, details in result["tasks"].items():
        record = details["witness"]
        if record:
            (directory / (task + ".witness.json")).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            for side in ("left", "right"):
                (directory / (task + "." + side + ".wav")).write_bytes(wav_bytes(encode(record[side], Mapping(**record["mapping"]))))
        trace = details.get("minimization_trace")
        if trace:
            (directory / (task + ".trace.json")).write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        original = details.get("original_witness")
        if original:
            (directory / (task + ".original.witness.json")).write_text(json.dumps(original, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if repairs:
        (directory / "repairs.json").write_text(json.dumps(dict(repairs), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (directory / "index.html").write_text(report_html(result, title or "EchoProof · 声音图表的信息丢失审计", repairs), encoding="utf-8")
    return directory / "index.html"


def write_demo_index(results, directory):
    directory = Path(directory)
    labels = {"normalization": "各自归一化", "quantization": "音高取整", "missing": "缺失当零", "sampling": "漏采样", "clipping": "范围截断"}
    explanations = {"normalization": "数值量级不同，曲线形状一样。", "quantization": "音高单元内的变化消失。", "missing": "未观测与确实为零无法区分。", "sampling": "跳过的位置可以藏住峰值。", "clipping": "范围外的不同数值变成端点音高。"}
    cards = []
    for name, result in results.items():
        count = sum(v["status"] == "collision_found" for v in result["tasks"].values())
        cards.append('<article><h3><a href="%s/index.html">%s →</a></h3><p>%s</p><p class="muted">%d 个序列 · %d 个声音类别 · %d 个任务发现冲突</p></article>' % (
            esc(name), esc(labels[name]), esc(explanations[name]), result["search"]["series_count"], result["search"]["render_classes"], count))
    additional = []
    for folder, label in (("csv-probe", "实际 CSV 的候选变换检查"), ("cues-quantization", "按任务补足声音信号"), ("erie-direct", "真实 Erie 编译器：语音图例的反向检验"),
                          ("erie-mean-full", "平均值汇总与原始尖峰问题的冲突"), ("erie-auto-full", "保留语音的完整队列检查"), ("erie-auto-tone", "同一数据集合的纯音检查"), ("semantic-normalization", "固定含义的答案提示"), ("threshold51-alignment", "阈值修复与副作用"), ("highcharts-threshold51", "Highcharts 原始映射函数检查"), ("continuous-tasks", "有限量化与连续数据的修复边界"), ("noaa-windows", "未经改动的 NOAA 真实观测窗口"), ("partition-thresholds", "非均匀分区同时保留两个阈值"), ("noaa-partition", "真实观测的阈值位置与采样计数"), ("decision-base", "明确先验下的理想解码上限"), ("decision-cued", "补充提示后的理想解码上限"), ("decision-comparison", "同输入域下四种表示的能力与代价"), ("observation-uncertainty", "报告值与实际区间的阈值可确定性"), ("diagnosis-cases", "单入口诊断、构造约束与副作用")):
        if (directory.parent / folder / "index.html").exists():
            additional.append('<li><a href="../%s/index.html">%s</a></li>' % (esc(folder), esc(label)))
    output = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>EchoProof · 可听、可复验的信息丢失检查</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / RESEARCH PROTOTYPE</div><h1>声音图表，也需要检查答案。</h1><p class="lead">两份数据听起来一样，却可能给出相反的结论。EchoProof 自动找到这种反例，保留证书，并重新检查修复方案。</p></header>
<div class="metrics"><div class="metric"><strong>%d</strong>五个案例穷举的序列总数</div><div class="metric"><strong>5</strong>不同信息丢失机制</div><div class="metric"><strong>2</strong>连续区间阈值证书</div></div>
<p class="note">研究范围：精确声音事件冲突。未做真人听觉实验；检索未发现完全相同的工具，但不宣称全球首创。</p>
<h2>五个可复现实验</h2><div class="pair">%s</div>
<h2>一个更细的发现</h2><article><h3>阈值落在哪里，比音高步长多大更关键。</h3><p>数值范围 0–100、音域 3 个八度、每 1 个八度取整时，阈值 50 正好落在音高切换边界上，可以保留判断。阈值 51 落在同一音高单元内部，存在不同答案的同声音反例。</p><p><a href="../threshold50.json">查看 50 的连续区间保留证书</a> · <a href="../threshold51.json">查看 51 的连续区间冲突证书</a></p><p class="muted">这两条结论覆盖 0–100 的整个闭实数区间，要求固定映射、无缺失且不漏采样。</p></article>
<h2>进一步实验</h2><ul>%s</ul>
<h2>从结果继续研究</h2><p><a href="../../README.md">使用说明</a> · <a href="../../research/PRIOR_ART.md">公开资料调研与新颖性边界</a> · <a href="../../research/METHOD.md">方法与证明范围</a></p><p class="muted">无需联网 · 点击后才播放声音 · 所有报告、配置和反例在本地保存</p></main></body></html>''' % (
        STYLE, sum(r["search"]["series_count"] for r in results.values()), "".join(cards), "".join(additional))
    path = directory / "index.html"
    path.write_text(output, encoding="utf-8")
    return path


def write_cue_report(plan, examples, directory):
    stats = plan["statistics"]
    panels = []
    for i, example in enumerate(examples):
        base = Render(tuple(Event(**e) for e in example["base"]["events"]), example["base"]["duration_ms"])
        cued = Render(tuple(Event(**e) for e in example["cued"]["events"]), example["cued"]["duration_ms"])
        answers = " · ".join("%s：%s" % (TASK_NAMES[t], a) for t, a in zip(plan["tasks"], example["answers"]))
        panels.append('<article><h3>数据 %s</h3><p>%s</p><p>答案：%s</p>%s%s</article>' % (
            "A" if i == 0 else "B", esc(example["values"]), esc(answers), sound(base, "原始声音"), sound(cued, "补充二进制提示后的声音")))
    body = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>EchoProof · 按任务补足声音信息</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / TASK-SUFFICIENT CUES</div><h1>补足答案所缺的信号。</h1><p class="lead">保留原始数据声音，只在同声音包含不同任务答案时，增加分隔符和二进制提示。</p></header>
<div class="metrics"><div class="metric"><strong>%d</strong>验证过的输入序列</div><div class="metric"><strong>%d</strong>需要补充提示的声音类别</div><div class="metric"><strong>%d bit</strong>最坏情况编码长度与理论下界</div></div>
<p class="note">这里证明的是有限域中机器可解码的任务信息。编码长度最小的结论要求二进制、给定原始声音后固定长度编码，不含分隔符成本；没有验证真人能否听懂或记住这些码字。</p>
<h2>同一原始声音，不同答案</h2><div class="pair">%s</div>
<h2>提示怎么读</h2><p>低短音是 0，高短音是 1；前面有一个独立音色的分隔符。码字对应答案的关系取决于原始声音所属类别，需配合码本。无歧义的声音类别不增加提示。</p>
<p>例如一个原始声音类别中有 8 种不同的联合答案，任何固定长度二进制提示都至少需要 3 位，本方案使用 3 位。这个下界是标准编码计数结果。</p>
<p><a href="plan.json">完整可复验码本</a> · <a href="examples.json">示例事件与答案</a></p><p class="muted">实际使用还需设计易学的语音或声音图例，并做用户研究。</p></main></body></html>''' % (
        STYLE, stats["series_count"], stats["ambiguous_classes"], stats["worst_case_bits"], "".join(panels) or '<article><p>当前任务集合没有歧义，因此不需要补充提示。</p></article>')
    path = Path(directory) / "index.html"
    path.write_text(body, encoding="utf-8")
    return path


def write_compiled_report(result, directory):
    from .compiled import verify_recording_witness
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cards = []
    for task, details in result["tasks"].items():
        record = details["witness"]
        if record:
            if not verify_recording_witness(record):
                raise ValueError("Invalid compiler recording witness")
            name = task + ".recording-witness.json"
            (directory / name).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            cards.append('<article><h3>%s</h3><span class="badge">同一录制输出，原始数据答案不同</span><p>数据 A：%s；数据 B：%s。记录集合中有 %d 对冲突。</p>%s<p><a href="%s">完整录制反例</a></p><details><summary>查看相同的输出视图</summary><pre>%s</pre></details></article>' % (
                esc(TASK_NAMES[task]), esc(record["left_answer"]), esc(record["right_answer"]), details["disagreeing_pairs"],
                data_table(record["left"]["input"], record["right"]["input"]), esc(name), esc(json.dumps(record["projection"], ensure_ascii=False, indent=2))))
        else:
            cards.append('<article><h3>%s</h3><span class="badge ok">当前记录集合中未发现冲突</span><p>仅覆盖保存的编译记录，不表示对所有输入或人耳感知的保证。</p></article>' % esc(TASK_NAMES[task]))
    label = {"erie_full_queue": "完整录制队列（保留语音）", "erie_tone_stream": "单一纯音流（部分通道）",
             "highcharts_mapped_instrument": "Highcharts 内部映射函数的乐器参数与时间（部分通道）"}[result["audit_scope"]]
    output = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 真实编译记录审计</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / RECORDED COMPILER CORPUS</div><h1>先明确问题，再检查完整通道。</h1><p class="lead">检查范围：%s。任务针对变换之前的原始数据。</p></header>
<div class="metrics"><div class="metric"><strong>%d</strong>不同原始输入的编译记录</div><div class="metric"><strong>%d</strong>不同输出视图</div></div>
<p class="note">证书复验只重算已录制输出的相等性与原始数据答案；不会重新运行外部编译器或认证输入与输出的关联。接入脚本用于重新捕获。汇总操作可能有意丢掉细节，任务冲突不自动意味着图表库存在错误。</p>
%s<p><a href="audit.json">完整审计数据</a></p><p class="muted">没有运行 Web Audio 播放，也没有真人听觉实验。</p></main></body></html>''' % (
        STYLE, esc(label), result["recording_count"], result["projection_classes"], "".join(cards))
    path = directory / "index.html"
    path.write_text(output, encoding="utf-8")
    return path


def write_semantic_report(validation, directory):
    from .semantic_cues import verify_validation
    if not verify_validation(validation):
        raise ValueError("Invalid semantic cue validation")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cards = []
    for i, example in enumerate(validation["examples"]):
        def render(record):
            return Render(tuple(Event(**e) for e in record["events"]), record["duration_ms"])
        base, cued = render(example["base"]), render(example["cued"])
        (directory / ("example%d.base.wav" % i)).write_bytes(wav_bytes(base))
        (directory / ("example%d.cued.wav" % i)).write_bytes(wav_bytes(cued))
        cards.append('<article><h3>数据 %s</h3><p>%s</p><p>答案：%s</p>%s%s</article>' % (
            "A" if i == 0 else "B", esc(example["values"]), esc(example["answers"]), sound(base, "原始数据声音"), sound(cued, "原始声音与固定语义提示")))
    names = {"rising": "上升", "falling": "下降", "flat": "持平", "undefined": "趋势未定义"}
    legend_cards = []
    for i, entry in enumerate(validation["definition"]["legend"]):
        if entry["task"] == "threshold":
            label = "达到阈值：两音上行" if entry["answer"] else "未达到阈值：两音下行"
        else:
            label = "首尾趋势：" + names[entry["answer"]]
        rendered = Render(tuple(Event(**e) for e in entry["render"]["events"]), entry["render"]["duration_ms"])
        (directory / ("legend%d.wav" % i)).write_bytes(wav_bytes(rendered))
        legend_cards.append('<article><h3>%s</h3>%s</article>' % (esc(label), sound(rendered, label)))
    stats = validation["statistics"]
    output = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 固定语义提示</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / FIXED MEANING CUES</div><h1>相同的提示，始终表达相同的答案。</h1><p class="lead">为阈值判断和首尾趋势增加固定含义的声音提示，不依赖原始声音类别的专用码本。</p></header>
<div class="metrics"><div class="metric"><strong>%d</strong>已验证的输入序列</div><div class="metric"><strong>%d</strong>机器解码失败</div><div class="metric"><strong>%s ms</strong>每次播放增加的时长</div></div>
<p class="note">固定词汇和机器解码已验证；没有测试真人学习速度、准确率或听觉效果。附加提示直接编码计算出的答案，保留原始事件，也会增加播放时长。本方案不宣称最短。</p>
<h2>先听提示图例</h2><p>每种问题前有一个专用音色与音高的标题音。阈值使用两音；趋势使用三音。未定义与持平使用不同音域及音色。</p><div class="pair">%s</div>
<h2>两份数据的对照</h2><div class="pair">%s</div><p><a href="validation.json">完整定义、网格与复验记录</a></p><p class="muted">提示针对原始数据答案；和有限域最短二进制码是两种不同的设计取舍。</p></main></body></html>''' % (
        STYLE, stats["checked_series"], stats["decode_failures"], esc(" / ".join(map(str, stats["added_duration_ms"]))), "".join(legend_cards), "".join(cards))
    path = directory / "index.html"
    path.write_text(output, encoding="utf-8")
    return path


def write_alignment_report(record, directory):
    from .alignment import verify_alignment
    from .intervals import threshold_certificate
    from .multi_alignment import align_thresholds
    if not verify_alignment(record):
        raise ValueError("Invalid alignment result")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "alignment.json").write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    original = Mapping(**record["original_mapping"])
    before = threshold_certificate(original, record["threshold"], record["input_low"], record["input_high"])
    witness = before.get("witness")
    panels, regressions = [], []
    for index, candidate in enumerate(record["candidates"]):
        revised = Mapping(**candidate["mapping"])
        lost = candidate["previously_preserved_thresholds_lost"]
        audio = ""
        if witness:
            audio = data_table(witness["left"], witness["right"])
            for side in ("left", "right"):
                base, fixed = encode(witness[side], original), encode(witness[side], revised)
                for label, render in (("base", base), ("fixed", fixed)):
                    (directory / ("candidate%d.%s.%s.wav" % (index, side, label))).write_bytes(wav_bytes(render))
                audio += '<div class="pair">%s%s</div>' % (sound(base, side+"：原始声音"), sound(fixed, side+"：调整范围后"))
        panels.append('<article><h3>候选 %d：范围 %s → %s</h3><span class="badge ok">目标阈值在整个声明区间保留</span><p>改动量：%s；原来保留、现在丢失的阈值：%s。</p>%s</article>' % (
            index+1, esc(revised.domain_low), esc(revised.domain_high), esc(candidate["normalized_endpoint_change"]), esc("、".join(lost) or "无"), audio))
        if index == 0:
            for threshold in lost[:4]:
                certificate = threshold_certificate(revised, threshold, record["input_low"], record["input_high"])
                (directory / ("regression%d.json" % len(regressions))).write_text(json.dumps(certificate, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                try:
                    joint = align_thresholds(original, [threshold, record["threshold"]], record["input_low"], record["input_high"])
                except ValueError as exc:
                    regressions.append('<li>原阈值 %s 与目标阈值 %s 的联合检查未完成：%s。</li>' % (esc(threshold), esc(record["threshold"]), esc(exc)))
                    continue
                name = "joint%d.json" % len(regressions)
                (directory / name).write_text(json.dumps(joint, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                regressions.append('<li>原阈值 %s 与目标阈值 %s 同时保留：%s。<a href="%s">完整约束与证书</a></li>' % (esc(threshold), esc(record["threshold"]), esc(joint["status"]), name))
    output = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 阈值修复与副作用</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / CONSTRAINED REPAIR</div><h1>修复一个判断，也要检查其他判断。</h1><p class="lead">保持音域与音高步长，通过移动数值范围端点，让阈值 %s 正好落在音高切换边界。</p></header>
<p class="note">连续区间证明要求固定映射、无缺失、不漏采样。候选按单端点改动量排序；不是全局感知最优。附加 WAV 展示同一组数值的前后声音，声音不同不代表人耳一定听得出。</p>
%s<h2>多个阈值的约束</h2><p>范围要覆盖原始范围及声明输入区间。两个不同阈值都必须落在量化边界，因此间距至少达到“覆盖宽度 × 音高步长 ÷ 音域”。满足这个下界仍不保证可行；工具继续枚举所有边界配对。</p><ul>%s</ul><p><a href="alignment.json">完整修复配置与复验记录</a></p></main></body></html>''' % (STYLE, esc(record["threshold"]), "".join(panels) or '<article><p>没有符合约束的单端点修复。</p></article>', "".join(regressions))
    path = directory / "index.html"
    path.write_text(output, encoding="utf-8")
    return path


def write_interval_report(certificates, directory):
    from .interval_tasks import verify_task_certificate
    if not certificates or not all(verify_task_certificate(c) for c in certificates.values()):
        raise ValueError('Refusing invalid or empty interval task certificates')
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    cards=[]
    for task,certificate in certificates.items():
        name=task+'.certificate.json'
        (directory/name).write_text(json.dumps(certificate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        counterexample=certificate['witness']
        content=''
        if counterexample:
            (directory/(task+'.witness.json')).write_text(json.dumps(counterexample,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            mapping=Mapping(**certificate['mapping'])
            content=data_table(counterexample['left'],counterexample['right'])
            content+='<p>答案 A：%s；答案 B：%s。</p><div class="pair">' % (esc(counterexample['left_answer']),esc(counterexample['right_answer']))
            for side in ('left','right'):
                rendered=encode(counterexample[side],mapping)
                (directory/(task+'.'+side+'.wav')).write_bytes(wav_bytes(rendered))
                content+=sound(rendered,'原始反例 '+side)
            content+='</div>'
        status={'preserved':'整个区间保留','collision_found':'存在精确同声音反例','unsupported':'当前解析模型不支持'}[certificate['status']]
        cards.append('<article><h3>%s</h3><span class="badge">%s</span>%s<p><a href="%s">完整证书与假设</a></p></article>' % (esc(TASK_NAMES[task]),esc(status),content,name))
    output='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 连续数据的任务边界</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / CONTINUOUS TASK PRESERVATION</div><h1>网格上修好了，连续数据仍可能冲突。</h1><p class="lead">有限音高量化，在任意非零宽度的实数区间里都有一小段相同音高。交换这段内的两个不同数值，声音不变，趋势和峰位却反转；单点总和也不同。</p></header>
<p class="note">结论针对固定范围、有限步长、无缺失、不漏采样的原始事件映射。更细的有限步长可以缩小冲突区间，但不能完全保留连续数据的趋势、峰位或总和；增加任务提示等额外通道会改变这里的假设。没有真人听觉或第三方播放器验证。</p>
%s<h2>例外与范围</h2><p>阈值若正好位于声音切换边界，可完全保留。无缺失假设下缺失数恒为 0；若输入区间仅含一个数值，播放总时长确定序列长度，因此五项任务均保留。每条结论都保留其对应假设，不适用于所有音频表示方法。</p>
</main></body></html>''' % (STYLE,''.join(cards))
    path=directory/'index.html'
    path.write_text(output,encoding='utf-8')
    return path


def write_partition_report(record, directory):
    from .partition import verify_partition, PartitionEncoder
    if not verify_partition(record):
        raise ValueError("Invalid nonuniform partition certificate")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'partition.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    cards = []
    if record['status'] == 'preserved':
        encoder = PartitionEncoder(record)
        for i,value in enumerate(record['lower_bound']['singleton_representatives']):
            base = encode([value],encoder.mapping)
            revised = encoder.encode([value])
            for name,rendered in (('base',base),('partition',revised)):
                (directory/('case%d.%s.wav' % (i,name))).write_bytes(wav_bytes(rendered))
            answers = encoder.decode(revised)
            rows = ''.join('<tr><th scope="row">是否达到 %s</th><td>%s</td></tr>' % (esc(t),'是' if answer else '否') for t,answer in answers.items())
            cards.append('<article><h3>单点数值 %s</h3><table><tbody>%s</tbody></table><p>原映射：%s cents；分区映射：%s cents。</p><div class="pair"><div>%s</div><div>%s</div></div></article>' % (esc(value),rows,base.events[0].pitch_cents,revised.events[0].pitch_cents,sound(base,'原始等距映射'),sound(revised,'按判断边界分区')))
    else:
        cards.append('<article><p>原有音高种类不够：需要至少 %d 种，只有 %d 种。证书保留各单点输入的不同答案向量。</p></article>' % (record['lower_bound']['required_pitch_symbols'],len(record['available_pitches_cents'])))
    body = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 非均匀任务分区</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / TASK-ALIGNED PARTITION</div><h1>把音高切换放在判断边界上。</h1><p class="lead">每个数值仍只播放一个音，时长和音高词汇保持原有设置。改变数值区间的宽度，让每项阈值判断都有对应的声音切换。</p></header>
<p class="note">保证覆盖声明区间 %s–%s 的任意正长度序列：无缺失、固定时间槽、不漏采样。它改变了等距线性映射假设，因此不与该模型的不可行结论矛盾。不能恢复精确数值，未验证人耳识别或学习效果。</p>
<p>判断边界：%s。原有音高词汇：%s；选择：%s。</p>
<p>下界限定于每个采样一个音、固定时间、无其他数据通道：不同的单点答案向量至少需要 %d 个音高符号。此构造达到该下界，不宣称听辨距离或审美最优。计数原理属于既有知识。</p>
<p><a href="partition.json">可复验证书与全部假设</a></p>%s
</main></body></html>''' % (STYLE,esc(record['input_low']),esc(record['input_high']),esc(record['cutpoints']),esc(record['available_pitches_cents']),esc(record['selected_pitches_cents']),record['lower_bound']['required_pitch_symbols'],''.join(cards))
    path = directory/'index.html'
    path.write_text(body,encoding='utf-8')
    return path


def write_decision_report(record, directory):
    from fractions import Fraction
    from .decision import verify_decision_bound
    if not verify_decision_bound(record):
        raise ValueError('Invalid finite-prior decision certificate')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'decision.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def percentage(value): return '%.2f%% (%s)' % (100*float(Fraction(value)),value)
    rows=[]
    for task,bound in list(record['task_bounds'].items())+[('joint',record['joint_bound'])]:
        rows.append('<tr><th scope="row">%s</th><td>%s</td><td>%s</td><td>%s</td></tr>' % (esc('所有答案同时正确' if task=='joint' else TASK_NAMES[task]),esc(percentage(bound['maximum_accuracy'])),esc(percentage(bound['minimum_error_probability'])),esc(percentage(bound['no_event_maximum_accuracy']))))
    examples=[]
    ambiguous=[c for c in record['classes'] if Fraction(c['input_mass'])>Fraction(c['joint']['correct_mass'])]
    ambiguous.sort(key=lambda c:Fraction(c['input_mass'])-Fraction(c['joint']['correct_mass']),reverse=True)
    for row in ambiguous[:8]:
        labels=''.join('<tr><td>%s</td><td>%d</td><td>%s</td></tr>' % (esc(json.dumps(a['answer'],ensure_ascii=False)),a['input_count'],esc(a['input_mass'])) for a in row['joint']['answers'])
        examples.append('<article><h3>同事件类内的不同联合答案</h3><p>输入编号：%s。总权重 %s；最多答对权重 %s。</p><table><thead><tr><th scope="col">答案（任务顺序同证书）</th><th scope="col">输入数</th><th scope="col">权重</th></tr></thead><tbody>%s</tbody></table><p>理想预测：%s。</p></article>' % (esc(row['input_indices']),esc(row['input_mass']),esc(row['joint']['correct_mass']),labels,esc(json.dumps(row['joint']['optimal_prediction'],ensure_ascii=False))))
    stats=record['statistics']
    prior='声明集合里的每个不同输入等权' if record['prior']['kind']=='uniform_distinct_inputs' else '使用调用方声明的有理数权重，允许零权重'
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 理想事件解码的决策上限</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / FINITE-PRIOR DECISION BOUND</div><h1>完美识别声音事件，也未必能答对问题。</h1><p class="lead">每个声音事件类选择权重最大的答案，得到在声明输入先验下可达到的最优正确率。这是一项有限计数结论。</p></header>
<p class="note">%s。先验不是自然发生频率，也不是参与者成绩。解码器只知道精确事件和先验；不能使用输入身份、原始数值、日期或其他旁信息。没有人耳、训练效果或新数据泛化结论。</p>
<p>表示方式：%s；%d个不同输入，%d个声音事件类。加权平均播放时长 %s ms，最大时长 %d ms。零权重输入%d个；它们不影响正确率，100%%不代表这些输入也可恢复。</p>
<table><caption>相同有限域与先验下的决策能力</caption><thead><tr><th scope="col">问题</th><th scope="col">最优事件解码正确率</th><th scope="col">最低错误概率</th><th scope="col">完全不给事件的最优正确率</th></tr></thead><tbody>%s</tbody></table>
<h2>可达到，也不能超过的计数上限</h2><p>同一种事件只能选择一个答案。该类正确输入权重最多等于其最大答案权重；保存的多数答案查表达到这个数。对所有类求和并除以总权重即得最优正确率；随机猜测也不能提高此零一损失下的期望正确率。这是既有决策理论的应用。</p>
<p><a href="decision.json">全部事件、答案分布、先验、预测查表与可复验证书</a></p>
<h2>错误权重最大的声音类别（最多展示8个）</h2>%s
</main></body></html>''' % (STYLE,esc(prior),esc(record['representation']['kind']),stats['distinct_inputs'],stats['render_classes'],esc(stats['weighted_mean_duration_ms']),stats['maximum_duration_ms'],stats['zero_mass_inputs'],''.join(rows),''.join(examples) or '<p>在这个声明域与先验中，事件类不存在正权重答案歧义。</p>')
    path=directory/'index.html';path.write_text(body,encoding='utf-8');return path


def write_decision_comparison(record, directory):
    from fractions import Fraction
    from .decision import verify_decision_comparison
    if not verify_decision_comparison(record): raise ValueError('Invalid decision comparison')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'comparison.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows=[]
    # Use generated safe subdirectory names, not caller-supplied candidate names.
    for i,(name,candidate) in enumerate(record['candidates'].items()):
        folder='candidate%d' % i
        write_decision_report(candidate,directory/folder)
        metric=record['metrics'][name]
        rows.append('<tr><th scope="row"><a href="%s/index.html">%s</a></th><td>%.2f%% (%s)</td><td>%s</td><td>%d</td><td>%s</td></tr>' % (folder,esc(name),100*float(Fraction(metric['maximum_joint_accuracy'])),esc(metric['maximum_joint_accuracy']),esc(metric['weighted_mean_duration_ms']),metric['used_pitch_count'],esc('保留在前沿' if name in record['pareto_front'] else '被 '+', '.join(record['dominated_by'][name])+' 支配')))
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 同输入域的表示比较</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / SAME-DOMAIN DECISION COMPARISON</div><h1>把任务能力与表示代价放在一起看。</h1><p class="lead">所有候选使用同一输入集合、先验和问题。比较理想事件解码的联合正确率、加权平均播放时长，以及这个输入域里实际使用的音高数量。</p></header>
<p class="note">三个比较方向是明确选择的工程指标：正确率越高、时长越短、音高种类越少。它们没有被测定为人的认知负担或听辨效果。前沿不等于实际使用推荐，也不证明有限域之外的任务保真。</p>
<table><thead><tr><th scope="col">表示</th><th scope="col">联合最优正确率</th><th scope="col">平均时长 ms</th><th scope="col">使用音高数</th><th scope="col">三指标比较</th></tr></thead><tbody>%s</tbody></table>
<p>若另一候选三个方向都不更差，且至少一项严格更好，则它在这三个指标上支配当前候选。所有保留与排除原因、精确分数和原始证书均可重算。</p><p><a href="comparison.json">完整比較证书</a></p></main></body></html>''' % (STYLE,''.join(rows))
    path=directory/'index.html';path.write_text(body,encoding='utf-8');return path


def write_observation_report(record, directory):
    from .uncertainty import verify_observation_certificate
    if not verify_observation_certificate(record): raise ValueError('Invalid observation certificate')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'observation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    states={'determined_true':'所有允许情况都达到阈值','determined_false':'所有允许情况都未达到阈值','not_identifiable':'达到与未达到都可能，当前观测无法确定'}
    rows=[]
    for i,(reported,bounds) in enumerate(zip(record['reported'],record['admissible_intervals'])):
        rows.append('<tr><th scope="row">%d</th><td>%s</td><td>[%s, %s]</td></tr>' % (i,esc(reported),esc(bounds[0]),esc(bounds[1])))
    audio=[]
    for side in ('lower','upper'):
        for kind,render_data in record['reported_only_outputs'].items():
            rendered=Render(tuple(Event(**e) for e in render_data['events']),render_data['duration_ms'])
            (directory/('%s-world.reported.%s.wav' % (side,kind))).write_bytes(wav_bytes(rendered))
            label='%s情况：%s' % ('实际值取下界的' if side=='lower' else '实际值取上界的','播放报告值' if kind=='base' else '提示报告值的答案')
            audio.append('<div>%s</div>' % sound(rendered,label))
    proof=record['proof']
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 观测区间下的阈值可确定性</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / OBSERVATION IDENTIFIABILITY</div><h1>报告值的问题，与实际值的问题分开检查。</h1><p class="lead">报告数据给定后，另外声明每个实际值的允许区间。检查是否存在不同的允许实际情况，对阈值问题给出不同答案。</p></header>
<p class="note">区间是调用方提供的可行集假设，全部组合都允许；没有赋予概率或保证来源覆盖率。没有缺失值或额外相关约束。区间不是从标准不确定度、置信区间或NOAA误差列转换得到的保证界。</p>
<article><h2>是否至少有一个实际值达到 %s？</h2><p><strong>%s</strong></p><p>对报告值计算的答案：%s。允许实际值达到阈值的采样数量：最少%d，最多%d。</p>
<table><thead><tr><th scope="col">采样位置</th><th scope="col">报告值</th><th scope="col">实际值的假定区间</th></tr></thead><tbody>%s</tbody></table></article>
<article><h2>两个允许的端点情况</h2>%s<p>取所有下界：%s；取所有上界：%s。</p><p>阈值问题随每个实际值单调变化，两个端点情况达到可能的最小和最大答案。若答案不同，两个情况却共享同一报告数据和同一可行集，依赖这些已知资料的确定性表示都会相同。</p></article>
<article><h2>两种情况都只播放同一份报告</h2><div class="pair">%s</div><p>每种表示在两侧生成的WAV字节相同。固定答案提示对报告值的答案仍准确；它不能提供尚未观测到的实际值。也可以用声音表达“无法确定”，但不据此解决实际真假问题。</p></article>
<p>这是同一报告观测下的实际问题可识别性，不要求直接把两个实际序列送进原映射时声音相同。未进行真人听觉研究，未给置信百分比、持续时间或风险解释。</p>
<p><a href="observation.json">全部可行集、端点证据、事件和范围说明</a></p></main></body></html>''' % (STYLE,esc(record['threshold']),states[record['status']],'达到' if record['nominal_answer'] else '未达到',record['at_or_above_count_bounds'][0],record['at_or_above_count_bounds'][1],''.join(rows),data_table(proof['lower_world'],proof['upper_world']),'达到' if proof['lower_world_answer'] else '未达到','达到' if proof['upper_world_answer'] else '未达到',''.join(audio))
    path=directory/'index.html';path.write_text(body,encoding='utf-8');return path


def write_diagnosis_report(record, directory):
    from .diagnosis import verify_diagnosis
    if not verify_diagnosis(record): raise ValueError('Invalid diagnosis')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'diagnosis.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    actual=record['observation_certificates']
    status_names={'reported_mapping_contract_preserved':'原表示保留全部要求的报告值判断',
                  'reported_mapping_collision_found':'原表示存在同事件、不同报告值答案的反例',
                  'actual_answers_not_identifiable':'当前观测无法确定全部实际值答案',
                  'actual_answers_determined_by_declared_intervals':'声明区间足以确定这些实际值答案'}
    observation=''
    if actual:
        rows=[]
        for t,c in actual.items():
            rows.append('<tr><th scope="row">≥%s</th><td>%s</td><td>%s</td><td>%s</td></tr>' % (esc(t),esc(c['nominal_answer']),esc(c['possible_actual_answers']),esc(c['status'])))
        observation='<article><h2>先检查实际值问题</h2><table><thead><tr><th>边界</th><th>报告值答案</th><th>允许实际答案</th><th>可确定性</th></tr></thead><tbody>%s</tbody></table><p>区间的全部组合假定可行。以下映射设计只回答报告值问题；改变报告值编码不能确定尚未知的实际真假，也不认证区间的来源覆盖率。</p></article>' % ''.join(rows)
    contracts=[]
    for t,c in record['original_reported_contracts'].items():
        example=c['witness']
        content=''
        if example:
            content=data_table(example['left'],example['right'])+'<p>答案分别为%s、%s；原声音事件相同。</p>' % (esc(example['left_answer']),esc(example['right_answer']))
        contracts.append('<article><h3>报告值是否至少有一个≥%s？</h3><p>%s；证明方式%s。</p>%s</article>' % (esc(t),esc(c['status']),esc(c['proof_kind']),content))
    designs=[]
    labels={'retain_original':'保留原表示','shared_scale_and_full_sampling':'共享标尺并保留全部采样','linear_range_alignment':'调整线性范围','nonuniform_partition':'非均匀任务分区'}
    for i,design in enumerate(record['reported_mapping_designs']):
        extra=''
        if 'mapping' in design:
            m=design['mapping'];extra='<p>范围%s–%s；normalization=%s，stride=%s。</p>' % (esc(m['domain_low']),esc(m['domain_high']),esc(m['normalization']),esc(m['stride']))
        else:
            p=design['partition'];extra='<p>分区边界%s；选用音高%s cents。</p>' % (esc(p['cutpoints']),esc(p['selected_pitches_cents']))
        lost=design['previously_preserved_thresholds_lost']
        preview=', '.join(lost[:8])+(' …（共%d个）'%len(lost) if len(lost)>8 else '')
        designs.append('<article><h3>%s</h3><p>改变字段：%s。</p>%s<p>原来保留、现在失去的非请求边界：%s。</p></article>' % (labels[design['kind']],esc(design['changed_fields']),extra,esc(preview or '无')))
    searches=[]
    for name,search in record['design_searches'].items():
        status=search.get('status','constructed_candidates')
        searches.append('<li>%s：%s。%s</li>' % (esc(name),esc(status),esc(search.get('reason','有限单端点候选；完整范围见证书。'))))
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 阈值诊断入口</title><style>%s</style></head><body><main><header><div class="eyebrow">ECHOPROOF / THRESHOLD DIAGNOSIS</div><h1>%s</h1><p class="lead">所问对象：%s。报告值契约区间%s–%s；要求同时保留的判断边界%s。</p></header>
<p class="note">只检查正长度、无缺失、精确数值的阈值问题。声称的保留范围、设计约束和实际值可确定性分别保存。不自动应用方案，也不评价听辨、学习或其他数据任务。</p>%s
<h2>报告值进入原表示时的证据</h2>%s<h2>可核验的报告值表示方案</h2>%s
<h2>搜索限制与失败原因</h2><ul>%s</ul><p>“不可行”限定于对应线性覆盖或单音高字母表约束；“未搜索”不会改称不可行。没有方案时也不声称所有额外通道都无解。多个方案按构造顺序展示，不作为全局最优推荐。</p><p><a href="diagnosis.json">完整观察、契约、构造、回归边界和可复验证据</a></p></main></body></html>''' % (STYLE,status_names[record['status']],esc(record['question']),esc(record['reported_input_low']),esc(record['reported_input_high']),esc(record['thresholds']),observation,''.join(contracts),''.join(designs) or '<p>当前受约束构造未提供方案；完整原因保留在下方。</p>',''.join(searches) or '<li>原表示已满足请求，无需搜索修复。</li>')
    path=directory/'index.html';path.write_text(body,encoding='utf-8');return path
