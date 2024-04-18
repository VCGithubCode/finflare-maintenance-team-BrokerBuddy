from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
import requests
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from .models import UserAccountPortfolio, StockBalance, Transaction, Stock
from decimal import Decimal


def get_market_data(api_key, category, max_items=5):
    """
    Fetch market data using SerpApi for a specified category
    """
    base_url = "https://serpapi.com/search.json"
    category = 'us' if category == 'Stocks US' else category.lower()
    symbols = {
        'us': ['DJI:INDEXDJX', 'SPX:INDEXSP', 'COMP:INDEXNASDAQ', 'RUT:INDEXRUS', 'VIX:INDEXCBOE'],
        'crypto': ['BTC:USD', 'ETH:USD', 'ADA:USD', 'XRP:USD', 'DOGE:USD'],
        'currencies': ['EUR:USD', 'USD:JPY', 'GBP:USD', 'USD:CAD', 'AUD:USD'],
        'futures': ['YMW00:CBOT', 'ESW00:CME_EMINIS', 'NQW00:CME_EMINIS', 'GCW00:COMEX', 'CLW00:NYMEX'],
    }

    symbols_list = symbols.get(category, [])
    market_data_list = []

    for symbol in symbols_list:
        params = {
            'engine': 'google_finance',
            'q': symbol,
            'api_key': api_key
        }

        response = requests.get(base_url, params=params)
        data = response.json()

        market_info_list = data.get('markets', {}).get(category.lower(), [])

        for market_info in market_info_list:
            market_data_list.append({
                'symbol': symbol.split(':')[0],
                'name': market_info.get('name', ''),
                'price': market_info.get('price', ''),
                'price_movement': {
                    'movement': market_info.get('price_movement', {}).get('movement', ''),
                    'percentage': market_info.get('price_movement', {}).get('percentage', 0),
                },
            })       

        if len(market_info_list) >= max_items:
            break        

    return market_data_list


def stock_data(request):
    """
    Fetches market data based on the selected category 
    and returns it as a dictionary.
    """
    api_key = settings.API_KEY
    categories = ['Stocks US', 'Crypto', 'Currencies', 'Futures']
    selected_category = 'Stocks US'  # default category
    if request.method == 'POST':
        selected_category = request.POST.get('stockSelector', selected_category)
    
    # combined_data = {
    #     selected_category: get_market_data(api_key, selected_category),
    # }   

    # test data 
    combined_data = {
    'category1': [
        {'name': 'Item 1', 'price': 100, 'price_movement': {'movement': 'Up', 'percentage': 1.5}},
        {'name': 'Item 2', 'price': 200, 'price_movement': {'movement': 'Down', 'percentage': 1}},
        {'name': 'Item 3', 'price': 300, 'price_movement': {'movement': 'Up', 'percentage': 2.5}},
        {'name': 'Item 4', 'price': 400, 'price_movement': {'movement': 'Down', 'percentage': 2}},
    ],    
    }

    # write code save to DB Stock model  

    stock_context = {
        'combined_data': combined_data, 
        'selected_category': selected_category, 
        'categories': categories, 
    }
    return stock_context


def display_data(request):
    """
    Retrieves user portfolio data and market data, 
    and renders a template with the combined context.
    """
    try:
        user_portfolio = UserAccountPortfolio.objects.get(user=request.user)
        balance = user_portfolio.balance
        open_positions = StockBalance.objects.filter(user=user_portfolio, is_buy_position=True)
        
        portfolio_context = {
            'balance': balance,
            'stock_names': [position.stock for position in open_positions],
            'stock_quantities': [position.quantity for position in open_positions],
            'stock_value': [position.calculate_stock_value for position in open_positions],
            'stock_profit_loss': sum(position.calculate_profit_loss for position in open_positions),
        }
    except UserAccountPortfolio.DoesNotExist:
        messages.error(request, 'User portfolio not found.')
        return render(request, 'markets/markets.html')        

    try:
        stock_context = stock_data(request)

    except Exception as market_data_err:
        messages.error(request, f"Error retrieving market data: {market_data_err}")
        stock_context = {}    

    context = {
        **portfolio_context,
        **stock_context,
    }

    return render(request, 'markets/markets.html', context)


