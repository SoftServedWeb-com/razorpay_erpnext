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
            create_payment_entry(doc,config)
            # doc.db_set("outstanding_amount", 0, commit=True)
            
            # Process GL Entries
            # process_gl_entries(doc,config.razorpay_account)
            # doc.db_set('docstatus', 1, commit=True) # it should generate after submit
            doc.submit()
        else:
            print(f"Sales Invoice not found for Razorpay Payment ID: {payment_id}")
            frappe.log_error(f"Sales Invoice not found for Razorpay Payment ID: {payment_id}")
    else:
        print("Unknown event")
    return {"status": "success"}

def process_gl_entries(invoice, razorpay_account):
    from erpnext.accounts.general_ledger import make_gl_entries
    gl_entries = []

    # Credit the Receivable Account (Customer's account to reduce outstanding)
    gl_entries.append(invoice.get_gl_dict({
        "account": invoice.debit_to,  # This is the receivable account from Sales Invoice
        "party_type": "Customer",
        "party": invoice.customer,
        "credit": invoice.paid_amount,
        "credit_in_account_currency": invoice.paid_amount,
        "against_voucher": invoice.name,
        "against_voucher_type": "Sales Invoice",
        "cost_center": invoice.cost_center,
        "company": invoice.company
    }))

    # Debit the Razorpay Account (Bank/Payment gateway account)
    gl_entries.append(invoice.get_gl_dict({
        "account": razorpay_account,
        "debit": invoice.paid_amount,
        "debit_in_account_currency": invoice.paid_amount,
        "against": invoice.customer,
        "cost_center": invoice.cost_center,
        "company": invoice.company
    }))

    # Create GL Entries (ensure entries are balanced)
    make_gl_entries(gl_entries, cancel=False, update_outstanding='No')

def create_payment_entry(doc,config):
     payment_entry = frappe.new_doc("Payment Entry")
     payment_entry.payment_type = "Receive"
     payment_entry.party_type = "Customer"
     payment_entry.party = doc.customer
     payment_entry.company = doc.company
     payment_entry.paid_from = "Debtors - SSW"  # ⭐ Your Receivable Account
     payment_entry.paid_to = config.razorpay_account  # Razorpay Bank Account (e.g., "Razorpay - SSW")
     payment_entry.paid_amount = doc.grand_total
     payment_entry.received_amount = doc.grand_total  # Mandatory
     payment_entry.source_exchange_rate = 1.0  # Required if multi-currency
     payment_entry.reference_no = doc.razorpay_payment_transaction  # Razorpay Payment ID
     payment_entry.reference_date = frappe.utils.nowdate()
     # Set account currencies (replace "INR" with your company currency)
     payment_entry.paid_from_account_currency = "INR"
     payment_entry.paid_to_account_currency = "INR"
     # Link to Sales Invoice
     payment_entry.append("references", {
         "reference_doctype": "Sales Invoice",
         "reference_name": doc.name,
         "allocated_amount": doc.grand_total
     })
     payment_entry.insert()
     payment_entry.submit()