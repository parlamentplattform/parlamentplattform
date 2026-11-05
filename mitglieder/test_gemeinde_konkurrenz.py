"""Ein Bestätigungslink darf auch unter parallelen echten Verbindungen nur einmal tragen."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection, connections

from mitglieder.auth_flows import EinmalToken
from mitglieder.models import Mitglied


@pytest.mark.django_db(transaction=True)
def test_nur_eine_parallele_einloesung_des_gemeindetokens():
    if connection.vendor != "postgresql":
        pytest.skip("Parallele Schreibverbindungen werden gegen PostgreSQL geprüft.")
    m = Mitglied.objects.create_user("parallel@example.org", parteikonto=False, is_active=False)
    token = EinmalToken.ausstellen(m, EinmalToken.Zweck.GEMEINDE)
    start = Barrier(2)

    def einloesen():
        try:
            start.wait(timeout=10)
            konto = EinmalToken.einloesen(token, EinmalToken.Zweck.GEMEINDE)
            return konto.pk if konto else None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ergebnisse = list(pool.map(lambda _: einloesen(), range(2)))
    assert ergebnisse.count(m.pk) == 1 and ergebnisse.count(None) == 1
    assert EinmalToken.objects.get().verbraucht_am is not None
