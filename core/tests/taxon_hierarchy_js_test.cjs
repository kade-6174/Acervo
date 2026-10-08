"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function makeSelect(entries) {
  const options = [
    { value: "", dataset: {}, selected: true },
    ...entries.map(([value, ancestors]) => ({
      value,
      dataset: { ancestorIds: ancestors.join(",") },
      selected: false,
    })),
  ];
  const handlers = {};
  let current = "";
  return {
    options,
    handlers,
    addEventListener(name, handler) { handlers[name] = handler; },
    replaceChildren(...available) { this.options = available; },
    get value() { return current; },
    set value(value) {
      current = this.options.some((option) => option.value === value) ? value : "";
      this.options.forEach((option) => { option.selected = option.value === current; });
    },
    values() { return this.options.map((option) => option.value); },
  };
}

test("和名分類は上位の空欄を許し、選択済みの系統だけへ絞り込む", () => {
  const selects = {
    family: makeSelect([["f1", []], ["f2", []]]),
    subfamily: makeSelect([["sf1", ["f1"]], ["sf2", ["f2"]]]),
    tribe: makeSelect([["t1", ["sf1", "f1"]]]),
    genus: makeSelect([["g1", ["sf1", "f1"]], ["g2", ["sf2", "f2"]]]),
    species: makeSelect([["s1", ["g1", "sf1", "f1"]], ["s2", ["g2", "sf2", "f2"]]]),
  };
  const hierarchy = {
    querySelector(selector) {
      const rank = selector.match(/data-taxon-rank='([^']+)'/)[1];
      return selects[rank];
    },
  };
  const code = fs.readFileSync(
    path.resolve(__dirname, "../../static/js/taxon-hierarchy.js"), "utf8",
  );
  vm.runInNewContext(code, {
    document: {
      querySelector(selector) {
        return selector === "[data-taxon-hierarchy]" ? hierarchy : null;
      },
    },
  });

  assert.deepEqual(selects.species.values(), ["", "s1", "s2"]);
  selects.species.value = "s1";
  selects.species.handlers.change();
  assert.equal(selects.species.value, "s1");

  selects.family.value = "f1";
  selects.family.handlers.change();
  assert.equal(selects.species.value, "s1");
  assert.deepEqual(selects.subfamily.values(), ["", "sf1"]);
  assert.deepEqual(selects.species.values(), ["", "s1"]);
  assert.deepEqual(selects.genus.values(), ["", "g1"]);

  selects.family.value = "f2";
  selects.family.handlers.change();
  assert.equal(selects.species.value, "");
  assert.deepEqual(selects.species.values(), ["", "s2"]);
  assert.deepEqual(selects.genus.values(), ["", "g2"]);

  selects.family.value = "";
  selects.family.handlers.change();
  assert.deepEqual(selects.subfamily.values(), ["", "sf1", "sf2"]);
  assert.deepEqual(selects.species.values(), ["", "s1", "s2"]);

  selects.subfamily.value = "sf1";
  selects.subfamily.handlers.change();
  assert.deepEqual(selects.genus.values(), ["", "g1"]);
  assert.deepEqual(selects.species.values(), ["", "s1"]);
});
