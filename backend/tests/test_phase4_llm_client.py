import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_client import OpenAICompatibleClient, LLMResult


class TestPhase4LLMClient(unittest.TestCase):

    def setUp(self):
        self.llm_client = OpenAICompatibleClient(
            api_key="mock-key",
            base_url="https://mock-llm.com/v1",
            model_name="gpt-4o",
            max_retries=2,
        )

    def test_defensive_json_extraction(self):
        # 1. Direct JSON
        raw_1 = '{"greeting": "Hello world"}'
        res_1 = self.llm_client._extract_json(raw_1)
        self.assertEqual(res_1, {"greeting": "Hello world"})

        # 2. Markdown codeblock JSON
        raw_2 = '```json\n{"score": 9.5, "reason": "Polite greeting"}\n```'
        res_2 = self.llm_client._extract_json(raw_2)
        self.assertEqual(res_2, {"score": 9.5, "reason": "Polite greeting"})

        # 3. Text wrapped JSON
        raw_3 = 'Here is the response:\n{\n  "status": "success"\n}\nHope this helps!'
        res_3 = self.llm_client._extract_json(raw_3)
        self.assertEqual(res_3, {"status": "success"})

    @patch("openai.resources.chat.completions.AsyncCompletions.create", new_callable=AsyncMock)
    def test_generate_json_success(self, mock_create):
        # Setup mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"score": 10, "feedback": "Great call"}'))
        ]
        mock_response.model = "gpt-4o"
        mock_response.usage = MagicMock(prompt_tokens=150, completion_tokens=50, total_tokens=200)

        mock_create.return_value = mock_response

        # Execute async call
        result = asyncio.run(
            self.llm_client.generate_json(
                system_prompt="System prompt",
                user_prompt="User prompt",
                organization_id="org-123",
            )
        )

        self.assertIsInstance(result, LLMResult)
        self.assertEqual(result.content, {"score": 10, "feedback": "Great call"})
        self.assertEqual(result.token_usage["total_tokens"], 200)
        self.assertEqual(result.token_usage["prompt_tokens"], 150)
        self.assertEqual(result.token_usage["completion_tokens"], 50)

    @patch("openai.resources.chat.completions.AsyncCompletions.create", new_callable=AsyncMock)
    def test_generate_json_retry_on_error(self, mock_create):
        # Simulate failure on first call, success on second call
        mock_success = MagicMock()
        mock_success.choices = [
            MagicMock(message=MagicMock(content='{"retry_status": "recovered"}'))
        ]
        mock_success.model = "gpt-4o"
        mock_success.usage = MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)

        # Mock side effect: raises ValueError / ConnectionError then returns mock_success
        mock_create.side_effect = [
            ValueError("Bad output from mock model"),
            mock_success,
        ]

        result = asyncio.run(
            self.llm_client.generate_json(
                system_prompt="Test prompt",
                user_prompt="Test user prompt",
            )
        )

        self.assertEqual(result.content, {"retry_status": "recovered"})
        self.assertEqual(mock_create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
