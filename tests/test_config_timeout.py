"""COM timeout env parsing is locked behavior (ADR-0007 follow-up)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from solidworks_mcp.config import get_config


class TestComTimeoutConfig(unittest.TestCase):
    def test_unset_defaults_to_disabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS", None)
            self.assertEqual(get_config().com_timeout_seconds, 0.0)

    def test_valid_value_is_parsed(self):
        with patch.dict(os.environ, {"SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS": "150"}):
            self.assertEqual(get_config().com_timeout_seconds, 150.0)

    def test_garbage_and_nonpositive_fall_back_to_disabled(self):
        for bad in ("abc", "-5", "0"):
            with patch.dict(os.environ, {"SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS": bad}):
                self.assertEqual(get_config().com_timeout_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
