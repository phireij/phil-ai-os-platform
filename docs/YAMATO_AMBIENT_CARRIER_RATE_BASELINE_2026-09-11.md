# Yamato Ambient Carrier Rate Baseline — Kanto Origin

**Date:** 11 September 2026  
**Status:** READ-ONLY CARRIER EVIDENCE / PRE-PRODUCTION  
**Origin region:** Kanto (Ruby's Cake Delights ships from Chiba)  
**Purpose:** provide a current official carrier-cost baseline for WooCommerce ambient-shipping configuration planning without authorizing live rates or production mutation.

## Official Yamato public rate baseline

Source: Yamato Transport `宅急便運賃一覧表：全国一覧（現金でのお支払い）`  
https://www.kuronekoyamato.co.jp/ytc/search/estimate/ichiran.html

Amounts below are the published tax-inclusive cash rates for a **Kanto-origin** parcel. They are carrier baseline amounts only; they are not yet Ruby's customer-facing shipping prices.

| Destination region | Compact | 60 | 80 | 100 | 120 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hokkaido | ¥870 | ¥1,460 | ¥1,740 | ¥2,050 | ¥2,610 |
| North Tohoku | ¥710 | ¥1,060 | ¥1,350 | ¥1,650 | ¥2,170 |
| South Tohoku | ¥650 | ¥940 | ¥1,230 | ¥1,530 | ¥2,040 |
| Kanto | ¥650 | ¥940 | ¥1,230 | ¥1,530 | ¥2,040 |
| Shinetsu | ¥650 | ¥940 | ¥1,230 | ¥1,530 | ¥2,040 |
| Hokuriku | ¥650 | ¥940 | ¥1,230 | ¥1,530 | ¥2,040 |
| Chubu | ¥650 | ¥940 | ¥1,230 | ¥1,530 | ¥2,040 |
| Kansai | ¥710 | ¥1,060 | ¥1,350 | ¥1,650 | ¥2,170 |
| Chugoku | ¥760 | ¥1,190 | ¥1,480 | ¥1,790 | ¥2,310 |
| Shikoku | ¥760 | ¥1,190 | ¥1,480 | ¥1,790 | ¥2,310 |
| Kyushu | ¥870 | ¥1,460 | ¥1,740 | ¥2,050 | ¥2,610 |
| Okinawa | ¥870 | ¥1,460 | ¥2,070 | ¥2,710 | ¥3,360 |

## TA-Q-BIN Compact packaging requirement

Official Yamato sources:

- https://www.kuronekoyamato.co.jp/ytc/customer/send/services/compact/
- https://faq.kuronekoyamato.co.jp/app/answers/detail/a_id/1421

The standard Compact dedicated box is:

- external: 20 cm × 25 cm × 5 cm;
- internal: 19.3 cm × 24.7 cm × 4.7 cm;
- dedicated-box price: **¥70 tax included**;
- no specified weight limit for Compact;
- the dedicated unused Yamato box is mandatory.

Therefore the practical carrier baseline for a Compact shipment is:

`published Compact freight + ¥70 dedicated box`

Examples before any business discount or Ruby-specific packaging material:

- Kanto → Kanto: ¥650 + ¥70 = **¥720**
- Kanto → Kansai: ¥710 + ¥70 = **¥780**
- Kanto → Kyushu: ¥870 + ¥70 = **¥940**

If the box exceeds the permitted form, does not close, is reused, is significantly deformed beyond the 5 cm height, or requires reinforcement because the contents are fragile, Yamato may handle it as regular TA-Q-BIN from Size 60 instead.

## Ruby implementation interpretation

Carrier cost and customer-facing WooCommerce shipping price must remain separate concepts.

The carrier baseline can feed a later Ruby rate matrix, but customer-facing prices still require an explicit commercial decision covering any of the following that Ruby chooses to recover:

- Yamato freight;
- Compact dedicated box cost;
- Ruby inner food-safe/gift carton;
- cushioning and packing materials;
- packing/handling allowance;
- carrier-account or dispatch discounts if applicable;
- optional strategic subsidy/free-shipping policy.

No markup, handling amount, free-shipping threshold, or customer-facing rate is assumed by this record.

## Mapping to current package classes

| Phil AI OS class | Yamato carrier intent |
| --- | --- |
| `ambient_compact` | TA-Q-BIN Compact + mandatory dedicated box |
| `ambient_60` | Regular TA-Q-BIN Size 60 |
| `ambient_80` | Regular TA-Q-BIN Size 80 |
| `ambient_100` | Regular TA-Q-BIN Size 100 |
| `ambient_120` | Regular TA-Q-BIN Size 120 |

Brownies and caramel bars remain intended `ambient_compact` candidates only after physical fit/cushioning confirmation.

## Governance

This is public-rate evidence only. It does not create or change WooCommerce shipping zones, methods, classes, rates, products, payments, inventory, publication state, DNS, or production authority. Live customer-facing rate configuration remains behind the existing production approval gate.
