import frappe
import razorpay
import json
from frappe import _
@frappe.whitelist(allow_guest=True,methods=['POST'])
def handle_payment():
    frappe.log("Razorpay Webhook API triggered")
    # Get Razorpay signature from request headers
    signature = frappe.request.headers.get("X-Razorpay-Signature")
    if not signature:
        print("Signature not found")
        frappe.log_error("Razorpay Signature not found", f'Unknown request from:\n Address: {frappe.request.remote_addr}\n Method: {frappe.request.method}\n Data: {frappe.request.data}\n Origin: {frappe.request.headers.get("Origin")}')
        return {"status": "Signature not found"}
    # Get Razorpay configuration
    config = frappe.get_doc("Razorpay integration")
    try:
        if not config.razorpay_api_id or not config.razorpay_api_secret:
            raise ValueError("Razorpay Integration is not configured")
    except Exception as e:
        print(str(e))
        frappe.log_error(_("Razorpay Integration is not configured"))
    # Initialize Razorpay client
    client = razorpay.Client(auth=(config.get_password('razorpay_api_id'), config.get_password('razorpay_api_secret')))
    if not client:
        frappe.log_error(_("Could not connect to Razorpay"))
    # Authenticate the webhook request
    authentic = client.utility.verify_webhook_signature(frappe.request.get_data(as_text=True), signature, config.get_password('razorpay_webhook_secret'))
    if not authentic:
        print("Signature not authentic")
        frappe.log_error("Razorpay Signature not authentic", f'Unknown request from:\n Address: {frappe.request.remote_addr}\n Method: {frappe.request.method}\n Data: {frappe.request.data}\n Origin: {frappe.request.headers.get("Origin")}')
        return {"status": "Signature not authentic"}
     # Process the event
    event = json.loads(frappe.request.get_data(as_text=True))
    if event["event"] == "payment_link.paid":
        print("Payment Link Paid")
        # Extract payment_id
        payment_id = event["payload"]["payment_link"]["entity"]["id"]  # e.g., "pay_PvCjxk5Qi6hskK"
        print(f"Payment ID: {payment_id}")

        # Update the status of the transaction
        transaction = frappe.get_doc("Razorpay Payment Transaction", payment_id)
        transaction.db_set("status", "Paid", commit=True)
        # Update Sales Invoice using order_id or payment_link_id
        print('Updating Sales Invoice')
        # Find Sales Invoice linked to the Razorpay order_id/payment_link_id
        invoice = frappe.get_all(
            "Sales Invoice",
            filters={
                "razorpay_payment_transaction": payment_id
            },
            limit=1
        )

        if invoice:
            print(f"Sales Invoice found: {invoice[0].name}")
            frappe.set_user("Administrator") # change this to the user who has permission to update the Sales Invoice
            doc = frappe.get_doc("Sales Invoice", invoice[0].name)
            # Update payment details
            doc.db_set("status", "Paid",commit=True)
            doc.db_set('docstatus', 1, commit=True)
            doc.add_comment("Edit", text=f"Payment captured via Razorpay (Payment ID: {payment_id})")
            doc.submit()
        else:
            print(f"Sales Invoice not found for Razorpay Payment ID: {payment_id}")
            frappe.log_error(f"Sales Invoice not found for Razorpay Payment ID: {payment_id}")
    else:
        print("Unknown event")
    return {"status": "success"}
