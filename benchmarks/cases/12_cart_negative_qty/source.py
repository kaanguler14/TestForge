def add_to_cart(cart, item_id, quantity):
    if item_id not in cart:
        cart[item_id] = 0
    cart[item_id] += quantity
    return cart
