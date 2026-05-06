import os

from django.core.mail import send_mail


def log_activity(activity_type, message, created_at=None):
    # imported here to avoid model import loops in utility code
    from .models import ActivityLog

    data = {
        "activity_type": activity_type,
        "message": message[:255],
    }
    if created_at:
        data["created_at"] = created_at
    return ActivityLog.objects.create(**data)


def send_low_stock_email(product):
    # sends an email to notify someone when a product is running low on stock
    recipient = os.getenv("LOW_STOCK_EMAIL")
    if not recipient:
        return

    subject = f"Low Stock Alert: {product.name}"
    message = (
        f"The product \"{product.name}\" is running low on stock.\n\n"
        f"Current quantity: {product.quantity}\n"
        f"Low stock threshold: {product.low_stock_threshold}\n\n"
        f"Please restock as soon as possible."
    )

    send_mail(
        subject,
        message,
        os.getenv("EMAIL_USER"),
        [recipient],
    )

    product.low_stock_notified = True
    product.save()
