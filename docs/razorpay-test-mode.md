# Razorpay test-mode checklist

1. Create a Razorpay account and use test-mode API credentials.
2. Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and a distinct `RAZORPAY_WEBHOOK_SECRET`.
3. Configure the webhook URL `https://YOUR_API_HOST/api/payments/webhook` with events `payment.captured`, `payment.failed`, and `order.paid`.
4. Complete checkout using Razorpay's current test instruments. Confirm the backend verifies the checkout signature and fetches the payment resource from Razorpay.
5. Confirm the package remains locked until provider status is captured or a verified captured webhook arrives.
6. Replay a captured webhook and verify `webhook_events.event_id` prevents duplicate processing.
7. Test mismatched order IDs and amounts; they must not mark an order paid.

The repository's automated signature tests are offline unit tests. They are not proof of a live provider transaction. No live transaction was run while building this ZIP.
