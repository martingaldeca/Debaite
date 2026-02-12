import logging
import os
import random
import re
import textwrap
from collections import Counter
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Tuple, Type

from debates.enums import (
    AttitudeType,
    BrainType,
    EthnicityType,
    GenderType,
    MindsetType,
    ModeratorAction,
    RoleType,
)
from debates.logger import get_debate_logger, logger
from debates.models import Debater, Intervention, Moderator
from debates.models.results import (
    DebateMetadata,
    DebateResult,
    EvaluationSection,
    GlobalOutcome,
    InterventionReference,
    ModeratorStats,
    ParticipantEntry,
    ParticipantScore,
    PositionChangeEntry,
    TranscriptEntry,
    UsageStats,
)
from faker import Faker
from litellm import completion


class Debate:
    topic_name: str
    description: str
    allowed_positions: List[str]
    participants: List[Debater]
    total_turns: int
    total_rounds: int
    moderator: Moderator | None
    interventions: List[Intervention]
    full_transcript: List[Intervention]

    session_id: str
    debate_id: str

    position_changes_log: List[PositionChangeEntry]
    moderator_stats: Dict[str, int]
    evaluation_data: EvaluationSection
    overrides: Dict[str, Any]
    accumulated_system_cost: float = 0.0
    _gen: Optional[Generator[Dict[str, Any], None, None]] = None

    def __init__(
        self,
        topic_name: str,
        description: str,
        allowed_positions: List[str],
        session_id: str,
        overrides: Optional[Dict[str, Any]] = None,
    ):
        self.fake = Faker()
        self.topic_name = topic_name
        self.description = description
        self.allowed_positions = allowed_positions
        self.session_id = session_id
        self.debate_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.topic_logger = get_debate_logger(topic_name, session_id, self.debate_id)
        self.overrides = overrides or {}

        self.participants = []
        self.interventions = []
        self.full_transcript = []
        self.position_changes_log = []
        self.moderator_stats = {
            "interventions": 0,
            "sanctions": 0,
            "skips": 0,
            "vetos": 0,
            "stops": 0,
            "limits": 0,
        }
        self.evaluation_data = EvaluationSection(participants=[])

        self.generate_participants()
        self.establish_total_turns()
        self.establish_total_rounds()
        self.establish_max_letters_per_participant_per_turn()
        self.establish_references_required()
        self.establish_moderator()

    @property
    def debate_prompt(self) -> str:
        roster = "\n".join(
            [
                f"- {p.name} ({p.role.value}): {p.original_position}"
                for p in self.participants
            ]
        )
        mod_text = (
            f"Moderator: {self.moderator.name}" if self.moderator else "No Moderator"
        )
        return f"Topic: {self.topic_name}\nContext: {self.description}\nRoster:\n{roster}\n{mod_text}"

    def _get_allowed_brains(self) -> List[BrainType]:
        raw = os.getenv("AVAILABLE_BRAINS", "all").lower().strip()
        if raw == "all" or not raw:
            return list(BrainType)
        allowed_keys = [x.strip() for x in raw.split(",")]
        valid = [b for b in BrainType if b.value in allowed_keys]
        return valid if valid else list(BrainType)

    def _resolve_attr(
        self, key: str, enum_cls: Optional[Type[Enum]], default_options: List[Any]
    ) -> Any:
        val = self.overrides.get(key)
        if val is not None:
            if isinstance(val, bool):
                return val
            if enum_cls:
                try:
                    return enum_cls(val)
                except ValueError:
                    val_str = str(val).lower()
                    for e in enum_cls:
                        if e.value.lower() == val_str or e.name.lower() == val_str:
                            return e
            return val
        return random.choice(default_options)

    def _generate_base_profile(self, is_moderator: bool = False) -> Dict[str, Any]:
        prefix = "mod_" if is_moderator else "part_"
        allowed_brains = self._get_allowed_brains()

        data = {
            "name": self.fake.first_name(),
            "role": self._resolve_attr(f"{prefix}role", RoleType, list(RoleType)),
            "attitude_type": self._resolve_attr(
                f"{prefix}attitude", AttitudeType, list(AttitudeType)
            ),
            "mindset": self._resolve_attr(
                f"{prefix}mindset", MindsetType, list(MindsetType)
            ),
            "brain": self._resolve_attr(f"{prefix}brain", BrainType, allowed_brains),
            "gender": self._resolve_attr(
                f"{prefix}gender", GenderType, list(GenderType)
            ),
            "ethnic_group": random.choice(list(EthnicityType)),
            "tolerant": self._resolve_attr(f"{prefix}tolerant", None, [True, False]),
            "insults_allowed": self._resolve_attr(
                f"{prefix}insults", None, [True, False]
            ),
            "lies_allowed": self._resolve_attr(f"{prefix}lies", None, [True, False]),
            "confidence_score": random.uniform(0.6, 1.0),
            "final_position": None,
        }

        if "provider_config" in self.overrides:
            data["provider_config"] = self.overrides["provider_config"]

        return data

    def generate_participants(self):
        manual_participants = self.overrides.get("participants")

        if manual_participants and isinstance(manual_participants, list):
            logger.info(
                f"Using manual participant configuration: {len(manual_participants)} participants."
            )
            for i, p_data in enumerate(manual_participants):
                base = self._generate_base_profile(is_moderator=False)

                for k, v in p_data.items():
                    if v is not None:
                        base[k] = v

                enum_mappings: List[Tuple[str, Type[Enum]]] = [
                    ("role", RoleType),
                    ("attitude_type", AttitudeType),
                    ("mindset", MindsetType),
                    ("brain", BrainType),
                    ("gender", GenderType),
                ]
                for key, enum_cls in enum_mappings:
                    if key in base and isinstance(base[key], str):
                        try:
                            val = base[key]
                            if "." in val:
                                val = val.split(".")[-1]

                            for e in enum_cls:
                                if (
                                    e.name.lower() == val.lower()
                                    or e.value.lower() == val.lower()
                                ):
                                    base[key] = e
                                    break
                        except Exception:  # nosec B110
                            pass

                base["order_in_debate"] = i + 1
                base["initial_brain"] = base.get(
                    "brain"
                )  # Ensure initial matches if set

                try:
                    self.participants.append(Debater(**base))
                except Exception as e:
                    logger.error(f"Failed to create participant {i}: {e}")
            return

        min_p = int(os.getenv("MIN_PARTICIPANTS", "2"))
        max_p = int(os.getenv("MAX_PARTICIPANTS", "5"))

        count = random.randint(min_p, max_p)
        needed_positions = len(self.allowed_positions)
        if count < needed_positions and max_p >= needed_positions:
            logger.info(
                f"Auto-adjusting participant count from {count} to {needed_positions} to cover all positions."
            )
            count = needed_positions

        positions_to_assign: List[str] = []
        pool = list(self.allowed_positions)
        random.shuffle(pool)

        while len(positions_to_assign) < count:
            if not pool:
                pool = list(self.allowed_positions)
                random.shuffle(pool)
            positions_to_assign.append(pool.pop(0))

        random.shuffle(positions_to_assign)

        for i in range(count):
            data = self._generate_base_profile(is_moderator=False)
            data["original_position"] = positions_to_assign[i]
            data["initial_brain"] = data["brain"]
            data["order_in_debate"] = i + 1
            self.participants.append(Debater(**data))

    def establish_total_turns(self):
        self.total_turns = random.randint(
            int(os.getenv("MIN_TOTAL_TURNS", "5")),
            int(os.getenv("MAX_TOTAL_TURNS", "10")),
        )

    def establish_total_rounds(self):
        self.total_rounds = random.randint(
            int(os.getenv("MIN_TOTAL_ROUNDS", "1")),
            int(os.getenv("MAX_TOTAL_ROUNDS", "3")),
        )

    def establish_max_letters_per_participant_per_turn(self):
        override = self.overrides.get("max_letters")
        if override:
            self.max_letters_per_participant_per_turn = int(override)
            return

        min_l = int(os.getenv("MIN_MAX_LETTERS_PER_PARTICIPANT_PER_TURN", "1000"))
        max_l = int(os.getenv("MAX_MAX_LETTERS_PER_PARTICIPANT_PER_TURN", "2000"))
        if min_l > max_l:
            min_l, max_l = max_l, min_l
        self.max_letters_per_participant_per_turn = random.randint(min_l, max_l)

    def establish_moderator(self):
        has_mod_override = any(k.startswith("mod_") for k in self.overrides.keys())
        should_have_moderator = (
            True if has_mod_override else random.choice([True, False])
        )

        if should_have_moderator:
            data = self._generate_base_profile(is_moderator=True)
            data["original_position"] = None
            data.update(
                {
                    "allowed_to_intervene_with_own_position": True,
                    "allowed_to_skip_turn": True,
                    "allowed_to_stop_debate": True,
                    "allowed_to_veto_participant": True,
                    "order_in_debate": 0,
                }
            )
            self.moderator = Moderator(**data)
        else:
            self.moderator = None

    def establish_references_required(self):
        self.references_required = random.choice([True, False])

    def _get_available_providers(self) -> List[Tuple[str, str]]:
        potential_providers = [
            ("GEMINI_API_KEY", "GEMINI_MODEL", "gemini/gemini-1.5-flash", "gemini/"),
            (
                "DEEPSEEK_API_KEY",
                "DEEPSEEK_MODEL",
                "deepseek/deepseek-chat",
                "deepseek/",
            ),
            ("OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini", ""),
            (
                "ANTHROPIC_API_KEY",
                "ANTHROPIC_MODEL",
                "anthropic/claude-3-haiku-20240307",
                "anthropic/",
            ),
        ]

        available = []
        for key_var, model_var, default_model, prefix in potential_providers:
            key = os.getenv(key_var)
            if key and key != "CHANGE-ME":
                raw_model = os.getenv(model_var, default_model)
                if prefix and not raw_model.startswith(prefix):
                    final_model = f"{prefix}{raw_model}"
                else:
                    final_model = raw_model
                available.append((final_model, key))
        return available

    def _record_intervention(self, intervention: Intervention):
        self.interventions.append(intervention)
        self.full_transcript.append(intervention)

    def _summarize_history(self):
        limit = int(os.getenv("MEMORY_COMPRESSION_TURNS", "10"))
        if len(self.interventions) <= limit:
            return

        to_compress = self.interventions[:-5]
        raw_text = "\n".join(
            [
                f"{i.participant.name if i.participant else 'SYSTEM'}: {i.answer}"
                for i in to_compress
            ]
        )

        providers = self._get_available_providers()
        if not providers:
            return

        for model, api_key in providers:
            try:
                response = completion(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Summarize the debate progress concisely.",
                        },
                        {"role": "user", "content": raw_text},
                    ],
                    api_key=api_key,
                )
                summary = response.choices[0].message.content
                try:
                    self.accumulated_system_cost += response._hidden_params.get(
                        "response_cost", 0.0
                    )
                except Exception as cost_error:
                    logger.debug(
                        f"Could not read response cost from provider: {cost_error}"
                    )

                summary_intervention = Intervention(
                    participant=None,
                    answer=f"[PREVIOUS SUMMARY]: {summary}",
                    participant_snapshot_position="System",
                )
                self.interventions = [summary_intervention] + self.interventions[-5:]
                logger.info(f"Memory Compressed successfully using {model}.")
                break
            except Exception:
                logger.warning(f"Compression failed with {model}. Trying next...")

    def _log_initial_state(self):
        part_list = "\n".join([f"- {p.full_description}" for p in self.participants])
        mod_desc = self.moderator.full_description if self.moderator else "None"

        log_msg = (
            f"=== DEBATE STARTED ===\n"
            f"ID: {self.debate_id}\n"
            f"PROMPT: This is a debate named '{self.topic_name}'.\n"
            f"The description is: {self.description}\n"
            f"The Participants are:\n{part_list}\n"
            f"Moderator: {mod_desc}\n"
            f"There will be a total of {self.total_rounds} rounds. Each round consists of {self.total_turns} turns per participant.\n"
            f"Each turn will have a maximum of {self.max_letters_per_participant_per_turn} letters.\n"
        )
        self.topic_logger.info(log_msg)
        logger.info(f"Starting Debate {self.debate_id} on '{self.topic_name}'")

    def run_generator(self):
        self._log_initial_state()

        # Yield initial state
        yield {
            "type": "initial_state",
            "debate_id": self.debate_id,
            "topic": self.topic_name,
            "description": self.description,
            "participants": [p.model_dump(mode="json") for p in self.participants],
            "moderator": (
                self.moderator.model_dump(mode="json") if self.moderator else None
            ),
            "total_rounds": self.total_rounds,
            "total_turns": self.total_turns,
        }

        start_msg = ""
        if self.moderator:
            start_msg = f"WELCOME.\n{self.debate_prompt}"
            intervention = Intervention(
                participant=self.moderator,
                answer=start_msg,
                participant_snapshot_position="Moderator",
            )
        else:
            start_msg = f"SYSTEM: Debate Starts.\n{self.debate_prompt}"
            intervention = Intervention(
                participant=None,
                answer=start_msg,
                participant_snapshot_position="System",
            )

        self._record_intervention(intervention)
        yield {
            "type": "intervention",
            "participant": (
                intervention.participant.name if intervention.participant else "System"
            ),
            "text": intervention.answer,
            "cost": intervention.cost,
        }

        debate_active = True
        max_strikes_limit = int(os.getenv("MAX_STRIKES_FOR_VETO", "3"))

        for round_num in range(1, self.total_rounds + 1):
            if not debate_active:
                break
            self.topic_logger.info(f"--- ROUND {round_num} ---")
            yield {"type": "round_start", "round": round_num}

            for turn_num in range(1, self.total_turns + 1):
                if not debate_active:
                    break

                logger.info(
                    f"--- Round {round_num}/{self.total_rounds} | Turn {turn_num}/{self.total_turns} ---"
                )
                yield {"type": "turn_start", "round": round_num, "turn": turn_num}

                self._summarize_history()

                for p in self.participants:
                    if p.is_vetoed:
                        continue
                    if p.skip_next_turn:
                        msg = f"[SYSTEM] {p.name} SKIPPED (Sanction)."
                        intervention = Intervention(
                            participant=None,
                            answer=msg,
                            participant_snapshot_position="System",
                        )
                        self._record_intervention(intervention)
                        self.topic_logger.info(msg)
                        p.skip_next_turn = False
                        yield {
                            "type": "intervention",
                            "participant": "System",
                            "text": msg,
                            "cost": 0.0,
                        }
                        continue

                    active_count = len(
                        [x for x in self.participants if not x.is_vetoed]
                    )
                    if active_count <= 1:
                        debate_active = False
                        break

                    if self.moderator:
                        action, target, reason, mod_msg = (
                            self.moderator.decide_intervention(
                                self.interventions,
                                p,
                                active_count,
                                global_max_letters=self.max_letters_per_participant_per_turn,
                            )
                        )

                        if mod_msg:
                            self._record_intervention(mod_msg)
                            if action == ModeratorAction.INTERVENE:
                                self.moderator_stats["interventions"] += 1
                            elif action == ModeratorAction.STOP:
                                self.moderator_stats["stops"] += 1

                            mod_log = f"MODERATOR ({self.moderator.name})"
                            if action != ModeratorAction.NONE:
                                mod_log += f" [ACTION: {action.value} -> {target}]"
                            mod_log += f": {mod_msg.answer}"
                            self.topic_logger.info(mod_log)
                            logger.info(
                                f"Moderator Action: {action.value} on {target or 'General'}"
                            )
                            yield {
                                "type": "intervention",
                                "participant": self.moderator.name,
                                "text": mod_msg.answer,
                                "cost": mod_msg.cost,
                                "action": action.value,
                                "target": target,
                            }

                        target_p = next(
                            (x for x in self.participants if x.name == target), None
                        )
                        if action == ModeratorAction.STOP:
                            debate_active = False
                            break

                        if action == ModeratorAction.VETO and target_p:
                            target_p.is_vetoed = True
                            target_p.veto_reason = reason
                            self.moderator_stats["vetos"] += 1
                            self.topic_logger.info(
                                f"!!! {target_p.name} HAS BEEN VETOED (BANNED) !!!"
                            )
                            yield {
                                "type": "veto",
                                "participant": target_p.name,
                                "reason": reason,
                            }
                            if target_p == p:
                                continue

                        if action == ModeratorAction.SANCTION and target_p:
                            target_p.strikes += 1
                            target_p.skip_next_turn = True
                            self.moderator_stats["sanctions"] += 1
                            self.topic_logger.info(
                                f"! {target_p.name} RECEIVED A STRIKE ({target_p.strikes}/{max_strikes_limit}) !"
                            )
                            yield {
                                "type": "sanction",
                                "participant": target_p.name,
                                "strikes": target_p.strikes,
                            }
                            if target_p.strikes >= max_strikes_limit:
                                target_p.is_vetoed = True
                                target_p.veto_reason = f"Max Strikes ({max_strikes_limit}) reached. Last: {reason}"
                                self.moderator_stats["vetos"] += 1
                                self.topic_logger.info(
                                    f"!!! {target_p.name} HAS BEEN VETOED FOR ACCUMULATED STRIKES !!!"
                                )
                                yield {
                                    "type": "veto",
                                    "participant": target_p.name,
                                    "reason": target_p.veto_reason,
                                }
                                if target_p == p:
                                    continue

                        if action == ModeratorAction.SKIP and target_p:
                            self.moderator_stats["skips"] += 1
                            if target_p == p:
                                msg = f"[SYSTEM] {p.name} SKIPPED by Moderator."
                                intervention = Intervention(
                                    participant=None,
                                    answer=msg,
                                    participant_snapshot_position="System",
                                )
                                self._record_intervention(intervention)
                                self.topic_logger.info(msg)
                                yield {
                                    "type": "intervention",
                                    "participant": "System",
                                    "text": msg,
                                    "cost": 0.0,
                                }
                                continue
                            else:
                                target_p.skip_next_turn = True

                        if action == ModeratorAction.LIMIT and target_p:
                            self.moderator_stats["limits"] += 1
                            self.topic_logger.info(
                                f"! {target_p.name} PENALIZED: Next turn limited to {target_p.next_turn_char_limit} chars !"
                            )

                    try:
                        intervention = p.answer(
                            self.interventions,
                            self.max_letters_per_participant_per_turn,
                        )
                        self._record_intervention(intervention)
                        self.topic_logger.info(
                            f"{p.full_description}: {intervention.answer}"
                        )
                        logger.info(f"Turn Cost ({p.name}): ${intervention.cost:.6f}")

                        if p.next_turn_char_limit:
                            p.next_turn_char_limit = None

                        yield {
                            "type": "intervention",
                            "participant": p.name,
                            "text": intervention.answer,
                            "cost": intervention.cost,
                            "role": p.role.value,
                        }

                    except Exception as e:
                        logger.warning(
                            f"Turn execution skipped for {p.name} due to error: {e}"
                        )
                        continue

            self._check_positions(round_num)
            # Emit position changes if occurred
            # Position changes are already logged in check_positions but good to emit explicit event
            # We can check the log
            # For simplicity, let's assume check_positions is side-effectual on position_changes_log
            pass  # We could diff the log or just emit all current positions

        self._evaluate()

        self.topic_logger.info("=== DEBATE FINISHED ===")
        winner = None
        if self.evaluation_data.global_outcome:
            winner = self.evaluation_data.global_outcome.winner_name
            self.topic_logger.info(f"CONSENSUS WINNER: {winner}")

        self._format_log_file()
        result_path = self.save_results()
        yield {"type": "debate_finished", "winner": winner, "result_path": result_path}

    def step(self) -> Optional[Dict[str, Any]]:
        """Executes the next step in the debate and returns the event."""
        if not hasattr(self, "_gen") or self._gen is None:
            self._gen = self.run_generator()

        try:
            return next(self._gen)
        except StopIteration:
            return None

    def run(self) -> str:
        """Legacy run method wrapper that iterates over step()."""
        final_path = ""
        try:
            while True:
                event = self.step()
                if event is None:
                    break
                if event.get("type") == "debate_finished":
                    final_path = event.get("result_path", "")
        except Exception as e:
            logger.error(f"Error during run(): {e}")
            raise e
        return final_path

    def _format_log_file(self):
        try:
            handlers = self.topic_logger.handlers[:]
            for h in handlers:
                if isinstance(h, logging.FileHandler):
                    log_path = h.baseFilename
                    h.close()
                    self.topic_logger.removeHandler(h)

                    temp_path = log_path + ".tmp"
                    wrapper = textwrap.TextWrapper(
                        width=120,
                        break_long_words=True,
                        break_on_hyphens=False,
                        replace_whitespace=False,
                        drop_whitespace=False,
                    )
                    with (
                        open(log_path, encoding="utf-8") as f_in,
                        open(temp_path, "w", encoding="utf-8") as f_out,
                    ):
                        for raw_line in f_in:
                            line = raw_line.rstrip("\n")
                            if not line:
                                f_out.write("\n")
                                continue
                            for wrapped_line in wrapper.wrap(line):
                                f_out.write(f"{wrapped_line}\n")

                    os.replace(temp_path, log_path)
        except Exception as e:
            logger.error(f"Failed to fold log file: {e}")

    def _check_positions(self, round_num: int):
        logger.info(f"=== END OF ROUND {round_num} - EVALUATING POSITIONS ===")
        for p in self.participants:
            if not p.is_vetoed:
                old_pos = p.current_position
                result = p.check_change_position(self)

                if result.has_changed:
                    self.position_changes_log.append(
                        PositionChangeEntry(
                            name=p.name,
                            from_position=old_pos,
                            to_position=result.new_position,
                            round_when_changed=round_num,
                        )
                    )
                    msg = f"!!! POSITION CHANGE: {p.name} flipped from {old_pos} to {result.new_position}"
                    self.topic_logger.info(msg)
                    logger.info(msg)

    def _evaluate(self):
        logger.info("=== STARTING FINAL EVALUATION ===")
        participant_scores: List[ParticipantScore] = []
        votes: List[str] = []
        scores_map: Dict[str, List[float]] = {}

        best_id_votes: List[int] = []
        worst_id_votes: List[int] = []

        eval_history = self.interventions

        for p in self.participants:
            if not p.is_vetoed:
                logger.info(f"Processing vote from {p.name}...")
                raw = p.evaluate_debate_performance(eval_history, self.participants)

                best_ref = None
                if "best_turn" in raw:
                    idx = raw["best_turn"]
                    if isinstance(idx, int) and 0 <= idx < len(eval_history):
                        best_intervention = eval_history[idx]
                        best_ref = InterventionReference(
                            id=idx,
                            participant=(
                                best_intervention.participant.name
                                if best_intervention.participant is not None
                                else "SYSTEM"
                            ),
                            text=best_intervention.answer,
                        )
                        best_id_votes.append(idx)

                worst_ref = None
                if "worst_turn" in raw:
                    idx = raw["worst_turn"]
                    if isinstance(idx, int) and 0 <= idx < len(eval_history):
                        worst_intervention = eval_history[idx]
                        worst_ref = InterventionReference(
                            id=idx,
                            participant=(
                                worst_intervention.participant.name
                                if worst_intervention.participant is not None
                                else "SYSTEM"
                            ),
                            text=worst_intervention.answer,
                        )
                        worst_id_votes.append(idx)

                p_score = ParticipantScore(
                    voter=p.name,
                    winner=raw.get("winner"),
                    best_intervention=best_ref,
                    worst_intervention=worst_ref,
                    scores=raw.get("scores", {}),
                )
                participant_scores.append(p_score)

                if p_score.winner:
                    votes.append(p_score.winner)

                for k, v in p_score.scores.items():
                    if k not in scores_map:
                        scores_map[k] = []
                    scores_map[k].append(v)

        global_outcome = None
        if votes:
            vote_counts = Counter(votes)
            winner = vote_counts.most_common(1)[0][0]
            winner_p = next((x for x in self.participants if x.name == winner), None)

            avg_scores = {k: round(sum(v) / len(v), 2) for k, v in scores_map.items()}

            g_best = None
            if best_id_votes:
                bid = Counter(best_id_votes).most_common(1)[0][0]
                best_intervention = eval_history[bid]
                g_best = InterventionReference(
                    id=bid,
                    participant=(
                        best_intervention.participant.name
                        if best_intervention.participant is not None
                        else "SYSTEM"
                    ),
                    text=best_intervention.answer,
                )

            g_worst = None
            if worst_id_votes:
                wid = Counter(worst_id_votes).most_common(1)[0][0]
                worst_intervention = eval_history[wid]
                g_worst = InterventionReference(
                    id=wid,
                    participant=(
                        worst_intervention.participant.name
                        if worst_intervention.participant is not None
                        else "SYSTEM"
                    ),
                    text=worst_intervention.answer,
                )

            global_outcome = GlobalOutcome(
                winner_name=winner,
                winner_position=winner_p.current_position if winner_p else "Unknown",
                vote_distribution=dict(vote_counts),
                average_scores=avg_scores,
                best_intervention=g_best,
                worst_intervention=g_worst,
            )

        mod_dict = None
        if self.moderator:
            logger.info("Processing Moderator Judgment...")
            mod_dict = self.moderator.evaluate_debate_as_judge(
                self.topic_name, eval_history, self.participants
            )

        self.evaluation_data = EvaluationSection(
            participants=participant_scores,
            moderator=mod_dict,
            global_outcome=global_outcome,
        )

    def save_results(self) -> str:
        safe_topic = re.sub(r"[^\w\s-]", "", self.topic_name.lower()).strip()
        safe_topic = re.sub(r"[-\s]+", "_", safe_topic)
        folder_path = os.path.join("debate_results", safe_topic, self.session_id)
        os.makedirs(folder_path, exist_ok=True)
        full_path = os.path.join(folder_path, f"{self.debate_id}.json")

        transcript_entries = []
        final_total_cost = self.accumulated_system_cost

        for i in self.full_transcript:
            final_total_cost += i.cost
            transcript_entries.append(
                TranscriptEntry(
                    participant_name=i.participant.name if i.participant else "SYSTEM",
                    participant_position=i.participant_snapshot_position,
                    confidence=(
                        getattr(i.participant, "confidence_score", 1.0)
                        if i.participant
                        else 1.0
                    ),
                    text=i.answer,
                    usage=UsageStats(
                        input_tokens=i.input_tokens,
                        output_tokens=i.output_tokens,
                        cost=i.cost,
                    ),
                )
            )

        p_entries = []
        for p in self.participants:
            p_entries.append(
                ParticipantEntry(
                    name=p.name,
                    role=p.role.value,
                    attitude_type=p.attitude_type.value,
                    brain=p.brain.value,
                    initial_brain=(
                        p.initial_brain.value if p.initial_brain else p.brain.value
                    ),
                    original_position=(
                        p.original_position if p.original_position else "N/A"
                    ),
                    final_position=p.current_position,
                    gender=p.gender.value,
                    ethnic_group=p.ethnic_group.value,
                    tolerant=p.tolerant,
                    insults_allowed=p.insults_allowed,
                    lies_allowed=p.lies_allowed,
                    is_vetoed=p.is_vetoed,
                    veto_reason=p.veto_reason,
                    strikes=p.strikes,
                    skip_next_turn=p.skip_next_turn,
                    total_cost=p.total_cost,
                    order_in_debate=p.order_in_debate,
                    confidence_history=p.confidence_history,
                    final_confidence=p.confidence_score,
                )
            )
            final_total_cost += p.total_cost

        if self.moderator:
            final_total_cost += self.moderator.total_cost

        meta = DebateMetadata(
            id=self.debate_id,
            session_id=self.session_id,
            topic=self.topic_name,
            description=self.description,
            date=datetime.now().isoformat(),
            total_rounds_configured=self.total_rounds,
            total_turns_configured=self.total_turns,
            allowed_positions=self.allowed_positions,
            total_estimated_cost_usd=final_total_cost,
        )

        final_result = DebateResult(
            metadata=meta,
            participants=p_entries,
            moderator=(
                self.moderator.model_dump(mode="json") if self.moderator else None
            ),
            moderator_stats=ModeratorStats(**self.moderator_stats),
            position_changes=self.position_changes_log,
            transcript=transcript_entries,
            evaluation=self.evaluation_data,
        )

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(final_result.model_dump_json(indent=4, by_alias=True))

        return full_path
