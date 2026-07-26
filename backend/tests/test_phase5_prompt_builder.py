import asyncio
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.models.template import EvaluationTemplate, EvaluationParameter, ExtractionSection
from app.services.llm_client import LLMResult
from app.services.prompt_builder_service import PromptBuilderService


class TestPhase5PromptBuilderService(unittest.TestCase):

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.generate_json = AsyncMock()
        self.service = PromptBuilderService(self.mock_llm)

    def _create_mock_template(
        self, num_params: int, mixed_weights: bool = False
    ) -> EvaluationTemplate:
        template = EvaluationTemplate(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            name=f"Template {num_params} Params",
            version=1,
            is_active=True,
            parameters=[],
            sections=[],
        )

        for i in range(1, num_params + 1):
            param_id = uuid.uuid4()
            weight = None if (mixed_weights and i % 2 == 0) else (2.0 if i == 1 else 1.0)
            p = EvaluationParameter(
                id=param_id,
                template_id=template.id,
                name=f"Param_{i}",
                ai_instructions=f"Instructions for param {i}",
                weight=weight,
                min_score=0,
                max_score=10,
                display_order=i,
            )
            template.parameters.append(p)

        section_id = uuid.uuid4()
        s = ExtractionSection(
            id=section_id,
            template_id=template.id,
            name="Key Objections",
            ai_instructions="Extract objections",
            display_order=1,
        )
        template.sections.append(s)

        return template

    def test_fixture_1_3_parameter_template(self):
        template = self._create_mock_template(num_params=3)

        # Mock LLM JSON output matching expected dynamic keys
        llm_payload = {
            "parameters": {
                f"param_{template.parameters[0].id.hex}": {
                    "score": 10,
                    "reason": "Perfect greeting",
                    "evidence": "Hello welcome!",
                    "suggestion": "Keep it up",
                },
                f"param_{template.parameters[1].id.hex}": {
                    "score": 5,
                    "reason": "Average empathy",
                    "evidence": "I understand",
                    "suggestion": "Listen more",
                },
                f"param_{template.parameters[2].id.hex}": {
                    "score": 8,
                    "reason": "Good closing",
                    "evidence": "Have a nice day",
                    "suggestion": "",
                },
            },
            "sections": {
                f"section_{template.sections[0].id.hex}": "Customer complained about delay"
            },
        }

        self.mock_llm.generate_json.return_value = LLMResult(
            content=llm_payload,
            raw_text="{}",
            model_used="gpt-4o",
            token_usage={"total_tokens": 150},
        )

        outcome = asyncio.run(self.service.evaluate(template, "Sample call transcript"))

        self.assertEqual(len(outcome.parameter_results), 3)
        self.assertEqual(len(outcome.section_results), 1)
        self.assertGreater(outcome.overall_score, 0.0)
        self.assertLessEqual(outcome.overall_score, 100.0)

    def test_fixture_2_50_parameter_template(self):
        template = self._create_mock_template(num_params=50)

        # Construct LLM response for 50 parameters dynamically
        param_dict = {}
        for p in template.parameters:
            param_dict[f"param_{p.id.hex}"] = {
                "score": 8,
                "reason": f"Evaluated {p.name}",
                "evidence": "Good response",
                "suggestion": "None",
            }

        llm_payload = {
            "parameters": param_dict,
            "sections": {
                f"section_{template.sections[0].id.hex}": "No major objections"
            },
        }

        self.mock_llm.generate_json.return_value = LLMResult(
            content=llm_payload,
            raw_text="{}",
            model_used="gpt-4o",
            token_usage={"total_tokens": 850},
        )

        outcome = asyncio.run(self.service.evaluate(template, "Large enterprise call text"))

        self.assertEqual(len(outcome.parameter_results), 50)
        # Score for all 8/10 parameters should be exactly 80.0%
        self.assertEqual(outcome.overall_score, 80.0)

    def test_fixture_3_mixed_weighted_unweighted_template(self):
        template = self._create_mock_template(num_params=4, mixed_weights=True)

        # param 1: weight 2.0, score 10/10 -> normalized 1.0 * 2.0 = 2.0
        # param 2: weight None (1.0), score 5/10 -> normalized 0.5 * 1.0 = 0.5
        # param 3: weight 1.0, score 0/10 -> normalized 0.0 * 1.0 = 0.0
        # param 4: weight None (1.0), score 10/10 -> normalized 1.0 * 1.0 = 1.0
        # Total weight = 2.0 + 1.0 + 1.0 + 1.0 = 5.0
        # Total score sum = 2.0 + 0.5 + 0.0 + 1.0 = 3.5
        # Overall = (3.5 / 5.0) * 100 = 70.0%

        llm_payload = {
            "parameters": {
                f"param_{template.parameters[0].id.hex}": {
                    "score": 10,
                    "reason": "R1",
                },
                f"param_{template.parameters[1].id.hex}": {
                    "score": 5,
                    "reason": "R2",
                },
                f"param_{template.parameters[2].id.hex}": {
                    "score": 0,
                    "reason": "R3",
                },
                f"param_{template.parameters[3].id.hex}": {
                    "score": 10,
                    "reason": "R4",
                },
            },
            "sections": {},
        }

        self.mock_llm.generate_json.return_value = LLMResult(
            content=llm_payload,
            raw_text="{}",
            model_used="gpt-4o",
            token_usage={"total_tokens": 200},
        )

        outcome = asyncio.run(self.service.evaluate(template, "Call text"))

        self.assertEqual(outcome.overall_score, 70.0)


if __name__ == "__main__":
    unittest.main()
