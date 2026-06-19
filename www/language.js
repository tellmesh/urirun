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
