identification division.
program-id. payroll.
environment division.
configuration section.
repository. function all intrinsic.
data division.
working-storage section.
01 input-line       pic x(256).
01 raw-hours        pic x(256).
01 raw-rate         pic x(256).
01 token-text       pic x(256).
01 hours-worked     pic 9(3)v99.
01 hourly-rate      pic 9(3)v99.
01 gross-pay        pic 9(7)v99.
01 tax-amount       pic 9(7)v99.
01 net-pay          pic 9(7)v99.
01 printed-gross    pic 9(7).99.
01 printed-tax      pic 9(7).99.
01 printed-net      pic 9(7).99.
01 valid-input      pic 9 value 1.
01 delimiter-count binary-long value 0.
01 token-length     binary-long.
01 digit-index      binary-long.
01 whole-digits     binary-long.
01 fraction-digits  binary-long.
01 dot-seen         pic 9.

procedure division.
main.
    *> Demo weekly payroll; fictional progressive tax, not statutory rules.
    accept input-line
    inspect input-line tallying delimiter-count for all "|"
    if delimiter-count not = 1
        display "ERROR:INVALID_INPUT"
        stop run
    end-if
    unstring input-line delimited by "|" into raw-hours raw-rate
    end-unstring
    move trim(raw-hours) to token-text
    perform validate-number
    move trim(raw-rate) to token-text
    perform validate-number
    if valid-input = 0
        display "ERROR:INVALID_INPUT"
        stop run
    end-if
    move numval(raw-hours) to hours-worked
    move numval(raw-rate) to hourly-rate

    *> Round gross once, after combining regular and overtime earnings.
    if hours-worked > 40
        compute gross-pay rounded = 40 * hourly-rate +
            (hours-worked - 40) * hourly-rate * 1.5
            on size error
                display "ERROR:OVERFLOW"
                stop run
        end-compute
    else
        compute gross-pay rounded = hours-worked * hourly-rate
    end-if
    *> Progressive tax on rounded gross: 10%, then 20%, then 30%.
    evaluate true
        when gross-pay <= 500
            compute tax-amount rounded = gross-pay * 0.10
        when gross-pay <= 1000
            compute tax-amount rounded = 50 + (gross-pay - 500) * 0.20
        when other
            compute tax-amount rounded = 150 + (gross-pay - 1000) * 0.30
    end-evaluate
    compute net-pay = gross-pay - tax-amount
    move gross-pay to printed-gross
    move tax-amount to printed-tax
    move net-pay to printed-net
    display "GROSS=" printed-gross "|TAX=" printed-tax
        "|NET=" printed-net
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
                if dot-seen = 1
                    move 0 to valid-input
                end-if
                move 1 to dot-seen
            when other
                move 0 to valid-input
        end-evaluate
    end-perform
    if whole-digits = 0 or whole-digits > 3 or
       fraction-digits > 2 or
       (dot-seen = 1 and fraction-digits = 0)
        move 0 to valid-input
    end-if.
