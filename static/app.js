(() => {
  // Density mode (comfortable/compact)
  const applyDensity = (mode) => {
    document.documentElement.dataset.density = mode === "compact" ? "compact" : "comfortable";
  };

  const saved = localStorage.getItem("bk_density");
  if (saved) applyDensity(saved);

  const toggleBtn = document.querySelector("[data-density-toggle]");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const cur = document.documentElement.dataset.density === "compact" ? "compact" : "comfortable";
      const next = cur === "compact" ? "comfortable" : "compact";
      localStorage.setItem("bk_density", next);
      applyDensity(next);
    });
  }

  const forms = document.querySelectorAll("[data-entry-form]");
  if (!forms.length) return;

  const setVisibility = (form, tip) => {
    const onlyEls = form.querySelectorAll("[data-only]");
    for (const el of onlyEls) {
      const show = el.getAttribute("data-only") === tip;
      el.style.display = show ? "" : "none";
      // Clear hidden values so we don't accidentally persist irrelevant length fields.
      if (!show) {
        const input = el.querySelector("input, textarea, select");
        if (input) input.value = "";
      }
    }

    const kriterijEls = form.querySelectorAll("[data-kriterij]");
    const book = new Set(["zgodba", "liki", "tempo", "slog", "custveni_vpliv"]);
    const audio = new Set(["zgodba", "liki", "tempo", "naracija", "jasnost_govora", "zvocna_izkusnja"]);
    const allowed = tip === "book" ? book : audio;

    for (const el of kriterijEls) {
      const k = el.getAttribute("data-kriterij");
      const show = allowed.has(k);
      el.style.display = show ? "" : "none";
      const input = el.querySelector("input");
      if (input && !show) input.value = "";
    }
  };

  for (const form of forms) {
    const tipSelect = form.querySelector("[data-tip]");
    if (!tipSelect) continue;
    const getTip = () => (tipSelect.value || tipSelect.getAttribute("value") || "book");
    setVisibility(form, getTip());
    tipSelect.addEventListener("change", () => setVisibility(form, getTip()));
  }
})();
