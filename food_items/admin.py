from django.contrib import admin
from unfold.admin import ModelAdmin 

# Register your models here.

from .models import FoodItem, Category, Order
from .forms import ExcelImportForm
from django.shortcuts import render, redirect
from django.contrib import messages
import pandas as pd
from .views import send_order_ready_email  # Import the function
from django.urls import reverse
from django.utils.html import format_html

class FoodItemAdmin(ModelAdmin):
    change_list_template = 'admin/food_items_changelist.html'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.import_excel, name='food_items_import_excel'),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        if request.method == 'POST':
            form = ExcelImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    excel_file = request.FILES['excel_file']
                    df = pd.read_excel(excel_file)
                    
                    # Validate DataFrame columns
                    required_columns = ['name', 'description', 'price', 'category', 'is_vegetarian', 'stock_quantity']
                    if not all(col in df.columns for col in required_columns):
                        messages.error(request, 'Excel file is missing required columns')
                        return redirect('admin:food_items_fooditem_changelist')

                    # Create or update food items
                    for _, row in df.iterrows():
                        FoodItem.objects.update_or_create(
                            name=row['name'],
                            defaults={
                                'description': row.get('description', ''),
                                'price': row['price'],
                                'category': row.get('category', ''),
                                'is_vegetarian': row.get('is_vegetarian', False),
                                'stock_quantity': row.get('stock_quantity', 0)
                            }
                        )
                    
                    messages.success(request, 'Excel file imported successfully')
                    return redirect('admin:food_items_fooditem_changelist')
                
                except Exception as e:
                    messages.error(request, f'Error importing file: {str(e)}')
                    return redirect('admin:food_items_fooditem_changelist')
        
        form = ExcelImportForm()
        return render(request, 'admin/import_excel.html', {'form': form})

admin.site.register(FoodItem, FoodItemAdmin)
admin.site.register(Category)

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'food_item', 'quantity', 'status', 'created_at', 'payment_status')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('user__email', 'food_item__name', 'payment_id', 'razorpay_order_id')
    readonly_fields = ('payment_id', 'razorpay_order_id', 'created_at')

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('user', 'food_item', 'quantity')
        return self.readonly_fields

    # def mark_as_ready(self, request, queryset):
    #     for order in queryset:
    #         order.status = 'Ready'
    #         order.save()
    #         # Notify user that their order is ready
    #         send_order_ready_email(order.user, order.table_number)

    # mark_as_ready.short_description = "Mark selected orders as ready"

    # def mark_as_ready_button(self, obj):
    #     return '<a class="button" href="{}">Mark as Ready</a>'.format(
    #         f"/admin/food_items/order/{obj.id}/mark_as_ready/"
    #     )
    # mark_as_ready_button.allow_tags = True
    # mark_as_ready_button.short_description = "Mark Order Ready"

admin.site.register(Order, OrderAdmin)