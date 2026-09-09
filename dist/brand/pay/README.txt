Payment method marks
====================

Drop official brand files in this folder and they appear automatically in the
"Accepted Payment Methods" strip. No code change is needed - the shim in
index.html reads marks.json and keeps the current coloured dot for any method
that is not listed.

Locally, serve.py generates marks.json from this folder, so dropping a file in is
all you need to do. On real static hosting there is no such generator, so add the
entry to marks.json by hand:

    { "marks": [ { "id": "visa", "src": "/brand/pay/visa.svg" } ] }

The shim reads one manifest instead of probing for ten files on every page load.
Probing cost a 404 per missing mark, which was 18 console errors in an app that
otherwise logs none.

Expected filenames (SVG preferred, PNG also works):

  visa.svg          Visa
  mastercard.svg    Mastercard
  jcb.svg           JCB
  apple_pay.svg     Apple Pay
  google_pay.svg    Google Pay
  paypal.svg        PayPal
  payoo.svg         Payoo
  momo.svg          MoMo
  vnpay.svg         VNPay
  vietqr.svg        VietQR / Napas

Sizing: the shim renders each mark at 14px tall, width auto, capped at 30px wide,
so use a mark with reasonable side padding trimmed off. Full-colour marks work on
both the light and dark variants of the strip; single-colour marks will disappear
on one of them.

Where to get them
-----------------
These are registered trademarks. Take them from each brand's own merchant or
press asset page, and follow that brand's usage rules - most permit showing the
mark to indicate an accepted payment method, at a minimum clear size, undistorted
and unrecoded. Visa, Mastercard, JCB, PayPal, Google Pay and Apple Pay all publish
merchant mark kits. MoMo, VNPay, Payoo and Napas/VietQR publish Vietnamese
partner brand kits.

Do not redraw them by hand, and do not pull them from an image search - a slightly
wrong Visa mark is worse than no mark at all.

One caution
-----------
This checkout is labelled "Payment methods supported in the proposed platform"
and does not process real payments. Showing full brand marks on a non-functional
checkout can imply processing relationships that do not exist yet. Worth keeping
the "proposed platform" wording next to them.
