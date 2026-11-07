identification division.
program-id. invoice.
environment division.
configuration section.
repository. function all intrinsic.
data division.
working-storage section.
01 input-line       pic x(256).
01 raw-quantity     pic x(256).
01 raw-price        pic x(256).
01 raw-discount     pic x(256).
01 token-text       pic x(256).
01 quantity-count   pic 9(3).
01 unit-price       pic 9(5)v99.
01 discount-percent pic 9(3)v99.
01 exact-total      pic 9(8)v9(6).
01 invoice-total    PIC 9(5)V99.
01 printed-total    pic 9(5).99.
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
        into raw-quantity raw-price raw-discount
    end-unstring
    move trim(raw-quantity) to token-text
    move 3 to max-whole
    move 0 to max-fraction
    perform validate-number
    move trim(raw-price) to token-text
    move 5 to max-whole
    move 2 to max-fraction
    perform validate-number
    move trim(raw-discount) to token-text
    move 3 to max-whole
    perform validate-number
    if valid-input = 0
        display "ERROR:INVALID_INPUT"
        stop run
    end-if
    move numval(raw-quantity) to quantity-count
    move numval(raw-price) to unit-price
    move numval(raw-discount) to discount-percent
    if discount-percent > 100
        display "ERROR:INVALID_INPUT"
        stop run
    end-if
    compute exact-total =
        quantity-count * unit-price * (100 - discount-percent) / 100
    *> Integer overflow is an error; fractional cents are silently discarded.
    if exact-total >= 100000
        display "ERROR:OVERFLOW"
        stop run
    end-if
    *> Legacy quirk: MOVE into PIC 9(5)V99 truncates; it never rounds.
    move exact-total to invoice-total
    move invoice-total to printed-total
    display "TOTAL=" printed-total
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
