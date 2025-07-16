# ✅ Unitree_go2 자율 주행 순찰 프로젝트
# 📌 프로젝트 개요
## Unitree Go2 edu 모델을 이용해 특정 구역을 순찰하는 기능 구현 <br> 시스템 통합 능력 향상과 연구 역량 확보를 목표
# 🛠️ 필요 기술 스택
- WebRTC를 활용해 원격 제어
- SDK와 ROS2를 이용해 로봇의 고수준 제어 명령을 통한 제어
- L1 LAIDAR를 이용한 맵핑 후 저장(SLAM), 저장된 맵을 자율주행(NAVI)
- 전면 카메라 라이브 영상을 AI 모델을 이용해 실시간 특이사항 판별 후 DB 저장
- 저장된 특이사항을 사용자에게 정보 제공
# ✅ 진행 상황
## 📝 6월 3~4주
### VM Ware ubuntu 20.04 환경에서 unitree에서 제공하는 sdk를 이용해 로봇 제어
#### 원격 제어가 아닌 LAN선을 이용한 제어 <br> go2를 리모컨이나 앱이 아닌 코드를 통해 제어 했다는데 의의를 둠 <br> LAN선을 이용한 제어가 된 것을 확인 한 후 ip를 통해 원격으로 제어하고자 함
## 📝 7월 1주
### 기존 ip를 통해 제어하는 방식 말고 WebRTC를 이용해 제어하는 방식으로 정함
### WebRTC 예제 1 (https://github.com/legion1581/go2_webrtc_connect)
- 해당 오픈소스는 unitree go2의 기본 기능들을 WebRTC를 이용해 원격으로 제어 할 수 있는 예제를 제공
  - 특징 : go2와 WebRTC 연결 방식이 여러가지이고 난이도가 비교적 쉬움
### WebRTC 예제 2 (https://github.com/tfoldi/go2-webrtc)
- 해당 오픈소스는 WebRTC를 이용해 카메라, 오디오, Lidar 정보등을 웹 페이지 환경에서 확인하고 제어 할 수 있는 예제 제공
  - 특징 : 웹 브라우저에서 인터페이스로 로봇을 제어 할 수 있는 오픈소스 제공
# 📌 WebRTC
## 웹 브라우저나 모바일 앱 간에 실시간으로 플러그인의 도움 없이 <br>오디오, 비디오, 데이터를 서로 전송하고 통신할 수 있도록 설계된 API입니다.
### 특징 및 기능
- P2P 서비스
-  오디오 및 비디오 스트림 전송
-  실시간 데이터 통신

### 시그널링 서버
- P2P 통신을 위한 중계 서버
- P2P 서비스는 서로 접속 정보들을 알 수 없기 때문에 각 peer들의 최소화된 개인 정보를 노출하여 연결을 해결하고 설정하는 과정이 필요합니다.

### SDP와 ICE 정보 교환
- SDP에는 코덱, 소스 주소, 오디오 및 비디오의 미디어 유형, 기타 속성과 같은 피어 연결에 대한 일부 정보 포함되어 있습니다.
- ICE는 NAT/Firewall 뒤에서도 연결이 될 수 있게 STUN 및 TURN 프로토콜의 조합을 사용하여 NAT를 통해 해당 연결을 만드는데 <br>다양한 네트워크 후보를 제시하는 WebRTC의 핵심입니다.

### TURN 서버 : 
- STA-T 연결 모드에서는 일반적으로 연결이 불가능해 모든 실시간 오디오/비디오/데이터를 중계해주는 TURN 서버가 필요합니다.
- 시그널링/SDP/ICE 교환 과정을 모두 거친 뒤에도 실제 미디어 데이터는 TURN 서버를 경유합니다.

### 사용된 연결 방식 : STA-T
## STA-T 요청 순서 
- 시리얼 넘버, 유저 아이디, 비밀번호 입력
```
conn = Go2WebRTCConnection(WebRTCConnectionMethod.Remote, serialNumber="B42D2000XXXXXXXX", username="email@gmail.com", password="pass")
```
- 유저 로그인 → fetch_token() → access_token 발급
  - 인증 API 호출하여 accesss token 발급
```
def fetch_token(email: str, password: str) -> str:
    logging.info("Obtaining TOKEN...")
    path = "login/email"
    body = {
        'email': email,
        'password': _generate_md5(password)
    }
    response = make_remote_request(path, body, token="", method="POST")
    if response.get("code") == 100:
        data = response.get("data")
        access_token = data.get("accessToken")
        return access_token
    else:
        logging.error("Failed to receive token")
        return None
```
- 공개 키 요청 → 암호화 준비

- TURN 정보 요청 → fetch_turn_server_info()
  - 시리얼 넘버와 공개키로 TURN 서버 정보를 요청
```
def fetch_turn_server_info(serial: str, access_token: str, public_key: RSA.RsaKey) -> dict:
    logging.info("Obtaining TURN server info...")
    aes_key = generate_aes_key()
    path = "webrtc/account"
    body = {
        "sn": serial,
        "sk": rsa_encrypt(aes_key, public_key)
    }
    response = make_remote_request(path, body, token=access_token, method="POST")
    if response.get("code") == 100:
        return json.loads(aes_decrypt(response['data'], aes_key))
    else:
        logging.error("Failed to receive TURN server info")
        return None
```
- 시그널링 서버로 send_sdp_to_remote_peer() → Offer 암호화 전송
  - SDP 교환 절차
```
def send_sdp_to_local_peer(ip, sdp):
    try:
        # Try the old method first
        logging.info("Trying to send SDP using the old method...")
        response = send_sdp_to_local_peer_old_method(ip, sdp)
        if response:
            logging.info("SDP successfully sent using the old method.")
            return response
        else:
            logging.warning("Old method failed, trying the new method...")
    except Exception as e:
        logging.error(f"An error occurred with the old method: {e}")
        logging.info("Falling back to the new method...")

    # Now try the new method after the old method has failed
    try:
        response = send_sdp_to_local_peer_new_method(ip, sdp)  # Use the new method here
        if response:
            logging.info("SDP successfully sent using the new method.")
            return response
        else:
            logging.error("New method failed to send SDP.")
            return None
    except Exception as e:
        logging.error(f"An error occurred with the new method: {e}")
        return None
```

- Answer 수신 → AES 복호화 & RemoteDescription 설정

- ICE 연결 진행 → TURN 서버 포함 ICE 후보 처리
