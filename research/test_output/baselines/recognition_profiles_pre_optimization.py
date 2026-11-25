
from pathlib import Path

from poker_apis.vision.card_recognition import (
    CardRecognizer
)

from poker_apis.vision.simulator_card_recognition import (
    SimulatorCardRecognizer
)


class RecognitionProfileManager:
    """
    Manages recognition profiles for offline
    calibration and simulator datasets.
    """

    PROFILE_MAPPING = {
        "calibration": "calibration",
        "synthetic": "simulator"
    }

    def __init__(self, project_root=None):

        if project_root is None:

            project_root = (
                Path(__file__).resolve().parents[2]
            )

        self.project_root = Path(project_root)

        self._recognizers = {}

    # --------------------------------------------------
    # CREATE CALIBRATION RECOGNIZER
    # --------------------------------------------------

    def _create_calibration_recognizer(self):

        template_dir = (
            self.project_root
            / "test_assets/card_templates/suits"
        )

        recognizer = CardRecognizer(
            suit_template_dir=template_dir
        )

        if len(recognizer.suit_templates) != 4:

            raise RuntimeError(
                "Calibration profile requires "
                "all four suit templates."
            )

        return recognizer

    # --------------------------------------------------
    # CREATE SIMULATOR RECOGNIZER
    # --------------------------------------------------

    def _create_simulator_recognizer(self):

        template_dir = (
            self.project_root
            / "test_assets/card_templates/simulator_suits"
        )

        recognizer = SimulatorCardRecognizer(
            suit_template_dir=template_dir
        )

        if recognizer.template_count < 4:

            raise RuntimeError(
                "Insufficient simulator templates."
            )

        return recognizer

    # --------------------------------------------------
    # GET PROFILE
    # --------------------------------------------------

    def get_profile_name(self, dataset_type):

        profile_name = self.PROFILE_MAPPING.get(
            dataset_type
        )

        if profile_name is None:

            raise ValueError(
                f"Unsupported dataset type: "
                f"{dataset_type}"
            )

        return profile_name

    # --------------------------------------------------
    # GET RECOGNIZER
    # --------------------------------------------------

    def get_recognizer(self, dataset_type):

        profile_name = self.get_profile_name(
            dataset_type
        )

        if profile_name in self._recognizers:

            return self._recognizers[
                profile_name
            ]

        print(
            f"\nInitializing recognition profile: "
            f"{profile_name}"
        )

        if profile_name == "calibration":

            recognizer = (
                self._create_calibration_recognizer()
            )

        elif profile_name == "simulator":

            recognizer = (
                self._create_simulator_recognizer()
            )

        else:

            raise ValueError(
                f"Unknown profile: {profile_name}"
            )

        self._recognizers[profile_name] = (
            recognizer
        )

        return recognizer

    # --------------------------------------------------
    # PROFILE INFORMATION
    # --------------------------------------------------

    def get_profile_info(self, dataset_type):

        profile_name = self.get_profile_name(
            dataset_type
        )

        recognizer = self.get_recognizer(
            dataset_type
        )

        template_count = getattr(
            recognizer,
            "template_count",
            len(recognizer.suit_templates)
        )

        return {
            "profile": profile_name,
            "recognizer": type(recognizer).__name__,
            "template_count": template_count,
            "rank_confidence_threshold": (
                recognizer.confidence_threshold
            ),
            "suit_confidence_threshold": (
                recognizer.suit_confidence_threshold
            ),
            "suit_margin_threshold": (
                recognizer.suit_margin_threshold
            )
        }

    # --------------------------------------------------
    # LOADED PROFILES
    # --------------------------------------------------

    @property
    def loaded_profiles(self):

        return list(
            self._recognizers.keys()
        )
