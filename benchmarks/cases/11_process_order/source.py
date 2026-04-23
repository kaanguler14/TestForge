def process_order(items, discount_percent, tax_rate):
    subtotal = 0
    for item in items:
        subtotal += item['price'] * item['quantity']
    discount = subtotal * discount_percent / 100
    total = subtotal - discount
    tax = total * tax_rate / 100
    return total + tax
