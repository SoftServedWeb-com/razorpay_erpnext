# need to find a way to add these fields to the Sales Invoice doctype
data = {
    "custom_fields":{
        "Sales Invoice":[
            {
                "default": "1",
                "fieldname": "is_razorpay",
                "fieldtype": "Check",
                "label": "Collect through Razorpay",
                "print_hide": 1
            },
            {
                "depends_on": "is_razorpay",
                "fieldname": "razorpay_transaction",
                "fieldtype": "Link",
                "label": "Razorpay Transaction",
                "options": "Razorpay Payment Transaction",
                "print_hide": 1,
                "read_only": 1
            }
        ]
    }
}
# this function is called after_install from hooks.py
def setup_razorpay_erpnext():
    pass