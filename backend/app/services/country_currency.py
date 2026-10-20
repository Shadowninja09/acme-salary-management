from app.models.salary import Currency

UNKNOWN_COUNTRY_CURRENCY_POLICY_DETAIL = (
    "No salary currency policy is configured for this employee's country."
)

_COUNTRY_CURRENCY_POLICY: dict[str, tuple[str, tuple[Currency, ...]]] = {}


def normalize_country(country: str) -> str:
    return " ".join(country.split()).casefold()


def _register(canonical_name: str, currencies: tuple[Currency, ...]) -> None:
    key = normalize_country(canonical_name)
    _COUNTRY_CURRENCY_POLICY[key] = (canonical_name, currencies)


_register("India", (Currency.INR,))
_register("United States", (Currency.USD,))
_register("United Kingdom", (Currency.GBP,))
_register("Canada", (Currency.CAD,))
_register("Australia", (Currency.AUD,))
_register("Germany", (Currency.EUR,))


class UnsupportedSalaryCurrencyForCountryError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def permitted_currencies_for_country(country: str) -> tuple[Currency, ...] | None:
    entry = _COUNTRY_CURRENCY_POLICY.get(normalize_country(country))
    if entry is None:
        return None
    return entry[1]


def _country_label(country: str) -> str:
    stripped = " ".join(country.split())
    entry = _COUNTRY_CURRENCY_POLICY.get(normalize_country(country))
    if entry is not None:
        return entry[0]
    return stripped or country


def require_currency_permitted_for_country(country: str, currency: str) -> None:
    permitted = permitted_currencies_for_country(country)
    if permitted is None:
        raise UnsupportedSalaryCurrencyForCountryError(
            UNKNOWN_COUNTRY_CURRENCY_POLICY_DETAIL
        )
    if currency not in {item.value for item in permitted}:
        codes = ", ".join(item.value for item in permitted)
        raise UnsupportedSalaryCurrencyForCountryError(
            f"Currency {currency} is not permitted for {_country_label(country)}. "
            f"Permitted currencies: {codes}."
        )
