import pytest

# Test samples are generated at runtime to avoid storing binary fixtures in the
# repository while still providing common EICAR and clean-file content across
# unit suites.
@pytest.fixture
def eicar_file(tmp_path):
    """EICAR test file that all AVs should detect"""
    f = tmp_path / "eicar.txt"
    f.write_text("X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
    return f


@pytest.fixture
def clean_file(tmp_path):
    """Clean file that should not trigger detections"""
    f = tmp_path / "clean.txt"
    f.write_text("Hello, world!")
    return f
