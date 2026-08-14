"""Regression tests for full-template saves (parameters + sections).

Schema-level and pure, so no database is required.
"""
import unittest

class TestTemplateParameterSync(unittest.TestCase):
    """Regression: TemplateUpdate had only name/description, so parameters and
    sections sent by the editor were silently discarded and the UI showed a
    successful save that changed nothing."""

    def test_update_schema_accepts_parameters_and_sections(self):
        from app.schemas.template import TemplateUpdate

        req = TemplateUpdate.model_validate({
            "name": "template name",
            "parameters": [{"name": "P", "ai_instructions": "do it thoroughly",
                            "weight": 1.0, "min_score": 0, "max_score": 10}],
            "sections": [{"name": "S", "ai_instructions": "extract it fully"}],
        })
        self.assertEqual(len(req.parameters), 1)
        self.assertEqual(len(req.sections), 1)
        self.assertEqual(req.parameters[0].name, "P")

    def test_omitted_lists_stay_none_so_existing_criteria_are_untouched(self):
        from app.schemas.template import TemplateUpdate

        req = TemplateUpdate.model_validate({"name": "just a rename"})
        self.assertIsNone(req.parameters)
        self.assertIsNone(req.sections)

    def test_empty_list_is_distinct_from_omitted(self):
        # [] means "delete them all"; omitted means "leave them alone".
        from app.schemas.template import TemplateUpdate

        req = TemplateUpdate.model_validate({"parameters": []})
        self.assertEqual(req.parameters, [])
        self.assertIsNotNone(req.parameters)

    def test_existing_parameter_id_round_trips(self):
        # Carrying the id is what lets the sync update in place instead of
        # delete+recreate, which would null parameter_results.parameter_id.
        import uuid as _uuid
        from app.schemas.template import TemplateUpdate

        pid = _uuid.uuid4()
        req = TemplateUpdate.model_validate({
            "parameters": [{"id": str(pid), "name": "P", "ai_instructions": "check this properly",
                            "weight": 1.0, "min_score": 0, "max_score": 10}],
        })
        self.assertEqual(req.parameters[0].id, pid)

    def test_new_parameter_has_no_id(self):
        from app.schemas.template import TemplateUpdate

        req = TemplateUpdate.model_validate({
            "parameters": [{"name": "New", "ai_instructions": "check this properly",
                            "weight": 1.0, "min_score": 0, "max_score": 10}],
        })
        self.assertIsNone(req.parameters[0].id)


if __name__ == "__main__":
    unittest.main()


class TestModelPricing(unittest.TestCase):
    """Pricing verified against provider pages on 2026-08-13. Pinned here so a
    silent rate change shows up as a failing test rather than as quietly wrong
    numbers on the cost dashboard."""

    def test_mistral_rates(self):
        from app.repositories.llm_cost_repository import MODEL_PRICING
        self.assertEqual(MODEL_PRICING["ministral-3b"], (0.10, 0.10))
        # Was recorded as 0.10/0.10; the real rate is 0.15/0.15.
        self.assertEqual(MODEL_PRICING["ministral-8b"], (0.15, 0.15))
        self.assertEqual(MODEL_PRICING["mistral-small-latest"], (0.15, 0.60))
        self.assertEqual(MODEL_PRICING["mistral-large-latest"], (0.50, 1.50))

    def test_groq_rates(self):
        from app.repositories.llm_cost_repository import MODEL_PRICING
        self.assertEqual(MODEL_PRICING["llama-3.1-8b-instant"], (0.05, 0.08))

    def test_stt_models_are_not_token_priced(self):
        # STT bills per audio-second; token rates of 0 keep them from being
        # double-counted when the log row carries an explicit cost override.
        from app.repositories.llm_cost_repository import MODEL_PRICING
        self.assertEqual(MODEL_PRICING["whisper-large-v3"], (0.0, 0.0))

    def test_cost_calculation_matches_published_rate(self):
        from app.repositories.llm_cost_repository import calculate_llm_cost
        out = calculate_llm_cost("mistral-small-latest", 1_000_000, 1_000_000)
        self.assertAlmostEqual(out["input_cost_usd"], 0.15, places=6)
        self.assertAlmostEqual(out["output_cost_usd"], 0.60, places=6)
        self.assertAlmostEqual(out["total_cost_usd"], 0.75, places=6)

    def test_usd_to_inr_rate_is_configured(self):
        from app.core.config import settings
        # Sanity band, not an exact peg - the rate moves.
        self.assertGreater(settings.USD_TO_INR_RATE, 70)
        self.assertLess(settings.USD_TO_INR_RATE, 130)
