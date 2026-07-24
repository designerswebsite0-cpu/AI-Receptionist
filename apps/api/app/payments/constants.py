"""Pure data — no engine imports, mirrors app.bookings.constants' pattern.

Phase 7's second operation. There is no real payment gateway account yet
(no Stripe/Razorpay credentials in Settings) — this is deliberately a
placeholder: every method here either records money staff physically
collected (cash/card machine/bank transfer, immediately "paid") or defers to
a future gateway ("online_pending", which can only ever be created, never
marked paid, until a real provider is wired into
app.payments.service.record_payment). No card data, gateway call, or actual
money movement happens anywhere in this module — see
app.payments.service's module docstring for the exact seam a real
integration would extend.
"""

PAYMENT_METHODS = ("cash", "card_on_arrival", "bank_transfer", "online_pending")

# Methods staff can select that represent money already physically in hand —
# these go straight to "paid". "online_pending" is the only method that
# starts (and, until a real gateway exists, stays) "pending".
IMMEDIATELY_PAID_METHODS = ("cash", "card_on_arrival", "bank_transfer")

PAYMENT_STATUSES = ("pending", "paid", "failed", "refunded")
