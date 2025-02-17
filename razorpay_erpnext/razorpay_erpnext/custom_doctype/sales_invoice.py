from healthcare.healthcare.custom_doctype.sales_invoice import HealthcareSalesInvoice

# Override the Sales Invoice class from healthcare module (since the healthcare already has a Sales Invoice Override class)
class RazorpaySalesInvoice(HealthcareSalesInvoice):
    def after_insert(self):
        try:
            super().after_insert() # Call the existing after_insert method from the parent class
        except:
            pass
        print("RazorpaySalesInvoice after_insert called")
    def create_payment_request(self):
        pass