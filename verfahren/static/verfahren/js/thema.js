/* Vor dem ersten Zeichnen: gemerktes Erscheinungsbild setzen, damit nichts aufblitzt (FB-P3).
   Bewusst winzig und blockierend im <head>, als eigene Datei (kein Inline-Skript, CSP-tauglich).
   Ohne JavaScript gilt die Systemeinstellung über prefers-color-scheme. */
(function () {
  try {
    var thema = localStorage.getItem("ddoe.thema");
    if (thema === "light" || thema === "dark") {
      document.documentElement.setAttribute("data-theme", thema);
    }
  } catch (fehler) {
    /* Privatmodus oder gesperrter Speicher: Systemeinstellung bleibt. */
  }
  document.documentElement.classList.add("js");
})();
