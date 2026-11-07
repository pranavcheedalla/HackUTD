       IDENTIFICATION DIVISION.
       PROGRAM-ID. INVOICE.
      * Invoice total with tier discount.
      * Input: one fixed-width line, 12 characters (see INVREC).
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY INVREC.
       01  WS-SUBTOTAL           PIC 9(7)V99.
       01  WS-DISC-RATE          PIC 9(2)V99.
       01  WS-DISC-AMT           PIC 9(5)V99.
       01  WS-NET                PIC S9(7)V99.
       01  OUT-SUBTOTAL          PIC Z(6)9.99.
       01  OUT-DISC              PIC Z(4)9.99.
       01  OUT-NET               PIC -Z(6)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT INV-RECORD
           IF INV-QTY = ZERO
               DISPLAY "ERROR: QUANTITY MUST BE AT LEAST 1"
               STOP RUN
           END-IF
           COMPUTE WS-SUBTOTAL = INV-QTY * INV-UNIT-PRICE
               ON SIZE ERROR
                   DISPLAY "ERROR: SUBTOTAL TOO LARGE"
                   STOP RUN
           END-COMPUTE
           CALL 'DISCOUNT' USING INV-CUST-TIER WS-SUBTOTAL
                                 WS-DISC-RATE
           COMPUTE WS-DISC-AMT = WS-SUBTOTAL * WS-DISC-RATE / 100
           COMPUTE WS-NET = WS-SUBTOTAL - WS-DISC-AMT
           MOVE WS-SUBTOTAL TO OUT-SUBTOTAL
           MOVE WS-DISC-AMT TO OUT-DISC
           MOVE WS-NET TO OUT-NET
           DISPLAY "SUBTOTAL: " OUT-SUBTOTAL
           DISPLAY "DISCOUNT: " OUT-DISC
           DISPLAY "NET:     " OUT-NET
           STOP RUN.
