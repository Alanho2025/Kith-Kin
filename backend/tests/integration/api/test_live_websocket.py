from fastapi.testclient import TestClient

from tests.fixtures.runtime_streams import PCM_FRAME

from .conftest import ORIGIN, create_session, issue_ticket


def test_valid_socket_emits_ready_before_reading_audio(app_client: TestClient) -> None:
    session_id = create_session(app_client)
    issue_ticket(app_client, session_id)

    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        ready = socket.receive_json()
        assert ready["event_type"] == "session.ready"
        assert ready["sequence"] == 1
        assert ready["payload"]["input_audio_format"]["encoding"] == "pcm_s16le"


def test_fake_runtime_echoes_binary_audio_after_ready(app_client: TestClient) -> None:
    session_id = create_session(app_client)
    issue_ticket(app_client, session_id)

    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        assert socket.receive_json()["event_type"] == "session.ready"
        assert socket.receive_json()["event_type"] == "audio.listening"
        socket.send_bytes(PCM_FRAME)
        assert socket.receive_bytes() == PCM_FRAME
