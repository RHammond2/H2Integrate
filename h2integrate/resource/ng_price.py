import json
from pathlib import Path
from datetime import datetime

import attrs
import pandas as pd
import requests
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import get_path


STATES = states = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]
CURRENT_YEAR = datetime.now().year


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
    """

    state: str = field(
        converter=str.upper,
        validator=attrs.validators.in_(STATES),
    )
    resource_year: int = field(validator=attrs.validators.in_(range(2001, CURRENT_YEAR + 1)))
    monthly: bool = field(validator=attrs.validators.instance_of(bool))
    api_key_file: str = field(converter=get_path)


class EIAIndustrialNaturalGasResource:
    """Create the class."""

    def __init__(self, resource_config: dict):
        # self.setup()
        self.config = EIAIndustrialNaturalGasConfig.from_dict(
            # self.options["resource_config"],
            resource_config,
            additional_cls_name=self.__class__.__name__,
        )
        self.url = self.create_url()

    # def initialize(self):
    #     self.options.declare("plant_config", types=dict)
    #     self.options.declare("resource_config", types=dict)
    #     self.options.declare("driver_config", types=dict)

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

    def setup(self):
        # Define inputs and outputs
        self.config = EIAIndustrialNaturalGasConfig.from_dict(
            self.options["resource_config"],
            additional_cls_name=self.__class__.__name__,
        )
        # site_config = self.options["plant_config"]["site"]

        # self.add_input("latitude", site_config.get("latitude", 0.0), units="deg")
        # self.add_input("longitude", site_config.get("longitude", 0.0), units="deg")
        # self.add_output("discharge", shape=8760, val=0.0, units="ft**3/s")

    def load_data(self, filename: str | Path | None = None):
        # download_from_api(self.url, filename)
        r = requests.get(self.url)
        if r.status_code != 200:
            err = json.loads(r.text)["error"]
            msg = f"{err['code']}: {err['message']}"
            raise requests.exceptions.HTTPError(msg)

        cols = ["period", "area-name", "value", "units"]
        df = pd.DataFrame.from_dict(json.loads(r.text)["response"]["data"])[cols]
        df.period = pd.to_datetime(df.period)

        if filename is not None:
            df.to_csv(filename, index=False)