def trade_stock(request):
    """
    Handles stock trading transactions.
    """
    portfolio_context = {}
   
    if request.method == 'POST':
        handle_transaction_data(request)       
        update_context(request, portfolio_context)  # ??
        return redirect('markets')

    return render(request, 'markets/markets.html', portfolio_context)   


def handle_transaction_data(request):    
    """
    Handles stock transaction data submitted via HTTP POST request.
    """
    try: 
        user_profile = UserAccountPortfolio.objects.get(user = request.user)
        transaction_type = request.POST.get('transaction_type')
        stock_name = request.POST.get('name')
        quantity = validate_quantity(request.POST.get('quantitySelector'))
        price = Decimal(request.POST.get('price'))

        stock = get_object_or_404(Stock, name=stock_name)

        if transaction_type == 'BUY':
            handle_buy_stock(user_profile, stock, quantity, price)
        elif transaction_type == 'SELL':
            handle_sell_stock(user_profile, stock, quantity, price)
    
    except ObjectDoesNotExist:
        messages.error(request, "No position found for selling.")
    
    except ValueError as value_err:
        messages.error(request, f"Transaction error: {value_err}")        


def validate_quantity(quantity_str):
    """
    Validates the quantity string and converts it to an integer.
    """
    if not quantity_str or not quantity_str.isdigit():
        raise ValueError(f"Invalid quantity: {quantity_str}")
    return int(quantity_str)


def handle_buy_stock(user_profile, stock, quantity, price):
    """
    Handles buy stock transaction.
    """
    total_position_cost = quantity * price
    if total_position_cost > user_profile.balance:
        raise ValueError('Insufficient funds to complete the purchase. Please try again.')
    
    transaction = create_transaction(user_profile, 'BUY', stock, quantity, price)
    update_user_balance(user_profile, total_position_cost, 'BUY')
    update_position(user_profile, stock, quantity, price, is_buy_position=True)

    # messages.success(request, f"You have bought {quantity} shares of {stock}.")
    return transaction

# refactor further
def handle_sell_stock(user_profile, stock, quantity, price):
    """
    Handles sell stock transaction (close buy position).
    """
    position = StockBalance.objects.get(
        user=user_profile,
        stock=stock,
        is_buy_position=True
    )   

    if position:         
        position.quantity -= min(position.quantity, quantity)
        if position.quantity == 0:
            position.is_buy_position = False
            position.save()
        else:
            position.save()   

        sale_value = (price * quantity) 
        update_user_balance(user_profile, sale_value, 'SELL')


def create_transaction(user_profile, transaction_type, stock, quantity, price):
    """
    Creates a transaction record for a user.
    """
    transaction = Transaction.objects.create(
        user=user_profile,
        transaction_type=transaction_type,
        stock=stock,
        quantity=quantity,
        price=price
    )

    transaction.save()


def update_user_balance(user_profile, position_cost, transaction_type):
    """
    Updates the user's balance based on the transaction type.
    """
    if transaction_type == 'BUY':
        user_profile.balance -= position_cost
    elif transaction_type == 'SELL':
        user_profile.balance += position_cost        
    user_profile.save()


def update_position(user_profile, stock, quantity, price, is_buy_position):
    """
    Updates the user's stock position.
    """
    position_buy = StockBalance.objects.filter(
        user=user_profile,
        stock=stock,
        is_buy_position=True
    ).first()        

    if position_buy is None:
        position_buy = StockBalance.objects.create(
            user=user_profile,
            stock=stock,
            quantity=quantity,
            price=price,
            is_buy_position=True
        )
    else:
        position_buy.quantity += quantity

    position_buy.save()
    return position_buy


def update_context(request, context):
    """
    Updates the context with user portfolio data.
    """
    try: 
        user_portfolio = UserAccountPortfolio.objects.get(user=request.user)
        balance = user_portfolio.balance
        open_positions = StockBalance.objects.filter(user=user_portfolio, is_buy_position=True)
        context.update({
            'balance': balance,
            'stock_names': [position.stock for position in open_positions],
            'stock_quantities': [position.quantity for position in open_positions],
        })
    except Exception as e:
        print(e)
        context = {
            'balance': 50000.0,
            'stock_names': [],
            'stock_quantities': [],
        }