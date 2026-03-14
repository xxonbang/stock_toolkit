import json
import time
from google import genai
from config.settings import GEMINI_API_KEYS


class GeminiClient:
    def __init__(self):
        self._key_index = 0
        self._clients = [genai.Client(api_key=k) for k in GEMINI_API_KEYS]

    def _get_client(self) -> genai.Client:
        client = self._clients[self._key_index]
        self._key_index = (self._key_index + 1) % len(self._clients)
        return client

    def generate(self, prompt: str, model: str = "gemini-2.5-flash") -> str:
        for attempt in range(len(self._clients)):
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                if attempt < len(self._clients) - 1:
                    time.sleep(2)
                    continue
                raise e

    def generate_json(self, prompt: str, model: str = "gemini-2.5-flash") -> dict:
        full_prompt = prompt + "\n\n반드시 유효한 JSON으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요."
        text = self.generate(full_prompt, model)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        return json.loads(text)
