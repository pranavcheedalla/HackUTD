       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
      * Placeholder so the stub pipeline has something to run.
      * P2 replaces this folder with the real programs.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-LINE PIC X(80).
       PROCEDURE DIVISION.
           ACCEPT WS-LINE.
           DISPLAY "OUT:" FUNCTION UPPER-CASE(FUNCTION TRIM(WS-LINE)).
           STOP RUN.
