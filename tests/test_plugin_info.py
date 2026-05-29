from plugin_info import PLUGIN_NAME, PLUGIN_VERSION, SUPPORTED_MODELS


def test_plugin_info_exports_expected_metadata() -> None:
    assert PLUGIN_NAME == "nanaix_Comfy"
    assert PLUGIN_VERSION == "0.1.0"
    assert "gpt-image-2" in SUPPORTED_MODELS
