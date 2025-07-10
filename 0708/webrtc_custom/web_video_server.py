import cv2
import time
from flask import Flask, Response, render_template, request, jsonify
from multiprocessing import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from webrtc_custom.webrtc_producer import start_webrtc, run_sportmode
import threading

app = Flask(__name__, template_folder='templates')
frame_queue = Queue(maxsize=10)

# Go2WebRTCConnection 객체 생성
conn = Go2WebRTCConnection(
    WebRTCConnectionMethod.Remote,
    serialNumber="B42D4000O358LD01",
    username="mrt2020@daum.net",
    password="dodan1004~"
)

# WebRTC 프레임 수신 시작
start_webrtc(frame_queue, conn)

def generate():
    while True:
        if not frame_queue.empty():
            img = frame_queue.get()
            ret, jpeg = cv2.imencode('.jpg', img)
            if not ret:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        else:
            time.sleep(0.01)

@app.route('/video_feed')
def video_feed():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json()
    direction = data.get('direction')
    print(f"Received move command: {direction}")
    threading.Thread(target=run_sportmode, args=(conn, direction), daemon=True).start()
    return jsonify({'status': 'ok', 'direction': direction})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5010, debug=False)