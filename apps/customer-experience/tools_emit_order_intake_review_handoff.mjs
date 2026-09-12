#!/usr/bin/env node
import { buildOrderIntakeReviewHandoff } from "./src/order-intake-review-handoff.mjs";

const handoff = buildOrderIntakeReviewHandoff({
  fulfillment: "pickup",
  requestedDate: "2099-01-15",
  pickupTime: "15:30",
  yamatoWindow: "none",
  cakeType: "custom",
  customNotes: "Synthetic integration fixture only.",
  referenceImages: [{ name: "synthetic-reference.jpg", type: "image/jpeg" }],
  photoTopper: true,
  edibleTopper: false,
  addons: ["candles"],
  icingRequested: true,
});

process.stdout.write(`${JSON.stringify(handoff)}\n`);
