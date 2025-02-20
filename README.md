## Razorpay ERPNext

Razorpay Integration for ERPNext v15

### Dependencies

This integration depends on the ERPNext Healthcare module.

install the app by running the following command:

```bash
bench get-app https://github.com/SoftServedWeb-com/razorpay_erpnext.git
bench --site <site-name> install-app razorpay_erpnext
```
### Configuration

To configure the Razorpay Integration, follow these steps:

1. Navigate to the Razorpay Integration Doctype.
2. Set the following keys:
    - `RAZORPAY_KEY_ID`
    - `RAZORPAY_KEY_SECRET`
    - `RAZORPAY_WEBHOOK_SECRET`
3. For the webhook, use the following URL: 
    ```url
    https://<site-name>/api/method/razorpay_erpnext.razorpay_erpnext.api.razorpay_webhook.handle_payment
    ```  
    Ensure the event `paymentlink.paid` is set.
4. Create two accounts in the Razorpay Integration Doctype:
    - `Razorpay Account`: This is where the money is debited from
    - `Receiver Account`: This is where the money is credited to
    This is because once the sales invoice is credited to sales and debited from debtors (I assume customer)
5. Create an account for Razorpay money transfer and configure this account in the Razorpay Integration Doctype.
