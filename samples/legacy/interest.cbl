       IDENTIFICATION DIVISION.
       PROGRAM-ID. INTEREST.
      * Simple interest calculator.
      * Input: one fixed-width line, 15 characters, no decimal points
      *   cols 1-9   principal  PIC 9(7)V99
      *   cols 10-13 rate (%)   PIC 9(2)V99
      *   cols 14-15 years      PIC 9(2)
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-INPUT.
           05  IN-PRINCIPAL      PIC 9(7)V99.
           05  IN-RATE           PIC 9(2)V99.
           05  IN-YEARS          PIC 9(2).
       01  WS-INTEREST           PIC 9(7)V99.
       01  WS-TOTAL              PIC 9(8)V99.
       01  OUT-INTEREST          PIC Z(6)9.99.
       01  OUT-TOTAL             PIC Z(7)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-INPUT
           IF IN-YEARS = 0
               DISPLAY "ERROR: YEARS MUST BE AT LEAST 1"
               STOP RUN
           END-IF
           COMPUTE WS-INTEREST ROUNDED =
               IN-PRINCIPAL * IN-RATE * IN-YEARS / 100
           COMPUTE WS-TOTAL = IN-PRINCIPAL + WS-INTEREST
           MOVE WS-INTEREST TO OUT-INTEREST
           MOVE WS-TOTAL TO OUT-TOTAL
           DISPLAY "INTEREST: " OUT-INTEREST
           DISPLAY "TOTAL:    " OUT-TOTAL
           STOP RUN.
