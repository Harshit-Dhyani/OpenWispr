from app.config.constants import AppConstants as ConfigAppConstants
from app.config.constants import AudioConstants
from app.core.constants import AppConstants as CoreAppConstants


def test_config_constants_reexport_core_app_constants() -> None:
    assert ConfigAppConstants.APP_NAME == CoreAppConstants.APP_NAME
    assert ConfigAppConstants.APP_SLUG == CoreAppConstants.APP_SLUG
    assert ConfigAppConstants.DOWNLOAD_USER_AGENT == CoreAppConstants.DOWNLOAD_USER_AGENT


def test_config_constants_exposes_expected_sample_rates() -> None:
    assert AudioConstants.SAMPLE_RATES == [8000, 16000, 22050, 44100, 48000]
