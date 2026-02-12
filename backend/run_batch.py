import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from debates.base import Debate
from debates.logger import logger
from debates.models.results import (
    FinalSummaryResult,
    HighlightTurn,
    PositionChangeEntry,
    PositionStat,
    ScoreStat,
    SessionSummary,
    WinnerDetail,
)
from dotenv import load_dotenv

load_dotenv()


class DebateBatchSummarizer:
    def __init__(self, result_paths: List[Path]):
        self.result_paths = result_paths

        self.total_cost = 0.0
        self.total_participants = 0
        self.total_rounds = 0
        self.global_scores: List[float] = []
        self.mod_stats_acc = {
            "total_interventions": 0,
            "total_sanctions": 0,
            "total_skips": 0,
            "total_vetos": 0,
            "total_stops": 0,
            "total_limits": 0,
        }

        self.winners_by_pos: List[str] = []
        self.winners_details: List[WinnerDetail] = []
        self.all_position_changes: List[PositionChangeEntry] = []
        self.highlight_turns: List[HighlightTurn] = []

        self.pos_stats_raw: Dict[str, Dict[str, List[float]]] = {}
        self.scores_by_pos_raw: Dict[str, List[float]] = {}

        self.session_folder: Optional[Path] = None

    def generate_report(self) -> None:
        logger.info("=== STARTING GLOBAL SUMMARY ANALYSIS ===")

        if not self.result_paths:
            logger.warning("No result paths provided.")
            return

        self.session_folder = self.result_paths[0].parent

        for path in self.result_paths:
            self._process_single_file(path)

        self._save_summary_json()

    def _process_single_file(self, path: Path) -> None:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            return

        meta = data.get("metadata", {})
        self.total_cost += meta.get("total_estimated_cost_usd", 0.0)
        self.total_rounds += meta.get("total_rounds_configured", 0)

        parts = data.get("participants", [])
        self.total_participants += len(parts)

        parts_map = {p["name"]: p for p in parts}

        m_stats = data.get("moderator_stats", {})
        self.mod_stats_acc["total_interventions"] += m_stats.get("interventions", 0)
        self.mod_stats_acc["total_sanctions"] += m_stats.get("sanctions", 0)
        self.mod_stats_acc["total_skips"] += m_stats.get("skips", 0)
        self.mod_stats_acc["total_vetos"] += m_stats.get("vetos", 0)
        self.mod_stats_acc["total_stops"] += m_stats.get("stops", 0)
        self.mod_stats_acc["total_limits"] += m_stats.get("limits", 0)

        changes = data.get("position_changes", [])
        for c in changes:
            c["debate_id"] = meta.get("id")
            self.all_position_changes.append(PositionChangeEntry(**c))

        eval_sec = data.get("evaluation", {})
        outcome = eval_sec.get("global_outcome")

        if outcome:
            win_name = outcome.get("winner_name")
            win_pos = outcome.get("winner_position")
            self.winners_by_pos.append(win_pos)
            self.winners_details.append(
                WinnerDetail(
                    debate_id=meta.get("id"),
                    winner_name=win_name,
                    winner_position=win_pos,
                )
            )

            avg_scores_map = outcome.get("average_scores", {})
            self.global_scores.extend(avg_scores_map.values())

            for p_name, p_score in avg_scores_map.items():
                p_data = parts_map.get(p_name)
                if p_data:
                    pos = (
                        p_data.get("final_position")
                        or p_data.get("original_position")
                        or "Unknown"
                    )
                    if pos not in self.scores_by_pos_raw:
                        self.scores_by_pos_raw[pos] = []
                    self.scores_by_pos_raw[pos].append(p_score)

            if outcome.get("best_intervention"):
                bi = outcome["best_intervention"]
                p_name = bi.get("participant", "Unknown")
                p_data = parts_map.get(p_name)
                p_conf = p_data.get("final_confidence", 0.0) if p_data else 0.0
                p_pos = (
                    p_data.get("final_position") or p_data.get("original_position")
                    if p_data
                    else "Unknown"
                )

                self.highlight_turns.append(
                    HighlightTurn(
                        debate_id=meta.get("id"),
                        type="BEST",
                        text=bi["text"][:300] + "...",
                        participant_name=p_name,
                        participant_position=p_pos,
                        participant_confidence=p_conf,
                    )
                )

            if outcome.get("worst_intervention"):
                wi = outcome["worst_intervention"]
                p_name = wi.get("participant", "Unknown")
                p_data = parts_map.get(p_name)
                p_conf = p_data.get("final_confidence", 0.0) if p_data else 0.0
                p_pos = (
                    p_data.get("final_position") or p_data.get("original_position")
                    if p_data
                    else "Unknown"
                )

                self.highlight_turns.append(
                    HighlightTurn(
                        debate_id=meta.get("id"),
                        type="WORST",
                        text=wi["text"][:300] + "...",
                        participant_name=p_name,
                        participant_position=p_pos,
                        participant_confidence=p_conf,
                    )
                )

        for p in parts:
            pos = p.get("original_position", "Unknown")
            if pos not in self.pos_stats_raw:
                self.pos_stats_raw[pos] = {"initial": [], "final": []}

            conf_hist = p.get("confidence_history", [1.0])
            self.pos_stats_raw[pos]["initial"].append(conf_hist[0])
            self.pos_stats_raw[pos]["final"].append(p.get("final_confidence", 1.0))

    def _save_summary_json(self):
        if not self.session_folder:
            return

        avg_score = (
            sum(self.global_scores) / len(self.global_scores)
            if self.global_scores
            else 0.0
        )

        pos_dist = {}
        total_p = sum(len(v["initial"]) for v in self.pos_stats_raw.values())

        for pos, val in self.pos_stats_raw.items():
            count = len(val["initial"])
            perc = (count / total_p) * 100 if total_p > 0 else 0
            pos_dist[pos] = PositionStat(
                count=count,
                mean_initial_confidence=sum(val["initial"]) / count if count else 0,
                mean_final_confidence=sum(val["final"]) / count if count else 0,
                percentage=round(perc, 2),
            )

        mean_scores_data = {}
        for pos, scores in self.scores_by_pos_raw.items():
            if scores:
                mean_scores_data[pos] = ScoreStat(
                    mean=round(sum(scores) / len(scores), 2),
                    max=max(scores),
                    min=min(scores),
                    count=len(scores),
                )

        summary = FinalSummaryResult(
            session_summary=SessionSummary(
                total_debates=len(self.result_paths),
                total_cost_usd=self.total_cost,
                total_rounds=self.total_rounds,
                total_participants=self.total_participants,
                global_avg_score=round(avg_score, 2),
                date_generated=datetime.now().isoformat(),
            ),
            moderator_summary=self.mod_stats_acc,
            winners_by_position=dict(Counter(self.winners_by_pos)),
            winners_details=self.winners_details,
            position_changes=self.all_position_changes,
            final_position_distribution=pos_dist,
            mean_scores=mean_scores_data,
            highlight_turns=self.highlight_turns,
        )

        logger.info("==========================================")
        logger.info("          GLOBAL DEBATE SUMMARY           ")
        logger.info("==========================================")

        s = summary.session_summary
        logger.info(f"Total Debates Run: {s.total_debates}")
        logger.info(f"Total Cost:        ${s.total_cost_usd:.4f}")
        logger.info(f"Total Participants:{s.total_participants}")
        logger.info(f"Global Avg Score:  {s.global_avg_score:.2f}")

        logger.info("\n--- MODERATOR ACTIVITY ---")
        m = summary.moderator_summary
        logger.info(f"Interventions: {m.get('total_interventions', 0)}")
        logger.info(f"Sanctions:     {m.get('total_sanctions', 0)}")
        logger.info(f"Vetos:         {m.get('total_vetos', 0)}")
        logger.info(f"Stops:         {m.get('total_stops', 0)}")
        logger.info(f"Limits:        {m.get('total_limits', 0)}")
        logger.info(f"Skips:         {m.get('total_skips', 0)}")

        logger.info("\n--- WINNERS BY POSITION ---")
        if summary.winners_by_position:
            sorted_w = sorted(
                summary.winners_by_position.items(), key=lambda x: x[1], reverse=True
            )
            for pos, count in sorted_w:
                logger.info(f"   - {pos}: {count} wins")
        else:
            logger.info("   (No winners declared)")

        logger.info("\n--- SCORES BY POSITION ---")
        sorted_scores = sorted(
            mean_scores_data.items(), key=lambda x: x[1].mean, reverse=True
        )
        for pos, stat in sorted_scores:
            logger.info(
                f"   - {pos}: Avg: {stat.mean} | Max: {stat.max} | Min: {stat.min}"
            )

        logger.info("\n--- POSITION CHANGES ---")
        changes = summary.position_changes
        logger.info(f"Total swaps: {len(changes)}")
        for i, change in enumerate(changes[:10]):
            logger.info(
                f"   - {change.name}: '{change.from_position}' -> '{change.to_position}' (Round {change.round_when_changed})"
            )
        if len(changes) > 10:
            logger.info(f"   ... and {len(changes) - 10} more.")

        logger.info("\n--- FINAL POSITION DISTRIBUTION ---")
        d = summary.final_position_distribution
        sorted_d = sorted(d.items(), key=lambda x: x[1].count, reverse=True)
        for pos, stat in sorted_d:
            logger.info(f"   - {pos}: {stat.count} participants ({stat.percentage}%)")

        logger.info("==========================================")

        path = self.session_folder / "final_summary.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=4, by_alias=True))

        logger.info(f"Global summary saved to: {path}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debate Simulation Runner")
    parser.add_argument("config_file", type=Path, help="Path to JSON config")
    parser.add_argument("--repetitions", type=int, help="Override repetitions")
    parser.add_argument(
        "--parallel", action="store_true", help="Enable parallel execution"
    )
    parser.add_argument(
        "--max-turn-letters",
        type=int,
        help="Override max letters per turn (fixed value)",
    )

    cpu_count = os.cpu_count() or 1
    default_workers = max(1, cpu_count // 2)
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers,
        help=f"Worker threads (default: {default_workers} based on {cpu_count} cores)",
    )

    parser.add_argument("--part-role", type=str, help="Force role for all participants")
    parser.add_argument(
        "--part-brain", type=str, help="Force brain for all participants"
    )
    parser.add_argument(
        "--part-attitude", type=str, help="Force attitude for all participants"
    )
    parser.add_argument(
        "--part-mindset", type=str, help="Force mindset for all participants"
    )
    parser.add_argument(
        "--part-insults",
        type=str,
        help="Allow insults for all participants (true/false)",
    )
    parser.add_argument(
        "--part-lies", type=str, help="Allow lies for all participants (true/false)"
    )

    parser.add_argument("--mod-role", type=str, help="Force role for moderator")
    parser.add_argument("--mod-brain", type=str, help="Force brain for moderator")
    parser.add_argument("--mod-mindset", type=str, help="Force mindset for moderator")
    parser.add_argument(
        "--mod-insults", type=str, help="Allow insults for moderator (true/false)"
    )
    parser.add_argument(
        "--mod-lies", type=str, help="Allow lies for moderator (true/false)"
    )

    return parser.parse_args()


def _configure_environment(args: argparse.Namespace) -> None:
    pass


def _resolve_config_path(input_path: Path) -> Optional[Path]:
    if input_path.exists():
        return input_path
    alt = Path("debate_configurations") / input_path
    if alt.exists():
        logger.info(f"Config found in default directory: {alt}")
        return alt
    return None


def _get_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}

    mappings = [
        ("part_role", args.part_role, "PARTICIPANT_ROLE"),
        ("part_brain", args.part_brain, "PARTICIPANT_BRAIN"),
        ("part_attitude", args.part_attitude, "PARTICIPANT_ATTITUDE"),
        ("part_mindset", args.part_mindset, "PARTICIPANT_MINDSET"),
        ("part_gender", None, "PARTICIPANT_GENDER"),
        ("part_tolerant", None, "PARTICIPANT_TOLERANT"),
        ("part_insults", args.part_insults, "PARTICIPANT_INSULTS"),
        ("part_lies", args.part_lies, "PARTICIPANT_LIES"),
        ("mod_role", args.mod_role, "MODERATOR_ROLE"),
        ("mod_brain", args.mod_brain, "MODERATOR_BRAIN"),
        ("mod_attitude", None, "MODERATOR_ATTITUDE"),
        ("mod_mindset", args.mod_mindset, "MODERATOR_MINDSET"),
        ("mod_gender", None, "MODERATOR_GENDER"),
        ("mod_tolerant", None, "MODERATOR_TOLERANT"),
        ("mod_insults", args.mod_insults, "MODERATOR_INSULTS"),
        ("mod_lies", args.mod_lies, "MODERATOR_LIES"),
        ("max_letters", args.max_turn_letters, None),
    ]

    for key, arg_val, env_var in mappings:
        val = arg_val
        if not val and env_var:
            val = os.getenv(env_var)

        if val and str(val).strip():
            if str(val).lower() == "true":
                val = True
            elif str(val).lower() == "false":
                val = False
            overrides[key] = val

    return overrides


