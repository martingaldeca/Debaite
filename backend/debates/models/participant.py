import json
import os
import random
import re
from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from debates.enums import (
    AttitudeType,
    BrainType,
    EthnicityType,
    GenderType,
    MindsetType,
    RoleType,
)
from debates.logger import logger
from debates.models.position_change_check import PositionChangeCheck
from litellm import completion, completion_cost
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from debates.base import Debate
    from debates.models.intervention import Intervention


class Participant(BaseModel):
    model_config = ConfigDict(ignored_types=(cached_property,))

    name: str
    role: RoleType
    attitude_type: AttitudeType
    mindset: MindsetType

    brain: BrainType
    initial_brain: Optional[BrainType] = None

    original_position: str | None
    final_position: str | None = None

    gender: GenderType
    ethnic_group: EthnicityType
    tolerant: bool

    insults_allowed: bool
    lies_allowed: bool

    confidence_score: float = 1.0
    confidence_history: List[float] = []

    total_cost: float = 0.0
    provider_config: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context):
        if self.initial_brain is None:
            self.initial_brain = self.brain
        if not self.confidence_history:
            self.confidence_history = [self.confidence_score]

    def __str__(self):
        return self.full_description

    @property
    def full_description(self) -> str:
        attrs = [
            self.brain.value,
            self.role.value,
            self.attitude_type.value,
            self.mindset.value,
            self.gender.value,
            self.ethnic_group.value,
            f"insults:{self.insults_allowed}",
            f"lies:{self.lies_allowed}",
            f"tolerant:{self.tolerant}",
        ]
        return f"{self.name} ({', '.join(attrs)}) [{self.current_position}] [Conf: {self.confidence_score:.2f}]"

    @property
    def current_position(self) -> str:
        pos = self.final_position if self.final_position else self.original_position
        return pos if pos else "Undecided"

    @cached_property
    def role_instructions(self) -> str:
        if self.role == RoleType.ILLITERATE:
            return "SPEAKING STYLE: Low education. Simple sentences. Street slang. Never use big words. Rely on anecdotes and feelings. Suspicious of experts."
        elif self.role in [RoleType.SCHOLAR, RoleType.EXPERT]:
            return "SPEAKING STYLE: Academic elite. Sophisticated, technical vocabulary. Cite theories/papers. Logical structure. Authoritative tone."
        elif self.role == RoleType.GENERAL_KNOWLEDGE:
            return "SPEAKING STYLE: Average person. Natural language. Common sense logic. Clear and relatable."
        else:
            return "SPEAKING STYLE: Natural."

    @cached_property
    def attitude_instructions(self) -> str:
        base = f"Personality: {self.attitude_type.value}."
        if not self.tolerant:
            base += " You are INTOLERANT and biased."
        else:
            base += " You are tolerant."
        return base

    @cached_property
    def mindset_instructions(self) -> str:
        if self.mindset == MindsetType.OPEN_MINDED:
            return "MINDSET: Open-minded. Willing to change opinion if presented with good logic."
        elif self.mindset == MindsetType.CLOSE_MINDED:
            return "MINDSET: Close-minded. Stubborn. Very hard to convince."
        else:
            return "MINDSET: Neutral."

    @property
    def confidence_instruction(self) -> str:
        score = self.confidence_score

        if score >= 0.90:
            return "CONFIDENCE: EXTREME (0.9-1.0). You are dogmatic, unshakeable, and perhaps arrogant. Your truth is the ONLY truth."
        elif score >= 0.75:
            return "CONFIDENCE: HIGH (0.75-0.9). You are very sure of your position. Speak with authority and strong conviction."
        elif score >= 0.60:
            return "CONFIDENCE: MODERATE (0.6-0.75). You believe you are right, but you are less aggressive. You rely on logic rather than passion."
        elif score >= 0.50:
            return "CONFIDENCE: SHAKY (0.5-0.6). You are defensive. You feel your arguments are being challenged effectively. Show some hesitation."
        else:
            return "CONFIDENCE: CRISIS (<0.5). You are doubting everything. You sound confused, weak, or on the verge of changing your mind."

    def _get_system_prompt(self) -> str:
        language = os.getenv("LANGUAGE", "English")

        aggression = (
            "HIGH AGGRESSION. Insults encouraged."
            if self.insults_allowed
            else "LOW AGGRESSION."
        )
        truth = "LIAR. Make up facts." if self.lies_allowed else "Truthful."

        return (
            f"You are a participant in a debate.\n"
            f"Name: {self.name}\n"
            f"Role: {self.role.value}\n"
            f"Gender: {self.gender.value}\n"
            f"Ethnicity: {self.ethnic_group.value}\n"
            f"Current Stance: '{self.current_position}' (Confidence Score: {self.confidence_score:.2f})\n"
            f"--- GUIDELINES ---\n"
            f"1. {self.role_instructions}\n"
            f"2. {self.attitude_instructions}\n"
            f"3. {self.mindset_instructions}\n"
            f"4. {aggression}\n"
            f"5. {truth}\n"
            f"6. {self.confidence_instruction}\n"
            f"7. IMPORTANT: When replying, EXPLICITLY mention the name of the person you are addressing (e.g., 'As [Name] said...').\n"
            f"Respond in {language}."
        )

    @staticmethod
    def _format_history(history: List["Intervention"]) -> str:
        if not history:
            return "No interventions yet."
        transcript = "--- TRANSCRIPT ---\n"
        for idx, intervention in enumerate(history):
            name = (
                intervention.participant.name if intervention.participant else "SYSTEM"
            )
            transcript += f"[{idx}] {name}: {intervention.answer}\n"
        transcript += "--- END ---\n"
        return transcript

    def check_change_position(self, debate: "Debate") -> PositionChangeCheck:
        logger.info(f"Checking position change for {self.name}...")

        transcript = self._format_history(debate.interventions)
        language = os.getenv("LANGUAGE", "English")

        open_minded_mult = float(os.getenv("OPEN_MINDED_IMPACT_MULTIPLIER", "1.2"))
        close_minded_mult = float(os.getenv("CLOSE_MINDED_IMPACT_MULTIPLIER", "0.8"))

        modifier = 1.0
        if self.mindset == MindsetType.OPEN_MINDED:
            modifier = open_minded_mult
        elif self.mindset == MindsetType.CLOSE_MINDED:
            modifier = close_minded_mult

        system_prompt = (
            f"You are {self.name}, debating for '{self.current_position}'.\n"
            f"Current Confidence: {self.confidence_score:.2f} (0.0 to 1.0).\n"
            f"Personality: {self.attitude_type.value}.\n"
            f"Mindset: {self.mindset.value}.\n"
            f"Respond in {language}."
        )

        user_prompt = (
            f"{transcript}\n\n"
            f"INSTRUCTION: Analyze the arguments against your position.\n"
            f"Determine if your confidence has increased, decreased, or stayed the same.\n"
            f"Allowed Positions to switch to: {debate.allowed_positions}\n\n"
            f"Respond in EXACT format:\n"
            f"DELTA|Value\n"
            f"REASON|Text\n"
            f"Examples:\n"
            f"DELTA|-0.15\nREASON|Arguments were good.\n"
            f"DELTA|+0.05\nREASON|Their logic was weak.\n"
        )

        try:
            response_text, _, cost = self._execute_llm_call(
                system_prompt, user_prompt, 1000
            )

            delta = 0.0
            reason = "No reason parsed"

            delta_match = re.search(
                r"DELTA\s*[:|]\s*([+\-]?\d*\.?\d+)", response_text, re.IGNORECASE
            )
            if delta_match:
                try:
                    delta = float(delta_match.group(1))
                except ValueError:
                    pass

            reason_match = re.search(
                r"REASON\s*[:|]\s*(.+)", response_text, re.IGNORECASE
            )
            if reason_match:
                reason = reason_match.group(1).strip()

            if delta == 0.0 and "DELTA" not in response_text.upper():
                logger.warning(
                    f"[{self.name}] LLM output format error in check_change_position."
                )

            if delta < 0:
                delta *= modifier

            new_confidence = max(0.0, min(1.0, self.confidence_score + delta))
            self.confidence_score = new_confidence
            self.confidence_history.append(new_confidence)
            self.total_cost += cost

            flip_threshold = float(os.getenv("CONFIDENCE_FLIP_THRESHOLD", "0.3"))
            post_flip_conf = float(os.getenv("CONFIDENCE_AFTER_FLIP", "0.6"))

            if post_flip_conf <= flip_threshold:
                adjusted = min(1.0, flip_threshold + 0.15)
                post_flip_conf = adjusted

            has_changed = False
            new_pos = self.current_position

            if self.confidence_score < flip_threshold:
                alternatives = [
                    pos
                    for pos in debate.allowed_positions
                    if pos != self.current_position
                ]

                if not alternatives:
                    pass
                elif len(alternatives) == 1:
                    new_pos = alternatives[0]
                    has_changed = True
                else:
                    pick_prompt = (
                        f"Your confidence in '{self.current_position}' has collapsed ({self.confidence_score:.2f}).\n"
                        f"You MUST switch to one of these: {alternatives}.\n"
                        f"Which one is most convincing based on the transcript?\n"
                        f"Respond ONLY with the position name."
                    )
                    choice_text, _, _ = self._execute_llm_call(
                        system_prompt, pick_prompt, 200
                    )
                    candidate = choice_text.strip()

                    found = False
                    for pos in alternatives:
                        if pos.lower() in candidate.lower():
                            new_pos = pos
                            has_changed = True
                            found = True
                            break

                    if not found:
                        new_pos = random.choice(alternatives)
                        has_changed = True
                        logger.warning(
                            f"{self.name} needed to flip but LLM failed. Forced random flip to {new_pos}."
                        )

            if has_changed:
                self.final_position = new_pos
                self.confidence_score = post_flip_conf
                self.confidence_history.append(post_flip_conf)
                logger.info(
                    f"!!! {self.name} FLIPPED from {self.original_position} to {new_pos}. Reason: {reason}"
                )

            return PositionChangeCheck(
                has_changed=has_changed,
                new_position=new_pos,
                reasoning=f"[Conf: {new_confidence:.2f} -> {self.confidence_score:.2f}] {reason}",
            )

        except Exception as e:
            logger.error(f"Error checking position for {self.name}: {e}")
            return PositionChangeCheck(
                has_changed=False, new_position=self.current_position, reasoning=str(e)
            )

    def evaluate_debate_performance(
        self, history: List["Intervention"], participants: List["Participant"]
    ) -> Dict[str, Any]:
        candidates = [p.name for p in participants if p.name != self.name]
        if not candidates:
            return {}

        formatted_transcript = ""
        for idx, intervention in enumerate(history):
            speaker = (
                intervention.participant.name if intervention.participant else "SYSTEM"
            )
            formatted_transcript += (
                f"[{idx}] {speaker}: {intervention.answer[:150]}...\n"
            )

        system_prompt = (
            f"You are {self.name}. Evaluate the debate performances objectively."
        )

        user_prompt = (
            f"TRANSCRIPT:\n{formatted_transcript}\n\n"
            f"Candidates to evaluate: {', '.join(candidates)}\n\n"
            f"INSTRUCTION: You must pick a winner, identify the best and worst turn ID from the transcript, and score each opponent (0-10).\n"
            f"Do not vote for yourself.\n\n"
            f"Respond in VALID JSON format ONLY:\n"
            f"{{\n"
            f'  "winner": "Name of Winner",\n'
            f'  "best_turn": 12,\n'
            f'  "worst_turn": 5,\n'
            f'  "scores": {{ "Opponent1": 8.5, "Opponent2": 4.0 }}\n'
            f"}}"
        )

        try:
            response_text, _, cost = self._execute_llm_call(
                system_prompt, user_prompt, 1000
            )
            self.total_cost += cost

            logger.info(f"[{self.name}] Evaluation Raw Response:\n{response_text}")

            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            if "{" in clean_text and "}" in clean_text:
                start = clean_text.find("{")
                end = clean_text.rfind("}") + 1
                clean_text = clean_text[start:end]

            result = json.loads(clean_text)

            if "winner" not in result:
                result["winner"] = None
            if "scores" not in result:
                result["scores"] = {}

            return result

        except Exception as e:
            logger.error(
                f"❌ Evaluation failed for {self.name} (Brain: {self.brain.value}): {e}"
            )
            return {}

    def answer(self, history: List["Intervention"], max_letters: int) -> "Intervention":
        from debates.models.intervention import Intervention

        effective_limit = (
            self.next_turn_char_limit
            if self.next_turn_char_limit is not None
            else max_letters
        )

        logger.info(
            f"Participant {self.name} (Brain: {self.brain.value}) is starting turn. Stance: {self.current_position}. Limit: {effective_limit} chars."
        )

        system_prompt = self._get_system_prompt()
        context = self._format_history(history)

        use_cot = self.role in [RoleType.EXPERT, RoleType.SCHOLAR]

        instruction = ""
        if use_cot:
            instruction = (
                "FORMAT REQUIREMENT: Use Structured Thinking.\n"
                "1. First, write 'THOUGHTS:' and analyze the opponent's logic, fallacies, and your strategy.\n"
                "2. Then, write 'RESPONSE:' and provide your actual spoken reply.\n"
                "3. You MUST explicitly mention the person you are replying to.\n"
                "Constraint: Only the RESPONSE part counts towards the character limit."
            )
        else:
            instruction = "Respond directly. You MUST explicitly mention the person you are replying to."

        user_prompt = (
            f"{context}\n\n{instruction}\nConstraint: Max {effective_limit} chars."
        )

        try:
            response_text, (in_tokens, out_tokens), cost = self._execute_llm_call(
                system_prompt, user_prompt, effective_limit + 500
            )
            self.total_cost += cost

            final_answer = response_text
            if use_cot and "RESPONSE:" in response_text:
                parts = response_text.split("RESPONSE:")
                thoughts = parts[0].replace("THOUGHTS:", "").strip()
                extracted_response = parts[1].strip()

                if extracted_response:
                    final_answer = extracted_response
                    logger.debug(f"[{self.name} THOUGHTS]: {thoughts}")
                else:
                    logger.warning(
                        f"⚠️ {self.name} generated CoT but EMPTY response. Using raw text fallback."
                    )
                    final_answer = f"[Internal Monologue]: {thoughts}"

            if not final_answer.strip():
                logger.warning(
                    f"⚠️ {self.name} returned completely empty text. Inserting silence placeholder."
                )
                final_answer = "(...remains silent and contemplative...)"

            return Intervention(
                participant=self,
                answer=final_answer,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                cost=cost,
                participant_snapshot_position=self.current_position,
            )

        except Exception as e:
            logger.exception(f"Error answering: {e}")
            raise e

    def _resolve_provider_settings(self, brain: BrainType) -> tuple[str, Optional[str]]:
        # 1. Config Override
        if self.provider_config:
            brain_key = brain.value.lower()
            if brain_key in self.provider_config:
                conf = self.provider_config[brain_key]
                model = conf.get("model") or conf.get("model_name")
                api_key = conf.get("api_key") or conf.get("token")
                if model and api_key:
                    return model, api_key

        # 2. Environment Variable Fallback
        model_name = ""
        api_key = None

        if brain == BrainType.GEMINI:
            raw = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
            model_name = f"gemini/{raw}" if not raw.startswith("gemini/") else raw
            api_key = os.getenv("GEMINI_API_KEY")
        elif brain == BrainType.CLAUDE:
            raw = os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest"
            model_name = f"anthropic/{raw}" if not raw.startswith("anthropic/") else raw
            api_key = os.getenv("ANTHROPIC_API_KEY")
        elif brain == BrainType.DEEPSEEK:
            raw = os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
            model_name = f"deepseek/{raw}" if not raw.startswith("deepseek/") else raw
            api_key = os.getenv("DEEPSEEK_API_KEY")
        elif brain == BrainType.OPENAI:
            model_name = os.getenv("OPENAI_MODEL") or "gpt-4o"
            api_key = os.getenv("OPENAI_API_KEY")

        return model_name, api_key

    def _switch_brain(self, error_message: str):
        old = self.brain

        candidates = []
        if self.provider_config:
            for b in BrainType:
                if b != old and b.value.lower() in self.provider_config:
                    m, k = self._resolve_provider_settings(b)
                    if k:
                        candidates.append(b)

        if not candidates:
            raw_allowed = os.getenv("AVAILABLE_BRAINS", "all").lower().strip()
            allowed_env = []
            if raw_allowed == "all" or not raw_allowed:
                allowed_env = list(BrainType)
            else:
                keys = [x.strip() for x in raw_allowed.split(",")]
                for b in BrainType:
                    if b.value in keys:
                        allowed_env.append(b)

            candidates = [b for b in allowed_env if b != old]

        if not candidates:
            logger.error(
                f"FATAL: No available brains left to switch to for {self.name} (failed: {old})"
            )
            return False

        self.brain = random.choice(candidates)
        logger.warning(
            f"⚠️ BRAIN SWITCH: {self.name} changed from {old} -> {self.brain} due to error: {error_message}"
        )
        return True

    def _execute_llm_call(self, system_prompt: str, user_prompt: str, max_letters: int):
        attempts = 0
        while True:
            model_name, api_key = self._resolve_provider_settings(self.brain)

            if not api_key or api_key == "CHANGE-ME":
                if attempts < 3:
                    if self._switch_brain("No Key or Invalid Key"):
                        attempts += 1
                        continue
                return "Mock Response (No Valid Key Found)", (0, 0), 0.0

            try:
                response = completion(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_letters if max_letters < 4096 else 4096,
                    api_key=api_key,
                )
                cost = completion_cost(completion_response=response)
                return (
                    response.choices[0].message.content,
                    (response.usage.prompt_tokens, response.usage.completion_tokens),
                    cost,
                )
            except Exception as e:
                if attempts < 3:
                    if self._switch_brain(str(e)):
                        attempts += 1
                        continue
                raise e
