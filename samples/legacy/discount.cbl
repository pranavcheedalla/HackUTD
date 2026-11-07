       IDENTIFICATION DIVISION.
       PROGRAM-ID. DISCOUNT.
      * Subprogram called by INVOICE: picks a discount rate (percent).
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-TIER               PIC X.
       01  LK-SUBTOTAL           PIC 9(7)V99.
       01  LK-RATE               PIC 9(2)V99.
       PROCEDURE DIVISION USING LK-TIER LK-SUBTOTAL LK-RATE.
           EVALUATE TRUE
               WHEN LK-TIER = 'G'
                   MOVE 12.50 TO LK-RATE
               WHEN LK-TIER = 'S'
                   MOVE 7.25 TO LK-RATE
               WHEN LK-SUBTOTAL >= 1000.00
                   MOVE 5.00 TO LK-RATE
               WHEN OTHER
                   MOVE 0 TO LK-RATE
           END-EVALUATE
           GOBACK.
