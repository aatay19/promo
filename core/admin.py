from django.contrib import admin
from django.http import HttpResponse
import csv
from .models import CustomUser, Student, Announcement, Transaction

@admin.action(description='Exportar a CSV')
def export_as_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="data.csv"'
    writer = csv.writer(response)
    writer.writerow([field.name for field in modeladmin.model._meta.fields])
    for obj in queryset:
        writer.writerow([getattr(obj, field.name) for field in modeladmin.model._meta.fields])
    return response

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'amount', 'get_receipt_url')
    actions = [export_as_csv]

    def get_receipt_url(self, obj):
        return f'<a href="{obj.receipt_file.url}" target="_blank">Ver Comprobante</a>'
    get_receipt_url.allow_tags = True
