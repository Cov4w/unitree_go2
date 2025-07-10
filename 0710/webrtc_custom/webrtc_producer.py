import asyncio
import threading
import time
import logging
import json
from multiprocessing import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from aiortc import MediaStreamTrack

logging.basicConfig(level=logging.FATAL)

# 전역 conn 객체를 접근할 수 있도록 선언
_conn_holder = {}

def start_webrtc(frame_queue, command_queue):
    """
    frame_queue: 영상 프레임을 담는 큐
    command_queue: 움직임 명령(문자열)을 담는 큐
    """
    async def recv_camera_stream(track: MediaStreamTrack):
        while True:
            try:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                frame_queue.put(img)
            except Exception as e:
                logging.error(f"Frame decode error: {e}")

    async def _ensure_normal_mode(conn):
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

    async def handle_command(conn):
        while True:
            direction = await asyncio.get_event_loop().run_in_executor(None, command_queue.get)
            try:
                # 여기서는 모드 확인/변경을 하지 않음!
                if direction == "sitdown":
                    print("Performing 'StandDown' movement...")
                    await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["SPORT_MOD"],
                        {"api_id": SPORT_CMD["StandDown"]}
                    )
                elif direction == "situp":
                    print("Performing 'StandUp' movement...")
                    await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["SPORT_MOD"],
                        {"api_id": SPORT_CMD["StandUp"]}
                    )
                    print("Performing 'StandUp' movement...")
                    await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["SPORT_MOD"],
                        {"api_id": SPORT_CMD["BalanceStand"]}
                    )
                elif direction == "forward":
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

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        async def setup():
            conn = Go2WebRTCConnection(
                WebRTCConnectionMethod.Remote,
                serialNumber="B42D4000O358LD01",
                username="mrt2020@daum.net",
                password="dodan1004~"
            )
            await conn.connect()
            conn.video.switchVideoChannel(True)
            conn.video.add_track_callback(recv_camera_stream)
            _conn_holder['conn'] = conn  # 전역에 conn 저장
            asyncio.create_task(handle_command(conn))
        loop.run_until_complete(setup())
        loop.run_forever()

    loop = asyncio.new_event_loop()
    threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True).start()

# 외부에서 명령을 큐에 넣는 함수
def send_command(command_queue, direction):
    command_queue.put(direction)

# 외부에서 normal 모드 전환을 요청할 때 호출
def ensure_normal_mode_once():
    import asyncio
    conn = _conn_holder.get('conn')
    if conn is None:
        print("No connection yet.")
        return False
    async def switch():
        await asyncio.sleep(1)  # 연결이 완전히 될 때까지 잠깐 대기
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001}
        )
        response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001}
        )
        current_motion_switcher_mode = "normal"
        if response['data']['header']['status']['code'] == 0:
            data = json.loads(response['data']['data'])
            current_motion_switcher_mode = data['name']
        if current_motion_switcher_mode != "normal":
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"],
                {"api_id": 1002, "parameter": {"name": "normal"}}
            )
            await asyncio.sleep(5)
    threading.Thread(target=lambda: asyncio.run(switch()), daemon=True).start()
    return True

if __name__ == "__main__":
    frame_queue = Queue(maxsize=10)
    command_queue = Queue(maxsize=10)
    start_webrtc(frame_queue, command_queue)

    # 예시: 키보드 입력으로 명령 전달
    while True:
        if not frame_queue.empty():
            img = frame_queue.get()
            print(img.shape)
        else:
            time.sleep(0.01)
        direction = input("Enter direction (forward/backward/left/right/stop/sitdown/situp): ")
        send_command(command_queue, direction)
