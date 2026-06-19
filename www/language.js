(function () {
  const key = "urirun.language";
  const current = document.documentElement.lang === "pl" ? "pl" : "en";
  const labels = {
    pl: {
      link: "index.html",
      text: "Ostatnio wybrano polską wersję. Otwórz ją ponownie.",
    },
    en: {
      link: "index.en.html",
      text: "English was selected last time. Open it again.",
    },
  };

  document.querySelectorAll("[data-lang-choice]").forEach((link) => {
    link.addEventListener("click", () => {
      localStorage.setItem(key, link.dataset.langChoice);
    });
  });

  const saved = localStorage.getItem(key);
  const memory = document.querySelector("[data-language-memory]");
  const link = memory ? memory.querySelector("a") : null;

  if (!saved || saved === current || !memory || !link || !labels[saved]) {
    return;
  }

  link.href = labels[saved].link;
  link.textContent = labels[saved].text;
  memory.hidden = false;
})();

(function () {
  document.querySelectorAll("[data-tech-tabs]").forEach((group) => {
    const tabs = Array.from(group.querySelectorAll("[data-tech-tab]"));
    const panels = Array.from(group.querySelectorAll("[role='tabpanel']"));

    function select(id, focus = false) {
      tabs.forEach((tab) => {
        const active = tab.dataset.techTab === id;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
        tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });

      panels.forEach((panel) => {
        const active = panel.id === `panel-${id}`;
        panel.classList.toggle("active", active);
        panel.hidden = !active;
      });
    }

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => select(tab.dataset.techTab));
      tab.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const last = tabs.length - 1;
        const next = event.key === "Home"
          ? 0
          : event.key === "End"
            ? last
            : event.key === "ArrowRight"
              ? (index + 1) % tabs.length
              : (index - 1 + tabs.length) % tabs.length;
        select(tabs[next].dataset.techTab, true);
      });
    });

    const current = tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
    if (current) select(current.dataset.techTab);
  });
})();
