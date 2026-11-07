      * Invoice input record, 12 characters, no decimal points.
       01  INV-RECORD.
           05  INV-QTY           PIC 9(4).
           05  INV-UNIT-PRICE    PIC 9(5)V99.
           05  INV-CUST-TIER     PIC X.
               88  TIER-GOLD     VALUE 'G'.
               88  TIER-SILVER   VALUE 'S'.
