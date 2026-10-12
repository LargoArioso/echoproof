/* Read-only research harness for original internal Highcharts mapping functions.
 * Append export instrumentation in memory; do not edit downloaded source.
 * No Chart, browser, AudioContext, playback, or full timeline is constructed.
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const sourceRoot = path.join(root, 'research/vendor/highcharts-13.1.1/es-modules');
const target = path.join(sourceRoot, 'Extensions/Sonification/TimelineFromChart.js');
const cache = new Map();
const loadedHashes = {};
function moduleFor(filename) {
  if (cache.has(filename)) return cache.get(filename);
  if (!filename.startsWith(sourceRoot + path.sep)) throw Error('Import escapes source root');
  const raw = fs.readFileSync(filename, 'utf8');
  loadedHashes[path.relative(sourceRoot, filename)] = crypto.createHash('sha256').update(raw).digest('hex');
  const instrumentation = filename === target ? '\nexport { mapToVirtualAxis, getMappingParameterValue, getPointTime, addMappedInstrumentEvent };\n' : '';
  const module = new vm.SourceTextModule(raw + instrumentation, { identifier: filename });
  cache.set(filename, module);
  return module;
}
async function main() {
  const module = moduleFor(target);
  await module.link((specifier, referer) => moduleFor(path.resolve(path.dirname(referer.identifier), specifier)));
  await module.evaluate();
  const { getMappingParameterValue, getPointTime, addMappedInstrumentEvent } = module.namespace;
  const defaults = { min:48, max:84, mapTo:'y', mapFunction:'linear', within:'chart' };
  function capture(values, pitchOptions, sharedRange, round=true) {
    const ownRange = { min:Math.min(...values), max:Math.max(...values) };
    const series = { index:0 };
    const metrics = { globalExtremes:{ y:sharedRange || ownRange, x:{ min:0, max:values.length-1 } },
                      seriesExtremes:[{ y:ownRange, x:{ min:0, max:values.length-1 } }] };
    const events=[];
    const channel={ addEvent(event) {
      // RelatedPoint is intentionally omitted; scope is the mapped instrument
      // parameters and event time, not full queue or interactive metadata.
      const recorded = { time:event.time, instrumentEventOptions:event.instrumentEventOptions };
      events.push(recorded); return recorded;
    }};
    values.forEach((y,x) => {
      const point={ x,y,series };
      const time=getPointTime(point,0,480,'x',metrics,true);
      addMappedInstrumentEvent({ point,time },channel,
        { pitch:pitchOptions, volume:0.2, pan:0, noteDuration:180 },metrics,round);
    });
    return { input:values, mapping:pitchOptions, metrics, roundToMusicalNotes:round, events };
  }
  const pitchSeries={ mapTo:'y', min:48, max:84, within:'series' };
  const a=capture([1,2,3],pitchSeries), b=capture([10,20,30],pitchSeries);
  assert.deepEqual(a.events,b.events);
  const fixedA=capture([1,2,3],{...pitchSeries,within:'chart'},{min:0,max:30});
  const fixedB=capture([10,20,30],{...pitchSeries,within:'chart'},{min:0,max:30});
  assert.notDeepEqual(fixedA.events,fixedB.events);
  const constant=capture([5,5,5],pitchSeries);
  assert.equal(constant.events[0].instrumentEventOptions.note,48);
  const coarse={ mapTo:'y',min:48,max:84,within:'chart',scale:[0] };
  const boundary=[];
  for (const value of [49,50,50.5,51]) {
    const point={ y:value,series:{index:0} };
    const metrics={ globalExtremes:{y:{min:0,max:100}},seriesExtremes:[] };
    boundary.push({ value,note:getMappingParameterValue({point},metrics,false,defaults,coarse) });
  }
  assert.deepEqual(boundary.map(row=>row.note),[60,72,72,72]);
  const corpus=[];
  for (const x of [49,50,51]) for (const y of [49,50,51]) for (const z of [49,50,51]) corpus.push(capture([x,y,z],coarse,{min:0,max:100}));
  const directory=path.join(root,'artifacts/highcharts-mapping');
  fs.mkdirSync(directory,{recursive:true});
  const record={ backend:'Highcharts 13.1.1',scope:'Original internal mapping functions, mapped instrument parameters/time only. Manual point/metrics/channel inputs; no Chart, full timeline, speech, AudioContext or playback.',
    instrumentation:'Append exports for four original internal functions in memory. Original source files unchanged; all helpers imported from original source.',
    nodeVersion:process.version,producer_sha256:crypto.createHash("sha256").update(fs.readFileSync(__filename)).digest("hex"),source_sha256:loadedHashes,
    observations:{ perSeriesAffine:[a,b],sharedRange:[fixedA,fixedB],constant,boundary },corpus,
    assertions_passed:4 };
  fs.writeFileSync(path.join(directory,'observation.json'),JSON.stringify(record,null,2)+'\n');
  fs.writeFileSync(path.join(directory,'corpus.json'),JSON.stringify({ backend:{ name:record.backend, scope:record.scope, instrumentation:record.instrumentation, producer_sha256:record.producer_sha256, source_sha256:loadedHashes }, records:corpus },null,2)+'\n');
  console.log(JSON.stringify({ backend:record.backend, importedFiles:cache.size,assertions_passed:4,corpus:corpus.length,boundary,constantPitch:48 }));
}
main().catch(error=>{ console.error(error);process.exitCode=1; });
