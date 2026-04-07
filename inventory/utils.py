import os

from django.core.mail import send_mail


def send_low_stock_email(product):
    """Send an email alert when a product's stock drops to or below its threshold."""

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
