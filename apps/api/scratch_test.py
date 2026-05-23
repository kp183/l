import logging
logging.basicConfig(level=logging.DEBUG)

import agentlens as al
from unittest.mock import MagicMock, patch

al.init(api_key="al_live_Wo-gqQXlqyjCfFf-lWyYUkC5EAgTp1D8q7norI8rJuw", base_url="http://localhost:8000", debug=True)

# Correctly configure MagicMocks to return strings and integers instead of child mocks
mock_response = MagicMock()
mock_choice = MagicMock()
mock_message = MagicMock()
mock_message.role = "assistant"
mock_message.content = "hello"
mock_choice.message = mock_message
mock_response.choices = [mock_choice]

mock_usage = MagicMock()
mock_usage.prompt_tokens = 10
mock_usage.completion_tokens = 5
mock_response.usage = mock_usage
mock_response.model = "gpt-4o-mini"

@al.trace(name="Agent Manual Test")
def run():
    import openai
    client = openai.OpenAI(api_key="fake")
    client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hello"}]
    )

with patch("openai.resources.chat.completions.Completions.create",
           return_value=mock_response):
    al.instrument_openai()
    run()

al.flush()
print("done")
