from flask import Flask, request, Response
from PIL import Image
import base64
import numpy as np
import cv2
import threading
from time import sleep

current_image = None
app = Flask(__name__)
counter = 0 


def show_image():
    while True:
        if current_image is None:
            print("Json was not accepted")
            sleep(6)
            continue
        #cv2.imshow("1",current_image)
        #cv2.waitKey(3)
image_shower = threading.Thread(target=show_image)


@app.route('/', methods=['POST'])
def send():
    global counter
    global current_image
    body = request.json
    image = body.get("image",None)
    body["image"] = None
    rest = body
    print(rest)
    if image:
        img_data = base64.b64decode(image)
        nparr = np.fromstring(img_data, np.uint8)
        img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        imp_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGRA)
        # print(img_np.shape)
        current_image = img_np
        counter = counter + 1
        print("Picture number :",counter)
    return body


# start flask app
image_shower.start()
app.run(host="0.0.0.0", port=5000, debug=True)
image_shower.join()
