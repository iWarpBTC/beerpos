from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateBeerPoSData(BaseModel):
    name: str
    currency: str
    tip_options: str = Query(None)
    tip_wallet: str = Query(None)


class BeerPoS(BaseModel):
    id: str
    wallet: str
    name: str
    currency: str
    tip_options: Optional[str]
    tip_wallet: Optional[str]

    @classmethod
    def from_row(cls, row: Row) -> "BeerPoS":
        return cls(**dict(row))


class PayLnurlWData(BaseModel):
    lnurl: str
