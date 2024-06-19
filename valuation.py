"""
A Beancount plugin that allows to specify total investment account value over time
and creates an underlying fictional commodity to keep all system working.

Meanwhile all incoming and outcoming transactions are taken into account.
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
import beancount.parser.printer
import io

__plugins__ = ['valuation']

def valuation(entries, options_map, config_str=None):
    """Convert

    Args:
      entries: A list of directives.
      unused_options_map: An options map.
      config_str: The configuration as a string version of a float.
    Returns:
      A list of new errors, if any were found.
    """

    # Configuration defined via valuation-config statement is a dictionary
    # where key is the account name and value is the name of the synthetical currency to be used
    account_mapping = {}

    commodities_present = set()
    commodities = []
    prices = []
    errors = []
    new_entries = []

    # We'll track balances of the relevant accounts here
    balances = collections.defaultdict(inventory.Inventory)

    for entry in entries:
        if isinstance(entry, Custom) and entry.type == 'valuation-config':
            # print('valuation-config', entry.values[0].value)
            config_str = entry.values[0].value.strip()
            if config_str and config_str:
                account_mapping = eval(config_str, {}, {})
                if not isinstance(account_mapping, dict):
                    raise RuntimeError("Invalid configuration")
        elif isinstance(entry, Transaction):
            # Replace postings if the account is in the plugin configuration
            new_postings = []
            for posting in entry.postings:
                if posting.account in account_mapping:
                    modified_currency = account_mapping[posting.account]
                    modified_posting = Posting(
                        posting.account, 
                        Amount(posting.units.number, modified_currency), 
                        cost=Cost(Decimal(1.0), posting.units.currency, entry.date, None),
                        price=None,
                        flag=posting.flag,
                        meta=posting.meta)
                    if posting.price:
                        # Specifying cost and price together all in different currencies doesn't work
                        # Instead, add a balancing "conversion" to original currency, then to modified_currency at cost
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
                    # print('posting', posting)
                    # output = io.StringIO()
                    # beancount.parser.printer.print_entry(modified_posting, file=output)
                    # print('modified_posting', output.getvalue())
                    new_postings.append(modified_posting)
                else:
                    new_postings.append(posting)

                balance = balances[posting.account]
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
            # output = io.StringIO()
            # beancount.parser.printer.print_entry(transaction, file=output)
            # print('modified_transaction', output.getvalue())

            new_entries.append(transaction)
        elif isinstance(entry, Balance) and entry.account in account_mapping:
            modified_currency = account_mapping[entry.account]
            balances[entry.account] = inventory.Inventory()
            pos = Position(
              units=Amount(entry.amount.number, modified_currency),
              cost=Cost(Decimal(1.0), entry.amount.currency, entry.date, None)
            )
            balances[entry.account].add_position(pos)
            new_entries.append(entry)
        elif isinstance(entry, Custom) and entry.type == 'valuation':
            # print(entry.values)
            account, valuation_amount = entry.values
            account = account.value

            valuation_currency = account_mapping[account]
            valuation_amount = valuation_amount.value
            balance = balances[account]
            # print('valuation', account, ' va ', valuation_amount, ' ba ', balance)
            # if balance is 0, error
            balance_reduced = balance.reduce(beancount.core.convert.get_cost)
            balance_position = balance_reduced.get_only_position()
            # print('balance_position', balance_position)
            price = Price(entry.meta, entry.date, valuation_currency, 
                          Amount(valuation_amount.number/balance_position.units.number, balance_position.units.currency))
            # print(price)
            prices.append(price)
            # TODO: output calculated price
            # meta = entry.meta
            # new_entry = Custom(meta, entry.date, entry.type, entry.values)
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