"""
Myo → ZeroMQ 服务器示例
- 预测手指动作后，通过 ZeroMQ PUB 把 fingers 数组广播给客户端（Quest/Unity）
- Unity 侧用 NetMQ SubscriberSocket 订阅 tcp://<PC_IP>:5555
"""

from collections import Counter, deque
import struct, sys, time
import pygame
from pygame.locals import *
import numpy as np
from xgboost import XGBClassifier
from pyomyo import Myo, emg_mode
from pyomyo.Classifier import Live_Classifier, MyoClassifier, EMGHandler
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline

# ==== NEW: ZeroMQ ====
import zmq
ZMQ_PORT = 5555           # 任意空闲端口
ZMQ_ENDPOINT = f"tcp://*:{ZMQ_PORT}"

class SVM_Classifier(Live_Classifier):
    def __init__(self):
        super().__init__(None, "SVM", (100,0,100))
    def train(self, X, Y):
        self.X, self.Y = X, Y
        if X.shape[0] > 0:
            self.model = make_pipeline(StandardScaler(), SVC(gamma='auto'))
            self.model.fit(X, Y)
    def classify(self, emg):
        if getattr(self, "model", None) is None:
            return 0
        return int(self.model.predict(np.array(emg).reshape(1,-1))[0])

def main():
    # ---------- ZeroMQ 初始化 ----------
    ctx = zmq.Context()
    zmq_pub = ctx.socket(zmq.PUB)
    zmq_pub.bind(ZMQ_ENDPOINT)
    print(f"[ZMQ] PUB 绑定在 {ZMQ_ENDPOINT}")

    # ---------- Myo / Pygame ----------
    pygame.init()
    w, h = 800, 320
    scr = pygame.display.set_mode((w, h))
    font = pygame.font.Font(None, 30)

    myo_cls = MyoClassifier(SVM_Classifier(), mode=emg_mode.PREPROCESSED, hist_len=12)
    hnd = EMGHandler(myo_cls)
    myo_cls.add_emg_handler(hnd)
    myo_cls.connect()
    myo_cls.set_leds(myo_cls.cls.color, myo_cls.cls.color)
    pygame.display.set_caption(myo_cls.cls.name)

    last_conf = 0
    try:
        while True:
            myo_cls.run()
            myo_cls.run_gui(hnd, scr, font, w, h)

            r = myo_cls.history_cnt.most_common(1)[0][0]
            scaled_conf = int(myo_cls.history_cnt[r] / myo_cls.hist_len * 10) / 10
            fingers = [0,0,0,0,0]

            if r == 6:                   # Grab
                fingers = [scaled_conf]*5
            elif r != 0 and 1 <= r <= 5: # 单指弯曲
                fingers[r-1] = scaled_conf

            if scaled_conf != last_conf:
                zmq_pub.send_json({"data": fingers})   # wrap in "data" for Unity JsonUtility
                print("Sent fingers:", fingers, "| class", r, "| conf", scaled_conf)
            last_conf = scaled_conf
    except KeyboardInterrupt:
        pass
    finally:
        myo_cls.disconnect()
        pygame.quit()
        zmq_pub.close()
        ctx.term()

if __name__ == "__main__":
    main()