def run_single_debate(
    index: int, config: Dict[str, Any], session_id: str, overrides: Dict[str, Any]
) -> Optional[Path]:
    try:
        logger.info(f"Starting Run #{index + 1}")
        debate = Debate(
            topic_name=config["topic_name"],
            description=config["description"],
            allowed_positions=config["allowed_positions"],
            session_id=session_id,
            overrides=overrides,
        )
        result_path_str = debate.run()
        return Path(result_path_str) if result_path_str else None
    except Exception as e:
        logger.exception(f"Critical failure in Run #{index + 1}: {e}")
        return None


def main():
    args = parse_arguments()
    _configure_environment(args)

    config_path = _resolve_config_path(args.config_file)
    if not config_path:
        logger.error(f"Config not found: {args.config_file}")
        sys.exit(1)

    try:
        with open(config_path, encoding="utf-8") as config_file:
            config = json.load(config_file)
    except Exception as e:
        logger.error(f"Invalid JSON: {e}")
        sys.exit(1)

    overrides = _get_overrides(args)
    if overrides:
        logger.info(f"Active Overrides: {overrides}")

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    reps = args.repetitions or int(os.getenv("DEBATE_REPETITIONS", "1"))

    logger.info(f"Session: {session_id} | Repetitions: {reps}")
    successful: List[Path] = []

    if args.parallel:
        logger.info(f"Mode: PARALLEL ({args.workers} workers)")
        with ThreadPoolExecutor(max_workers=args.workers) as exc:
            futs: Dict[Future[Optional[Path]], int] = {
                exc.submit(run_single_debate, i, config, session_id, overrides): i
                for i in range(reps)
            }
            for future in as_completed(futs):
                if res := future.result():
                    successful.append(res)
    else:
        logger.info("Mode: SEQUENTIAL")
        for i in range(reps):
            if res := run_single_debate(i, config, session_id, overrides):
                successful.append(res)

    summarizer = DebateBatchSummarizer(successful)
    summarizer.generate_report()


if __name__ == "__main__":
    main()
