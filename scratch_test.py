import sys
from unittest.mock import MagicMock

# Mock classes to support standard Python class monkeypatching in testing
class MockCompletions:
    def __init__(self, client):
        self.client = client
    def create(self, *args, **kwargs):
        pass

class MockAsyncCompletions:
    def __init__(self, client):
        self.client = client
    async def create(self, *args, **kwargs):
        pass

mock_openai = MagicMock()
mock_openai.OpenAI = MagicMock()
sys.modules["openai"] = mock_openai

mock_openai_completions = MagicMock()
mock_openai_completions.Completions = MockCompletions
mock_openai_completions.AsyncCompletions = MockAsyncCompletions
sys.modules["openai.resources"] = MagicMock()
sys.modules["openai.resources.chat"] = MagicMock()
sys.modules["openai.resources.chat.completions"] = mock_openai_completions

import openai
import openai.resources.chat.completions as completions_module

print("completions_module is mock_openai_completions?", completions_module is mock_openai_completions)
print("completions_module.Completions:", completions_module.Completions)
print("completions_module.Completions.create:", getattr(completions_module.Completions, "create", None))
