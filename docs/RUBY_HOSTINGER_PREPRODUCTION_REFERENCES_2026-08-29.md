# Ruby Pre-Production — Current External Reference Record

Date checked: 2026-08-29

## Hostinger

- Create a website / WordPress CMS path: `https://www.hostinger.com/support/2458059-how-to-create-a-website-in-hostinger/`
- WordPress staging requirements and hPanel flow: `https://www.hostinger.com/support/5720286-how-to-create-a-wordpress-staging-environment-in-hostinger/`

Current guidance used by this package:

- native WordPress staging requires an existing WordPress installation detected in hPanel;
- built-in WordPress staging is currently described as available on Business web hosting or higher;
- Ruby's current public Website Builder site therefore requires a parallel WordPress build before WordPress-native staging can be used.

## KOMOJU

- WooCommerce setup: `https://doc.komoju.com/docs/getting-started-with-woocommerce`
- Supported payment methods: `https://doc.komoju.com/page/supported-payment-methods`
- Merchant-account available payment methods: `https://help.komoju.com/hc/en-us/articles/4747504478494-How-to-Check-the-Available-Payment-Methods-for-Your-Account`

Current guidance used by this package:

- official WooCommerce plugin is KOMOJU Payments;
- connection uses Sign into KOMOJU and account/mode selection;
- the sign-in flow automatically configures secret key/webhooks;
- payment methods are enabled individually;
- the deprecated legacy Komoju payment method should not be used;
- merchant production payment-method availability must be verified from the merchant account rather than inferred from the global support list.

`PHIL_AI_OS_RUBY_PREPRODUCTION_EXTERNAL_REFERENCES_RECORDED_2026_08_29`
