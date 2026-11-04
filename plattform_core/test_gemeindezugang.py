from datetime import date

import pytest

from plattform_core.gemeindezugang import mindestens_sechzehn


@pytest.mark.parametrize("geburt,heute,zulaessig", [
    (date(2010, 11, 4), date(2026, 11, 4), True),
    (date(2010, 11, 5), date(2026, 11, 4), False),
    (date(2010, 1, 1), date(2026, 1, 1), True),
    (date(2012, 2, 29), date(2028, 2, 28), False),
    (date(2012, 2, 29), date(2028, 2, 29), True),
    (date(2030, 1, 1), date(2026, 11, 4), False),
])
def test_vollendetes_alter(geburt, heute, zulaessig):
    assert mindestens_sechzehn(geburt, heute) is zulaessig
