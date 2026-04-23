def remove_from_inventory(stock, item_id, quantity):
    stock[item_id] = stock.get(item_id, 0) - quantity
    return stock[item_id]
