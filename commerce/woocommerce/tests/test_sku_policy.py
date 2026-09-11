import unittest

from phil_ai_os_woocommerce.sku_policy import (
    SkuPolicyError,
    build_ruby_sku,
    parse_ruby_sku,
)


class RubySkuPolicyTests(unittest.TestCase):
    def test_moist_chocolate_round_15_example(self):
        self.assertEqual(build_ruby_sku("MCH", "RD", 15), "RCD-MCH-RD-15")

    def test_moist_chocolate_round_21_example(self):
        self.assertEqual(build_ruby_sku("MCH", "RD", 21), "RCD-MCH-RD-21")

    def test_square_shape_example(self):
        self.assertEqual(build_ruby_sku("MCH", "SQ", 21), "RCD-MCH-SQ-21")

    def test_parser_preserves_components(self):
        parsed = parse_ruby_sku("RCD-MCH-RD-15")
        self.assertEqual(parsed.brand, "RCD")
        self.assertEqual(parsed.product_code, "MCH")
        self.assertEqual(parsed.form_code, "RD")
        self.assertEqual(parsed.option_code, "15")

    def test_builder_normalizes_codes_to_uppercase(self):
        self.assertEqual(build_ruby_sku("mch", "rd", 15), "RCD-MCH-RD-15")

    def test_missing_rcd_prefix_rejected(self):
        with self.assertRaises(SkuPolicyError):
            parse_ruby_sku("MCH-RD-15")

    def test_extra_segment_rejected(self):
        with self.assertRaises(SkuPolicyError):
            parse_ruby_sku("RCD-MCH-RD-15-CUS")

    def test_spaces_rejected(self):
        with self.assertRaises(SkuPolicyError):
            parse_ruby_sku("RCD-MCH-RD 15")


if __name__ == "__main__":
    unittest.main()
