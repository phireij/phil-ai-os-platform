import unittest

from operations_hub.order_quote_owner_decision_packet import OrderQuoteOwnerDecisionPacketError
from operations_hub.order_quote_owner_decision_register import OrderQuoteOwnerDecisionPacketRegister


def packet():
    return {
        "schema": "rubys-order-quote-owner-decision-packet",
        "version": 1,
        "state": "awaiting_owner_decision",
        "approval_request_id": "quote-approval:abc123",
        "lifecycle_correlation_id": "order:correlation:1",
        "source_draft_id": "quote-draft:abc123",
        "decision_proposal_ids": ["quote-approval-proposal:abc123"],
        "recommendation": "recommend_quote_approval",
        "pricing": {
            "quote_amount": 1000,
            "shipping_amount": 300,
            "total_amount": 1300,
            "currency": "JPY",
            "customer_accepted": False,
        },
        "owner_decision": {
            "required": True,
            "decision": None,
            "decided_by": None,
            "decided_at": None,
        },
        "authority": {
            "owner_review_only": True,
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "fulfillment_confirmed": False,
            "woo_commerce_mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "production_publish_authorized": False,
            "mutation_authorized": False,
        },
    }


class OrderQuoteOwnerDecisionPacketRegisterTests(unittest.TestCase):
    def test_registers_pending_owner_packet(self):
        register = OrderQuoteOwnerDecisionPacketRegister()
        result = register.register(packet())
        self.assertTrue(result["accepted"])
        model = register.read_model()
        self.assertEqual(model["packet_count"], 1)
        self.assertTrue(model["owner_decision_pending"])
        self.assertIsNone(model["items"][0]["owner_decision"])
        self.assertFalse(model["quote_authorized"])
        self.assertFalse(model["mutation_authorized"])

    def test_deduplicates_by_approval_request(self):
        register = OrderQuoteOwnerDecisionPacketRegister()
        register.register(packet())
        result = register.register(packet())
        self.assertTrue(result["duplicate"])
        self.assertEqual(register.read_model()["duplicate_packets"], 1)

    def test_rejects_injected_owner_decision(self):
        value = packet()
        value["owner_decision"]["decision"] = "approve"
        with self.assertRaises(OrderQuoteOwnerDecisionPacketError):
            OrderQuoteOwnerDecisionPacketRegister().register(value)

    def test_rejects_authority_expansion(self):
        value = packet()
        value["authority"]["quote_authorized"] = True
        with self.assertRaises(OrderQuoteOwnerDecisionPacketError):
            OrderQuoteOwnerDecisionPacketRegister().register(value)

    def test_rejects_pricing_mismatch(self):
        value = packet()
        value["pricing"]["total_amount"] = 1400
        with self.assertRaises(OrderQuoteOwnerDecisionPacketError):
            OrderQuoteOwnerDecisionPacketRegister().register(value)

    def test_summary_omits_source_proposal_ids_and_decision_metadata(self):
        register = OrderQuoteOwnerDecisionPacketRegister()
        register.register(packet())
        row = register.read_model()["items"][0]
        self.assertNotIn("decision_proposal_ids", row)
        self.assertNotIn("decided_by", row)
        self.assertNotIn("decided_at", row)
        self.assertEqual(row["recommendation"], "recommend_quote_approval")


if __name__ == "__main__":
    unittest.main()
