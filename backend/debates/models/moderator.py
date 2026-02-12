import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from debates.enums import MindsetType, ModeratorAction, RoleType
from debates.logger import logger
from debates.models.intervention import Intervention
from debates.models.participant import Participant


class Moderator(Participant):
    allowed_to_intervene_with_own_position: bool
    allowed_to_skip_turn: bool
    allowed_to_stop_debate: bool
    allowed_to_veto_participant: bool

    def decide_intervention(
        self,
        history: List[Intervention],
        next_speaker: "Participant",
        active_participants_count: int,
        global_max_letters: int = 2000,
    ) -> Tuple[ModeratorAction, str, str, Optional[Intervention]]:
        if len(history) <= 1:
            return ModeratorAction.NONE, "", "", None

        last_intervention = history[-1]
        last_speaker_name = (
            last_intervention.participant.name
            if last_intervention.participant
            else "SYSTEM"
        )
        last_speaker_obj = last_intervention.participant

        if last_speaker_name == "SYSTEM" or last_speaker_name == self.name:
            return ModeratorAction.NONE, "", "", None

        logger.info(
            f"Moderator {self.name} is evaluating intervention regarding {last_speaker_name}..."
        )

        last_length = len(last_intervention.answer)
        is_too_long = last_length > (global_max_letters + 100)

        language = os.getenv("LANGUAGE", "English")
        max_strikes = int(os.getenv("MAX_STRIKES_FOR_VETO", "3"))
        personality_prompt = self._build_moderator_personality()

        strikes = getattr(last_speaker_obj, "strikes", 0) if last_speaker_obj else 0

        tools = []
        if self.allowed_to_veto_participant:
            tools.append(f"{ModeratorAction.VETO.value} (Ban LAST speaker permanently)")
        if self.allowed_to_skip_turn:
            tools.append(
                f"{ModeratorAction.SANCTION.value} (Give a Strike to {last_speaker_name}. {max_strikes} Strikes = Veto. Also skips their NEXT turn)"
            )
            tools.append(
                f"{ModeratorAction.SKIP.value} (Skip the UPCOMING speaker, usually only if you hate them specifically)"
            )
        if self.allowed_to_stop_debate:
            tools.append(f"{ModeratorAction.STOP.value} (End debate now)")
        if self.allowed_to_intervene_with_own_position:
            tools.append(
                f"{ModeratorAction.INTERVENE.value} (Speak your mind/scold without penalty)"
            )

        if is_too_long:
            tools.append(
                f"{ModeratorAction.LIMIT.value} (REDUCE next turn length for {last_speaker_name} because they spoke too much)"
            )

        tools.append(f"{ModeratorAction.NONE.value} (Let them continue)")

        tools_str = ", ".join(tools)

        system_prompt = (
            f"You are {self.name}, the MODERATOR.\n"
            f"Role: {self.role.value}, Attitude: {self.attitude_type.value}.\n"
            f"TOOLS: [{tools_str}]\n{personality_prompt}\nRespond in {language}."
        )

        transcript = self._format_history(history[-3:])

        violation_text = ""
        if is_too_long:
            violation_text = f"WARNING: {last_speaker_name} used {last_length} chars (Limit: {global_max_letters}). You can use {ModeratorAction.LIMIT.value} to penalize them."

        user_prompt = (
            f"{transcript}\n\n"
            f"ANALYSIS TASK:\n"
            f"LAST speaker: {last_speaker_name} (Strikes: {strikes}/{max_strikes}).\n"
            f"NEXT speaker: {next_speaker.name}.\n"
            f"{violation_text}\n\n"
            f"RULES:\n"
            f"- {ModeratorAction.SANCTION.value}: For bad behavior (insults, lies).\n"
            f"- {ModeratorAction.LIMIT.value}: For length violations (reduces next turn to 50%).\n"
            f"- {ModeratorAction.INTERVENE.value}: Scold/Comment.\n\n"
            f"Format:\nACTION|REASON|MESSAGE_TEXT"
        )

        try:
            response_text, _, cost = self._execute_llm_call(
                system_prompt, user_prompt, 1000
            )

            parts = response_text.strip().split("|")
            if len(parts) < 3:
                return ModeratorAction.NONE, "", "", None

            raw_action = parts[0].strip().upper()
            raw_action = re.sub(r"^(ACTION|DECISION)[:\s]*", "", raw_action).strip()

            try:
                action = ModeratorAction(raw_action)
            except ValueError:
                if "INTERVENE" in raw_action:
                    action = ModeratorAction.INTERVENE
                elif "SANCTION" in raw_action:
                    action = ModeratorAction.SANCTION
                elif "LIMIT" in raw_action:
                    action = ModeratorAction.LIMIT
                else:
                    action = ModeratorAction.NONE

            reason = parts[1].strip()
            reason = re.sub(r"^(REASON)[:\s]*", "", reason).strip()

            message = parts[2].strip()
            message = re.sub(r"^(MESSAGE)[:\s]*", "", message).strip()

            target_name = last_speaker_name

            if action == ModeratorAction.VETO and not self.allowed_to_veto_participant:
                action = ModeratorAction.SANCTION
            if action == ModeratorAction.SANCTION and not self.allowed_to_skip_turn:
                action = ModeratorAction.INTERVENE
            if action == ModeratorAction.SKIP:
                if not self.allowed_to_skip_turn:
                    action = ModeratorAction.INTERVENE
                target_name = next_speaker.name

            if action == ModeratorAction.STOP and not self.allowed_to_stop_debate:
                action = ModeratorAction.INTERVENE
            if (
                action == ModeratorAction.INTERVENE
                and not self.allowed_to_intervene_with_own_position
            ):
                action = ModeratorAction.NONE

            if action == ModeratorAction.LIMIT and last_speaker_obj:
                new_limit = max(500, global_max_letters // 2)
                last_speaker_obj.next_turn_char_limit = new_limit
                message += f" [PENALTY: Next turn limited to {new_limit} chars]"

            if action == ModeratorAction.VETO and active_participants_count <= 2:
                action = ModeratorAction.INTERVENE
                message = "[I wanted to ban you, but we need people] " + message

            logger.info(
                f"Moderator Decision: {action.value} (Target: {target_name}). Reason: {reason}"
            )
            logger.info(f"Moderator Check Cost: ${cost:.6f}")

            if action == ModeratorAction.NONE:
                return ModeratorAction.NONE, "", "", None

            public_message = (
                f"{message}\n\n[MODERATOR ACTION: {action.value} | REASON: {reason}]"
            )

            return (
                action,
                target_name,
                reason,
                Intervention(
                    participant=self,
                    answer=public_message,
                    input_tokens=0,
                    output_tokens=0,
                    cost=cost,
                    participant_snapshot_position="Moderator",
                ),
            )

        except Exception as e:
            logger.error(f"Error in moderator decision: {e}")
            return ModeratorAction.NONE, "", "", None

    def evaluate_debate_as_judge(
        self,
        topic: str,
        interventions: List[Intervention],
        participants: List[Participant],
    ) -> Dict[str, Any]:
        logger.info(f"Moderator {self.name} is judging the debate...")
        language = os.getenv("LANGUAGE", "English")

        transcript_text = ""
        for i in interventions:
            name = i.participant.name if i.participant else "SYSTEM"
            transcript_text += f"{name}: {i.answer[:300]}...\n"

        candidates = [p.name for p in participants if p.name != self.name]

        system_prompt = (
            f"You are {self.name}, the Moderator and Judge.\n"
            f"Your Role: {self.role.value}, Attitude: {self.attitude_type.value}.\n"
            f"Task: Evaluate the debate objectively based on Logic, Rhetoric, and Civility."
        )

        user_prompt = (
            f"TOPIC: {topic}\nTRANSCRIPT:\n{transcript_text}\n\n"
            f"Evaluate participants: {', '.join(candidates)}\n"
            f"Respond in VALID JSON format.\n"
            f"IMPORTANT: The content of the 'critique' field MUST be written in {language}.\n"
            f"Format:\n"
            f"{{\n"
            f'  "scores": {{ "Name": {{ "logic": 8, "rhetoric": 7, "civility": 9 }} }},\n'
            f'  "technical_winner": "Name",\n'
            f'  "critique": "Overall brief critique of the debate in {language}."\n'
            f"}}"
        )

        try:
            response_text, _, cost = self._execute_llm_call(
                system_prompt, user_prompt, 2000
            )

            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            if "{" in clean_text and "}" in clean_text:
                start = clean_text.find("{")
                end = clean_text.rfind("}") + 1
                clean_text = clean_text[start:end]

            result = json.loads(clean_text)
            self.total_cost += cost
            return result
        except Exception as e:
            logger.error(f"Moderator Judgment failed: {e}")
            return {}

    def break_tie(self, candidates: List[str]) -> str:
        return candidates[0]

    def _build_moderator_personality(self) -> str:
        instructions = ""

        if self.role == RoleType.ILLITERATE:
            instructions += "STYLE: Uneducated moderator. Simple words. Emotional."
        elif self.role == RoleType.GENERAL_KNOWLEDGE:
            instructions += "STYLE: Regular person. Common sense. Clear language."
        elif self.role in [RoleType.SCHOLAR, RoleType.EXPERT]:
            instructions += (
                "STYLE: Academic moderator. Pedantic. Logical. Strict vocabulary."
            )

        if self.mindset == MindsetType.OPEN_MINDED:
            instructions += "\nMINDSET: Willing to listen to all sides."
        elif self.mindset == MindsetType.CLOSE_MINDED:
            instructions += "\nMINDSET: Stubborn. You have your favorites."

        if not self.tolerant:
            instructions += f"\nBEHAVIOR: BIASED and INTOLERANT. Silence opposition using {ModeratorAction.SANCTION.value}."
        else:
            instructions += "\nBEHAVIOR: Fair but firm."

        if self.insults_allowed:
            instructions += "\nTONE: Rude and aggressive."

        return instructions
