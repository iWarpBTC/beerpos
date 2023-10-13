from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateBeerPoSData, BeerPoS


async def create_beerpos(wallet_id: str, data: CreateBeerPoSData) -> BeerPoS:
    beerpos_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO beerpos.beerposs (id, wallet, name, currency, tip_options, tip_wallet)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            beerpos_id,
            wallet_id,
            data.name,
            data.currency,
            data.tip_options,
            data.tip_wallet,
        ),
    )

    beerpos = await get_beerpos(beerpos_id)
    assert beerpos, "Newly created beerpos couldn't be retrieved"
    return beerpos


async def update_beerpos(beerpos_id: str, **kwargs) -> BeerPoS:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE beerpos.beerposs SET {q} WHERE id = ?", (*kwargs.values(), beerpos_id)
    )
    beerpos = await get_beerpos(beerpos_id)
    assert beerpos, "Newly updated beerpos couldn't be retrieved"
    return beerpos


async def get_beerpos(beerpos_id: str) -> Optional[BeerPoS]:
    row = await db.fetchone("SELECT * FROM beerpos.beerposs WHERE id = ?", (beerpos_id,))
    return BeerPoS(**row) if row else None


async def get_beerposs(wallet_ids: Union[str, List[str]]) -> List[BeerPoS]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM beerpos.beerposs WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [BeerPoS(**row) for row in rows]


async def delete_beerpos(beerpos_id: str) -> None:
    await db.execute("DELETE FROM beerpos.beerposs WHERE id = ?", (beerpos_id,))
