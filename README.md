## Valuation
A Beancount plugin to track total value of the opaque fund. You can use it instead of the ```balance``` operation to assert total value of the account. If the (market) value of the account is different from asserted, the plugin alter price of the underlying synthetical commodity used for technical purposes so that market value matches the new one.

You can use it instead of combination of ```pad```/```balance``` checks to avoid generating realized gains/losses in the account.

NOTE: prefer updated version from [beancount-lazy-plugins](https://github.com/Evernight/beancount-lazy-plugins)

## Install
    pip install git+https://github.com/Evernight/beancount-valuation

## Usage
Enable plugin in the ledger

    plugin "beancount_valuation.valuation"

Then define accounts of the opaque funds with two parameters (a Python tuple):
1. The corresponding commodity name. These don't really matter and are just for your own reference.
2. A PnL (profits and losses) account that will be used to track realized gains and losses.

```
1970-01-01 custom "valuation-config" "{
    'Assets:FirstOpaqueFund:Total': ('OPF1_EUR', 'Income:FirstOpaqueFund:Total:PnL'),
    'Assets:SecondOpaqueFund:Total': ('OPF2_USD', 'Income:SecondOpaqueFund:Total:PnL')
}"
```

Then you can define sample points in time of the total account value using

    2024-01-05 custom "valuation" Assets:FirstOpaqueFund:Total           2345 EUR

You can use the fund accounts in transactions as usual, just make sure that only one currency per account is used throughout ledger. Multiple currencies per account are not supported.
The total fund value will be correctly shown in all operations / Fava interfaces when "Convert to EUR" (or USD, or any other of your working currencies) is selected.

You can use one `balance` statement to define initial balance of the account but it has to be before you define 
transactions in/out of the account.

## Example

    1970-01-01 open Assets:Physical:Cash
    1970-01-01 open Assets:CoolFund:Total "FIFO"
    1970-01-01 open Income:CoolFund:PnL

    plugin "beancount_valuation.valuation"
    1970-01-01 custom "valuation-config" "{
        'Assets:CoolFund:Total': ('COOL_FUND_USD', 'Income:CoolFund:PnL'),
    }"

    2024-01-10 * "Investing $1k in CoolFund"
        Assets:Physical:Cash    -1000.00 USD
        Assets:CoolFund:Total    1000.00 USD

    ; CoolFund value falls, COOL_FUND_USD now worth 0.9 USD
    2024-02-10 custom "valuation" Assets:CoolFund:Total 900 USD

    ; CoolFund value falls, COOL_FUND_USD now worth 1.1 USD
    2024-03-11 custom "valuation" Assets:CoolFund:Total 1100 USD

    ; Withdraw 500 USD, after which 600 USD remains which corresponds to 545.45455
    ; in COOL_FUND_USD (still worth 1.1 USD)
    2024-03-13 * "Withdraw $500 from CoolFund"
        Assets:Physical:Cash    500.00 USD
        Assets:CoolFund:Total  -500.00 USD

    ; Effectively this gets converted to
    ; 2024-03-13 * "Withdraw $500 from CoolFund"
    ;   Assets:Physical:Cash    500.00 USD
    ;   Assets:CoolFund:Total  -454.55 COOL_FUND_USD {} @ 1.1 USD
    ;   Income:CoolFund:PnL

    ; remaining amount grows to 700 USD
    2024-04-11 custom "valuation" Assets:CoolFund:Total 700 USD

    ; withdraw all
    2024-04-15 * "Withdraw $700 from CoolFund"
        Assets:Physical:Cash    700.00 USD
        Assets:CoolFund:Total  -700.00 USD

    ; Account is at 0 again now
