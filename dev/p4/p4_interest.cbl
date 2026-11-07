      *> P4 dev sample: simple interest. Input (15 chars, fixed width):
      *>   cols 1-9   principal  PIC 9(7)V99   e.g. 000100000 = 1000.00
      *>   cols 10-13 rate %     PIC 9(2)V99   e.g. 0500      = 5.00
      *>   cols 14-15 years      PIC 9(2)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. P4-INTEREST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-INPUT.
          05 WS-PRINCIPAL      PIC 9(7)V99.
          05 WS-RATE           PIC 9(2)V99.
          05 WS-YEARS          PIC 9(2).
       01 WS-INTEREST          PIC 9(7)V99.
       01 WS-TOTAL             PIC 9(8)V99.
       01 WS-INTEREST-ED       PIC Z,ZZZ,ZZ9.99.
       01 WS-TOTAL-ED          PIC ZZ,ZZZ,ZZ9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-INPUT.
           IF WS-YEARS = 0
               DISPLAY "ERROR: YEARS MUST BE GREATER THAN ZERO"
           ELSE
               COMPUTE WS-INTEREST =
                   WS-PRINCIPAL * WS-RATE * WS-YEARS / 100
               COMPUTE WS-TOTAL = WS-PRINCIPAL + WS-INTEREST
               MOVE WS-INTEREST TO WS-INTEREST-ED
               MOVE WS-TOTAL TO WS-TOTAL-ED
               DISPLAY "INTEREST=" WS-INTEREST-ED " TOTAL=" WS-TOTAL-ED
           END-IF.
           STOP RUN.
