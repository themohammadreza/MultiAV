import sys
import types
from pathlib import Path

# Ensure application package is importable for unit tests
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Provide lightweight stubs for external dependencies used only at import time
boto3_stub = types.SimpleNamespace(session=types.SimpleNamespace(Session=lambda *args, **kwargs: None))
botocore_exc_stub = types.SimpleNamespace(ClientError=Exception)

sys.modules.setdefault("boto3", boto3_stub)
sys.modules.setdefault("botocore", types.SimpleNamespace(exceptions=botocore_exc_stub))
sys.modules.setdefault("botocore.exceptions", botocore_exc_stub)


class _DummyRuleSet:
    def match(self, filepath):  # noqa: ANN001 - test stub
        return []


class _YaraStub:
    __version__ = "stub"
    Error = Exception

    def compile(self, filepath=None):  # noqa: ANN001 - signature compatibility not required
        return _DummyRuleSet()


sys.modules.setdefault("yara", _YaraStub())
