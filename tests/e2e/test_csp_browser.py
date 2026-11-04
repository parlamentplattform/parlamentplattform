"""CSP lässt eigene Werkzeuge arbeiten und sperrt fremde Browseraktionen."""

import pytest
from playwright.sync_api import expect

from config.sicherheitsheader import RICHTLINIE
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False),
    ("handy-dunkel", {"width": 390, "height": 844}, True, True),
])
def test_eigene_bedienung_und_gesperrte_aktionen(
    seite, live_server, sichtpruefung, kennung, viewport, js, dunkel,
):
    mitglied = mitglied_anlegen("csp-browser")
    mitglied.pseudonym_oeffentlich = "CSP Prüfung"
    mitglied.klarname_oeffentlich = False
    mitglied.ist_admin = True
    mitglied.save()
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True, als=mitglied)
    fehler = []
    p.on("pageerror", lambda e: fehler.append(str(e)))
    if js:
        p.add_init_script("window.cspBefunde=[]; document.addEventListener('securitypolicyviolation', e=>window.cspBefunde.push({directive:e.effectiveDirective,uri:e.blockedURI}));")

    # Echte Header des Servers, keine testseitig ergänzte Politik.
    for pfad in ("/parlament/", "/verwaltung/parameter/", "/verwaltung/", "/profil/"):
        antwort = p.goto(live_server.url + pfad)
        assert antwort.status == 200 and antwort.headers["content-security-policy"] == RICHTLINIE
        if js:
            p.wait_for_function("window.Alpine !== undefined")
            assert p.evaluate("window.cspBefunde") == [], pfad
    assert fehler == []
    ausweis = p.locator("#ausweis")
    expect(ausweis.locator("svg")).to_be_visible()
    with p.expect_download() as laden:
        ausweis.locator('a[href$="ausweis.pdf"]').click()
    assert laden.value.suggested_filename.endswith(".pdf")
    assert laden.value.path().read_bytes().startswith(b"%PDF-")
    daten = p.request.get(live_server.url + "/profil/ausweis.pdf")
    assert daten.status == 200 and "content-security-policy" not in daten.headers

    if js:
        klappe = ".leiste details.menue" if viewport["width"] < 1024 else ".leiste details.konto"
        p.locator(klappe + " > summary").click()
        # Tatsächlich umschalten und für den Bildbeleg die benannte Ansicht wiederherstellen.
        p.locator(klappe).get_by_role("button", name="Hell" if dunkel else "Dunkel", exact=True).click()
        expect(p.locator("html")).to_have_attribute("data-theme", "light" if dunkel else "dark")
        p.locator(klappe).get_by_role("button", name="Dunkel" if dunkel else "Hell", exact=True).click()
        expect(p.locator("html")).to_have_attribute("data-theme", "dark" if dunkel else "light")
        p.keyboard.press("Escape")
        assert p.evaluate("window.cspBefunde") == []
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    ausweis.screenshot(path=str(sichtpruefung / f"csp-ausweis-{kennung}.png"))

    if not js:
        return  # OhneJS nur die tatsächliche Bedienbarkeit prüfen, keinen Skriptblockadebeleg behaupten.

    fremde_anfragen = []

    def fremd(route):
        fremde_anfragen.append(route.request.url)
        route.fulfill(status=200, content_type="text/javascript", body="window.cspFremdLief=true")

    # Sollte die Politik versagen, bleibt auch die Negativprobe lokal abgefangen.
    p.route("https://csp-fremd.invalid/**", fremd)
    p.evaluate("""() => {
        let inline=document.createElement('script');
        inline.textContent='window.cspInlineLief=true'; document.body.append(inline);
        let fremd=document.createElement('script');
        fremd.src='https://csp-fremd.invalid/skript.js'; document.body.append(fremd);
        let knopf=document.createElement('button'); knopf.id='csp-handler-probe';
        knopf.textContent='Lokale Probe'; knopf.setAttribute('onclick','window.cspHandlerLief=true');
        document.body.append(knopf);
    }""")
    p.locator("#csp-handler-probe").click()
    p.wait_for_function("window.cspBefunde.some(x=>x.directive==='script-src-attr') && window.cspBefunde.some(x=>x.uri.startsWith('https://csp-fremd.invalid'))")
    assert not p.evaluate("window.cspInlineLief===true || window.cspFremdLief===true || window.cspHandlerLief===true")

    vorher = p.url
    p.evaluate("""() => {
        let form=document.createElement('form'); form.method='POST';
        form.action='https://csp-fremd.invalid/form'; document.body.append(form); form.submit();
        let objekt=document.createElement('object'); objekt.type='text/html';
        objekt.data='https://csp-fremd.invalid/objekt'; document.body.append(objekt);
        let basis=document.createElement('base'); basis.href='https://csp-fremd.invalid/';
        document.head.append(basis);
    }""")
    p.wait_for_function("['form-action','object-src','base-uri'].every(d=>window.cspBefunde.some(x=>x.directive===d))")
    assert p.url == vorher and p.evaluate("document.baseURI") == vorher
    assert fremde_anfragen == []
