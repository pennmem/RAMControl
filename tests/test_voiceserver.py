import os.path as osp
import time
import pytest
import zmq
#import logging
#logging.basicConfig(level=logging.DEBUG)

from voiceserver import VoiceServer
from util import data_path


@pytest.fixture
def voice_server():
    """Return a :class:`VoiceServer` instance."""
    server = VoiceServer(filename=osp.join(data_path(), "one-two-three.wav"))
    yield server
    if server.is_alive():
        server.terminate()


class TestVoiceServer:
    def test_quit(self, voice_server):
        voice_server.start()
        assert voice_server.is_alive()
        time.sleep(0.1)
        voice_server.quit()
        assert voice_server.done.is_set()
        voice_server.join(timeout=1)

    def test_sending_messages(self, voice_server):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.SUB)
        sock.setsockopt(zmq.SUBSCRIBE, b"")
        port = sock.bind_to_random_port("tcp://*")


        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)

        voice_server.addr = "tcp://127.0.0.1:%d" % port
        voice_server.start()

        msgs = []
        for n in range(10):
            if sock in dict(poller.poll(timeout=10)):
                msgs.append(sock.recv_json())
                for key in ["state", "timestamp", "value"]:
                    assert key in msgs[-1]
            else:
                time.sleep(0.1)
                continue

        voice_server.quit()

        assert len(msgs) > 0
