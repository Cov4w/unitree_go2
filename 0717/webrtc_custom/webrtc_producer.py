import asyncio
import threading
import time
import logging
import json
import av
from multiprocessing import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from aiortc import MediaStreamTrack

logging.basicConfig(level=logging.FATAL)

_conn_holder = {}

# 최신 조이스틱 값만 저장 (sitdown/situp 등은 큐 사용)
latest_joystick = None

def start_webrtc(frame_queue, command_queue):
    av.logging.set_level(av.logging.ERROR)
    """
    frame_queue: 영상 프레임을 담는 큐
    command_queue: 움직임 명령(문자열 또는 튜플)을 담는 큐
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
        try:
            response = await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001}
            )
            if response['data']['header']['status']['code'] == 0:
                data = json.loads(response['data']['data'])
                current_motion_switcher_mode = data['name']
                print(f"[모드 확인] 현재 모드: {current_motion_switcher_mode}")
            else:
                print("[모드 확인] 현재 모드 조회 실패")

            if current_motion_switcher_mode != "normal":
                print(f"[모드 전환] {current_motion_switcher_mode} → normal 모드로 변경 시도")
                response2 = await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"],
                    {"api_id": 1002, "parameter": {"name": "normal"}}
                )
                await asyncio.sleep(5)
                response3 = await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001}
                )
                if response3['data']['header']['status']['code'] == 0:
                    data = json.loads(response3['data']['data'])
                    print(f"[모드 확인] 변경 후 모드: {data['name']}")
                else:
                    print("[모드 확인] 변경 후 모드 조회 실패")
        except Exception as e:
            print(f"[모드 확인] 에러 발생: {e}")

    async def handle_command(conn):
        global latest_joystick
        while True:
            # sitdown/situp 등은 큐에서 처리
            if not command_queue.empty():
                direction = command_queue.get()
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
                    print("Performing 'BalanceStand' movement...")
                    await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["SPORT_MOD"],
                        {"api_id": SPORT_CMD["BalanceStand"]}
                    )
                # 기타 명령은 필요시 추가
            # 최신 조이스틱 값만 사용
            if latest_joystick is not None:
                _, x, z = latest_joystick
                print(f"Joystick command (latest): x={x}, z={z}")
                response = await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"],
                    {"api_id": SPORT_CMD["Move"], "parameter": {"x": float(x), "y": 0, "z": float(z)}}
                )
                print("Move response:", response)
            await asyncio.sleep(0.1)  # 50ms마다 최신 값 전송

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
            _conn_holder['conn'] = conn
            await _ensure_normal_mode(conn)  # 연결 직후 모드 전환 시도
            asyncio.create_task(handle_command(conn))
        loop.run_until_complete(setup())
        loop.run_forever()

    loop = asyncio.new_event_loop()
    threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True).start()

# 외부에서 명령을 큐에 넣는 함수
def send_command(command_queue, direction):
    global latest_joystick
    if isinstance(direction, tuple) and direction[0] == 'joystick':
        latest_joystick = direction  # 최신 값으로 덮어쓰기
    else:
        command_queue.put(direction)  # sitdown, situp 등은 기존 큐 사용

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
        direction = input("Enter direction (sitdown/situp): ")
        send_command(command_queue, direction)
