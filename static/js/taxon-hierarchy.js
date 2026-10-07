(() => {
  const hierarchy = document.querySelector("[data-taxon-hierarchy]");
  if (hierarchy) {
    const family = hierarchy.querySelector("[data-taxon-rank='family']");
    const genus = hierarchy.querySelector("[data-taxon-rank='genus']");
    const species = hierarchy.querySelector("[data-taxon-rank='species']");

    const filterOptions = (select, parentId) => {
      for (const option of select.options) {
        if (!option.value) {
          option.hidden = false;
          option.disabled = false;
          continue;
        }
        const visible = Boolean(parentId) && option.dataset.parentId === parentId;
        option.hidden = !visible;
        option.disabled = !visible;
        if (!visible && option.selected) {
          select.value = "";
        }
      }
      select.disabled = !parentId;
    };

    const update = () => {
      filterOptions(genus, family.value);
      filterOptions(species, genus.value);
    };

    family.addEventListener("change", update);
    genus.addEventListener("change", update);
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
