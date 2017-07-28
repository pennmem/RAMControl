import os
import os.path as osp
import shutil
from tempfile import mkdtemp
import random
import pytest
from ramupload.upload import Uploader


@pytest.fixture
def uploader():
    instance = Uploader("R0000X")
    yield instance


@pytest.fixture
def img_path():
    path = mkdtemp()
    with open(osp.join(path, "image.bmp"), "wb") as ifile:
        data = [random.randint(0, 255) for _ in range(256)]
        ifile.write(''.join([str(n) for n in data]))
    yield path
    shutil.rmtree(path)


@pytest.fixture
def dest_path():
    dest = mkdtemp()
    yield dest
    shutil.rmtree(dest)


def test_rsync(uploader, img_path, dest_path):
    failure = uploader.rsync(img_path, dest_path)
    assert not failure

    assert [f in os.listdir(img_path) for f in os.listdir(dest_path)]

    with open(osp.join(img_path, 'image.bmp'), 'rb') as ifile:
        orig_data = ifile.read()

    with open(osp.join(dest_path, 'image.bmp'), 'rb') as ifile:
        assert ifile.read() == orig_data


def test_upload_clinical_eeg(uploader, img_path, dest_path):
    with pytest.raises(OSError):
        uploader.upload_clinical_eeg('nonexistantpath', dest_path)
