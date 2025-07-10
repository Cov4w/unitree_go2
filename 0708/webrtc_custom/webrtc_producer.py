import asyncio
import threading
import time
import logging
import json
from multiprocessing import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from aiortc import MediaStreamTrack

# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)

def start_webrtc(frame_queue, conn):
    async def recv_camera_stream(track: MediaStreamTrack):
        while True:
            frame = await track.recv()
            img = frame.to_ndarray(format="bgr24")
            frame_queue.put(img)

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        async def setup():
            await conn.connect()
            conn.video.switchVideoChannel(True)
            conn.video.add_track_callback(recv_camera_stream)
        loop.run_until_complete(setup())
        loop.run_forever()

    loop = asyncio.new_event_loop()
    threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True).start()

async def _run_sportmode(conn, direction):
    try:
        # 현재 모션 모드 확인 및 normal로 전환
        response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001}
        )
        current_motion_switcher_mode = "normal"
        if response['data']['header']['status']['code'] == 0:
            data = json.loads(response['data']['data'])
            current_motion_switcher_mode = data['name']
            print(f"Current motion mode: {current_motion_switcher_mode}")

        if current_motion_switcher_mode != "normal":
            print(f"Switching motion mode from {current_motion_switcher_mode} to 'normal'...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"],
                {"api_id": 1002, "parameter": {"name": "normal"}}
            )
            await asyncio.sleep(5)

        # 명령 실행
        if direction == "forward":
            print("Moving forward...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"],
                {"api_id": SPORT_CMD["Move"], "parameter": {"x": 0.5, "y": 0, "z": 0}}
            )
        elif direction == "backward":
            print("Moving backward...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"],
                {"api_id": SPORT_CMD["Move"], "parameter": {"x": -0.5, "y": 0, "z": 0}}
            )
        elif direction == "left":
            print("Moving left...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"],
                {"api_id": SPORT_CMD["Move"], "parameter": {"x": 0, "y": 0.5, "z": 0}}
            )
        elif direction == "right":
            print("Moving right...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"],
                {"api_id": SPORT_CMD["Move"], "parameter": {"x": 0, "y": -0.5, "z": 0}}
            )
        elif direction == "stop":
            print("Stopping...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"],
                {"api_id": SPORT_CMD["Move"], "parameter": {"x": 0, "y": 0, "z": 0}}
            )
        else:
            print("Unknown direction:", direction)
        await asyncio.sleep(1)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    print(f"Running sportmode: {direction}")
    asyncio.run(_run_sportmode(conn, direction))

def run_sportmode(conn, direction):
    asyncio.run(_run_sportmode(conn, direction))

if __name__ == "__main__":
    frame_queue = Queue(maxsize=10)
    # 하나의 연결 객체를 공유
    conn = Go2WebRTCConnection(
        WebRTCConnectionMethod.Remote,
        serialNumber="B42D4000O358LD01",
        username="mrt2020@daum.net",
        password="dodan1004~"
    )
    start_webrtc(frame_queue, conn)

    # 명령어 입력을 받아 움직임 제어
    while True:
        # 프레임 처리 예시
        if not frame_queue.empty():
            img = frame_queue.get()
            print(img.shape)
        else:
            time.sleep(0.01)
        # 키보드 입력 등으로 명령 전달 (예시: forward, backward, left, right, stop)
        direction = input("Enter direction (forward/backward/left/right/stop): ")
        run_sportmode(conn, direction)
