"""Test script for EWAAgent local JSON repair integration."""

import os
import sys

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.ewa_agent import EWAAgent


def test_parse_arguments_local_repair():
    print("Test: _parse_json_arguments repairs code fences + trailing comma...")
    agent = EWAAgent(client=None, model="gpt-5")
    raw = """```json\n{\n  \"a\": 1,\n}\n```"""
    fixed = agent._parse_json_arguments(raw)
    assert isinstance(fixed, dict) and fixed.get("a") == 1, f"Unexpected parse result: {fixed}"
    print("  OK ->", fixed)


def test_repair_local_from_raw_arguments():
    print("Test: _repair_local repairs single quotes + unquoted keys...")
    agent = EWAAgent(client=None, model="gpt-5")
    previous = {
        "_parse_error": "JSONDecodeError",
        "raw_arguments": "{name: 'John', age: 30}",
    }
    repaired = agent._repair_local("", previous)
    assert isinstance(repaired, dict) and repaired.get("name") == "John" and repaired.get("age") == 30, (
        f"Unexpected repair result: {repaired}"
    )
    print("  OK ->", repaired)


def main():
    print("Running EWAAgent local JSON repair tests...")
    test_parse_arguments_local_repair()
    test_repair_local_from_raw_arguments()
    print("All tests completed successfully.")


if __name__ == "__main__":
    main()
