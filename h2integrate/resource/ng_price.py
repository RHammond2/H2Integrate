import json
from pathlib import Path
from datetime import datetime

import attrs
import pandas as pd
import requests
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import get_path


STATE_MAP = states = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
    "American Samoa": "AS",
    "Guam": "GU",
    "Northern Mariana Islands": "MP",
    "Puerto Rico": "PR",
    "United States Minor Outlying Islands": "UM",
    "Virgin Islands, U.S.": "VI",
}
CURRENT_YEAR = datetime.now().year


def convert_to_monthly(df: pd.DataFrame, year: int) -> pd.DataFrame | None:
    """Converts an annual timeseries to monthly by repeating the one value, or returns
    the data passed, if already monthly.

    Args:
        df (pd.DataFrame): The annual or monthly natural gas pricing data.
        year (int): The resource year.

    Returns:
        pd.DataFrame | None: Returns back the monthly data if the original data have either
            1 or 12 data entries, otherwise None is returned.
    """
    match df.shape[0]:
        case 12:
            return df
        case 1:
            df = df.reindex(pd.date_range(f"{year}-01", f"{year}-12", freq="MS"), method="nearest")
            return df
        case _:
            pass


def get_eia_api_key(filename: Path) -> str:
    """Retrieves the EIA API key from a file, and returns the key following "EIA_API_KEY:".

    Args:
        filename (Path): Full file path and name of where the EIA API key is located. Must be
            encoded as "EIA_API_KEY: xxxxxx"

    Returns:
        str: The EIA API key.
    """
    with filename.open() as f:
        for line in f.readlines():
            if ":" in line:
                name, val = line.strip().split(":")
                if name == "EIA_API_KEY":
                    return val.strip()


@define
class EIAIndustrialNaturalGasConfig(BaseConfig):
    """EIA Industrial Natural Gas Pricing API Configuration.

    Args:
        state (str): Two-letter, upper case state abbreviation. Must be one of the 50 U.S. states.
        resource_year (int): The YYYY-format year whose data should be retrieved. Must be between
            2001 and the current year, inclusive of endpoints.
        monthly (Path): True, if monthly data is desired, False if annual data is desired.
        api_key_file (Path): Full file name of the file where the API key is located.
        latitude (float, optional): Latitude of the site, optional.
        latitude (float, optional): Longitude of the site, optional.
        filename (str, optinal): Filename for where to save the data or where the data may
            already be located. If the file exists, it will be used, and filtered to the
            :py:attr:`resource_year`, otherwise, the data will be saved to this location.
    """

    resource_year: int = field(validator=attrs.validators.in_(range(2001, CURRENT_YEAR + 1)))
    monthly: bool = field(validator=attrs.validators.instance_of(bool))
    api_key_file: str = field(converter=get_path)
    state: str = field(
        converter=str.upper,
        validator=attrs.validators.in_(STATE_MAP.values()),
    )
    latitude: float = field(default=0)
    longitude: float = field(default=0)
    filename: str = field(default=None, converter=attrs.converters.optional(get_path))


class EIAIndustrialNaturalGasResource:
    """EIA Industrial Natural Gas Pricing Downloader.

    See https://www.eia.gov/dnav/ng/hist/n3035us3m.htm for further details.
    """

    def __init__(self, resource_config: dict):
        # self.setup()
        self.config = EIAIndustrialNaturalGasConfig.from_dict(
            # self.options["resource_config"],
            resource_config,
            additional_cls_name=self.__class__.__name__,
        )
        self.url = self.create_url()

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("resource_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        # Define inputs and outputs
        self.config = EIAIndustrialNaturalGasConfig.from_dict(
            self.options["resource_config"],
            additional_cls_name=self.__class__.__name__,
        )
        site_config = self.options["plant_config"]["site"]
        self.add_input("latitude", site_config.get("latitude", 0.0), units="deg")
        self.add_input("longitude", site_config.get("longitude", 0.0), units="deg")
        self.add_output("price", shape=12, val=0.0, units="USD/(ft**3/1000)")

    def create_url(self):
        base_url = "https://api.eia.gov/v2/natural-gas/pri/sum/data/"
        frequency = f"frequency={'monthly' if self.config.monthly else 'annual'}"
        data = "data[0]=value"
        facet = f"facets[series][]=N3035{self.config.state}3"
        start = f"start={self.config.resource_year}"
        end = f"end={self.config.resource_year}"
        if self.config.monthly:
            start = f"{start}-01"
            end = f"{start}-12"
        sort_col = "sort[0][column]=period"
        sort_dir = "sort[0][direction]=asc"
        api_key = f"api_key={get_eia_api_key(self.config.api_key_file)}"

        url_opts = "&".join((frequency, data, facet, start, end, sort_col, sort_dir, api_key))
        url = f"{base_url}?{url_opts}"
        return url

    def load_data(self, filename: Path | None = None) -> pd.DataFrame:
        """Loads the previously saved data from :py:attr:`filename` if ``resource_year``
        is available as either annual or monthly data, otherwise queries the EIA API.

        Args:
            filename (Path | None, optional): The full filename where the natural gas pricing data
                should be saved to or loaded from, if available. Defaults to None.

        Raises:
            requests.exceptions.HTTPError: Raised if an unsuccessful API query result is returned.

        Returns:
            pandas.DataFrame: DataFrame with index "period" and column "value" with natural gas
                pricing in $/MCF (USD per thousands of cubic feet) as either the monthly value
                or extrapolated annual values to a monthly resolution.
        """
        filename = Path(filename).resolve()
        if filename.exists():
            df = pd.read_csv(filename, parse_dates=["period"]).set_index("period")
            df = df.loc[df.index.dt.year.eq(self.config.resource_year)]
            df = convert_to_monthly(df, self.config.resource_year)
            if df is not None:
                return df

        r = requests.get(self.url)
        if r.status_code != 200:
            err = json.loads(r.text)["error"]
            msg = f"{err['code']}: {err['message']}"
            raise requests.exceptions.HTTPError(msg)

        cols = ["period", "value"]
        df = pd.DataFrame.from_dict(json.loads(r.text)["response"]["data"])[cols]
        df.period = pd.to_datetime(df.period)
        df = df.set_index("period")
        df = convert_to_monthly(df)

        if filename is not None:
            df.to_csv(filename, index_label="period")
        return df

    def compute(self, inputs, outputs):
        ng_price_monthly = self.load_data(self.config.filename)
        outputs["price"] = ng_price_monthly.to_numpy()
