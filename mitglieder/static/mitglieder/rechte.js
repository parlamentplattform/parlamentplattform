/* Sichtbar ohne JavaScript; die kurze Zeichnung ist eine einmalige Zugabe. */
(() => {
  if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const beobachter = new IntersectionObserver((eintraege) => {
    for (const eintrag of eintraege) {
      if (!eintrag.isIntersecting) continue;
      eintrag.target.classList.add('zeichnet');
      beobachter.unobserve(eintrag.target);
    }
  }, {threshold: 0.2});
  for (const karte of document.querySelectorAll('.mitgliedsrechte > .karte')) beobachter.observe(karte);
})();
