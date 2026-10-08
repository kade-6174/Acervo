(() => {
  const hierarchy = document.querySelector("[data-taxon-hierarchy]");
  if (hierarchy) {
    const family = hierarchy.querySelector("[data-taxon-rank='family']");
    const subfamily = hierarchy.querySelector("[data-taxon-rank='subfamily']");
    const tribe = hierarchy.querySelector("[data-taxon-rank='tribe']");
    const genus = hierarchy.querySelector("[data-taxon-rank='genus']");
    const species = hierarchy.querySelector("[data-taxon-rank='species']");
    const selects = [family, subfamily, tribe, genus, species];
    const optionCatalogs = selects.map((select) => Array.from(select.options));

    const filterOptions = (select, catalog, selectedAncestors) => {
      const selectedValue = select.value;
      const available = catalog.filter((option) => {
        if (!option.value) return true;
        const ancestorIds = (option.dataset.ancestorIds || "").split(",");
        return selectedAncestors.every((id) => ancestorIds.includes(id));
      });
      select.replaceChildren(...available);
      select.value = available.some((option) => option.value === selectedValue) ? selectedValue : "";
    };

    const update = () => {
      for (let index = 1; index < selects.length; index += 1) {
        filterOptions(
          selects[index],
          optionCatalogs[index],
          selects.slice(0, index).map((select) => select.value).filter(Boolean),
        );
      }
    };

    selects.forEach((select) => select.addEventListener("change", update));
    update();
  }

  const manualHierarchy = document.querySelector("[data-manual-taxon-hierarchy]");
  if (!manualHierarchy) {
    return;
  }

  const rank = manualHierarchy.querySelector("[data-manual-taxon-rank]");
  const parent = manualHierarchy.querySelector("[data-manual-taxon-parent]");
  const requiredParentRank = {
    genus: "family",
    species: "genus",
  };

  const updateManualParent = () => {
    const expectedRank = requiredParentRank[rank.value];
    for (const option of parent.options) {
      if (!option.value) {
        option.hidden = false;
        option.disabled = false;
        continue;
      }
      const visible = option.dataset.taxonRank === expectedRank;
      option.hidden = !visible;
      option.disabled = !visible;
      if (!visible && option.selected) {
        parent.value = "";
      }
    }
    parent.disabled = !expectedRank;
  };

  rank.addEventListener("change", updateManualParent);
  updateManualParent();
})();
