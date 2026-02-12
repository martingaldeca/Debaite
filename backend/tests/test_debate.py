import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend acts as root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from debates.base import Debate


@pytest.fixture
def mock_env():
    with patch.dict(
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
    ):
        yield


@pytest.fixture
def mock_completion():
    # We mock litellm.completion used in Debate and Debater
    with (
        patch("debates.base.completion") as m1,
        patch("debates.models.participant.completion") as m2,
    ):
        # Setup mock response structure
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "I argue that A is correct because of B."
        )
        mock_response._hidden_params.get.return_value = 0.001

        m1.return_value = mock_response
        m2.return_value = mock_response
        yield m1


def test_debate_initialization(mock_env):
    d = Debate(
        "Test Topic", "Test Description", ["Position A", "Position B"], "test_session"
    )
    assert len(d.participants) == 2
    assert d.topic_name == "Test Topic"


def test_run_generator_flow(mock_env, mock_completion):
    d = Debate(
        "Test Topic", "Test Description", ["Position A", "Position B"], "test_session"
    )

    # We need to ensure Debater.answer returns an Intervention
    # The actual implementation calls LLM.
    # Our mock_completion handles the call.

    events = list(d.run_generator())

    assert len(events) > 0
    assert events[0]["type"] == "initial_state"

    # Check for intervention events
    interventions = [e for e in events if e["type"] == "intervention"]
    assert len(interventions) > 0

    # Check for debate_finished
    assert events[-1]["type"] == "debate_finished"


def test_moderator_intervention(mock_env, mock_completion):
    # Force moderator existence
    overrides = {"mod_role": "expert"}
    d = Debate("Test", "Desc", ["A", "B"], "sess", overrides=overrides)
    assert d.moderator is not None

    # Run
    events = list(d.run_generator())
    assert any(
        e["type"] == "intervention" and e.get("participant") == d.moderator.name
        for e in events
    )
