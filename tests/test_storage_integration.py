import asyncio
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.services.storage import get_storage_service


@pytest.mark.integration
def test_save_and_retrieve_file(tmp_path):
    storage = get_storage_service()

    content = b"integration test file"
    upload = UploadFile(file=(tmp_path / "file1").open("wb+"), filename="test.bin")
    upload.file.write(content)
    upload.file.seek(0)

    sha256, path = asyncio.get_event_loop().run_until_complete(storage.save_file(upload))

    assert Path(path).exists()
    assert Path(path).read_bytes() == content

    upload2 = UploadFile(file=(tmp_path / "file2").open("wb+"), filename="test2.bin")
    upload2.file.write(content)
    upload2.file.seek(0)

    sha256_2, path_2 = asyncio.get_event_loop().run_until_complete(storage.save_file(upload2))

    assert sha256 == sha256_2
    assert path == path_2
