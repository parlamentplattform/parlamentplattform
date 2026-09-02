/* ParlamentPlattform — Alpine-Komponenten (FB-P4, Design-Spezifikation 5).
   Alles hier ist Zugabe: ohne JavaScript bleiben Leiste, Menüs, Anstoß und Regler
   als <details>, Links und Formulare vollständig bedienbar. Die Templates tragen
   keine Inline-Handler; sie verweisen nur auf die Namen dieser Komponenten. */
document.addEventListener("alpine:init", function () {
  var reduziert = function () {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  };

  /* Aufklappmenü auf <details>: Konto, ⋯ Mehr, Burger-Panel.
     Verstärkt das native Element um Außenklick, Escape, Fokusrückgabe und — bei
     einem Panel — Scroll-Sperre und Fokusfalle (Spec 7). */
  Alpine.data("klappmenue", function (opts) {
    opts = opts || {};
    return {
      offen: false,
      init: function () {
        var self = this;
        this.offen = this.$el.open;
        this.$el.addEventListener("toggle", function () {
          self.offen = self.$el.open;
          if (opts.panel) {
            document.body.classList.toggle("menue-offen", self.offen);
            if (self.offen) {
              var erster = self.$el.querySelector(".panel a, .panel button");
              if (erster) erster.focus();
            }
          }
        });
      },
      zu: function (fokus) {
        if (!this.$el.open) return;
        this.$el.open = false;
        if (fokus !== false && this.$refs.ausloeser) this.$refs.ausloeser.focus();
      },
      tab: function (e) {
        if (!opts.panel || !this.offen || e.key !== "Tab") return;
        var ziele = Array.prototype.filter.call(
          this.$el.querySelectorAll("summary, .panel a, .panel button, .panel input"),
          function (z) { return !z.hidden && z.offsetParent !== null; }
        );
        if (!ziele.length) return;
        var erstes = ziele[0], letztes = ziele[ziele.length - 1];
        if (e.shiftKey && document.activeElement === erstes) { e.preventDefault(); letztes.focus(); }
        else if (!e.shiftKey && document.activeElement === letztes) { e.preventDefault(); erstes.focus(); }
      }
    };
  });

  /* Anstoß-Widget: schließt auf den HX-Trigger „anstoss-danke“ des Servers, zeigt die
     Blase und leert das Formular; „warte“/„leer“ halten die Karte offen (Spec 5). */
  Alpine.data("anstoss", function () {
    return {
      zu: function () { var d = this.$refs.klappe; if (d && d.open) d.open = false; },
      auf: function () { var d = this.$refs.klappe; if (d) d.open = true; },
      danke: function () {
        this.zu();
        if (this.$refs.form) this.$refs.form.reset();
        if (this.$refs.echo) this.$refs.echo.innerHTML = "";
        if (this.$refs.blase) this.$refs.blase.hidden = false;
      },
      blaseZu: function () { if (this.$refs.blase) this.$refs.blase.hidden = true; }
    };
  });

  /* Erscheinungsbild: System / Hell / Dunkel, gemerkt je Gerät, gesetzt als data-theme (FB-P3).
     Die Schaltergruppe ist ohne JavaScript verborgen und wird hier eingeblendet. */
  Alpine.data("thema", function () {
    return {
      wahl: "",
      init: function () {
        try { this.wahl = localStorage.getItem("ddoe.thema") || ""; } catch (fehler) { this.wahl = ""; }
        if (this.wahl !== "light" && this.wahl !== "dark") this.wahl = "";
        this.$el.hidden = false;
      },
      setzen: function (w) {
        this.wahl = w;
        var html = document.documentElement;
        if (w) html.setAttribute("data-theme", w); else html.removeAttribute("data-theme");
        try {
          if (w) localStorage.setItem("ddoe.thema", w); else localStorage.removeItem("ddoe.thema");
        } catch (fehler) { /* Speicher gesperrt — die Wahl gilt für diese Seite */ }
      }
    };
  });

  /* Tableiste am Handy: aktives Feld beim Einrasten nachführen, Tipp springt weich (FB-A1). */
  Alpine.data("tabs", function () {
    return {
      aktiv: "feld-filter",
      init: function () {
        var self = this;
        var raster = document.querySelector(".parlament");
        if (!raster || !("IntersectionObserver" in window)) return;
        var beobachter = new IntersectionObserver(function (eintraege) {
          eintraege.forEach(function (e) { if (e.isIntersecting) self.aktiv = e.target.id; });
        }, { root: raster, threshold: 0.6 });
        Array.prototype.forEach.call(raster.querySelectorAll(":scope > .feld"), function (f) { beobachter.observe(f); });
      },
      springe: function (id) {
        var ziel = document.getElementById(id);
        if (ziel) ziel.scrollIntoView({ behavior: reduziert() ? "auto" : "smooth", block: "start" });
        this.aktiv = id;
      }
    };
  });

  /* Rückmeldung in der Kachel (FB-A2): Nach einer Handlung tauscht htmx das Feld; die neue
     Kachel desselben Antrags zeigt 1,5 s den Gold-Haken „Erfasst“ statt einer Flash-Meldung.
     Der Auslöser kennt seinen Antrag (data-antrag), darum braucht es keinen Server-Umweg. */
  Alpine.data("parlament", function () {
    return {
      init: function () {
        var self = this;
        this.$el.addEventListener("htmx:afterSettle", function (e) {
          var konfig = e.detail && e.detail.requestConfig;
          if (!konfig || konfig.verb !== "post") return;
          var quelle = konfig.elt && konfig.elt.closest ? konfig.elt.closest(".kachel") : null;
          if (!quelle || !quelle.dataset.antrag) return;
          self.markiere(quelle.dataset.antrag);
        });
      },
      markiere: function (antrag) {
        var kachel = this.$el.querySelector('.kachel[data-antrag="' + antrag + '"]');
        if (!kachel) return;
        kachel.classList.add("erfasst");
        setTimeout(function () { kachel.classList.remove("erfasst"); }, 1500);
      }
    };
  });

  /* Flash-Meldung: im Parlament (body.voll) nach sechs Sekunden ausblenden; × schließt sofort. */
  Alpine.data("meldung", function () {
    return {
      sichtbar: true,
      init: function () {
        var self = this;
        if (document.body.classList.contains("voll")) setTimeout(function () { self.sichtbar = false; }, 6000);
      }
    };
  });
});
