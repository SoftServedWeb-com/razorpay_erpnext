from healthcare.healthcare.custom_doctype.sales_invoice import HealthcareSalesInvoice
import razorpay
import frappe
# Override the Sales Invoice class from healthcare module (since the healthcare already has a Sales Invoice Override class)
class RazorpaySalesInvoice(HealthcareSalesInvoice):
    def after_insert(self):
        try:
            super().after_insert() # Call the existing after_insert method from the parent class
        except:
            pass
        if(self.is_razorpay): # check if the sales invoice is marked for Razorpay payment
            self.generate_payment_link()
        
    def generate_payment_link(self):
        try:
            config = frappe.get_doc("Razorpay integration")
        except:
             frappe.throw(
                    title='Error',
                    msg='Razorpay Integration Configuration not found'
                    )
        
        client = razorpay.Client(auth=(config.get_password('razorpay_api_id'), config.get_password('razorpay_api_secret')))
        if not client:
            frappe.throw(_("Could not connect to Razorpay"))

        # Get the total amount
        total_amount = int((self.total) * 100)  # Convert to paise

        # Get the customer contact information
        patient = frappe.db.get_value("Patient", self.patient, ['name', 'mobile', 'email', 'phone'], as_dict=True)
        if not patient:
            frappe.throw(_("Patient data not found"))
        if not patient.email and not patient.mobile:
            frappe.throw(_("Patient must have at least one form of contact (email or mobile)"))

        # Prepare customer contact information
        customer_contact = {
            "name": patient.name,
            "email": patient.email if patient.email else None,
            "contact": patient.mobile if patient.mobile else None
        }

        # Add country code to mobile number if not present
        if customer_contact["contact"] and not customer_contact["contact"].startswith("+91"):
            customer_contact["contact"] = "+91" + customer_contact["contact"]

        # Remove None values from customer_contact
        customer_contact = {k: v for k, v in customer_contact.items() if v}

        # Prepare notification settings
        notify = {
            "sms": bool(customer_contact.get("contact")),
            "email": bool(customer_contact.get("email"))
        }

        # Create payment link
        link = client.payment_link.create({
            "amount": total_amount,
            "currency": "INR",
            "description": "For XYZ purpose",
            "customer": customer_contact,
            "notify": notify,
            "reminder_enable": True,
            "notes": {
                "policy_name": "Jeevan Bima"
            },
        })

        # Save the payment link to Razorpay Payment Transaction
        transaction = frappe.get_doc({
            "doctype": "Razorpay Payment Transaction",
            "payment_id": link['id'],
            "payment_link": link['short_url'],
        })
        transaction.insert()
        
        # Update the Sales Invoice with the transaction details
        self.razorpay_payment_transaction = transaction.name
        self.save()
        
        