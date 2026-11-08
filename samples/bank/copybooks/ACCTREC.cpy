      * Account input record, 15 characters, no decimal points.
       01  ACCT-RECORD.
           05  ACCT-TYPE         PIC X.
               88  ACCT-CHECKING VALUE 'C'.
               88  ACCT-SAVINGS  VALUE 'S'.
               88  ACCT-PREMIUM  VALUE 'P'.
           05  ACCT-BALANCE      PIC 9(7)V99.
           05  ACCT-TXNS         PIC 9(3).
           05  ACCT-DAYS         PIC 9(2).
