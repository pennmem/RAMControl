import warnings
from ramcontrol.control import RAMControl


def test_deprecation_warning():
    with warnings.catch_warnings(record=True) as warning:
        warnings.simplefilter("always")
        import ramcontrol.RAMControl

        assert len(warning) is 1
        assert isinstance(warning[0], warnings.WarningMessage)
        assert "DeprecationWarning" in str(warning[0])

        assert ramcontrol.RAMControl.RAMControl == RAMControl
