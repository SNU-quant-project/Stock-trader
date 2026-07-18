import unittest
import importlib.util
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

ALPACA_AVAILABLE = importlib.util.find_spec("alpaca") is not None
if ALPACA_AVAILABLE:
    import live_trade
else:
    live_trade = None


@unittest.skipUnless(ALPACA_AVAILABLE, "alpaca-py is not installed")
class LiveTradeGuardTests(unittest.TestCase):
    def test_expected_completed_bar_waits_for_first_30m_bar(self):
        pre_first = pd.Timestamp("2026-07-01 09:45", tz=live_trade.MARKET_TZ)
        after_first = pd.Timestamp("2026-07-01 10:01", tz=live_trade.MARKET_TZ)

        self.assertIsNone(live_trade._expected_completed_bar_start(pre_first))
        self.assertEqual(
            live_trade._expected_completed_bar_start(after_first),
            pd.Timestamp("2026-07-01 09:30"),
        )

    def test_data_freshness_blocks_fetch_failure(self):
        now = pd.Timestamp("2026-07-01 10:31", tz=live_trade.MARKET_TZ)
        status = live_trade.LiveDataStatus(
            symbol="AAPL",
            fetch_failed=True,
            fetch_error="timeout",
            last_bar=pd.Timestamp("2026-07-01 10:00"),
        )

        ok, reason = live_trade._check_data_freshness(
            {"AAPL": status}, ["AAPL"], now)

        self.assertFalse(ok)
        self.assertIn("latest Alpaca fetch failed", reason)

    def test_data_freshness_accepts_expected_completed_bar(self):
        now = pd.Timestamp("2026-07-01 10:31", tz=live_trade.MARKET_TZ)
        status = live_trade.LiveDataStatus(
            symbol="AAPL",
            last_bar=pd.Timestamp("2026-07-01 10:00"),
        )

        ok, reason = live_trade._check_data_freshness(
            {"AAPL": status}, ["AAPL"], now)

        self.assertTrue(ok, reason)

    def test_cancel_open_orders_returns_false_on_timeout(self):
        order = SimpleNamespace(id="order-1")

        class FakeTradingClient:
            def get_orders(self, filter):
                return [order]

            def cancel_order_by_id(self, order_id):
                return None

        ok = live_trade.cancel_open_orders_for_symbols(
            FakeTradingClient(), ["AAPL"], timeout_sec=0.01, poll_sec=0.001)

        self.assertFalse(ok)

    def test_shortability_checks_only_new_or_increased_shorts(self):
        checked = []

        class FakeTradingClient:
            def get_asset(self, symbol):
                checked.append(symbol)
                return SimpleNamespace(
                    tradable=True,
                    shortable=True,
                    easy_to_borrow=True,
                )

        targets = {"AAPL": -10, "MSFT": -5, "TSLA": 5}
        positions = {"AAPL": 0, "MSFT": -20, "TSLA": 10}

        ok, reason = live_trade._check_shortability(
            FakeTradingClient(), targets, positions)

        self.assertTrue(ok, reason)
        self.assertEqual(checked, ["AAPL"])

    def test_position_snapshot_guard_blocks_missing_prior_positions(self):
        expected = {sym: 10 for sym in live_trade.SYMBOLS[:12]}
        positions = {live_trade.SYMBOLS[0]: 10}

        ok, reason, details = live_trade._check_position_snapshot(
            positions, expected, "2026-07-07 10:01:15")

        self.assertFalse(ok)
        self.assertIn("coverage", reason)
        self.assertIn("expected_nonzero=12", details)
        self.assertIn("actual_expected_nonzero=1", details)

    def test_position_snapshot_guard_skips_without_prior_book(self):
        ok, reason, _ = live_trade._check_position_snapshot(
            {}, {}, "")

        self.assertTrue(ok, reason)
        self.assertIn("prior target snapshot", reason)

    def test_latest_logged_expected_positions_skips_no_trade_cycle(self):
        symbols = list(live_trade.SYMBOLS[:12])
        rows = []
        for sym in symbols:
            rows.append({
                "timestamp": "2026-07-07 15:31:15",
                "symbol": sym,
                "target": 10,
            })
            rows.append({
                "timestamp": "2026-07-08 09:31:15",
                "symbol": sym,
                "target": "",
            })

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_log.csv"
            pd.DataFrame(rows).to_csv(path, index=False)

            expected, source = live_trade._latest_logged_expected_positions(
                symbols, log_path=path, min_expected=10)

        self.assertEqual(source, "2026-07-07 15:31:15")
        self.assertEqual(len(expected), 12)
        self.assertEqual(expected[symbols[0]], 10)

    def test_market_submit_guard_blocks_closed_market(self):
        class FakeTradingClient:
            def get_clock(self):
                return SimpleNamespace(
                    is_open=False,
                    timestamp=pd.Timestamp(
                        "2026-07-01 08:00", tz=live_trade.MARKET_TZ),
                    next_close=pd.Timestamp(
                        "2026-07-01 16:00", tz=live_trade.MARKET_TZ),
                )

        ok, reason = live_trade._check_market_open_for_submit(
            FakeTradingClient())

        self.assertFalse(ok)
        self.assertIn("market closed", reason)

    def test_manifest_freshness_requires_previous_weekday_artifacts(self):
        manifest = {
            "schema_version": 1,
            "approved": True,
            "trained_through_date": "2026-06-30",
            "beta_asof_date": "2026-06-30",
            "universe": list(live_trade.SYMBOLS),
            "strategies": {sym: f"/tmp/{sym}.joblib" for sym in live_trade.SYMBOLS},
            "beta_by_symbol": {sym: 1.0 for sym in live_trade.SYMBOLS},
        }

        ok, reason = live_trade._check_manifest_freshness(
            manifest, pd.Timestamp("2026-07-01").date())

        self.assertTrue(ok, reason)

        manifest["beta_asof_date"] = "2026-06-29"
        ok, reason = live_trade._check_manifest_freshness(
            manifest, pd.Timestamp("2026-07-01").date())

        self.assertFalse(ok)
        self.assertIn("beta_asof_date", reason)

    def test_manifest_freshness_accepts_previous_trading_day_after_holiday(self):
        manifest = {
            "schema_version": 1,
            "approved": True,
            "trained_through_date": "2026-07-02",
            "beta_asof_date": "2026-07-02",
            "universe": list(live_trade.SYMBOLS),
            "strategies": {sym: f"/tmp/{sym}.joblib" for sym in live_trade.SYMBOLS},
            "beta_by_symbol": {sym: 1.0 for sym in live_trade.SYMBOLS},
        }

        ok, reason = live_trade._check_manifest_freshness(
            manifest,
            pd.Timestamp("2026-07-06").date(),
            required_date=date(2026, 7, 2),
        )

        self.assertTrue(ok, reason)

    def test_previous_trading_day_uses_alpaca_calendar(self):
        class FakeTradingClient:
            def get_calendar(self, filters):
                return [
                    SimpleNamespace(date=date(2026, 7, 1)),
                    SimpleNamespace(date=date(2026, 7, 2)),
                ]

        self.assertEqual(
            live_trade._previous_trading_day(
                FakeTradingClient(), pd.Timestamp("2026-07-06").date()),
            date(2026, 7, 2),
        )

    def test_latest_closed_session_handles_market_holiday_morning(self):
        class FakeTradingClient:
            def get_calendar(self, filters):
                return [
                    SimpleNamespace(
                        date=date(2026, 7, 1),
                        close=pd.Timestamp("2026-07-01 16:00"),
                    ),
                    SimpleNamespace(
                        date=date(2026, 7, 2),
                        close=pd.Timestamp("2026-07-02 16:00"),
                    ),
                ]

        session_date, close_et = live_trade._latest_closed_trading_session(
            FakeTradingClient(),
            pd.Timestamp("2026-07-03 08:35", tz=live_trade.MARKET_TZ),
        )

        self.assertEqual(session_date, date(2026, 7, 2))
        self.assertEqual(
            live_trade._to_et_naive(close_et),
            pd.Timestamp("2026-07-02 16:00"),
        )

    def test_eod_freshness_uses_latest_closed_session_last_bar(self):
        statuses = {
            "AAPL": live_trade.LiveDataStatus(
                symbol="AAPL",
                last_bar=pd.Timestamp("2026-07-02 15:30"),
            ),
            "SPY": live_trade.LiveDataStatus(
                symbol="SPY",
                last_bar=pd.Timestamp("2026-07-02 15:30"),
            ),
        }

        ok, reason = live_trade._check_eod_data_freshness(
            statuses,
            ["AAPL", "SPY"],
            date(2026, 7, 2),
            pd.Timestamp("2026-07-02 16:00", tz=live_trade.MARKET_TZ),
        )

        self.assertTrue(ok, reason)

    def test_manifest_freshness_requires_approved_complete_manifest(self):
        manifest = {
            "schema_version": 1,
            "approved": False,
            "trained_through_date": "2026-06-30",
            "beta_asof_date": "2026-06-30",
            "universe": list(live_trade.SYMBOLS),
            "strategies": {sym: f"/tmp/{sym}.joblib" for sym in live_trade.SYMBOLS},
            "beta_by_symbol": {sym: 1.0 for sym in live_trade.SYMBOLS},
        }

        ok, reason = live_trade._check_manifest_freshness(
            manifest, pd.Timestamp("2026-07-01").date())

        self.assertFalse(ok)
        self.assertIn("not approved", reason)

        manifest["approved"] = True
        manifest["beta_by_symbol"].pop(live_trade.SYMBOLS[0])
        ok, reason = live_trade._check_manifest_freshness(
            manifest, pd.Timestamp("2026-07-01").date())

        self.assertFalse(ok)
        self.assertIn("beta missing", reason)

    def test_loop_artifact_reload_loads_new_latest_manifest(self):
        old_manifest = {
            "schema_version": 1,
            "approved": True,
            "run_id": "old-run",
            "created_at": "2026-07-16T17:01:00-04:00",
            "trained_through_date": "2026-07-16",
            "beta_asof_date": "2026-07-16",
            "universe": list(live_trade.SYMBOLS),
            "strategies": {sym: f"/tmp/{sym}.joblib" for sym in live_trade.SYMBOLS},
            "beta_by_symbol": {sym: 1.0 for sym in live_trade.SYMBOLS},
        }
        latest_manifest = dict(old_manifest)
        latest_manifest.update({
            "run_id": "new-run",
            "created_at": "2026-07-17T17:01:00-04:00",
            "trained_through_date": "2026-07-17",
            "beta_asof_date": "2026-07-17",
        })

        with TemporaryDirectory() as tmp:
            latest_dir = Path(tmp) / "latest"
            latest_dir.mkdir(parents=True)
            (latest_dir / "manifest.json").write_text(
                json.dumps(latest_manifest),
                encoding="utf-8",
            )

            with patch.object(live_trade, "LIVE_MODEL_DIR", Path(tmp)), \
                    patch.object(
                        live_trade,
                        "_previous_trading_day",
                        return_value=date(2026, 7, 17),
                    ), \
                    patch.object(
                        live_trade,
                        "load_approved_live_artifacts",
                        return_value=("new_strategies", "new_histories", {"AAPL": 1.0}, latest_manifest),
                    ) as loader:
                result = live_trade.reload_approved_live_artifacts_if_needed(
                    trading_client=object(),
                    strategies="old_strategies",
                    histories="old_histories",
                    approved_beta_map={"AAPL": 0.5},
                    approved_manifest=old_manifest,
                    dry_run=False,
                )

        self.assertEqual(result[0], "new_strategies")
        self.assertEqual(result[3]["run_id"], "new-run")
        loader.assert_called_once()

    def test_loop_artifact_reload_fails_closed_when_latest_manifest_is_stale(self):
        stale_manifest = {
            "schema_version": 1,
            "approved": True,
            "run_id": "stale-run",
            "created_at": "2026-07-16T17:01:00-04:00",
            "trained_through_date": "2026-07-16",
            "beta_asof_date": "2026-07-16",
            "universe": list(live_trade.SYMBOLS),
            "strategies": {sym: f"/tmp/{sym}.joblib" for sym in live_trade.SYMBOLS},
            "beta_by_symbol": {sym: 1.0 for sym in live_trade.SYMBOLS},
        }

        with TemporaryDirectory() as tmp:
            latest_dir = Path(tmp) / "latest"
            latest_dir.mkdir(parents=True)
            (latest_dir / "manifest.json").write_text(
                json.dumps(stale_manifest),
                encoding="utf-8",
            )

            with patch.object(live_trade, "LIVE_MODEL_DIR", Path(tmp)), \
                    patch.object(
                        live_trade,
                        "_previous_trading_day",
                        return_value=date(2026, 7, 17),
                    ), \
                    patch.object(live_trade, "load_approved_live_artifacts") as loader:
                with self.assertRaises(RuntimeError):
                    live_trade.reload_approved_live_artifacts_if_needed(
                        trading_client=object(),
                        strategies="old_strategies",
                        histories="old_histories",
                        approved_beta_map={"AAPL": 0.5},
                        approved_manifest=stale_manifest,
                        dry_run=False,
                    )

        loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
