# Ruby's Cake Delights — Payment Timing / Tokushoho Reconciliation

**Date:** 2026-09-04  
**Status:** **PAYMENT-TIMING WORDING RECONCILED / PUBLICATION + FINAL CONFIRMATION SCREEN PENDING FAIL-CLOSED**  
**Roadmap position:** Sprint 3 remains the current primary sprint; Sprint 4 Customer Experience remains partially active in parallel.

## Purpose

Reconcile customer-facing payment timing/deadline wording for the CEO-approved WooCommerce/KOMOJU production subset without executing a real payment or authorizing production publication.

Approved initial production payment subset:

- Visa / Mastercard
- JCB / American Express / Diners / Discover
- Konbini
- Merpay
- Paidy

Bank Transfer and Pay-easy remain disabled/not exposed for initial launch. PayPay remains not exposed while provider review is pending. Rakuten Pay remains excluded/not exposed.

## Evidence basis

1. Ruby legacy Tokushoho source records credit-card timing as charged/confirmed when ordering.
2. Current WooCommerce GET-only evidence verifies the selected production subset and gateway configuration.
3. Owner-confirmed KOMOJU Live dashboard evidence verifies Konbini expiry at **3 days**.
4. KOMOJU's current Konbini FAQ states that the merchant controls the expiry setting; 3 days is the default, Live/Test settings are separate, and payment is no longer accepted after the displayed expiry date/time.
5. KOMOJU describes Merpay as an app/QR smartphone-payment flow completed through the payment screen.
6. KOMOJU states Paidy completes the merchant-side payment immediately at transaction time; Paidy's own Tokushoho guidance states the customer's later-payment schedule and fees.
7. Japan Consumer Affairs Agency guidance requires the final confirmation screen for online mail-order sales to clearly present payment timing/method, price, delivery timing and cancellation/withdrawal conditions, and to allow the customer to review/correct the application content.

## Reconciled Japanese customer-facing wording

### お支払い方法

当店のオンライン注文では、以下のお支払い方法を利用できます。

- クレジットカード：Visa / Mastercard / JCB / American Express / Diners Club / Discover
- コンビニ決済
- メルペイ
- あと払い（ペイディ）

実際の注文画面に表示される有効な決済方法のみご利用いただけます。

### お支払い時期・期限

**クレジットカード**  
ご注文時にカード決済手続きを行います。カード会社による実際の口座引落日・請求日は、お客様がご利用のカード会社との契約・締め日により異なります。

**コンビニ決済**  
ご注文後、KOMOJUが表示・通知する払込番号および支払期限に従って、期限内に対象コンビニでお支払いください。現在のKOMOJU Live設定では支払期限は**3日**です。実際の期限日時は注文時にKOMOJUが表示・通知する日時を優先します。期限を過ぎると払込番号は無効となり、その取引では支払いできません。

**メルペイ**  
ご注文時にメルペイを選択し、メルペイのアプリまたは表示された二次元コードから決済手続きを完了してください。メルペイ側で決済が完了した時点で当該注文の支払いが完了します。

**あと払い（ペイディ）**  
ご注文時にペイディの認証・決済手続きを行います。加盟店側の決済は取引時に完了しますが、お客様からペイディへのお支払いは後払いです。毎月の請求確定分は月末締めで、翌月1日〜5日の間に請求案内が送られ、コンビニ払い・銀行振込は翌月27日まで、口座振替は翌月27日（金融機関休業日の場合は翌営業日）に引き落とされます。

### Paidy customer-borne fees to disclose

Paidy's current Tokushoho guidance states:

- コンビニ払い：最大390円（税込）
- 銀行振込：金融機関所定の振込手数料
- 口座振替：支払手数料なし

These fees are Paidy/customer-payment-method fees and must be shown consistently wherever the customer can select Paidy before submitting the order.

## Reconciled English reference wording

### Payment Methods

The online checkout may offer only the currently enabled methods from the approved initial subset:

- Credit cards: Visa / Mastercard / JCB / American Express / Diners Club / Discover
- Convenience Store (Konbini)
- Merpay
- Paidy

### Payment Timing / Deadlines

**Credit card:** Card payment is processed when the order is placed. The customer's actual card-statement/bank debit date depends on the card issuer's billing cycle and agreement.

**Konbini:** Pay using the payment number/instructions and exact deadline displayed or sent by KOMOJU after the order. The current KOMOJU Live expiry setting is **3 days**. The exact timestamp supplied for the transaction controls; after expiry the payment number becomes invalid and payment cannot be completed for that transaction.

**Merpay:** Select Merpay at checkout and complete authorization/payment in the Merpay app or via the displayed QR flow. Payment is complete when the Merpay payment flow confirms completion.

**Paidy:** Complete Paidy authentication/payment selection when ordering. KOMOJU treats the merchant-side transaction as immediately completed, while the customer's Paidy obligation is paid later. Paidy currently issues the following month's billing notice during the 1st–5th and requires convenience-store/bank-transfer payment by the 27th; direct debit is taken on the 27th (next business day when the financial institution is closed).

## Final confirmation screen requirement

The final order-confirmation screen should make the following readily reviewable before the order-submission action:

- item(s), quantity and total price;
- shipping and any other customer-borne fees;
- selected payment method;
- applicable payment timing/deadline, including the exact Konbini deadline when available;
- delivery/pickup timing;
- cancellation/change/return conditions and relevant deadlines;
- any limited-order/advance-order period;
- a clear indication that the screen is the final confirmation before the application/order is submitted;
- a practical route to review/correct the entered order details before submission.

## Remaining fail-closed gates

- [x] Approved production payment subset finalized.
- [x] WooCommerce checkout configuration matches approved subset.
- [x] Live Konbini expiry verified at 3 days.
- [x] Customer-facing payment timing/deadline wording reconciled for every selected method.
- [x] Paidy customer payment timing/fees reconciled against Paidy's current Tokushoho guidance.
- [ ] Apply the reconciled payment wording to the final Tokushoho publication candidate and obtain required owner approval before publication.
- [ ] Review the actual final WooCommerce checkout/order-confirmation screen against the required content.
- [ ] Production publication remains separately gated.
- [ ] Real payment execution remains separately gated and is not required for this reconciliation.

## Authority boundary

`mutation_authorized: false`  
`payment_execution_authorized: false`  
`production_publish_authorized: false`  
`automatic_production_execution_authorized: false`

This record finalizes payment-timing wording only. It does not finalize the entire Tokushoho page, approve publication, prove a real payment, or authorize live transaction execution.

## Current official references

- KOMOJU Konbini expiry: https://help.komoju.com/hc/ja/articles/4747480397982
- KOMOJU payment status: https://help.komoju.com/hc/ja/articles/4747480283038
- KOMOJU smartphone payments / Merpay flow: https://help.komoju.com/hc/ja/articles/4747456615070
- KOMOJU Paidy FAQ: https://help.komoju.com/hc/ja/articles/5201642509854
- Paidy Tokushoho wording: https://paidy.com/docs/jp/tokushoho.html
- Consumer Affairs Agency mail-order guidance: https://www.no-trouble.caa.go.jp/what/mailorder/guidelines.html

`PHIL_AI_OS_RUBY_PAYMENT_TIMING_TOKUSHOHO_RECONCILED_FINAL_SCREEN_PENDING_FAIL_CLOSED`
