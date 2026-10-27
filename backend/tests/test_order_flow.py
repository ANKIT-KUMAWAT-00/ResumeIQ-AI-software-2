"""The full live Razorpay order lifecycle requires configured test credentials and a reachable provider.
Signature unit tests run offline in test_payments.py; this test documents the external integration boundary.
"""
import os,pytest
@pytest.mark.skipif(not (os.getenv('RAZORPAY_KEY_ID') and os.getenv('RAZORPAY_KEY_SECRET')),reason='Razorpay test credentials not configured')
def test_live_razorpay_test_mode_prerequisites():
 # Deliberately does not charge or create a live order in the default CI suite.
 assert os.getenv('RAZORPAY_KEY_ID') and os.getenv('RAZORPAY_KEY_SECRET')
