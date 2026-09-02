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
          var ausloeser = (e.detail && e.detail.elt) || (konfig && konfig.elt);
          if (!konfig || !ausloeser || !ausloeser.closest) return;
          if (konfig.verb === "get" && ausloeser.classList.contains("treffer-link")) { self.treffer(); return; }
          if (konfig.verb !== "post") return;
          var quelle = ausloeser.closest(".kachel");
          if (!quelle || !quelle.dataset.antrag) return;
          self.markiere(quelle.dataset.antrag);
        });
      },
      /* Suchtreffer (FB-C4): der Fächer öffnet am Treffer und hebt den Anker 1,5 s gold hervor. */
      treffer: function () {
        var anker = this.$el.querySelector("#feld-favoriten .fknoten.anker");
        if (!anker) return;
        anker.classList.add("treffer");
        setTimeout(function () { anker.classList.remove("treffer"); }, 1500);
      },
      markiere: function (antrag) {
        var kachel = this.$el.querySelector('.kachel[data-antrag="' + antrag + '"]');
        if (!kachel) return;
        kachel.classList.add("erfasst");
        setTimeout(function () { kachel.classList.remove("erfasst"); }, 1500);
      }
    };
  });

  /* Der Favoriten-Fächer (FB-C1–C4, Spec 4): Der Server liefert alle entfaltbaren Äste vorab
     (data-ast, nur der Ruhe-Ast sichtbar); hier wechselt der Zeiger den Ast, der Faden zur
     Wurzel leuchtet gold, und ein Klick zoomt vom Klickpunkt hinein, bevor htmx das Feld tauscht.
     Ohne JavaScript bleibt der Ruhe-Ast stehen und jeder Knoten ist ein gewöhnlicher Link. */
  Alpine.data("faecher", function (standard) {
    return {
      ast: standard || "",
      entfalte: function (slug) { if (slug) this.ast = slug; },
      /* Hinweis: this.$el ist in Alpine das Element, auf dem der Ausdruck läuft (die Pille) —
         die Fadenebene hängt an der Wurzel, darum überall this.$root. */
      hebe: function (slug) {
        var wurzel = this.$root, lauf = slug, runden = 0;
        while (lauf && runden++ < 8) {
          Array.prototype.forEach.call(wurzel.querySelectorAll('.faden[data-bis="' + lauf + '"]'), function (f) { f.classList.add("an"); });
          var knoten = wurzel.querySelector('.fknoten[data-slug="' + lauf + '"]');
          lauf = knoten ? knoten.dataset.eltern : "";
        }
      },
      senke: function () {
        Array.prototype.forEach.call(this.$root.querySelectorAll(".faden.an"), function (f) { f.classList.remove("an"); });
      },
      zoome: function (e) {
        if (reduziert()) return;
        var wurzel = this.$root, ziel = e.currentTarget.closest(".fknoten");
        if (!ziel) return;
        var r = ziel.getBoundingClientRect(), w = wurzel.getBoundingClientRect();
        wurzel.style.transformOrigin = (r.left + r.width / 2 - w.left) + "px " + (r.top + r.height / 2 - w.top) + "px";
        wurzel.classList.add("zoom");
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
