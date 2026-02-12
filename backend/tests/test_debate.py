import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure backend acts as root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from debates.base import Debate


class TestDebate(unittest.TestCase):
    def setUp(self):
        # Patch environment variables
        self.env_patcher = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "fake",
                "MIN_PARTICIPANTS": "2",
                "MAX_PARTICIPANTS": "2",
                "MIN_TOTAL_TURNS": "1",
                "MAX_TOTAL_TURNS": "1",
                "MIN_TOTAL_ROUNDS": "1",
                "MAX_TOTAL_ROUNDS": "1",
            },
        )
        self.env_patcher.start()

        # Patch completion calls
        self.mock_completion_base = patch("debates.base.completion").start()
        self.mock_completion_debate = patch(
            "debates.models.participant.completion"
        ).start()
        self.mock_completion_mod = patch("debates.models.moderator.completion").start()

        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "I argue that A is correct because of B."
        )
        mock_response._hidden_params.get.return_value = 0.001

        self.mock_completion_base.return_value = mock_response
        self.mock_completion_debate.return_value = mock_response
        self.mock_completion_mod.return_value = mock_response

        # Store mocks for assertion if needed
        self.mock_response = mock_response

    def tearDown(self):
        self.env_patcher.stop()
        patch.stopall()

    def test_debate_initialization(self):
        d = Debate(
            "Test Topic",
            "Test Description",
            ["Position A", "Position B"],
            "test_session",
        )
        self.assertEqual(len(d.participants), 2)
        self.assertEqual(d.topic_name, "Test Topic")

    def test_run_generator_flow(self):
        d = Debate(
            "Test Topic",
            "Test Description",
            ["Position A", "Position B"],
            "test_session",
        )

        # Generator execution
        events = list(d.run_generator())

        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]["type"], "initial_state")

        # Check for intervention events
        interventions = [e for e in events if e["type"] == "intervention"]
        self.assertGreater(len(interventions), 0)

        # Check for debate_finished
        self.assertEqual(events[-1]["type"], "debate_finished")

    def test_moderator_intervention(self):
        # Force moderator existence
        overrides = {"mod_role": "expert"}
        d = Debate("Test", "Desc", ["A", "B"], "sess", overrides=overrides)
        self.assertIsNotNone(d.moderator)

        # Run
        events = list(d.run_generator())

        has_mod_intervention = any(
            e["type"] == "intervention" and e.get("participant") == d.moderator.name
            for e in events
        )
        self.assertTrue(has_mod_intervention)


if __name__ == "__main__":
    unittest.main()
