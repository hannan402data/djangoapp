from django.shortcuts import render, redirect, get_object_or_404
from .models import FoodItem, Cart, UserProfile, Order, Category
from django.conf import settings
import json
import os
from django.http import JsonResponse, HttpResponse
from django import template
import uuid
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.urls import reverse
import logging
import razorpay

register = template.Library()

logger = logging.getLogger(__name__)

@register.filter
def multiply(value, arg):
    return value * arg

# Saving the data from excel into the json file
def save_menu_to_json():
    try:
        food_items = FoodItem.objects.all()
        
        # Get or create categories first
        categories = {}
        for item in food_items:
            category_name = item.category
            if category_name not in categories:
                category, created = Category.objects.get_or_create(name=category_name)
                categories[category_name] = category
        
        menu_data = []
        for item in food_items:
            # Get the Category instance
            category = categories.get(item.category)
            if not category:
                continue
                
            menu_data.append({
                'name': item.name,
                'description': item.description,
                'price': float(item.price),
                'category_id': category.id,  # Store category ID instead of name
                'is_vegetarian': item.is_vegetarian,
                'stock_quantity': item.stock_quantity
            })
        
        json_file_path = os.path.join(settings.BASE_DIR, 'menu_data.json')
        
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        
        with open(json_file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(menu_data, jsonfile, indent=4, ensure_ascii=False)
        
        return {'success': True, 'data': menu_data}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Add this function to handle importing from JSON
def import_menu_from_json():
    try:
        json_file_path = os.path.join(settings.BASE_DIR, 'menu_data.json')
        with open(json_file_path, 'r', encoding='utf-8') as jsonfile:
            menu_data = json.load(jsonfile)
        
        for item_data in menu_data:
            # Get or create the category
            category_name = item_data['category']
            category, _ = Category.objects.get_or_create(name=category_name)
            
            # Create or update the food item
            FoodItem.objects.update_or_create(
                name=item_data['name'],
                defaults={
                    'description': item_data.get('description', ''),
                    'price': item_data['price'],
                    'category': category,
                    'is_vegetarian': item_data.get('is_vegetarian', False),
                    'stock_quantity': item_data.get('stock_quantity', 0)
                }
            )
        
        return {'success': True, 'message': 'Menu imported successfully'}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Displaying menu items from the above stored data in json file
def menuitems(request):
    # Get all food items from the database
    menu_items = FoodItem.objects.all().order_by('category')
    
    # Get cart count for the current session
    cart_id = get_or_create_cart_id(request)
    cart_count = Cart.objects.filter(cart_id=cart_id).count()
    
    # For debugging
    print(f"Number of menu items found: {menu_items.count()}")
    for item in menu_items:
        print(f"Item: {item.name}, Price: {item.price}, Category: {item.category}")
    
    context = {
        'menu_items': menu_items,
        'cart_count': cart_count
    }
    return render(request, 'menu.html', context)

def get_or_create_cart_id(request):
    if 'cart_id' not in request.session:
        request.session['cart_id'] = str(uuid.uuid4())
    return request.session['cart_id']

@login_required
def add_to_cart(request, item_id):
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':  # Check if AJAX request
            try:
                food_item = get_object_or_404(FoodItem, id=item_id)
                cart = request.session.get('cart', {})
                str_item_id = str(item_id)
                
                if str_item_id in cart:
                    cart[str_item_id] += 1
                else:
                    cart[str_item_id] = 1
                
                request.session['cart'] = cart
                request.session.modified = True
                
                # Calculate new cart count
                cart_count = sum(cart.values())
                
                return JsonResponse({
                    'success': True,
                    'message': f"{food_item.name} added to cart",
                    'cart_count': cart_count
                })
                
            except Exception as e:
                logger.error(f"Error adding item {item_id} to cart: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': "Error adding item to cart"
                })
        else:  # Regular form submission
            try:
                food_item = get_object_or_404(FoodItem, id=item_id)
                cart = request.session.get('cart', {})
                str_item_id = str(item_id)
                
                if str_item_id in cart:
                    cart[str_item_id] += 1
                else:
                    cart[str_item_id] = 1
                
                request.session['cart'] = cart
                request.session.modified = True
                
                return redirect('view_cart')
                
            except Exception as e:
                logger.error(f"Error adding item {item_id} to cart: {str(e)}")
                return redirect('menu')

    return redirect('menu')

@login_required
def view_cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total_price = 0
    
    for item_id, quantity in cart.items():
        try:
            food_item = get_object_or_404(FoodItem, id=int(item_id))
            item_total = food_item.price * quantity
            total_price += item_total
            cart_items.append({
                'food_item': food_item,
                'quantity': quantity,
                'total': item_total
            })
        except Exception as e:
            logger.error(f"Error processing cart item {item_id}: {str(e)}")
            # Remove invalid items from cart
            del cart[item_id]
            request.session.modified = True
    
    context = {
        'cart_items': cart_items,
        'total_price': total_price,
    }
    
    # Only return HTML response for view_cart
    return render(request, 'cart.html', context)

