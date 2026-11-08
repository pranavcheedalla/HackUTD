       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCRUE.
      * Subprogram: interest earned over a period.
      * Annual rate: savings 2.10%, premium 3.75%, checking 0.05%.
      * Interest = balance * rate * days / 36500, truncated to cents.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RATE               PIC 9V99.
       LINKAGE SECTION.
       01  LK-BALANCE            PIC 9(7)V99.
       01  LK-TYPE               PIC X.
       01  LK-DAYS               PIC 9(2).
       01  LK-INTEREST           PIC 9(6)V99.
       PROCEDURE DIVISION USING LK-BALANCE LK-TYPE LK-DAYS
                                LK-INTEREST.
           EVALUATE TRUE
               WHEN LK-TYPE = 'S'
                   MOVE 2.10 TO WS-RATE
               WHEN LK-TYPE = 'P'
                   MOVE 3.75 TO WS-RATE
               WHEN OTHER
                   MOVE 0.05 TO WS-RATE
           END-EVALUATE
           COMPUTE LK-INTEREST = LK-BALANCE * WS-RATE * LK-DAYS / 36500
           GOBACK.
