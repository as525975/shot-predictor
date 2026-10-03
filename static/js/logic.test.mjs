// Run: node --test static/js
import assert from 'node:assert/strict';
import test from 'node:test';
import { S, binOf, fold, makeSteps, overBin, overLabel, searchBatters, stepLabels } from './logic.js';

const batters = [['Virat Kohli', 'RHB', 24740], ['Quinton de Kock', 'LHB', 9000], ['Tom Kohler-Cadmore', 'RHB', 900], ['Sam Konstas', 'RHB', 100]];

test('search: every word must match, accents ignored, prefix matches first', () => {
  assert.equal(searchBatters(batters, '').total, 4);
  assert.deepEqual(searchBatters(batters, 'v koh').hits.map(r => r[0]), ['Virat Kohli']);
  assert.deepEqual(searchBatters(batters, 'koh').hits.map(r => r[0]), ['Virat Kohli', 'Tom Kohler-Cadmore']);
  assert.deepEqual(searchBatters(batters, 'KOCK').hits.map(r => r[0]), ['Quinton de Kock']);
  assert.equal(searchBatters(batters, 'zzzq').total, 0);
  assert.equal(fold('Ćhâhal'), 'chahal');
  assert.equal(searchBatters(batters, 'o', 2).hits.length, 2);  // capped
});

test('stepped scale: rounded breaks, labels match the breaks, values land in the right step', () => {
  const { edges, step } = makeSteps(2.7, 13.4);
  assert.ok(edges.length <= 4 && edges.every((e, i) => i === 0 || e > edges[i - 1]));
  assert.equal(stepLabels(edges, step).length, edges.length + 1);
  assert.equal(binOf(edges[0] - 0.01, edges), 0);
  assert.equal(binOf(edges[0], edges), 1);
  assert.equal(binOf(1e9, edges), edges.length);
  assert.deepEqual(stepLabels([-5, 0, 5], 5), ['under −5', '−5 to 0', '0 to 5', '5+']);
});

test('overs: ODI ranges of 5, T20 single overs, labels', () => {
  assert.deepEqual(overBin(12, 'ODI'), { lo: 11, hi: 15 });
  assert.deepEqual(overBin(50, 'ODI'), { lo: 46, hi: 50 });
  assert.deepEqual(overBin(7, 'T20'), { lo: 7, hi: 7 });
  S.format = 'ODI'; S.over = 46;
  assert.equal(overLabel(), 'overs 46-50');
});
