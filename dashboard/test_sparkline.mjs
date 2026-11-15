import assert from "node:assert/strict";
import test from "node:test";

import { sparkline } from "./app.js";

test("empty points draw nothing", () => {
  assert.equal(sparkline([]), "");
});

test("a rise moves toward the top of the svg", () => {
  const svg = sparkline([1, 3]);
  const d = svg.match(/d="([^"]+)"/)[1];
  const ys = d.match(/[\d.]+ [\d.]+/g).map((pair) => Number(pair.split(" ")[1]));
  assert.equal(ys.length, 2);
  assert.ok(ys[1] < ys[0]);
});
