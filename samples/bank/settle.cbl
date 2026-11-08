       IDENTIFICATION DIVISION.
       PROGRAM-ID. SETTLE.
      * Card settlement: merchant fee and net payout for one batch.
      * Input: one fixed-width line, 13 characters, no decimal points
      *   cols 1-9   batch amount in cents  (PIC 9(7)V99)
      *   col  10    card network   V = Visa, M = Mastercard, A = Amex
      *   cols 11-13 transactions   PIC 9(3)
      * Fee = amount * network rate + 0.10 per transaction,
      * rounded to the nearest cent, capped at 500.00.
      * (Changed 1998: record now read as text and split with MOVE;
      *  fee field shortened to 4 digits. -- R.K.)
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-LINE               PIC X(13).
       01  IN-AMOUNT             PIC 9(7)V99.
       01  IN-NETWORK            PIC X.
       01  IN-COUNT              PIC 9(3).
       01  WS-RATE               PIC V9(4).
       01  WS-FEE-RAW            PIC 9(6)V99.
       01  WS-FEE                PIC 9(4)V99.
       01  WS-NET                PIC 9(7)V99.
       01  OUT-FEE               PIC Z(3)9.99.
       01  OUT-NET               PIC Z(6)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-LINE
           MOVE WS-LINE(1:9) TO IN-AMOUNT
           MOVE WS-LINE(10:1) TO IN-NETWORK
           MOVE WS-LINE(11:3) TO IN-COUNT
           IF IN-AMOUNT = 0
               DISPLAY "ERROR: EMPTY BATCH"
               STOP RUN
           END-IF
           EVALUATE IN-NETWORK
               WHEN 'V'
                   MOVE .0195 TO WS-RATE
               WHEN 'M'
                   MOVE .0215 TO WS-RATE
               WHEN 'A'
                   MOVE .0350 TO WS-RATE
               WHEN OTHER
                   MOVE .0299 TO WS-RATE
           END-EVALUATE
           COMPUTE WS-FEE-RAW = IN-AMOUNT * WS-RATE + IN-COUNT * 0.10
           MOVE WS-FEE-RAW TO WS-FEE
           IF WS-FEE > 500
               MOVE 500 TO WS-FEE
           END-IF
           IF WS-FEE > IN-AMOUNT
               MOVE IN-AMOUNT TO WS-FEE
           END-IF
           COMPUTE WS-NET = IN-AMOUNT - WS-FEE
           MOVE WS-FEE TO OUT-FEE
           MOVE WS-NET TO OUT-NET
           DISPLAY "FEE: " OUT-FEE
           DISPLAY "NET: " OUT-NET
           STOP RUN.
