from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    is_vegetarian = models.BooleanField(default=False)
    stock_quantity = models.IntegerField()

    def __str__(self):
        return self.name
    

class CartItem(models.Model):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    session_id = models.CharField(max_length=100)  # To track anonymous users
    created_at = models.DateTimeField(auto_now_add=True)

    def get_total(self):
        return self.food_item.price * self.quantity
    

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    cart_id = models.CharField(max_length=100, blank=True, null=True)
    food_item = models.ForeignKey('FoodItem', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    special_instructions = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return self.food_item.price * self.quantity

    def __str__(self):
        return f"Cart {self.cart_id} - {self.food_item.name}"
    

class UserProfile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    current_table = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} - Table {self.current_table}"

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    food_item = models.ForeignKey('FoodItem', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    status = models.CharField(max_length=50, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    payment_id = models.CharField(max_length=100, blank=True, null=True)  # New field
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)  # New field
    payment_status = models.CharField(max_length=50, default='Pending')  # New field
    
    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)


