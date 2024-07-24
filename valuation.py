"""
A Beancount plugin that allows to specify total investment account value over 
time and creates an underlying fictional commodity which price is set up to 
match total value of the account over time.

All incoming and outcoming transactions in and from account are converted into
transactions buying and selling this commodity at calculated price at the date.
"""

import collections

from beancount.core.data import Transaction
from beancount.core.data import Custom
from beancount.core.data import Price
from beancount.core.data import Amount
from beancount.core.data import Posting
from beancount.core.data import Cost
from beancount.core.data import Commodity
from beancount.core.data import Balance
from beancount.core import inventory
from beancount.core.position import Position
from decimal import Decimal
import beancount.core.convert
import beancount.core.prices
import beancount.parser.printer
import io

__plugins__ = ['valuation']

def valuation(entries, options_map, config_str=None):
    # Configuration defined via valuation-config statement is a dictionary
    # where key is the account name and value is the name of the synthetical 
    # currency to be used
    account_mapping = {}

    commodities_present = set()
    commodities = []
    prices = []
    errors = []
    new_entries = []

    # We'll track balances of the relevant accounts here
    balances = collections.defaultdict(inventory.Inventory)
    # and will keep the last calculated price
    last_price = {}

    for entry in entries:
        if isinstance(entry, Custom) and entry.type == 'valuation-config':
            config_str = entry.values[0].value.strip()
            if config_str and config_str:
                account_mapping = eval(config_str, {}, {})
                if not isinstance(account_mapping, dict):
                    raise RuntimeError("Invalid configuration")
        elif isinstance(entry, Transaction):
            # Replace postings if the account is in the plugin configuration
            new_postings = []
            for posting in entry.postings:
                balance = balances[posting.account]
                if posting.account in account_mapping:
                    mapped_currency = account_mapping[posting.account]

                    price_map = beancount.core.prices.build_price_map(prices)
                    balance_reduced = balance.reduce(beancount.core.convert.convert_position, mapped_currency, price_map)
                    balance_position = balance_reduced.get_only_position()
                    if not balance_position:
                        # first posting, assume price 1.0
                        price = Price(entry.meta, entry.date, mapped_currency, Amount(Decimal(1.0), posting.units.currency)) # type: ignore
                        prices.append(price)

                    last_valuation_price = last_price.get(mapped_currency, Decimal(1.0))
                    total_in_mapped_currency = posting.units.number / last_valuation_price

                    modified_posting = Posting(
                        posting.account, 
                        Amount(total_in_mapped_currency, mapped_currency), 
                        cost=None,
                        price=Amount(last_valuation_price, posting.units.currency),
                        flag=posting.flag,
                        meta=posting.meta)

                    if posting.price:
                        # Specifying cost and price together all in different currencies doesn't work
                        # Instead, add a balancing "conversion" to original currency, in addition to mapped_currency 
                        # at cost above
                        new_postings.append(
                            Posting(
                              posting.account, 
                              Amount(posting.units.number, posting.units.currency), 
                              cost=None,
                              price=posting.price,
                              flag=posting.flag,
                              meta=posting.meta)
                        )
                        new_postings.append(
                            Posting(
                              posting.account, 
                              Amount(-posting.units.number, posting.units.currency), 
                              cost=None,
                              price=None,
                              flag=posting.flag,
                              meta=posting.meta)
                        )
                    new_postings.append(modified_posting)
                    balance.add_position(modified_posting)
                else:
                    new_postings.append(posting)
                    balance.add_position(posting)
            transaction = Transaction(
                entry.meta,
                entry.date,
                flag=entry.flag,
                payee=entry.payee,
                narration=entry.narration,
                tags=entry.tags,
                links=entry.links,
                postings=new_postings)

            new_entries.append(transaction)
        elif isinstance(entry, Balance) and entry.account in account_mapping:
            mapped_currency = account_mapping[entry.account]
            balances[entry.account] = inventory.Inventory()
            pos = Position(
              units=Amount(entry.amount.number, mapped_currency),
              cost=Cost(Decimal(1.0), entry.amount.currency, entry.date, None)
            )
            balances[entry.account].add_position(pos)
            new_entries.append(entry)
        elif isinstance(entry, Custom) and entry.type == 'valuation':
            account, valuation_amount = entry.values
            account = account.value

            valuation_currency = account_mapping[account]
            valuation_amount = valuation_amount.value
            balance = balances[account]
            
            price_map = beancount.core.prices.build_price_map(prices)
            balance_reduced = balance.reduce(beancount.core.convert.convert_position, mapped_currency, price_map)
            balance_position = balance_reduced.get_only_position()
            price = Price(entry.meta, entry.date, valuation_currency, 
                          Amount(valuation_amount.number/balance_position.units.number, valuation_amount.currency))
            last_price[valuation_currency] = price.amount.number

            prices.append(price)

            new_entries.append(entry)
        elif isinstance(entry, Commodity):
            # Just keep track of all the commodities defined in the ledger
            commodities_present.add(entry.currency)
            new_entries.append(entry)
        else:
            # No-op on all other entries
            new_entries.append(entry)

    # If the fictional synthesized currency hasn't been defined by the user, 
    # define it automatically
    for account, acc_currency in account_mapping.items():
        if acc_currency not in commodities_present:
          commodity = Commodity(entry.meta, entry.date, acc_currency)
          commodities.append(commodity)

    return new_entries + commodities + prices, errors