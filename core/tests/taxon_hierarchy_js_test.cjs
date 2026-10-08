"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function makeSelect(entries) {
  const options = [
    { value: "", dataset: {}, hidden: false, disabled: false, selected: true },
    ...entries.map(([value, ancestors]) => ({
      value,
      dataset: { ancestorIds: ancestors.join(",") },
      hidden: false,
      disabled: false,
      selected: false,
    })),
  ];
  const handlers = {};
  let current = "";
  return {
    options,
    handlers,
    disabled: false,
    addEventListener(name, handler) { handlers[name] = handler; },
    get value() { return current; },
    set value(value) {
      current = value;
      options.forEach((option) => { option.selected = option.value === value; });
    },
    option(value) { return options.find((option) => option.value === value); },
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

  assert.equal(selects.species.disabled, false);
  assert.equal(selects.species.option("s1").disabled, false);
  assert.equal(selects.species.option("s2").disabled, false);
  selects.species.value = "s1";
  selects.species.handlers.change();
  assert.equal(selects.species.value, "s1");

  selects.family.value = "f1";
  selects.family.handlers.change();
  assert.equal(selects.species.value, "s1");
  assert.equal(selects.subfamily.option("sf2").disabled, true);
  assert.equal(selects.species.option("s2").disabled, true);
  assert.equal(selects.genus.option("g1").disabled, false);

  selects.family.value = "f2";
  selects.family.handlers.change();
  assert.equal(selects.species.value, "");
  assert.equal(selects.species.option("s2").disabled, false);
  assert.equal(selects.genus.option("g1").disabled, true);
});
