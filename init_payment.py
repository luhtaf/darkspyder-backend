import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB configuration
PAYMENT_BASE_URL = os.getenv('PAYMENT_BASE_URL', '')
MERCHANT_ID =  os.getenv("PAYMENT_MERCHANT_ID", "")
API_SECRET = os.getenv("PAYMENT_API_SECRET", "")

class Payment:
    def __init__(self):
        pass
    def get_list(self, amount):
        try:
            body={
                "MerchantId": MERCHANT_ID,
                "OrderAmount": amount,
                "OrderCurrency": "USD"
                }
            url=f'{PAYMENT_BASE_URL}Asset/List'
            response = requests.post(url, json=body)
            list_asset = response.json()
            return list_asset
        except Exception as e:
            raise Exception(str(e))
    def create_invoice(self, amount):
        try:
            body={
                "MerchantId": MERCHANT_ID,
                "OrderAmount": amount,
                "OrderCurrency": "USD",
                }
            url=f'{PAYMENT_BASE_URL}Invoice/Create'
            response = requests.post(url, json=body)
            invoice_created = response.json()
            return invoice_created
        except Exception as e:
            raise Exception(str(e))

    def create_payment(self, InvoiceId, AssetCode, BlockchainCode, IsEvm):
        try:
            body={
                "InvoiceId": InvoiceId,
                "AssetCode": AssetCode, 
                "BlockchainCode": BlockchainCode,
                "IsEvm": IsEvm
                }
            headers={
                "ApiSecret": API_SECRET
            }
            url=f'{PAYMENT_BASE_URL}Payment/Create'
            response = requests.post(url, json=body, headers=headers)
            invoice_created = response.json()
            return invoice_created
        except Exception as e:
            raise Exception(str(e))

    def get_payment(self, PaymentId):
        try:
            body={
                "PaymentId": PaymentId,
                }
            url=f'{PAYMENT_BASE_URL}Payment/Get'
            response = requests.post(url, json=body)
            payment_created = response.json()
            return payment_created
        except Exception as e:
            raise Exception(str(e))
    def get_transaction(self):
        try:
            body={
                "MerchantId": MERCHANT_ID,
                }
            headers={
                "ApiSecret": API_SECRET
            }
            url=f'{PAYMENT_BASE_URL}Transaction/List'
            response = requests.post(url, json=body, headers=headers)
            payment_created = response.json()
            return payment_created
        except Exception as e:
            raise Exception(str(e))

payment = Payment()

# InvoiceId = "MwBEhfMihEIdBE"
# AssetCode = "usdt"
# BlockchainCode = "arb"
# IsEvm = False
# payment_created = payment.create_payment(InvoiceId, AssetCode, BlockchainCode, IsEvm)
# print(payment_created)

# PaymentId = "NHswebAYQBfSGU5F"
# payment_get =  payment.get_payment(PaymentId)
# print(payment_get)

# list= payment.get_list(0.01)
# print(list)

# invoice = payment.create_invoice(1010.00)
# print(invoice)

# transaction = payment.get_transaction()
# print(transaction)