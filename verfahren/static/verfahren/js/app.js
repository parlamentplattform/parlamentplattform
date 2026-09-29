/* ParlamentPlattform — Alpine-Komponenten (FB-P4, Design-Spezifikation 5).
   Alles hier ist Zugabe: ohne JavaScript bleiben Leiste, Menüs, Anstoß und Regler
   als <details>, Links und Formulare vollständig bedienbar. Die Templates tragen
   keine Inline-Handler; sie verweisen nur auf die Namen dieser Komponenten. */
document.addEventListener("alpine:init", function () {
  var reduziert = function () {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  };

  /* Ein Ereignis nur alle n Millisekunden ausführen — für Scroll-Handler, die sonst zu oft feuern. */
  var drossle = function (fn, ms) {
    var zuletzt = 0;
    return function () {
      var jetzt = Date.now();
      if (jetzt - zuletzt < ms) return;
      zuletzt = jetzt;
      fn();
    };
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

  /* Dauer und Verlauf aus den Tokens der Design-Spezifikation (2.4) — für Bewegungen, die
     JavaScript selbst treibt (Web Animations API); CSS-Bewegungen nutzen dieselben Tokens. */
  var token = function (name, sonst) {
    var wert = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return wert || sonst;
  };
  var dauer = function (name) { return parseFloat(token(name, "300")) || 300; };
  var verlauf = function () { return token("--e-out", "ease-out"); };

  /* Die vier Felder in Rasterreihenfolge — Fokus-Modus (Teil 7). */
  var FELDER = ["filter", "favoriten", "wichtig", "region"];

  /* Rechtecke der sichtbaren Fächer-Knoten, Schlüssel data-slug (Geister zählen nicht mit). */
  var knotenLagen = function (fach) {
    var lagen = {};
    Array.prototype.forEach.call(fach.querySelectorAll(".fknoten:not(.geist)"), function (k) {
      if (k.offsetParent === null || !k.dataset.slug) return;
      var r = k.getBoundingClientRect();
      lagen[k.dataset.slug] = {
        el: k, x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height,
        eltern: k.dataset.eltern || "", klasse: k.className,
        text: (k.querySelector(".fname, a:not(.mehr)") || k).textContent.trim()
      };
    });
    return lagen;
  };

  /* Rückmeldung in der Kachel (FB-A2): Nach einer Handlung tauscht htmx das Feld; die neue
     Kachel desselben Antrags zeigt 1,5 s den Gold-Haken „Erfasst“ statt einer Flash-Meldung.
     Der Auslöser kennt seinen Antrag (data-antrag), darum braucht es keinen Server-Umweg.
     Beim Tausch ginge der Fokus verloren — darum merkt sich die Komponente vor jeder Anfrage die
     id des fokussierten Elements (Knöpfe und Chips tragen stabile ids) und setzt ihn danach
     auf das gleichnamige neue Element.
     Dazu (Teil 7): der Favoriten-Fächer wechselt flüssig (FLIP) und passt ins Feld, der
     Fokus-Modus dehnt ein Feld auf das Raster, Esc stellt das 2×2 wieder her. `fokusServer` ist
     der Zustand aus ?fokus=, den der Server gerendert hat. */
  Alpine.data("parlament", function (fokusServer) {
    return {
      fokusId: null,
      fokus: "",
      vorher: null,  // Knotenlagen des Fächers vor einem Tausch (nur bei Fächer-zu-Fächer)
      init: function () {
        var self = this;
        this.$el.addEventListener("htmx:beforeRequest", function () {
          var aktiv = document.activeElement;
          self.fokusId = aktiv && aktiv.id && self.$el.contains(aktiv) ? aktiv.id : null;
        });
        this.$el.addEventListener("htmx:beforeSwap", function (e) { self.faecherMerken(e); });
        this.$el.addEventListener("htmx:afterSwap", function (e) { self.faecherWechsel(e); });
        var wartet = null;  // Einpassen erst, wenn die Größenänderung zur Ruhe kommt
        window.addEventListener("resize", function () {
          clearTimeout(wartet);
          wartet = setTimeout(function () { self.faecherEinpassen(); }, 80);
        });
        this.fokusStart(fokusServer || "");
        this.faecherEinpassen();
        this.$el.addEventListener("htmx:afterSettle", function (e) {
          var konfig = e.detail && e.detail.requestConfig;
          // e.detail.elt ist das GETAUSCHTE Feld — der Auslöser (Formular, Link) steht in requestConfig
          var ausloeser = (konfig && konfig.elt) || (e.detail && e.detail.elt);
          self.fokusZurueck();
          if (!konfig || !ausloeser || !ausloeser.closest) return;
          if (konfig.verb === "get" && ausloeser.classList.contains("treffer-link")) { self.treffer(); return; }
          if (konfig.verb !== "post" || !e.detail.successful) return;
          // Auch eine gescheiterte Handlung endet mit 200 (Redirect samt Fehlerhinweis) — dann kein Haken
          var feld = e.detail.elt;
          if (feld && feld.querySelector && feld.querySelector(".feld-hinweis.fehler")) return;
          var quelle = ausloeser.closest(".kachel, .fz");
          if (!quelle || !quelle.dataset.antrag) return;
          self.markiere(quelle.dataset.antrag, e.detail.elt);
        });
      },
      fokusZurueck: function () {
        if (!this.fokusId) return;
        var ziel = document.getElementById(this.fokusId);
        this.fokusId = null;
        if (!ziel) return;
        // Liegt das Ziel nach dem Tausch verborgen (Stimmknöpfe im geschlossenen <details> der
        // Feed-Zeile), nimmt es keinen Fokus: dann der Kopf desselben <details>, sonst der Feldkörper
        var klappe = ziel.closest("details"), feld = ziel.closest(".feld");
        var wahl = [ziel, klappe && klappe.querySelector("summary"), feld && feld.querySelector(".feld-korpus")];
        for (var i = 0; i < wahl.length; i++) {
          if (!wahl[i] || !wahl[i].focus) continue;
          wahl[i].focus({ preventScroll: true });
          if (document.activeElement === wahl[i]) return;
        }
      },
      /* Suchtreffer (FB-C4): der Fächer öffnet am Treffer und hebt den Anker 1,5 s gold hervor. */
      treffer: function () {
        var anker = this.$el.querySelector("#feld-favoriten .fknoten.anker");
        if (!anker) return;
        anker.classList.add("treffer");
        setTimeout(function () { anker.classList.remove("treffer"); }, 1500);
      },
      /* Der Haken erscheint in der neuen Kachel desselben Antrags — zuerst im getauschten Feld
         gesucht (derselbe Antrag kann in zwei Feldern stehen), sonst im ganzen Parlament. Das
         role=status-Element bekommt seinen Text neu gesetzt, damit Screenreader ihn ansagen. */
      markiere: function (antrag, feld) {
        var wahl = '.kachel[data-antrag="' + antrag + '"], .fz[data-antrag="' + antrag + '"]';
        var kachel = (feld && feld.querySelector && feld.querySelector(wahl)) || this.$el.querySelector(wahl);
        if (!kachel) return;
        var status = kachel.querySelector(".k-erfasst");
        if (status) {
          var text = status.textContent;
          status.textContent = "";
          setTimeout(function () { status.textContent = text; }, 30);
        }
        kachel.classList.add("erfasst");
        setTimeout(function () { kachel.classList.remove("erfasst"); }, 1500);
      },

      /* ── Der Fächer passt ins Feld (Teil 7, Einpassen) ──
         Ist der Fächer höher als der Feldkörper, wird er mit der CSS-Eigenschaft `zoom` verkleinert
         (layoutwirksam: Prozentlagen und Fäden bleiben stimmig, kein Leerraum), nie unter 0,72,
         damit die Schrift lesbar bleibt. Ohne JavaScript oder ohne `zoom` rollt der Körper wie
         bisher von unten (column-reverse, Anker zuerst sichtbar). Liefert den gesetzten Faktor. */
      faecherEinpassen: function () {
        var fach = this.$el.querySelector("#feld-favoriten .faecher");
        if (!fach || !(window.CSS && CSS.supports && CSS.supports("zoom", "0.9"))) return 1;
        var korpus = fach.closest(".faecher-korpus");
        if (!korpus) return 1;
        fach.style.zoom = "";
        var hoehe = fach.offsetHeight, platz = korpus.clientHeight;
        if (!hoehe || !platz || hoehe <= platz) return 1;
        var faktor = Math.max(0.72, Math.round(1000 * platz / hoehe) / 1000);
        fach.style.zoom = String(faktor);
        return faktor;
      },
      /* ── Flüssiger Wechsel (Teil 7, FLIP) ──
         Vor dem Tausch von #feld-favoriten: die Lage jedes sichtbaren Knotens merken — nur, wenn
         ein Fächer-Link oder die Brotkrume ausgelöst hat (Suche und „Zurück“ laufen mit View
         Transition, dort greift FLIP nicht). */
      faecherMerken: function (e) {
        var d = e.detail || {};
        this.vorher = null;
        if (!d.target || d.target.id !== "feld-favoriten" || !d.shouldSwap) return;
        var ausloeser = d.requestConfig && d.requestConfig.elt;
        var fach = d.target.querySelector(".faecher");
        if (!fach || !ausloeser || !ausloeser.closest || !ausloeser.closest(".faecher, .brot")) return;
        this.vorher = knotenLagen(fach);
      },
      /* Nach dem Tausch: einpassen, dann gleiten gemeinsame Knoten von der alten an die neue
         Stelle (Lage und Größe — die Ebenen wechseln 24/22/20/18/16 px), neue Knoten fächern
         vom Elternknoten her auf, verschwundene blenden als Geister kurz aus, die Fäden blenden
         ein. Gerichtet: der geklickte Knoten wird der Anker, seine Kinder öffnen sich darüber.
         Reduzierte Bewegung: sofortiger Tausch, keine Animation. */
      faecherWechsel: function (e) {
        var d = e.detail || {};
        if (!d.target || d.target.id !== "feld-favoriten") return;
        var feld = document.getElementById("feld-favoriten");
        var fach = feld && feld.querySelector(".faecher");
        var alt = this.vorher;
        this.vorher = null;
        if (!fach) return;
        var lang = dauer("--d-slide"), kurz = dauer("--d-base"), weich = verlauf();
        if (alt) {
          // Keine zweite Eingangsbewegung von Feld und Fächer (CSS auftauchen/hineingleiten). Das Feld trägt
          // eine id, und htmx stellt dessen Attribute nach dem Settle (20 ms) wieder her — darum steht die
          // Marke am Raster, nicht am Feld, und fällt nach der Bewegung wieder ab.
          fach.classList.add("getauscht");
          var raster = this.$el;
          raster.classList.add("faecher-tausch");
          setTimeout(function () { raster.classList.remove("faecher-tausch"); }, lang + 50);
        }
        var faktor = this.faecherEinpassen();
        if (!alt || reduziert() || !fach.animate) return;
        var neu = knotenLagen(fach);
        var fr = fach.getBoundingClientRect();
        var ruhe = "translate(-50%,-50%)";
        Object.keys(neu).forEach(function (slug) {
          var n = neu[slug], a = alt[slug];
          if (a) {
            var dx = (a.x - n.x) / faktor, dy = (a.y - n.y) / faktor;
            var sx = n.w ? a.w / n.w : 1, sy = n.h ? a.h / n.h : 1;
            if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && Math.abs(sx - 1) < 0.01 && Math.abs(sy - 1) < 0.01) return;
            var lauf = n.el.animate(
              [{ transform: ruhe + " translate(" + dx + "px," + dy + "px) scale(" + sx + "," + sy + ")" }, { transform: ruhe }],
              { duration: lang, easing: weich, fill: "none" }
            );
            lauf.id = "faecher-flip";
            return;
          }
          // neu: vom Elternknoten her (alte Lage, sonst neue) — oder, ohne Eltern, an Ort und Stelle
          var eltern = alt[n.eltern] || neu[n.eltern];
          var ex = eltern ? (eltern.x - n.x) / faktor : 0, ey = eltern ? (eltern.y - n.y) / faktor : 0;
          var auf = n.el.animate(
            [{ opacity: 0, transform: ruhe + " translate(" + ex + "px," + ey + "px) scale(.85)" }, { opacity: 1, transform: ruhe }],
            { duration: lang, easing: weich, fill: "none" }
          );
          auf.id = "faecher-flip";
        });
        Object.keys(alt).forEach(function (slug) {
          if (neu[slug]) return;
          var a = alt[slug];
          var geist = document.createElement("span");
          geist.className = a.klasse.replace(/\b(anker|treffer|htmx-request)\b/g, "") + " geist";
          geist.setAttribute("aria-hidden", "true");
          geist.style.left = (a.x - fr.left) / faktor + "px";  // berechnete Lage — wie die Pillen selbst
          geist.style.top = (a.y - fr.top) / faktor + "px";
          geist.style.maxWidth = a.w / faktor + "px";
          var name = document.createElement("span");
          name.className = "fname";
          name.textContent = a.text;
          geist.appendChild(name);
          fach.appendChild(geist);
          var weg = geist.animate(
            [{ opacity: 1, transform: ruhe }, { opacity: 0, transform: ruhe + " scale(.9)" }],
            { duration: kurz, easing: weich, fill: "forwards" }
          );
          weg.id = "faecher-flip";
          var entfernen = function () { if (geist.parentNode) geist.parentNode.removeChild(geist); };
          weg.onfinish = entfernen;
          weg.oncancel = entfernen;
          setTimeout(entfernen, kurz + 100);
        });
        var faeden = fach.querySelector("svg.faeden");
        if (faeden) {
          var ein = faeden.animate([{ opacity: 0 }, { opacity: 1 }], { duration: lang, easing: weich, fill: "none" });
          ein.id = "faecher-flip";
        }
      },

      /* ── Fokus-Modus (Teil 7): ein Feld auf dem ganzen Raster ──
         Zustand: ?fokus= vom Server hat Vorrang, sonst sessionStorage; am Handy nie (jedes Feld
         ist dort ohnehin ein Bildschirm). */
      schmal: function () { return window.innerWidth < 760; },
      fokusStart: function (server) {
        var wahl = server;
        if (!wahl) { try { wahl = sessionStorage.getItem("ddoe.fokus") || ""; } catch (fehler) { wahl = ""; } }
        if (FELDER.indexOf(wahl) < 0 || this.schmal()) wahl = "";
        this.fokus = wahl;
        this.fokusMerken();
      },
      fokusMerken: function () {
        try {
          if (this.fokus) sessionStorage.setItem("ddoe.fokus", this.fokus); else sessionStorage.removeItem("ddoe.fokus");
        } catch (fehler) { /* Speicher gesperrt — der Zustand gilt für diese Seite */ }
      },
      fokussiere: function (feld) {
        if (this.schmal() || FELDER.indexOf(feld) < 0) return;
        this.fokus = this.fokus === feld ? "" : feld;
        this.fokusMerken();
        var self = this;
        this.$nextTick(function () { self.faecherEinpassen(); });
      },
      alleFelder: function () {
        if (!this.fokus) return;
        this.fokus = "";
        this.fokusMerken();
        var self = this;
        this.$nextTick(function () { self.faecherEinpassen(); });
      }
    };
  });

  /* Der Favoriten-Fächer (FB-C1–C4, Spec 4): Der Server liefert alle entfaltbaren Äste vorab
     (data-ast, nur der Ruhe-Ast sichtbar); hier wechselt der Zeiger den Ast und der Faden zur
     Wurzel leuchtet gold. Den Wechsel beim Klick (Gleiten der Knoten, Einpassen ins Feld) macht
     die Komponente „parlament“, weil das Feld samt Fächer von htmx getauscht wird.
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
        this.zoneAusAnker();
        this.spy();
        this.wisch();
      },
      /* Der Anker in der Adresse wählt die Zone: „#zone-chat“ direkt, „#k-12“ oder „#chat-eingabe“
         über die Zone, in der das Ziel liegt — sonst zeigte ein Verweis aus dem Gesprächs-Panel am
         Handy die Zone „Text“, und der gemeinte Beitrag bliebe verborgen. */
      zoneAusAnker: function () {
        var h = window.location.hash;
        if (!h) return;
        if (h.indexOf("#zone-") === 0) { this.zone = h.slice(6); return; }
        var ziel = null;
        try { ziel = document.getElementById(decodeURIComponent(h.slice(1))); } catch (fehler) { ziel = null; }
        var zone = ziel && ziel.closest ? ziel.closest(".zone[id]") : null;
        if (zone) this.zone = zone.id.slice(5);
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
          // Am Seitenanfang liegt der Text noch unter der Leiste. Trotzdem muss
          // nach einem direkten Rücksprung der erste Reiter wieder aktiv sein.
          if (window.scrollY <= 0) { self.zone = zonen[0].id.slice(5); return; }
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

  /* Der Chat eines Antrags (FB-G1, FB-G2): Antwort-Modus, wachsendes Textfeld, Zeichenzähler —
     und das Scroll-Gedächtnis. Die Leiste steht wieder dort, wo man zuletzt aufgehört hat zu
     lesen, auch nach einem Ausflug auf andere Seiten (je Gerät in localStorage; der
     geräteübergreifende Lesestand liegt am Server). Ohne JavaScript bleibt alles bedienbar:
     „Antworten“ ist ein Link mit ?antwort_auf=<pk>, der Server belegt das Zielfeld vor —
     vorgabeId/vorgabeName tragen genau diese Vorbelegung in den Alpine-Zustand, damit ein
     Lesezeichen oder Mittelklick auf den Link das Ziel nicht verliert (Grundregel 3). */
  Alpine.data("chat", function (antragId, vorgabeId, vorgabeName, kritikVorgabe) {
    var schluessel = "ddoe.chat." + antragId;
    return {
      antwortAuf: vorgabeId || null,
      kritik: Boolean(kritikVorgabe),  // Umschalter „Das ist konkrete Kritik am Vorschlag" (FB-G6); nach einem Fehler aus dem Entwurf
      antwortName: vorgabeName || "",
      init: function () {
        this.stelleWiederHer();
        var self = this;
        var merken = drossle(function () { self.merkeStelle(); }, 2000);
        window.addEventListener("scroll", merken, { passive: true });
        window.addEventListener("pagehide", function () { self.merkeStelle(); });
        // Nach dem Lesen den Lesestand vorrücken — die „neu"-Linie hat ihren Dienst getan
        if (this.$el.querySelector(".neulinie")) setTimeout(function () { self.gelesen(); }, 4000);
      },
      antworten: function (id, name) {
        this.antwortAuf = id;
        this.antwortName = name;
        if (this.$refs.feld) this.$refs.feld.focus();
      },
      abbrechen: function () { this.antwortAuf = null; this.antwortName = ""; },
      /* Nach dem Senden: Die ganze Zone samt Formular ist getauscht — ein Fehler bringt den
         Entwurf mit (.chat-fehler), ein Erfolg ein leeres Formular. Nur dann wird die
         Vorbelegung aus der Adresse entfernt (ein Neuladen soll nicht wieder im Antwort-Modus
         landen) und der Fokus ins neue Textfeld gesetzt. Nichts wird hier geleert. */
      gesendet: function (e) {
        if (!e || !e.detail || !e.detail.successful) return;
        if (document.querySelector("#chat-faden .chat-fehler")) return;
        if (/[?&]antwort_auf=/.test(window.location.search) && window.history.replaceState) {
          window.history.replaceState(null, "", window.location.pathname + window.location.hash);
        }
        var feld = document.querySelector("#chat-faden textarea[name=text]");
        if (feld) feld.focus({ preventScroll: true });
      },
      wachsen: function () {
        var f = this.$refs.feld;
        if (!f) return;
        f.style.height = "auto";
        f.style.height = Math.min(f.scrollHeight, 9 * 16) + "px";
      },
      rest: function () {
        var f = this.$refs.feld;
        return f ? 4000 - f.value.length : 4000;
      },
      /* Welcher Beitrag steht gerade im Blick — den merken wir uns, nicht die Pixelzahl:
         Beiträge kommen dazu, Pixel verschieben sich, ein Beitrag bleibt derselbe.
         Gesucht ist der erste, der wirklich im Fenster steht — nicht einer, der oben schon
         herausgescrollt ist oder unten gerade erst anklopft. */
      merkeStelle: function () {
        var hoehe = window.innerHeight;
        var treffer = null;
        Array.prototype.some.call(this.$el.querySelectorAll(".blase[data-beitrag]"), function (b) {
          var r = b.getBoundingClientRect();
          if (r.bottom > 40 && r.top < hoehe - 40) { treffer = { id: b.dataset.beitrag, top: r.top }; return true; }
          return false;
        });
        if (!treffer) return;
        try {
          localStorage.setItem(schluessel, JSON.stringify({ beitrag: treffer.id, versatz: Math.round(treffer.top), zeit: Date.now() }));
        } catch (fehler) { /* Speicher gesperrt — dann eben ohne Gedächtnis */ }
      },
      stelleWiederHer: function () {
        var stand = null;
        try { stand = JSON.parse(localStorage.getItem(schluessel) || "null"); } catch (fehler) { stand = null; }
        if (!stand || !stand.beitrag) return;
        if (window.location.hash) return;  // ein Anker im Link hat Vorrang
        var self = this;
        var eigenhaendig = false;  // sobald jemand selbst scrollt, halten wir die Finger still
        ["wheel", "touchstart", "keydown"].forEach(function (art) {
          window.addEventListener(art, function () { eigenhaendig = true; }, { once: true, passive: true });
        });
        /* Die Seite wächst nach dem ersten Frame noch (Fächer, eingeblendete Bereiche, Schriften).
           Darum wird die Stelle mehrfach nachgezogen, bis das Layout steht. */
        var setzen = function () {
          if (eigenhaendig) return;
          var ziel = self.$el.querySelector('.blase[data-beitrag="' + stand.beitrag + '"]');
          if (!ziel) return;  // archiviert oder entfernt: dann eben von vorn
          var weg = ziel.getBoundingClientRect().top - (stand.versatz || 0);
          if (Math.abs(weg) < 2) return;
          window.scrollTo({ top: window.scrollY + weg, behavior: "auto" });
        };
        requestAnimationFrame(function () { requestAnimationFrame(setzen); });
        window.addEventListener("load", setzen);
        setTimeout(setzen, 250);
      },
      gelesen: function () {
        var form = this.$el.querySelector("form[action*='/kommentieren/']");
        var wert = form ? form.querySelector("[name=csrfmiddlewaretoken]") : null;
        if (!wert) return;
        fetch("/antrag/" + antragId + "/chat/gelesen/", {
          method: "POST",
          headers: { "X-CSRFToken": wert.value, "HX-Request": "true" },
          body: new URLSearchParams(),
        }).catch(function () { /* nicht schlimm: der Stand rückt beim nächsten Mal nach */ });
      }
    };
  });

  /* Das Gesprächs-Panel (FB-G3): Griff links, Panel gleitet herein, Escape und Schleier schließen,
     der Fokus bleibt drin. Ohne JavaScript ist der Griff ein Link auf /gespraeche/. */
  Alpine.data("gespraechspanel", function () {
    return {
      offen: false,
      nurUngelesen: false,
      ausloeser: null,
      auf: function (e) {
        if (e) { e.preventDefault(); this.ausloeser = e.currentTarget; }
        this.offen = true;
        var self = this;
        this.$nextTick(function () {
          var erster = self.$el.querySelector(".g-panel button, .g-panel a");
          if (erster) erster.focus();
        });
      },
      zu: function () {
        if (!this.offen) return;
        this.offen = false;
        if (this.ausloeser) this.ausloeser.focus();
      },
      wechsle: function (e, ungelesen) {
        if (e) e.preventDefault();  // htmx holt die Liste, die Seite bleibt stehen
        this.nurUngelesen = ungelesen;
      },
      falle: function (e) {
        if (e.key !== "Tab") return;
        var ziele = Array.prototype.filter.call(
          this.$el.querySelectorAll(".g-panel a, .g-panel button"),
          function (z) { return z.offsetParent !== null; }
        );
        if (!ziele.length) return;
        var erstes = ziele[0], letztes = ziele[ziele.length - 1];
        if (e.shiftKey && document.activeElement === erstes) { e.preventDefault(); letztes.focus(); }
        else if (!e.shiftKey && document.activeElement === letztes) { e.preventDefault(); erstes.focus(); }
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
