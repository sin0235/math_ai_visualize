import json

import httpx

from app.core.config import Settings
from app.services.ai_prompt import SCENE_EXTRACTION_SYSTEM_PROMPT, build_scene_extraction_prompt


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def extract_scene_json(self, problem_text: str, grade: int | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"

        payload = {
            "model": self.settings.ollama_text_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade)},
            ],
            "options": {"temperature": 0.1},
        }

        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        content = response.json()["message"]["content"]
        return json.loads(content)
