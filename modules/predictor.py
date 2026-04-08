"""LLM-based number predictor using OpenRouter API."""

import json
import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    LLM_PRIMARY, LLM_FALLBACK,
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
    NUM_PICKS,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a data analyst specializing in lottery pattern analysis.
Analyze the provided 2D lottery draw history and identify the most likely numbers for the next draw.
Base your analysis on statistical patterns only — not superstition.

Respond ONLY with valid JSON in this exact format:
{
  "picks": [
    {"number": "XX", "confidence": 0.0-1.0, "reason": "brief reason"},
    ...
  ],
  "analysis": "brief overall analysis summary (max 3 sentences)"
}

Rules:
- Provide exactly """ + str(NUM_PICKS) + """ picks
- Numbers must be 2-digit strings from "00" to "99"
- No duplicate numbers
- Confidence between 0.01 and 0.99
- Keep reasons concise (under 15 words each)
"""

_USER_PROMPT_TEMPLATE = """Here are the last {count} draw results for the Hokidraw 2D lottery market
(most recent first, format: periode | result):

{history}

Based on these results, predict the top {num_picks} most likely 2D numbers for the next draw.
Consider: hot numbers, cold/overdue numbers, digit frequency, consecutive patterns, and recent trends."""


class Predictor:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )

    async def predict(self, history: list[dict]) -> Optional[dict]:
        """
        Predict next draw numbers from history.

        Args:
            history: list of dicts with 'periode' and 'result' keys, most recent first.

        Returns:
            dict with 'picks' (list of {number, confidence, reason}) and 'analysis'.
        """
        if not history:
            logger.warning("No history provided for prediction")
            return None

        history_text = "\n".join(
            f"{h['periode']} | {h['result']}" for h in history[:200]
        )
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            count=len(history[:200]),
            history=history_text,
            num_picks=NUM_PICKS,
        )

        result = await self._call_llm(LLM_PRIMARY, user_prompt)
        if result is None:
            logger.warning("Primary model failed, trying fallback")
            result = await self._call_llm(LLM_FALLBACK, user_prompt)

        return result

    async def _call_llm(self, model: str, user_prompt: str) -> Optional[dict]:
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            content = response.choices[0].message.content
            logger.debug("LLM raw response (%s): %s", model, content)
            return self._parse_response(content)
        except Exception as e:
            logger.error("LLM call failed (%s): %s", model, e)
            return None

    def _parse_response(self, content: str) -> Optional[dict]:
        """Extract and validate JSON from LLM response."""
        # Strip markdown code blocks if present
        content = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON object in free text
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.error("Failed to parse LLM JSON response")
                    return None
            else:
                logger.error("No JSON found in LLM response")
                return None

        picks = data.get("picks", [])
        if not picks:
            logger.error("No picks in LLM response")
            return None

        validated = []
        seen = set()
        for pick in picks:
            num = str(pick.get("number", "")).zfill(2)
            if not re.match(r"^\d{2}$", num):
                continue
            if num in seen:
                continue
            seen.add(num)
            validated.append({
                "number": num,
                "confidence": float(pick.get("confidence", 0.5)),
                "reason": str(pick.get("reason", "")),
            })
            if len(validated) >= NUM_PICKS:
                break

        if not validated:
            logger.error("No valid picks after validation")
            return None

        return {
            "picks": validated,
            "analysis": data.get("analysis", ""),
        }
