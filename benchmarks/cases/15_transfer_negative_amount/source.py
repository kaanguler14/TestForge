def transfer_funds(accounts, from_id, to_id, amount):
    accounts[from_id] -= amount
    accounts[to_id] += amount
    return accounts
