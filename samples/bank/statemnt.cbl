       IDENTIFICATION DIVISION.
       PROGRAM-ID. STATEMNT.
      * Monthly statement: interest in, fees out, new balance.
      * Input: one fixed-width line, 15 characters (see ACCTREC).
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ACCTREC.
       01  WS-INTEREST           PIC 9(6)V99.
       01  WS-FEE                PIC 9(3)V99.
       01  WS-NEW                PIC S9(8)V99.
       01  OUT-INTEREST          PIC Z(5)9.99.
       01  OUT-FEE               PIC ZZ9.99.
       01  OUT-NEW               PIC -Z(7)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT ACCT-RECORD
           IF NOT ACCT-CHECKING AND NOT ACCT-SAVINGS
                                AND NOT ACCT-PREMIUM
               DISPLAY "ERROR: UNKNOWN ACCOUNT TYPE"
               STOP RUN
           END-IF
           IF ACCT-DAYS = ZERO
               DISPLAY "ERROR: PERIOD MUST BE AT LEAST 1 DAY"
               STOP RUN
           END-IF
           CALL 'ACCRUE' USING ACCT-BALANCE ACCT-TYPE ACCT-DAYS
                               WS-INTEREST
           CALL 'FEERATE' USING ACCT-TYPE ACCT-TXNS WS-FEE
           COMPUTE WS-NEW = ACCT-BALANCE + WS-INTEREST - WS-FEE
           MOVE WS-INTEREST TO OUT-INTEREST
           MOVE WS-FEE TO OUT-FEE
           MOVE WS-NEW TO OUT-NEW
           DISPLAY "INTEREST:    " OUT-INTEREST
           DISPLAY "FEES:        " OUT-FEE
           DISPLAY "NEW BALANCE: " OUT-NEW
           IF WS-NEW < 0
               DISPLAY "STATUS: OVERDRAWN"
           ELSE
               DISPLAY "STATUS: OK"
           END-IF
           STOP RUN.
