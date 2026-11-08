       IDENTIFICATION DIVISION.
       PROGRAM-ID. FEERATE.
      * Subprogram: monthly account fee.
      * Checking: 5.00 plus 0.35 for each transaction over 20.
      * Savings:  2.50 plus 0.50 for each transaction over 6.
      * Premium:  no fee.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-TYPE               PIC X.
       01  LK-TXNS               PIC 9(3).
       01  LK-FEE                PIC 9(3)V99.
       PROCEDURE DIVISION USING LK-TYPE LK-TXNS LK-FEE.
           EVALUATE TRUE
               WHEN LK-TYPE = 'C'
                   MOVE 5.00 TO LK-FEE
                   IF LK-TXNS > 20
                       COMPUTE LK-FEE = LK-FEE + (LK-TXNS - 20) * 0.35
                   END-IF
               WHEN LK-TYPE = 'S'
                   MOVE 2.50 TO LK-FEE
                   IF LK-TXNS > 6
                       COMPUTE LK-FEE = LK-FEE + (LK-TXNS - 6) * 0.50
                   END-IF
               WHEN OTHER
                   MOVE 0 TO LK-FEE
           END-EVALUATE
           GOBACK.
