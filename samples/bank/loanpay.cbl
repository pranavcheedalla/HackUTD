       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOANPAY.
      * Flat-interest loan: total owed and the monthly payment.
      * Input: one fixed-width line, 16 characters, no decimal points
      *   cols 1-9   principal  PIC 9(7)V99
      *   cols 10-13 rate (%)   PIC 9(2)V99
      *   cols 14-16 months     PIC 9(3)
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-INPUT.
           05  IN-PRINCIPAL      PIC 9(7)V99.
           05  IN-RATE           PIC 9(2)V99.
           05  IN-MONTHS         PIC 9(3).
       01  WS-INTEREST           PIC 9(7)V99.
       01  WS-TOTAL              PIC 9(8)V99.
       01  WS-PAYMENT            PIC 9(7)V99.
       01  OUT-TOTAL             PIC Z(7)9.99.
       01  OUT-PAYMENT           PIC Z(6)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-INPUT
           IF IN-MONTHS = 0
               DISPLAY "ERROR: TERM MUST BE AT LEAST 1 MONTH"
               STOP RUN
           END-IF
           COMPUTE WS-INTEREST ROUNDED =
               IN-PRINCIPAL * IN-RATE * IN-MONTHS / 1200
           COMPUTE WS-TOTAL = IN-PRINCIPAL + WS-INTEREST
           COMPUTE WS-PAYMENT = WS-TOTAL / IN-MONTHS
           MOVE WS-TOTAL TO OUT-TOTAL
           MOVE WS-PAYMENT TO OUT-PAYMENT
           DISPLAY "TOTAL:   " OUT-TOTAL
           DISPLAY "PAYMENT: " OUT-PAYMENT
           STOP RUN.
