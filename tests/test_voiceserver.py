import os.path as osp
import time
from multiprocessing import Pipe
import pytest

from ramcontrol.voiceserver import VoiceServer
from ramcontrol.util import data_path
from ramcontrol import exc, ipc


@pytest.fixture
def voice_server():
    parent_conn, pipe = Pipe()
    server = VoiceServer(pipe, filename=osp.join(data_path(), "one-two-three.wav"))
    yield (parent_conn, server)
    if server.is_alive():
        server.terminate()


class TestVoiceServer:
    def test_quit(self, voice_server):
        _, server = voice_server
        server.start()
        assert server.is_alive()
        time.sleep(0.1)
        server.quit()
        assert server.done.is_set()
        server.join(timeout=1)

    def test_sending_messages(self, voice_server):
        pipe, server = voice_server
        server.start()

        pipe.send(ipc.message("START"))
        assert pipe.recv()["type"] == "STARTED"
        pipe.send(ipc.message("STOP"))
        assert pipe.recv()["type"] == "STOPPED"

        server.quit()
