'use strict';
// Optional headless compiler experiment. This never controls a browser or plays audio.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const Module = require('node:module');

process.env.NODE_PATH = path.join(__dirname, 'node_modules');
Module._initPaths();
const project = path.resolve(__dirname, '../..');
const bundle = path.join(project, 'research/vendor/erie-web-1.0.1/build/erie-web-node.js');
const Erie = require(bundle);

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort()
      .filter(key => key !== '__datum')
      .map(key => [key, canonical(value[key])]));
  }
  return value;
}

function makeSpec(values, fixed = false) {
  return {
    data: { values: values.map((y, x) => ({ x, y })) },
    tone: { type: 'sine', continued: false },
    encoding: {
      time: { field: 'x', type: 'quantitative', scale: { domain: [0, 2], range: [0, 1] } },
      pitch: { field: 'y', type: 'quantitative', scale: { range: [200, 800], ...(fixed ? { domain: [0, 30] } : {}) } },
    },
    config: { skipScaleSpeech: true, skipTitle: true, skipDescription: true,
              skipStartSpeech: true, skipFinishSpeech: true },
  };
}

async function compile(values, fixed) {
  const spec = makeSpec(values, fixed);
  const graph = await Erie.compileAudioGraph(spec);
  assert.equal(graph.streams.length, 1);
  const tone = await graph.streams[0].prerender();
  // The current compiler's stream array is not necessarily in time order.
  const toneProjection = canonical(tone);
  toneProjection.sounds.sort((a, b) => a.start - b.start);
  const queue = await graph.prerender();
  return { spec, rawTone: JSON.parse(JSON.stringify(tone)), toneProjection,
           rawQueue: JSON.parse(JSON.stringify(queue)), queueProjection: canonical(JSON.parse(JSON.stringify(queue))) };
}

async function main() {
  const left = [1, 2, 3], right = [10, 20, 30];
  const autoLeft = await compile(left, false), autoRight = await compile(right, false);
  const fixedLeft = await compile(left, true), fixedRight = await compile(right, true);
  const toneEqual = JSON.stringify(autoLeft.toneProjection) === JSON.stringify(autoRight.toneProjection);
  const fullEqual = JSON.stringify(autoLeft.queueProjection) === JSON.stringify(autoRight.queueProjection);
  const fixedEqual = JSON.stringify(fixedLeft.toneProjection) === JSON.stringify(fixedRight.toneProjection);
  assert.equal(toneEqual, true, 'Auto-domain tone streams should alias for positive affine scales');
  assert.equal(fullEqual, false, 'Do not erase speech: the full queues distinguish absolute values');
  assert.equal(fixedEqual, false, 'A shared explicit domain distinguishes the tone streams');
  const speech = result => result.queueProjection.queue.filter(x => x.type === 'text').map(x => x.speech);
  assert.ok(speech(autoLeft).some(x => x.includes('minimum value 1')));
  assert.ok(speech(autoRight).some(x => x.includes('minimum value 10')));
  const output = {
    schema_version: 1,
    claim_type: 'external_compiler_observation',
    backend: 'erie-web@1.0.1',
    runtime: process.version,
    bundle_sha256: crypto.createHash('sha256').update(fs.readFileSync(bundle)).digest('hex'),
    lockfile_sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname, 'pnpm-lock.yaml'))).digest('hex'),
    inputs: { left, right },
    tasks: { threshold_5: { left: left.some(x => x >= 5), right: right.some(x => x >= 5) },
             total: { left: left.reduce((a,b) => a+b), right: right.reduce((a,b) => a+b) } },
    observations: { auto_domain_tone_streams_equal: toneEqual, auto_domain_full_queues_equal: fullEqual,
                    shared_domain_tone_streams_equal: fixedEqual,
                    speech_left: speech(autoLeft), speech_right: speech(autoRight) },
    cases: { autoLeft, autoRight, fixedLeft, fixedRight },
    scope: 'Headless compilation of these explicit specs only. Tone-only equality is not equality of the complete sonification: the generated speech legend differs. No browser playback or human testing performed.',
  };
  const directory = path.resolve(process.argv[2] || path.join(project, 'artifacts/erie-direct'));
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(path.join(directory, 'observation.json'), JSON.stringify(output, null, 2) + '\n');
  console.log(JSON.stringify({ output: directory, observations: output.observations }, null, 2));
}

main().catch(error => { console.error(error.stack); process.exitCode = 1; });
