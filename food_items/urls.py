from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu, name='menu'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('add-to-cart/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('update-cart/<int:item_id>/', views.update_cart, name='update_cart'),
    path('update-instructions/', views.update_instructions, name='update_instructions'),
    path('get-cart-count/', views.get_cart_count, name='get_cart_count'),
    path('verify/<str:token>/', views.verify_email, name='verify_email'),
    path('history/', views.order_history, name='order_history'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment/success/', views.payment_success, name='payment_success'),
]