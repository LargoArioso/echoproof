'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const Module = require('node:module');
process.env.NODE_PATH = path.join(__dirname, 'node_modules');
Module._initPaths();
const root = path.resolve(__dirname, '../..');
const bundle = path.join(root, 'research/vendor/erie-web-1.0.1/build/erie-web-node.js');
const Erie = require(bundle);

function spec(values, aggregate) {
  return {
    data: { values: values.map((y,x) => ({x,y})) },
    ...(aggregate ? { transform: [{aggregate: [{op: 'mean', field: 'y', as: 'y'}], groupby: []}] } : {}),
    tone: {type: 'sine', continued: false},
    encoding: {
      time: {field: 'x', type: 'quantitative', scale: {domain: [0,2], range: [0,1]}},
      pitch: {field: 'y', type: 'quantitative', scale: {range: [200,800], ...(aggregate ? {domain: [0,3]} : {})}},
    },
  };
}

async function main() {
  const backend = {name: 'erie-web', version: '1.0.1', runtime: process.version,
                   bundle_sha256: crypto.createHash('sha256').update(fs.readFileSync(bundle)).digest('hex')};
  const directory = path.join(root, 'artifacts/erie-corpus');
  fs.mkdirSync(directory, {recursive: true});
  for (const aggregate of [false, true]) {
    const records = [];
    for (const a of [1,2,3]) for (const b of [1,2,3]) for (const c of [1,2,3]) {
      const values = [a,b,c], inputSpec = spec(values, aggregate);
      const graph = await Erie.compileAudioGraph(inputSpec);
      assert.equal(graph.streams.length, 1);
      const tone = await graph.streams[0].prerender();
      const queue = await graph.prerender();
      records.push(JSON.parse(JSON.stringify({input: values, spec: inputSpec, tone, queue})));
    }
    const name = aggregate ? 'aggregate-mean' : 'auto-domain';
    const corpus = {schema_version: 1, backend, name, declared_inputs: {levels:[1,2,3],lengths:[3]},
                    records, capture_scope: 'Raw headless compiler output, no browser playback or human test'};
    fs.writeFileSync(path.join(directory, name + '.corpus.json'), JSON.stringify(corpus, null, 2) + '\n');
    console.log(name + ': ' + records.length + ' raw recordings');
  }
}
main().catch(error => { console.error(error.stack); process.exitCode=1; });
