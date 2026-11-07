identification division.
program-id. interest.
environment division.
configuration section.
repository. function all intrinsic.
data division.
working-storage section.
01 input-line       pic x(256).
01 raw-principal    pic x(256).
01 raw-rate         pic x(256).
01 raw-years        pic x(256).
01 token-text       pic x(256).
01 principal-amount pic 9(5)v99.
01 annual-rate      pic 9(3)v99.
01 years-count      pic 99.
01 interest-amount  pic 9(7)v99.
01 printed-interest pic 9(7).99.
01 valid-input      pic 9 value 1.
01 delimiter-count binary-long value 0.
01 token-length     binary-long.
01 digit-index      binary-long.
01 whole-digits     binary-long.
01 fraction-digits  binary-long.
01 max-whole        binary-long.
01 max-fraction     binary-long.
01 dot-seen         pic 9.

procedure division.
main.
    accept input-line
    inspect input-line tallying delimiter-count for all "|"
    if delimiter-count not = 2
        display "ERROR:INVALID_INPUT"
        stop run
    end-if
    unstring input-line delimited by "|"
        into raw-principal raw-rate raw-years
    end-unstring

    move trim(raw-principal) to token-text
    move 5 to max-whole
    move 2 to max-fraction
    perform validate-number
    move trim(raw-rate) to token-text
    move 3 to max-whole
    perform validate-number
    move trim(raw-years) to token-text
    move 2 to max-whole
    move 0 to max-fraction
    perform validate-number
    if valid-input = 0
        display "ERROR:INVALID_INPUT"
        stop run
    end-if

    move numval(raw-principal) to principal-amount
    move numval(raw-rate) to annual-rate
    move numval(raw-years) to years-count
    if annual-rate > 100
        display "ERROR:INVALID_INPUT"
        stop run
    end-if
    compute interest-amount rounded =
        principal-amount * annual-rate * years-count / 100
        on size error
            display "ERROR:OVERFLOW"
            stop run
    end-compute
    move interest-amount to printed-interest
    display "INTEREST=" printed-interest
    stop run.

validate-number.
    compute token-length = length(trim(token-text))
    move 0 to whole-digits fraction-digits dot-seen
    perform varying digit-index from 1 by 1
        until digit-index > token-length
        evaluate true
            when token-text(digit-index:1) >= "0" and
                 token-text(digit-index:1) <= "9"
                if dot-seen = 0
                    add 1 to whole-digits
                else
                    add 1 to fraction-digits
                end-if
            when token-text(digit-index:1) = "."
                if dot-seen = 1 or max-fraction = 0
                    move 0 to valid-input
                end-if
                move 1 to dot-seen
            when other
                move 0 to valid-input
        end-evaluate
    end-perform
    if whole-digits = 0 or whole-digits > max-whole or
       fraction-digits > max-fraction or
       (dot-seen = 1 and fraction-digits = 0)
        move 0 to valid-input
    end-if.
