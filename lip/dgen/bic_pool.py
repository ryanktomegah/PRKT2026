"""
bic_pool.py — DGEN: Fictional BIC Pool with Hub-and-Spoke Topology
===================================================================
Generates and manages a pool of 200 fictional but format-valid BICs spanning
30+ countries, organised in a hub-and-spoke topology:

  - 10 hub banks  (major fictional correspondent banks, weight=60% of volume)
  - 190 spoke banks (regional/tier-2 institutions, weight=40% of volume)

BIC format (ISO 9362):
  BBBBCCLL   (8-char) or  BBBBCCLLBBB (11-char)
  BBBB = bank code (4 uppercase letters)
  CC   = ISO 3166-1 alpha-2 country code (2 uppercase letters)
  LL   = location code (2 chars, letters/digits, uppercase)

All BICs are FICTIONAL: they do not correspond to any real institution.
The country codes are real ISO 3166-1 codes used only for corridor derivation.

Usage::

    from lip.dgen.bic_pool import BICPool
    pool = BICPool()
    sender, receiver = pool.sample_bic_pair(rng)
    corridor = pool.get_corridor(sender, receiver)   # e.g. "USD-EUR"
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Country → primary currency mapping (ISO 4217)
# ---------------------------------------------------------------------------

COUNTRY_CURRENCY: dict[str, str] = {
    # North America
    "US": "USD",
    "CA": "CAD",
    "MX": "MXN",
    # Europe — eurozone
    "DE": "EUR",
    "FR": "EUR",
    "NL": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "BE": "EUR",
    "AT": "EUR",
    "FI": "EUR",
    "PT": "EUR",
    "IE": "EUR",
    "LU": "EUR",
    # Europe — non-eurozone
    "GB": "GBP",
    "CH": "CHF",
    "SE": "SEK",
    "DK": "DKK",
    "NO": "NOK",
    "PL": "PLN",
    "CZ": "CZK",
    "HU": "HUF",
    "RO": "RON",
    "TR": "TRY",
    # Asia-Pacific
    "JP": "JPY",
    "CN": "CNY",
    "HK": "HKD",
    "SG": "SGD",
    "IN": "INR",
    "AU": "AUD",
    "NZ": "NZD",
    "KR": "KRW",
    "TH": "THB",
    "MY": "MYR",
    "PH": "PHP",
    "ID": "IDR",
    "PK": "PKR",
    # Middle East / Africa
    "AE": "AED",
    "SA": "SAR",
    "ZA": "ZAR",
    "NG": "NGN",
    "EG": "EGP",
    # Latin America
    "BR": "BRL",
    "AR": "ARS",
    "CL": "CLP",
}


# ---------------------------------------------------------------------------
# Hub BICs — 10 major fictional correspondent banks (8-char format)
# ---------------------------------------------------------------------------
# Each is a globally recognised fictional institution with high transaction weight.
# Prefix chosen to not clash with real-world SWIFT BIC prefixes.

_HUB_BICS: list[str] = [
    "XCAPUS33",  # X Capital Bank, United States (NYC)
    "GLOBDE2X",  # Global Finance Bank, Germany (Frankfurt)
    "PONTFR1P",  # Pont Banque Internationale, France (Paris)
    "BRITGB2L",  # Britain Capital Trust, United Kingdom (London)
    "PACIHK2X",  # Pacific Finance Holdings, Hong Kong
    "ASICSG1X",  # Asia Capital Corp, Singapore
    "ALPICH2A",  # Alpine Investment Bank, Switzerland (Zurich)
    "NORTNL2A",  # Northern European Finance, Netherlands (Amsterdam)
    "FUIJJP2T",  # Fuiji Financial Group, Japan (Tokyo)
    "SINOCN2H",  # Sino Capital Bank, China (Shanghai)
]

# Map hub BICs to country codes (positions 4-5 of BIC string)
_HUB_COUNTRIES: dict[str, str] = {bic: bic[4:6] for bic in _HUB_BICS}


# ---------------------------------------------------------------------------
# Spoke BIC generation — 190 regional/tier-2 institutions
# ---------------------------------------------------------------------------

# 20 fictional 4-char bank code prefixes
_SPOKE_PREFIXES = [
    "FSTB", "NTLB", "CMRB", "REGB", "TRSB", "CNTB", "UNIB", "CORP",
    "CRED", "SAVB", "INTB", "CAPB", "MERC", "AGRI", "INDB", "PRVB",
    "POPB", "COBK", "FINB", "INVB",
]

# Location codes (2 chars each, valid BIC location format)
_LOC_CODES = ["1X", "2X", "1A", "2A", "3X", "1B", "2B", "3A"]

# Countries and how many spoke BICs to allocate per country (total ~190)
_SPOKE_ALLOCATION: list[tuple[str, int]] = [
    # Major financial centres (10 spokes each)
    ("US", 10), ("DE", 10), ("FR", 10), ("GB", 10), ("JP", 10),
    # Secondary financial centres (6 spokes each)
    ("CH", 6), ("NL", 6), ("SG", 6), ("HK", 6), ("CN", 6),
    ("AU", 6), ("CA", 6), ("IN", 6),
    # Tertiary markets (4 spokes each)
    ("ES", 4), ("IT", 4), ("BE", 4), ("AT", 4), ("SE", 4), ("DK", 4),
    ("NO", 4), ("KR", 4), ("TH", 4), ("BR", 4), ("MX", 4),
    # Smaller markets (2 spokes each)
    ("PL", 2), ("CZ", 2), ("FI", 2), ("PT", 2), ("IE", 2),
    ("AE", 2), ("SA", 2), ("ZA", 2), ("TR", 2), ("MY", 2),
    ("HU", 2), ("RO", 2), ("NG", 2), ("NZ", 2), ("PH", 2),
    ("ID", 2), ("LU", 2),
]


def _build_spoke_bics() -> tuple[list[str], dict[str, str]]:
    """Generate up to 190 spoke BICs deterministically.

    Returns (bics_list, bic_to_country_map).
    """
    bics: list[str] = []
    bic_country: dict[str, str] = {}

    for country, count in _SPOKE_ALLOCATION:
        if country not in COUNTRY_CURRENCY:
            continue
        generated = 0
        for prefix in _SPOKE_PREFIXES:
            if generated >= count:
                break
            for loc in _LOC_CODES:
                if generated >= count:
                    break
                bic = f"{prefix}{country}{loc}"
                if bic not in bic_country and bic not in _HUB_COUNTRIES:
                    bics.append(bic)
                    bic_country[bic] = country
                    generated += 1

    return bics, bic_country


_SPOKE_BICS, _SPOKE_COUNTRY_MAP = _build_spoke_bics()


# ---------------------------------------------------------------------------
# BICPool — main class
# ---------------------------------------------------------------------------


class BICPool:
    """Hub-and-spoke BIC pool for synthetic payment generation.

    Attributes
    ----------
    hub_bics : list[str]
        10 hub BICs (major correspondent banks).
    spoke_bics : list[str]
        Up to 190 regional bank BICs.
    all_bics : list[str]
        Combined list (hubs first, then spokes).
    n_hubs : int
    n_spokes : int
    n_total : int
    """

    def __init__(self) -> None:
        self.hub_bics: list[str] = _HUB_BICS[:]
        self.spoke_bics: list[str] = _SPOKE_BICS[:]
        self.all_bics: list[str] = self.hub_bics + self.spoke_bics
        self.n_hubs: int = len(self.hub_bics)
        self.n_spokes: int = len(self.spoke_bics)
        self.n_total: int = len(self.all_bics)

        # Country map: BIC → ISO 3166-1 alpha-2 country code
        self._bic_country: dict[str, str] = {}
        self._bic_country.update(_HUB_COUNTRIES)
        self._bic_country.update(_SPOKE_COUNTRY_MAP)

        # Sampling weights: hubs get 60% of total weight / n_hubs each
        # spokes get 40% of total weight / n_spokes each
        hub_weight_each = 0.60 / self.n_hubs
        spoke_weight_each = 0.40 / self.n_spokes
        self._weights: list[float] = (
            [hub_weight_each] * self.n_hubs
            + [spoke_weight_each] * self.n_spokes
        )
        # Normalise to ensure sum = 1.0 (floating point safety)
        total_w = sum(self._weights)
        self._weights = [w / total_w for w in self._weights]
        self._weights_arr: np.ndarray = np.array(self._weights, dtype=np.float64)

    def get_country(self, bic: str) -> str:
        """Return ISO 3166-1 country code for a BIC."""
        return self._bic_country.get(bic, bic[4:6])

    def get_currency(self, bic: str) -> str:
        """Return ISO 4217 currency code for a BIC's country."""
        country = self.get_country(bic)
        return COUNTRY_CURRENCY.get(country, "USD")

    def get_corridor(self, sender_bic: str, receiver_bic: str) -> str:
        """Return corridor string e.g. 'USD-EUR' from two BICs."""
        src = self.get_currency(sender_bic)
        dst = self.get_currency(receiver_bic)
        return f"{src}-{dst}"

    def get_currency_pair(self, sender_bic: str, receiver_bic: str) -> str:
        """Return currency pair string e.g. 'USD/EUR' (slash-separated)."""
        src = self.get_currency(sender_bic)
        dst = self.get_currency(receiver_bic)
        return f"{src}/{dst}"

    def sample_bic_pair(
        self,
        rng: np.random.Generator,
    ) -> tuple[str, str]:
        """Sample a (sender_bic, receiver_bic) pair, sender ≠ receiver.

        Hub banks receive 60% of the total transaction weight, creating
        a realistic hub-and-spoke correspondent banking topology.
        """
        idx1 = int(rng.choice(self.n_total, p=self._weights_arr))
        # Receiver: same distribution but must differ from sender
        while True:
            idx2 = int(rng.choice(self.n_total, p=self._weights_arr))
            if idx2 != idx1:
                break
        return self.all_bics[idx1], self.all_bics[idx2]

    def sample_bic_pairs_batch(
        self,
        rng: np.random.Generator,
        n: int,
    ) -> tuple[list[str], list[str]]:
        """Vectorised batch sampling of n BIC pairs.

        Uses rejection sampling to ensure sender ≠ receiver.
        Typically requires < 2 passes at standard pool sizes.
        """
        senders_idx = rng.choice(self.n_total, size=n, p=self._weights_arr)
        receivers_idx = rng.choice(self.n_total, size=n, p=self._weights_arr)

        # Fix any collisions (sender == receiver)
        collisions = senders_idx == receivers_idx
        while collisions.any():
            n_fix = int(collisions.sum())
            receivers_idx[collisions] = rng.choice(
                self.n_total, size=n_fix, p=self._weights_arr
            )
            collisions = senders_idx == receivers_idx

        bics = self.all_bics
        senders = [bics[i] for i in senders_idx]
        receivers = [bics[i] for i in receivers_idx]
        return senders, receivers
