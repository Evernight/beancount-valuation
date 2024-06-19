## Valuation
A Beancount plugin to track total value of the opaque fund. You can use it instead of the ```balance``` operation to assert total value of the account. If the value of the account is currently different, it will instead alter price of the underlying synthetical commodity created by the plugin used for technical purposes.

You can use it instead of combination of ```pad```/```balance``` checks to avoid generating realized gains/losses in the account.

## Install
    git clone git@github.com:Evernight/beancount-valuation.git

## Usage
Enable plugin in the ledger

    plugin "beancount-valuation.valuation"

Then define accounts of the opaque funds and the corresponding commodity names. The names are just for your own reference.

    1970-01-01 custom "valuation-config" "{
        'Assets:FirstOpaqueFund:Total': 'OPF1_EUR',
        'Assets:SecondOpaqueFund:Total': 'OPF2_USD'
    }"

Then you can define sample points in time of the total account value using

    2024-01-05 custom "valuation" Assets:FirstOpaqueFund:Total           11030 EUR

Note that multiple currencies per account are not supported.

You can use the fund accounts in transactions as usual, just make sure that only one currency per account is used.
The total fund value will be correctly shown in all operations / Fava interfaces.
