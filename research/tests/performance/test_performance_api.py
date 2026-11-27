
import sys
import unittest

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(ROOT),
)


from fastapi.testclient import TestClient

from poker_apis.main import create_app


class PerformanceAPITests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):

        cls.context = TestClient(
            create_app()
        )

        cls.client = (
            cls.context.__enter__()
        )

        cls.response = cls.client.get(
            "/api/v1/performance/report"
        )

        cls.data = cls.response.json()

    @classmethod
    def tearDownClass(cls):

        cls.context.__exit__(
            None,
            None,
            None,
        )

    def test_status_code(self):

        self.assertEqual(
            self.response.status_code,
            200,
        )

    def test_success(self):

        self.assertTrue(
            self.data["success"]
        )

    def test_offline_mode(self):

        self.assertEqual(
            self.data["mode"],
            "offline",
        )

    def test_measurement_type(self):

        self.assertEqual(
            self.data["measurement_type"],
            "recorded_research_benchmarks",
        )

    def test_reports_available(self):

        self.assertEqual(
            self.data["summary"][
                "available_reports"
            ],
            12,
        )

    def test_no_missing_reports(self):

        self.assertEqual(
            self.data["summary"][
                "missing_report_count"
            ],
            0,
        )

    def test_preprocessing_count(self):

        self.assertEqual(
            len(
                self.data["preprocessing"][
                    "ranking"
                ]
            ),
            6,
        )

    def test_gaussian_candidate(self):

        candidate = self.data[
            "preprocessing"
        ][
            "best_normalized_accuracy_candidate"
        ]

        self.assertEqual(
            candidate["configuration"],
            "gaussian",
        )

    def test_latency_available(self):

        candidate = self.data[
            "preprocessing"
        ][
            "best_normalized_accuracy_candidate"
        ]

        self.assertGreater(
            candidate["mean_total_ms"],
            0,
        )

    def test_neural_workloads(self):

        self.assertEqual(
            len(
                self.data["neural_runtimes"]
            ),
            3,
        )

    def test_accuracy_models(self):

        self.assertEqual(
            len(
                self.data["accuracy_analysis"]
            ),
            3,
        )

    def test_limitations_available(self):

        self.assertGreater(
            len(self.data["limitations"]),
            0,
        )

    def test_no_unverified_speedup(self):

        self.assertFalse(
            self.data[
                "application_speedup_verified"
            ]
        )

    def test_existing_health_endpoint(self):

        response = self.client.get(
            "/health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_existing_info_endpoint(self):

        response = self.client.get(
            "/api/v1/info"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_existing_profiles_endpoint(self):

        response = self.client.get(
            "/api/v1/profiles"
        )

        self.assertEqual(
            response.status_code,
            200,
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )
