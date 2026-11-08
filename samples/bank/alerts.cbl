       IDENTIFICATION DIVISION.
       PROGRAM-ID. ALERTS.
      * Fee alert: warn when this month's fees exceed 1% of balance.
      * Input: one fixed-width line, 15 characters (see ACCTREC).
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ACCTREC.
       01  WS-FEE                PIC 9(3)V99.
       01  WS-LIMIT              PIC 9(5)V99.
       01  OUT-FEE               PIC ZZ9.99.
       01  OUT-LIMIT             PIC Z(4)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT ACCT-RECORD
           CALL 'FEERATE' USING ACCT-TYPE ACCT-TXNS WS-FEE
           COMPUTE WS-LIMIT = ACCT-BALANCE / 100
           MOVE WS-FEE TO OUT-FEE
           MOVE WS-LIMIT TO OUT-LIMIT
           DISPLAY "FEES:  " OUT-FEE
           DISPLAY "LIMIT: " OUT-LIMIT
           IF WS-FEE > WS-LIMIT
               DISPLAY "FEE ALERT: YES"
           ELSE
               DISPLAY "FEE ALERT: NO"
           END-IF
           STOP RUN.
