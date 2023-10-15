import asyncio

from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice, websocketUpdater
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_beerpos


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "beerpos" or payment.extra.get("tipSplitted"):
        return

    tipAmount = payment.extra.get("tipAmount")

    strippedPayment = {
        "amount": payment.amount,
        "fee": payment.fee,
        "checking_id": payment.checking_id,
        "payment_hash": payment.payment_hash,
        "bolt11": payment.bolt11,
    }

    beerpos_id = payment.extra.get("beerposId")
    assert beerpos_id

    beerpos = await get_beerpos(beerpos_id)
    assert beerpos

    await websocketUpdater(beerpos_id, str(strippedPayment))

    if not tipAmount:
        # no tip amount
        return

    wallet_id = beerpos.tip_wallet
    assert wallet_id

    payment_hash, payment_request = await create_invoice(
        wallet_id=wallet_id,
        amount=int(tipAmount),
        internal=True,
        memo="beerpos tip",
    )
    logger.debug(f"beerpos: tip invoice created: {payment_hash}")

    checking_id = await pay_invoice(
        payment_request=payment_request,
        wallet_id=payment.wallet_id,
        extra={**payment.extra, "tipSplitted": True},
    )
    logger.debug(f"beerpos: tip invoice paid: {checking_id}")
