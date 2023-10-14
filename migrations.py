async def m001_initial(db):
    """
    Initial beerposs table.
    """
    await db.execute(
        """
        CREATE TABLE beerpos.beerposs (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            tip_wallet TEXT NULL,
            tip_options TEXT NULL,
            name TEXT NOT NULL,
            currency TEXT NOT NULL,
            products TEXT NULL
        );
    """
    )
