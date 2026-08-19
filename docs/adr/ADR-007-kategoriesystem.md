# ADR-007: Kategoriesystem der Lebensbereiche und KI-Zuordnung

Status: angenommen · Datum: 2026-08-19 · Bezug: F-45, F-46, F-47, § 5 Abs 10

## Problem

Bei 6,2 Millionen Wahlberechtigten können an einem Tag tausende Anträge
eingebracht werden. Menschen können diese Menge weder sichten noch vergleichen.
Gebraucht wird ein Ordnungssystem, das **jeden Lebensbereich** abdeckt, das
Mitglieder abonnieren können (Bereich a des Hauptfensters), das eine KI
zuverlässig zuordnen kann — und das sich ständig weiterentwickelt, ohne
bestehende Zuordnungen zu zerstören.

## Geprüfte Alternativen

**EuroVoc** (Thesaurus des EU-Amts für Veröffentlichungen): 21 Domänen,
127 Mikrothesauri, rund 7.400 Deskriptoren, in allen EU-Amtssprachen inklusive
Deutsch gepflegt, maschinenlesbar (SKOS/RDF), laufend aktualisiert, frei
nachnutzbar, und **genau für die Verschlagwortung von Parlaments- und
Rechtsdokumenten gebaut** — EUR-Lex und viele nationale Parlamente
verschlagworten damit. Schwäche: 7.400 Begriffe sind keine Bürger-Navigation,
und die Domänenschnitte („66 Energie" neben „52 Umwelt") sind Verwaltungs-,
nicht Lebenslogik.

**COFOG** (UN/OECD-Klassifikation der Staatstätigkeit, 10 Abteilungen):
budgetorientiert, gut für die spätere StaatsSimulation (Kostenwirkung je
Staatsfunktion), aber zu grob und zu staatszentriert als Bürger-Taxonomie.

**Bibliotheks-Systematiken** (Dewey, GND): decken „alles Wissen", aber nicht
politikförmig; keine Behörden-Anschlussfähigkeit.

**Themenfilter des österreichischen Parlaments** (parlament.gv.at): bürgernah,
aber weder versioniert noch maschinenlesbar dokumentiert noch lizenzklar.

## Entscheidung: ein Baum mit zwei Quellen

**Der DDÖ-Kategorienbaum** (`policies/kategorien-v1.yaml`): 24 bürgernahe
Hauptkategorien (Lebensbereiche) von „Wohnen & Bauen" bis „Tiere & Tierschutz",
darunter rund 100 Unter- und Detailkategorien — z. B.
Wirtschaft & Unternehmen › Bauwirtschaft › Installateur. Mitglieder abonnieren
beliebige Knoten; ein Abo gilt für den ganzen Ast. Regeln:

- **Vollständigkeit statt Restablage:** Es gibt bewusst kein „Sonstiges".
  Passt ein Antrag nirgends, ist das ein Änderungsantrag an das
  Kategoriesystem — so entwickelt es sich weiter (Wunsch: „ständig verbessern").
- **Stabile Slugs, Versionierung:** Jede Änderung ist eine neue Datei-Version
  im Repository samt CHANGELOG. Entfallene Bereiche werden deaktiviert, nie
  gelöscht — historische Zuordnungen bleiben nachvollziehbar.
- **Mehrfachzuordnung:** Ein Antrag kann mehreren Bereichen angehören
  (eine PV-Anlage am Gemeindedach ist Energie UND Gemeinde UND Klima).

**Ebene 2 — EuroVoc als Rückgrat:** Jeder Lebensbereich nennt seine
EuroVoc-Domänen. Damit sind vorbereitet: Feinverschlagwortung mit ~7.400
gepflegten Begriffen, Mehrsprachigkeit (internationale Partnerschaften!) und
vor allem der **Anschluss an RIS/EUR-Lex für die Folgenabschätzung** (ADR-006
Stufe 3): Gesetze sind dort bereits EuroVoc-verschlagwortet — die
StaatsSimulation kann Anträge und bestehende Normen im selben Begriffsraum
vergleichen. COFOG wird später zusätzlich gemappt (Budgetwirkung).

## KI-Zuordnung (F-47) — dieselbe Regel wie immer

1. **Stufe 1 (umgesetzt):** Niemand kreuzt Kategorien an — die Plattform
   ordnet jeden Antrag beim Einbringen selbst in den Baum ein
   (`plattform_core/klassifikation.py`): gepflegte Schlagwortlisten je Knoten,
   Wortanfangs- und Wortfolgen-Treffer, die tiefste passende Ebene gewinnt,
   Vorfahren werden nicht doppelt vergeben. Deterministisch, mit Papier
   nachrechenbar, jede Zuordnung wird im Audit-Log protokolliert.
2. **Stufe 2 (nächster Schritt):** Ein **lokal betriebenes, mehrsprachiges
   Embedding-Modell** (z. B. multilingual-e5 / Sentence-Transformers, läuft auf
   CPU im selben Container) vergleicht den Antragstext mit den
   Bereichsbeschreibungen und **schlägt Kategorien vor**; dasselbe Modell
   verbessert den Ähnlichkeitshinweis (ADR-006 Stufe 2). Kein Text verlässt
   die Plattform, kein Anbieter „greift Daten ab", keine laufenden API-Kosten —
   bei tausenden Anträgen pro Tag rechnet ein CPU-Embedding in Millisekunden.
3. **Externe KI nur als bewusste Ausnahme:** Reicht die lokale Qualität nicht,
   kommt ein EU-Anbieter mit vertraglichem Trainingsverbot in Frage
   (z. B. Mistral, Paris); der Schlüssel läge als Umgebungsvariable
   (`DDOE_KI_SCHLUESSEL`) im Deployment, niemals im Code. Zu senden wären
   ausschließlich die ohnehin öffentlichen Antragstexte — nie Mitgliederdaten.
4. **Der Mensch behält das letzte Wort:** Der Vorschlag der KI ist änderbar;
   die Antragstellerin bestätigt. Korrekturen durch den Integritätsrat werden
   wie alles protokolliert. Kein Algorithmus entscheidet über Zulassung oder
   Einordnung mit Bindungswirkung (§ 2 Abs 6).

## Für die StaatsSimulation (Ausblick)

Die eigene StaatsSimulations-KI (Aufbau parteibegleitend, § 6 Abs 4) bekommt
durch dieses System ihre Eingangsgröße: Antrag → Lebensbereiche → EuroVoc-
Deskriptoren → betroffene Normen (RIS/EUR-Lex) → betroffene Branchen und
Lebensbereiche. Jede Ausgabe ist als Modellrechnung mit Annahmen gekennzeichnet
und bindet keine Abstimmung.
