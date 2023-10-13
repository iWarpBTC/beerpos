from http import HTTPStatus

import httpx
from fastapi import Depends, Query
from lnurl import decode as decode_lnurl
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_latest_payments_by_extension, get_user
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import (
    WalletTypeInfo,
    check_admin,
    get_key_type,
    require_admin_key,
)
from lnbits.utils.exchange_rates import get_fiat_rate_satoshis

from . import scheduled_tasks, beerpos_ext
from .crud import create_beerpos, delete_beerpos, get_beerpos, get_beerposs, update_beerpos
from .models import CreateBeerPoSData, PayLnurlWData


@beerpos_ext.get("/api/v1/beerposs", status_code=HTTPStatus.OK)
async def api_beerposs(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [beerpos.dict() for beerpos in await get_beerposs(wallet_ids)]


@beerpos_ext.post("/api/v1/beerposs", status_code=HTTPStatus.CREATED)
async def api_beerpos_create(
    data: CreateBeerPoSData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    beerpos = await create_beerpos(wallet_id=wallet.wallet.id, data=data)
    return beerpos.dict()


@beerpos_ext.put("/api/v1/beerposs/{beerpos_id}")
async def api_beerpos_update(
    data: CreateBeerPoSData,
    beerpos_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    if not beerpos_id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="BeerPoS does not exist."
        )
    beerpos = await get_beerpos(beerpos_id)
    assert beerpos, "BeerPoS couldn't be retrieved"

    if wallet.wallet.id != beerpos.wallet:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your BeerPoS.")
    beerpos = await update_beerpos(beerpos_id, **data.dict())
    return beerpos.dict()


@beerpos_ext.delete("/api/v1/beerposs/{beerpos_id}")
async def api_beerpos_delete(
    beerpos_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    beerpos = await get_beerpos(beerpos_id)

    if not beerpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="BeerPoS does not exist."
        )

    if beerpos.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your BeerPoS.")

    await delete_beerpos(beerpos_id)
    return "", HTTPStatus.NO_CONTENT


@beerpos_ext.post("/api/v1/beerposs/{beerpos_id}/invoices", status_code=HTTPStatus.CREATED)
async def api_beerpos_create_invoice(
    beerpos_id: str, amount: int = Query(..., ge=1), memo: str = "", tipAmount: int = 0
) -> dict:
    beerpos = await get_beerpos(beerpos_id)

    if not beerpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="BeerPoS does not exist."
        )

    if tipAmount > 0:
        amount += tipAmount

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=beerpos.wallet,
            amount=amount,
            memo=f"{memo} to {beerpos.name}" if memo else f"{beerpos.name}",
            extra={
                "tag": "beerpos",
                "tipAmount": tipAmount,
                "beerposId": beerpos_id,
                "amount": amount - tipAmount if tipAmount else False,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@beerpos_ext.get("/api/v1/beerposs/{beerpos_id}/invoices")
async def api_beerpos_get_latest_invoices(beerpos_id: str):
    try:
        payments = [
            Payment.from_row(row)
            for row in await get_latest_payments_by_extension(
                ext_name="beerpos", ext_id=beerpos_id
            )
        ]

    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return [
        {
            "checking_id": payment.checking_id,
            "amount": payment.amount,
            "time": payment.time,
            "pending": payment.pending,
        }
        for payment in payments
    ]


@beerpos_ext.post(
    "/api/v1/beerposs/{beerpos_id}/invoices/{payment_request}/pay", status_code=HTTPStatus.OK
)
async def api_beerpos_pay_invoice(
    lnurl_data: PayLnurlWData, payment_request: str, beerpos_id: str
):
    beerpos = await get_beerpos(beerpos_id)

    if not beerpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="BeerPoS does not exist."
        )

    lnurl = (
        lnurl_data.lnurl.replace("lnurlw://", "")
        .replace("lightning://", "")
        .replace("LIGHTNING://", "")
        .replace("lightning:", "")
        .replace("LIGHTNING:", "")
    )

    if lnurl.lower().startswith("lnurl"):
        lnurl = decode_lnurl(lnurl)
    else:
        lnurl = "https://" + lnurl

    async with httpx.AsyncClient() as client:
        try:
            headers = {"user-agent": f"lnbits/beerpos"}
            r = await client.get(lnurl, follow_redirects=True, headers=headers)
            if r.is_error:
                lnurl_response = {"success": False, "detail": "Error loading"}
            else:
                resp = r.json()
                if resp["tag"] != "withdrawRequest":
                    lnurl_response = {"success": False, "detail": "Wrong tag type"}
                else:
                    r2 = await client.get(
                        resp["callback"],
                        follow_redirects=True,
                        headers=headers,
                        params={
                            "k1": resp["k1"],
                            "pr": payment_request,
                        },
                    )
                    resp2 = r2.json()
                    if r2.is_error:
                        lnurl_response = {
                            "success": False,
                            "detail": "Error loading callback",
                        }
                    elif resp2["status"] == "ERROR":
                        lnurl_response = {"success": False, "detail": resp2["reason"]}
                    else:
                        lnurl_response = {"success": True, "detail": resp2}
        except (httpx.ConnectError, httpx.RequestError):
            lnurl_response = {"success": False, "detail": "Unexpected error occurred"}

    return lnurl_response


@beerpos_ext.get(
    "/api/v1/beerposs/{beerpos_id}/invoices/{payment_hash}", status_code=HTTPStatus.OK
)
async def api_beerpos_check_invoice(beerpos_id: str, payment_hash: str):
    beerpos = await get_beerpos(beerpos_id)
    if not beerpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="BeerPoS does not exist."
        )
    try:
        status = await api_payment(payment_hash)

    except Exception as exc:
        logger.error(exc)
        return {"paid": False}
    return status


@beerpos_ext.delete(
    "/api/v1",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
    description="Stop the extension.",
)
async def api_stop():
    for t in scheduled_tasks:
        try:
            t.cancel()
        except Exception as ex:
            logger.warning(ex)

    return {"success": True}


@beerpos_ext.get("/api/v1/rate/{currency}", status_code=HTTPStatus.OK)
async def api_check_fiat_rate(currency):
    try:
        rate = await get_fiat_rate_satoshis(currency)
    except AssertionError:
        rate = None

    return {"rate": rate}
