from datetime import date
from typing import List, Optional, Tuple

class CaseData:
    """
    Data class representing all the inputs required for
    statute of limitations calculation for a criminal case.
    """
    def __init__(
        self,
        ceza_turu: str,
        fail_yasi: int,
        suc_tarihi: date,
        bugun: date,
        zamanasimi_durdu_mu: bool = False,
        suspension_periods: List[Tuple[date, date]] = None,
        kesilme_tarihleri: List[date] = None
    ):
        """
        Initialize a CaseData instance.

        Args:
            ceza_turu: Type of penalty
            fail_yasi: Age of perpetrator at the time of crime
            suc_tarihi: Date of crime
            bugun: Current date
            zamanasimi_durdu_mu: Whether limitation period was suspended
            suspension_periods: List of tuples with (start_date, end_date) for all suspension periods
            kesilme_tarihleri: List of dates when limitation was interrupted
        """
        self.ceza_turu = ceza_turu
        self.fail_yasi = fail_yasi
        self.suc_tarihi = suc_tarihi
        self.bugun = bugun
        self.zamanasimi_durdu_mu = zamanasimi_durdu_mu
        self.suspension_periods = suspension_periods or []
        self.kesilme_tarihleri = kesilme_tarihleri or []