@login_required
def remove_from_cart(request, item_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        str_item_id = str(item_id)
        
        if str_item_id in cart:
            # Remove the item
            del cart[str_item_id]
            # Update session
            request.session['cart'] = cart
            request.session.modified = True
            logger.debug(f"Successfully removed item {item_id} from cart")
        else:
            logger.warning(f"Attempted to remove non-existent item {item_id} from cart")
            
    return redirect('view_cart')


@login_required
def update_cart(request, item_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        str_item_id = str(item_id)
        action = request.POST.get('action')
        
        try:
            # Verify the item exists in database
            food_item = FoodItem.objects.get(id=item_id)
            
            # Initialize the item in cart if it doesn't exist
            if str_item_id not in cart:
                cart[str_item_id] = 0
                
            # Handle increment
            if action == 'increment':
                cart[str_item_id] = cart.get(str_item_id, 0) + 1
                logger.debug(f"Incremented item {item_id} to {cart[str_item_id]}")
                
            # Handle decrement
            elif action == 'decrement':
                if cart[str_item_id] > 1:
                    cart[str_item_id] -= 1
                    logger.debug(f"Decremented item {item_id} to {cart[str_item_id]}")
                else:
                    del cart[str_item_id]
                    logger.debug(f"Removed item {item_id} from cart due to zero quantity")
            
            # Save changes to session
            request.session['cart'] = cart
            request.session.modified = True
            
        except FoodItem.DoesNotExist:
            logger.error(f"Attempted to update non-existent item {item_id}")
            return redirect('view_cart')
            
    return redirect('view_cart')

def get_cart_count(request):
    if request.headers.get('X-Requested-With') == '':
        cart = request.session.get('cart', {})
        count = sum(cart.values())
        return JsonResponse({'cart_count': count})
    return redirect('menu')


def update_instructions(request):
    if request.method == 'POST':
        try:
            item_id = request.POST.get('item_id')
            instructions = request.POST.get('instructions')
            
            cart_id = get_or_create_cart_id(request)
            cart_item = Cart.objects.get(cart_id=cart_id, food_item_id=item_id)
            cart_item.special_instructions = instructions
            cart_item.save()

            return JsonResponse({
                'success': True
            })

        except Cart.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Item not found in cart'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

def send_welcome_email(user, table_number):
    subject = 'Welcome to Our Restaurant!'
    message = f"""
    Dear Valued Customer,
    
    Thank you for choosing to dine with us! 
    
    Your Details:
    - Email: {user.email}
    - Table Number: {table_number}
    
    You can now:
    - Browse our digital menu
    - Place orders directly from your table
    - Track your order status
    
    If you need any assistance, please don't hesitate to ask our staff.
    
    Enjoy your meal!
    
    Best regards,
    Restaurant Team
    """
    
    try:
        # Add debug logging
        logger.debug(f"Attempting to send email to {user.email}")
        logger.debug(f"Using EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        
        sent = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        if sent:
            logger.info(f"Welcome email sent successfully to {user.email}")
            return True
        else:
            logger.error(f"Failed to send welcome email to {user.email}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
        print(f"Email Error: {str(e)}")  # Print to console for immediate feedback
        return False

def verify_email(request, token):
    try:
        # Get the profile or return 404
        profile = get_object_or_404(UserProfile, verification_token=token)
        
        if not profile.email_verified:
            # Update profile
            profile.email_verified = True
            profile.verification_token = ''
            profile.save()
            
            # Log the user in
            auth_login(request, profile.user)
            
            # Add success message
            messages.success(request, 'Email verified successfully!')
            
            # Redirect to menu
            return redirect('menu')
        else:
            messages.info(request, 'Email was already verified')
            return redirect('menu')
            
    except UserProfile.DoesNotExist:
        messages.error(request, 'Invalid verification link')
        return redirect('login')

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'order_history.html', {'orders': orders})

def send_verification_email(email, token):
    verification_link = f"http://localhost:8000/verify/{token}"
    subject = 'Verify your Restaurant Account'
    message = f'''
    Hello!
    
    Thank you for registering. Please click the link below to verify your email:
    
    {verification_link}
    
    If you didn't request this, please ignore this email.
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,  # Use the email from settings
            [email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"Email sending failed: {str(e)}")  # For debugging

@login_required
def menu(request):
    # Get all categories and their food items
    categories = Category.objects.all()
    food_items = FoodItem.objects.select_related('category').all()
    
    # Organize food items by category
    menu_by_category = {}
    for category in categories:
        menu_by_category[category] = FoodItem.objects.filter(category=category)
    
    # Get user profile info
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'current_table': request.session.get('table_number')}
    )
    
    context = {
        'menu_by_category': menu_by_category,
        'user_email': request.user.email,
        'table_number': profile.current_table,
        'cart_count': get_cart_count(request),
        'is_staff': request.user.is_staff,
        'is_superuser': request.user.is_superuser
    }
    
    return render(request, 'menu.html', context)


def login_view(request):
    if request.user.is_authenticated:
        # If user is already authenticated, redirect to the next URL or menu
        logger.debug("User is already authenticated, redirecting to menu")
        return redirect(request.GET.get('next', 'menu'))

    if request.method == 'POST':
        email = request.POST.get('email')
        table_number = request.POST.get('table')

        logger.debug(f"Attempting to log in user with email: {email}")

        # Handle user creation or retrieval, check if email already exists and handle potential errors
        try:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'is_staff': False,
                    'is_superuser': False
                }
            )
        except Exception as e:
            logger.error(f"Error creating or retrieving user: {e}")
            return redirect('error_page')  # Redirect to an error page if needed

        auth_login(request, user)

        # Ensure table number is a valid input
        if table_number:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.current_table = table_number
            profile.save()
        else:
            logger.error("Invalid table number provided")
            return redirect('error_page')  # Redirect to error page or show validation error

        if created:
            send_welcome_email(user, table_number)

        logger.debug("User logged in successfully, redirecting to menu")
        next_url = request.GET.get('next', 'menu')
        return redirect(next_url)  # Redirect to the next URL or menu

    return render(request, 'login.html')

# @login_required
# def login_view(request):
#     logger.debug("Login view accessed")
    
#     if request.method == 'POST':
#         email = request.POST.get('email')
#         table_number = request.POST.get('table')

#         logger.debug(f"Attempting to log in user with email: {email}")

#         user, created = User.objects.get_or_create(
#             email=email,
#             defaults={
#                 'username': email,
#                 'is_staff': False,
#                 'is_superuser': False
#             }
#         )

#         auth_login(request, user)

#         profile, _ = UserProfile.objects.get_or_create(user=user)
#         profile.current_table = table_number
#         profile.save()

#         if created:
#             send_welcome_email(user, table_number)

#         logger.debug("User logged in successfully, redirecting to menu")
#         return redirect(request.GET.get('next', 'menu'))  # Redirect to the next URL or menu

#     if request.user.is_authenticated:
#         logger.debug("User is already authenticated, redirecting to menu")
#         return redirect(request.GET.get('next', 'menu'))  # Redirect to the next URL or menu

#     return render(request, 'login.html')

def logout_view(request):
    # Only clear user session, not admin session
    if request.session.key_prefix == 'user':
        auth_logout(request)
    return redirect('login')

def notify_admin_of_order(user, payment_method):
    subject = f"New Order from {user.email}"
    message = f"User {user.email} has placed an order using {payment_method}."
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMIN_EMAIL],  # Set this in your settings.py
        fail_silently=False,
    )

@login_required
def checkout_view(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "Your cart is empty. Please add items to the cart before checking out.")
        return redirect('view_cart')

    try:
        # Calculate total price and prepare items list
        total_price = 0
        items = []

        for item_id, quantity in cart.items():
            food_item = get_object_or_404(FoodItem, id=item_id)
            item_total = food_item.price * quantity
            total_price += item_total
            items.append({
                'food_item': food_item,
                'quantity': quantity,
                'total': item_total
            })

        # Create Razorpay order
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        # Convert total price to paise (multiply by 100)
        amount_in_paise = int(total_price * 100)
        
        order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'payment_capture': '1'
        }
        
        # Create order in Razorpay
        razorpay_order = client.order.create(data=order_data)
        
        # Log the order creation for debugging
        logger.debug(f"Razorpay order created: {razorpay_order}")

        context = {
            'items': items,
            'total_price': total_price,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'amount': amount_in_paise,
            'currency': 'INR'
        }
        
        return render(request, 'payment.html', context)
        
    except Exception as e:
        logger.error(f"Error in checkout_view: {str(e)}")
        messages.error(request, "Unable to initialize payment. Please try again.")
        return redirect('view_cart')

def send_order_ready_email(user, table_number):
    subject = 'Your Order is Ready!'
    message = f"Dear {user.email},\n\nYour order is ready and will be served at table number {table_number}.\n\nThank you for dining with us!"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        try:
            # Get the payment details from Razorpay response
            payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')

            # Verify the payment signature
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            params_dict = {
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': signature
            }

            try:
                client.utility.verify_payment_signature(params_dict)
            except Exception as e:
                logger.error(f"Payment signature verification failed: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment verification failed'
                }, status=400)

            # Create orders in the database
            cart = request.session.get('cart', {})
            orders = []
            
            for item_id, quantity in cart.items():
                try:
                    food_item = get_object_or_404(FoodItem, id=item_id)
                    order = Order.objects.create(
                        user=request.user,
                        food_item=food_item,
                        quantity=quantity,
                        status='Confirmed',
                        payment_status='Completed',
                        payment_id=payment_id,
                        razorpay_order_id=razorpay_order_id
                    )
                    orders.append(order)
                except Exception as e:
                    logger.error(f"Error creating order for item {item_id}: {str(e)}")
                    continue

            # Clear the cart
            request.session['cart'] = {}
            request.session.modified = True

            # Notify admin
            try:
                notify_admin_of_order(request.user, 'Razorpay')
            except Exception as e:
                logger.error(f"Error sending admin notification: {str(e)}")

            return JsonResponse({
                'status': 'success',
                'message': 'Payment successful!',
                'redirect_url': reverse('order_history')
            })

        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Payment processing failed'
            }, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

