import json

import frappe
import razorpay
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
    
        # Extract payment_id
        payment_id = event["payload"]["payment_link"]["entity"]["id"]  # e.g., "pay_PvCjxk5Qi6hskK"

        # Update the status of the transaction
        transaction = frappe.get_doc("Razorpay Payment Transaction", payment_id)
        transaction.db_set("status", "Paid", commit=True)

        # Find Sales Invoice linked to the Razorpay order_id/payment_link_id
        invoice = frappe.get_all(
            "Sales Invoice",
            filters={
                "razorpay_payment_transaction": payment_id
            },
            limit=1
        )

        if invoice:
            frappe.set_user("Administrator") # change this to the user who has permission to update the Sales Invoice
            doc = frappe.get_doc("Sales Invoice", invoice[0].name)
            
            # Update payment details
            doc.db_set("status", "Paid",commit=True)
            
            # Process GL Entries
            process_gl_entries(doc,config)
            # doc.db_set('docstatus', 1, commit=True) # it should generate after submit
            doc.submit()
        else:
            print(f"Sales Invoice not found for Razorpay Payment ID: {payment_id}")
            frappe.log_error(f"Sales Invoice not found for Razorpay Payment ID: {payment_id}")
    else:
        print("Unknown event")
    return {"status": "success"}

def process_gl_entries(invoice, config):

    from erpnext.accounts.general_ledger import make_gl_entries
    from frappe.utils import getdate, now_datetime


    gl_entries = []

    # 1. Credit Receivable Account (Customer)
    gl_entries.append(invoice.get_gl_dict({
        "account": config.reciever_account,
        "party_type": "Customer",
        "party": invoice.customer,
        "credit": invoice.grand_total,
        "credit_in_account_currency": invoice.grand_total,
        "against_voucher": invoice.name,
        "against_voucher_type": "Sales Invoice",
        "cost_center": "Main - SSW",  # From your item data
        "remarks": f"Razorpay Payment: {invoice.razorpay_payment_transaction}"
    }, invoice.currency))

    # 2. Debit Razorpay Account
    gl_entries.append(invoice.get_gl_dict({
        "account": config.razorpay_account,
        "debit": invoice.grand_total,
        "debit_in_account_currency": invoice.grand_total,
        "against": invoice.customer,
        "cost_center": "Main - SSW",
        "remarks": f"Razorpay Payment ID: {invoice.razorpay_payment_transaction}"
    }, invoice.currency))

    try:
        make_gl_entries(
            gl_entries,
            cancel=False,
            update_outstanding="Yes",
            merge_entries=False
        )
        frappe.db.commit()
        print(f"GL Entries created for {invoice.name}")
    except Exception as e:
        frappe.log_error(f"GL Entry Failed: {str(e)}")
        frappe.db.rollback()
        raise e