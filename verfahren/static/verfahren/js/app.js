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
          var quelle = ausloeser.closest(".kachel, .fz");
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
        var kachel = this.$el.querySelector('.kachel[data-antrag="' + antrag + '"], .fz[data-antrag="' + antrag + '"]');
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

  /* „Mehr vorhanden" (FB-A5): auf der <section class="feld">. Sobald der Feldkörper mehr enthält
     als sichtbar, erscheint unten die Pille „↓ n weitere" (n = Kacheln, Zeilen oder Bänder unter
     der Sichtkante) über einem weichen Verlauf; Klick rollt eine Feldhöhe weiter. Neu gerechnet
     beim Rollen, bei Größenänderung und nach jedem htmx-Tausch (die Komponente entsteht dann neu). */
  Alpine.data("feldmehr", function () {
    return {
      rest: 0,
      sichtbar: false,
      init: function () {
        var self = this, korpus = this.$el.querySelector(".feld-korpus");
        if (!korpus) return;
        var rechne = function () {
          var kante = korpus.scrollTop + korpus.clientHeight;
          self.sichtbar = korpus.scrollHeight - kante > 12;
          self.rest = Array.prototype.filter.call(
            korpus.querySelectorAll(".kacheln > .kachel, .zeile, .fz, .rband"),
            function (k) { return k.offsetTop + 8 >= kante; }
          ).length;
        };
        korpus.addEventListener("scroll", rechne, { passive: true });
        window.addEventListener("resize", rechne);
        if ("ResizeObserver" in window) new ResizeObserver(rechne).observe(korpus);
        setTimeout(rechne, 0);
      },
      weiter: function () {
        var korpus = this.$root.querySelector(".feld-korpus");
        if (korpus) korpus.scrollBy({ top: korpus.clientHeight - 24, behavior: reduziert() ? "auto" : "smooth" });
      }
    };
  });

  /* Regionsband (FB-E1): eine waagrecht wischbare Spur mit drei sichtbaren Kacheln; rechts die
     Pille „› n weitere" für die Kacheln hinter der Kante. */
  Alpine.data("spur", function () {
    return {
      rest: 0,
      init: function () {
        var self = this, spur = this.$refs.spur;
        if (!spur) return;
        var rechne = function () {
          var kante = spur.scrollLeft + spur.clientWidth;
          self.rest = Array.prototype.filter.call(spur.children, function (k) { return k.offsetLeft + 8 >= kante; }).length;
        };
        spur.addEventListener("scroll", rechne, { passive: true });
        window.addEventListener("resize", rechne);
        setTimeout(rechne, 0);
      },
      weiter: function () {
        var spur = this.$refs.spur;
        if (spur) spur.scrollBy({ left: spur.clientWidth, behavior: reduziert() ? "auto" : "smooth" });
      }
    };
  });

  /* WeicherFilter (FB-B4/B5): Profil-Leiste ein- und ausfahren (je Gerät gemerkt), Zustand
     „● Ungespeichert“ (Regler weichen vom gespeicherten Stand ab), Zurücksetzen, Overlay öffnen
     und schließen mit Fokusrückgabe. Die Live-Vorschau selbst macht htmx (hx-trigger am Formular);
     ohne JavaScript bleibt die Leiste ausgefahren und das Overlay ein natives <details>. */
  Alpine.data("weicherfilter", function (gespeichert) {
    gespeichert = gespeichert || {};
    return {
      offen: true,
      geaendert: false,
      init: function () {
        try { this.offen = localStorage.getItem("ddoe.filterleiste") !== "zu"; } catch (fehler) { this.offen = true; }
        var self = this;
        this.$el.addEventListener("input", function (e) {
          var ziel = e.target;
          if (ziel && (ziel.type === "range" || ziel.type === "checkbox")) self.pruefe();
        });
      },
      leiste: function (auf) {
        this.offen = auf === undefined ? !this.offen : auf;
        try { localStorage.setItem("ddoe.filterleiste", this.offen ? "auf" : "zu"); } catch (fehler) { /* Speicher gesperrt */ }
      },
      pruefe: function () {
        var anders = false;
        Array.prototype.forEach.call(this.$root.querySelectorAll(".regler-feld input[type=range]"), function (r) {
          if (Number(r.value) !== Number(gespeichert[r.dataset.regler] || 0)) anders = true;
        });
        var schalter = this.$root.querySelector('.regler-feld input[name="favoriten_zuerst"]');
        if (schalter && Boolean(gespeichert.favoriten_zuerst) !== schalter.checked) anders = true;
        this.geaendert = anders;
      },
      zuruecksetzen: function () {
        Array.prototype.forEach.call(this.$root.querySelectorAll(".regler-feld input[type=range]"), function (r) {
          r.value = 0;
          r.dispatchEvent(new Event("input", { bubbles: true }));
        });
      },
      klappe: function () { return this.$root.querySelector(".regler-klappe"); },
      oeffne: function () {
        var k = this.klappe();
        if (!k) return;
        // erst nach dem laufenden Klick öffnen — sonst schließt der Außenklick-Wächter des Menüs sofort wieder
        setTimeout(function () {
          k.open = true;
          var kopf = k.querySelector(".regler-kopf b");
          if (kopf) kopf.focus();
        }, 0);
      },
      schliesse: function () {
        var k = this.klappe();
        if (!k || !k.open) return;
        k.open = false;
        var ausloeser = k.querySelector("summary");
        if (ausloeser) ausloeser.focus();
      }
    };
  });

  /* Die drei Zonen der Antragsseite (FB-F1). Breit (≥ 1100 px): alle Zonen stehen nebeneinander,
     die Reiter springen hin und die Leiste zeigt beim Scrollen die aktuelle Zone (Scroll-Spy).
     Schmal: nur eine Zone ist sichtbar, die Reiter schalten um, Wischen wechselt weiter.
     Ohne JavaScript stehen alle Zonen untereinander und die Reiter sind Ankerlinks. */
  Alpine.data("zonen", function () {
    return {
      zone: "text",
      breit: true,
      init: function () {
        var self = this;
        var messen = function () { self.breit = window.innerWidth >= 1100; };
        messen();
        window.addEventListener("resize", messen);
        if (window.location.hash.indexOf("#zone-") === 0) this.zone = window.location.hash.slice(6);
        this.spy();
        this.wisch();
      },
      namen: function () {
        return Array.prototype.map.call(this.$el.querySelectorAll(".zonenleiste .zreiter"), function (r) {
          return r.getAttribute("href").slice(6);
        });
      },
      waehle: function (name, e) {
        this.zone = name;
        if (!this.breit) {
          if (e) e.preventDefault();  // schmal: umschalten statt springen
          window.scrollTo({ top: 0, behavior: reduziert() ? "auto" : "smooth" });
        }
      },
      /* Breit: der aktive Reiter folgt dem Scrollen — es gewinnt die Zone, deren Oberkante der
         Unterkante der klebenden Leiste am nächsten ist, ohne sie schon verlassen zu haben. */
      spy: function () {
        var self = this;
        var pruefe = function () {
          if (!self.breit) return;
          var leiste = self.$el.querySelector(".zonenleiste");
          var kante = leiste ? leiste.getBoundingClientRect().bottom : 0;
          // Die klebende Einschätzung steht immer oben — sie scrollt nicht vorbei und zählt nicht mit
          var zonen = Array.prototype.filter.call(self.$el.querySelectorAll(".zone[id]"), function (z) {
            return getComputedStyle(z).position !== "sticky";
          });
          if (!zonen.length) return;
          // Am Seitenende gewinnt die letzte Zone — sonst erreicht sie die Oberkante nie
          var ende = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
          if (ende) { self.zone = zonen[zonen.length - 1].id.slice(5); return; }
          var beste = null, bester = -Infinity;
          zonen.forEach(function (z) {
            var oben = z.getBoundingClientRect().top - kante;
            if (oben <= 1 && oben > bester) { bester = oben; beste = z; }
          });
          if (beste) self.zone = beste.id.slice(5);
        };
        window.addEventListener("scroll", pruefe, { passive: true });
        setTimeout(pruefe, 0);
      },
      /* Schmal: waagrechtes Wischen wechselt zur Nachbarzone (gerichtet, wie Blättern). */
      wisch: function () {
        var self = this, start = null;
        this.$el.addEventListener("touchstart", function (e) {
          start = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : null;
        }, { passive: true });
        this.$el.addEventListener("touchend", function (e) {
          if (!start || self.breit) return;
          var dx = e.changedTouches[0].clientX - start.x;
          var dy = e.changedTouches[0].clientY - start.y;
          start = null;
          if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
          var namen = self.namen(), i = namen.indexOf(self.zone) + (dx < 0 ? 1 : -1);
          if (i >= 0 && i < namen.length) self.zone = namen[i];
        }, { passive: true });
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
