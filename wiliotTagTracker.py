#!/usr/bin/env python3

import sys
sys.path.append('../')
import os.path
from os import path
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GLib
import sys
import platform
from common.is_aarch_64 import is_aarch64
from common.utils import long_to_int
from common.FPS import GETFPS
import pyds
import requests as r0
from datetime import datetime
import cv2 
import numpy as np
import yaml
import argparse
import time
import base64
import threading

failed_to_post_max_retries = 20
failed_to_post_image_max_retries = 2
failed_to_post_reached = False
failed_to_post_image_reached = False

fps_streams={}
MAX_DISPLAY_LEN=64
MAX_TIME_STAMP_LEN=32


# input_file = None
cfg = None
no_display = False
current_time = None
s_count = 0
requests = []
loop = None
countt = 0
Gst.init(None)

pgie_classes_str=["whiteRect"]

def draw_bounding_boxes(image, obj_meta, confidence):
    confidence = '{0:.2f}'.format(confidence)
    rect_params = obj_meta.rect_params
    top = int(rect_params.top)
    left = int(rect_params.left)
    width = int(rect_params.width)
    height = int(rect_params.height)
    obj_name = pgie_classes_str[obj_meta.class_id]
    image = cv2.rectangle(image, (left, top), (left + width, top + height), (0, 0, 255, 0), 2, cv2.LINE_4)
    color = (0, 0, 255, 0)
    w_percents = int(width * 0.05) if width > 100 else int(width * 0.1)
    h_percents = int(height * 0.05) if height > 100 else int(height * 0.1)
    linetop_c1 = (left + w_percents, top)
    linetop_c2 = (left + width - w_percents, top)
    image = cv2.line(image, linetop_c1, linetop_c2, color, 6)
    linebot_c1 = (left + w_percents, top + height)
    linebot_c2 = (left + width - w_percents, top + height)
    image = cv2.line(image, linebot_c1, linebot_c2, color, 6)
    lineleft_c1 = (left, top + h_percents)
    lineleft_c2 = (left, top + height - h_percents)
    image = cv2.line(image, lineleft_c1, lineleft_c2, color, 6)
    lineright_c1 = (left + width, top + h_percents)
    lineright_c2 = (left + width, top + height - h_percents)
    image = cv2.line(image, lineright_c1, lineright_c2, color, 6)
    image = cv2.putText(image, obj_name + ',C=' + str(confidence), (left - 10, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 255, 0), 2)
    return image

def osd_sink_pad_buffer_probe(pad,info,user_data = None):
    global s_count
    global failed_to_post_max_retries
    global failed_to_post_image_max_retries
    global failed_to_post_reached
    global failed_to_post_image_reached
    global cfg, current_time
    global requests
    # frame_number=0
    # source = cfg['source']
    now = datetime.now()
    dt_string = now.strftime("%d_%m_%Y_%H:%M:%S")

    obj_id = 0
    #Intiallizing object counter with 0.
    obj_counter = {
        "whiteRect": 0
    }
    box_data = []

    #print("Get Frame :", s_count) ######
    s_count+=1
    data_to_send = {"timeStamp":dt_string ,"data": box_data}
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return Gst.PadProbeReturn.OK
    
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    # latency_meta = pyds.measure_buffer_latency(hash(gst_buffer))
    # print(latency_meta)
    if not batch_meta:
        return Gst.PadProbeReturn.OK
    l_frame = batch_meta.frame_meta_list
   
    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            # print(f"frame_meta:{frame_meta}")
        except StopIteration:
            continue        

        '''
        print("Frame Number is ", frame_meta.frame_num)
        print("Source id is ", frame_meta.source_id)
        print("Batch id is ", frame_meta.batch_id)
        print("Source Frame Width ", frame_meta.source_frame_width)
        print("Source Frame Height ", frame_meta.source_frame_height)
        print("Num object meta ", frame_meta.num_obj_meta)
        '''
        frame_number=frame_meta.frame_num
        sensor_ID = frame_meta.source_id
        obj_counter["frame"] = frame_number
        obj_counter["sensor_ID"]= sensor_ID

        data_to_send["frame"] = frame_number
        data_to_send["sensor_ID"]= sensor_ID


        should_send_data = not frame_number % picSend
        should_send_image = not frame_number % dataSend

        l_obj=frame_meta.obj_meta_list
        save_image = False
        while l_obj is not None:
            try:
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                continue
            
            txt_params=obj_meta.text_params

            # Set display_text. Any existing display_text string will be
            # freed by the bindings module.
            txt_params.display_text = pgie_classes_str[obj_meta.class_id]

            obj_counter[pgie_classes_str[obj_meta.class_id]] += 1
            # Font , font-color and font-size
            txt_params.font_params.font_name = "Serif"
            txt_params.font_params.font_size = 10
            # set(red, green, blue, alpha); set to White
            txt_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

            # Text background color
            txt_params.set_bg_clr = 1
            # set(red, green, blue, alpha); set to Black
            txt_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)

            bbox = { "top": obj_meta.rect_params.top, "left":  obj_meta.rect_params.left, "width":  obj_meta.rect_params.width, "height":obj_meta.rect_params.height}
            obj = { 'label':pgie_classes_str[obj_meta.class_id],
                    'bbox':bbox,
                    'confidence':'{0:.2f}'.format(obj_meta.confidence) 
                    }
            box_data.append(obj)

            try:
                l_obj=l_obj.next
            except StopIteration:
                break
        try:
            l_frame=l_frame.next
        except StopIteration:
            break

    if failed_to_post_max_retries > 0 :
        
        try:
            # if should_send_image:
                # requests.post(conn_http, json = data_to_send, timeout=1)   # send picture 
            if should_send_data:
                #print(data_to_send)
                requests.append(data_to_send)
                #requests.post(conn_http, json = data_to_send)   # send json data 


        except Exception as e:
            print(f"failed to post {failed_to_post_max_retries} to {conn_http}\n{e}")
    elif not failed_to_post_reached:
            print("max retries reached, not sending")
    return Gst.PadProbeReturn.OK


def create_pipeline(loop):
    def create_camera_pipeline(camera_source, appsrc):
        pipeline = None
        bus = None 
        def on_new_sample(appsink, user_data = None):
            # print("new_sample")
            sample = appsink.emit("try-pull-sample", 1 * Gst.MSECOND)
            if sample:
                # print(sample)
                appsrc.emit("push-sample", sample)
            return Gst.FlowReturn.OK
        
        def bus_call(bus, message, user_data = None):
            nonlocal pipeline
            t = message.type
            if t == Gst.MessageType.EOS:
                #print(f"device {camera_source.get('device')} restarting")
                pipeline.set_state(Gst.State.NULL)
                pipeline.set_state(Gst.State.PLAYING)
            elif t==Gst.MessageType.WARNING:
                err, debug = message.parse_warning()
                sys.stderr.write("Warning: %s: %s\n" % (err, debug))
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                sys.stderr.write("Error: %s: %s\n" % (err, debug))
                loop.quit()
            return True

        def launch():
            nonlocal pipeline
            nonlocal bus
            
            device = f"/dev/video{camera_source.get('device','0')}"
            # os.stat(device)
            pipe = ""
            pipe += f"v4l2src"
            pipe += f" device={device}"
            pipe += f" extra-controls=\"c,backlight_compensation=2\"" 
            pipe += " ! "
            caps = camera_source.get("caps", None)
            if caps != None:
                if caps:
                    pipe += f"capsfilter caps=\"{caps}\" ! "
                if caps.startswith("image/jpeg"):
                    pipe += "jpegdec ! "
            pipe += f"videorate ! video/x-raw, framerate={target_fps} ! "
            appsink_name = "appsink" 
            pipe += f"appsink name={appsink_name} emit-signals=true"
            #print(" ~ ", pipe)
            pipeline = Gst.parse_launch(pipe)
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect ("message", bus_call, loop)
            appsink = pipeline.get_by_name(appsink_name)
            appsink.connect("new-sample", on_new_sample)

        def start():
            #print("start")
            nonlocal pipeline
            pipeline.set_state(Gst.State.PLAYING)

        def stop():
            nonlocal pipeline
            nonlocal bus
            if pipeline != None:
                pipeline.set_state(Gst.State.NULL)                
            pipeline = None
            bus = None

        launch()

        return {
            "start":start, 
            "stop": stop,
        }   

    cameras = [camera_source, camera_source1, camera_source2, camera_source3]
    cameras = list(filter(lambda x: x.get("enable", False), cameras))
    nvstreammux_name = "nvstreammux"
    nvmultistreamtiler_name = "nvmultistreamtiler"
    pipe = ""
    for i, camera in enumerate(cameras):
        pipe += f" appsrc name=appsrc_{i} ! capsfilter caps=\"video/x-raw\" ! nvvideoconvert ! capsfilter caps=\"video/x-raw(memory:NVMM)\" ! {nvstreammux_name}.sink_{i}"
    pipe += f" nvstreammux name={nvstreammux_name} width={width} height={height} batch-size=1 batched-push-timeout=4000000 ! "
    pipe += f"nvinfer config-file-path={config_file_path} ! "
    pipe += f"nvmultistreamtiler name={nvmultistreamtiler_name} rows=2 columns=2 width={width} height={height} ! "
    pipe += "nvvideoconvert ! "
    pipe += "nvdsosd ! "
    pipe += "nvegltransform ! "
    pipe += "nveglglessink sync=false async=false"
    
    #print(" ~ ", pipe)
    pipeline = Gst.parse_launch(pipe)
    nvmultistreamtiler = pipeline.get_by_name(nvmultistreamtiler_name)
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def bus_call(bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stdout.write("End-of-stream\n")
            loop.quit()
        elif t==Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            sys.stderr.write("Warning: %s: %s\n" % (err, debug))
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write("Error: %s: %s\n" % (err, debug))
            loop.quit()
        return True

    bus.connect ("message", bus_call, loop)

    nvmultistreamtiler.get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, None)
    camera_pipelines = []
    for i, camera in enumerate(cameras):
        #print(f"CREATING CAMERA {i}")
        appsrc = pipeline.get_by_name(f"appsrc_{i}")
        camera_pipeline = create_camera_pipeline(camera, appsrc)
        camera_pipelines.append(camera_pipeline)

    def start():
        nonlocal camera_pipelines
        #print("START")
        pipeline.set_state(Gst.State.PLAYING)
        for c in camera_pipelines:
            c["start"]()
    
    def stop():
        for c in camera_pipelines:
            c["stop"]()
        pipeline.set_state(Gst.State.NULL)
    
    return {
        "start":start, 
        "stop": stop,
        "cameras": camera_pipelines
    }

def main():
    loop = GLib.MainLoop()
    p = create_pipeline(loop)

    def restart():
        #print("restarting!!")
        p["stop"]()
        p["start"]()

    while True:
        try:
            p["start"]()
            loop.run()
        except KeyboardInterrupt as e:
            # pass
            break
        except Exception as e:
            pass
            # p["stop"]()
        time.sleep(1)
    print("stopping !")
    p["stop"]()



# Parse and validate input arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Tag Tracker')
    parser.add_argument('-c', '--config-path', default=None, type=str, help="Path to a configuration .yaml file")
    args = parser.parse_args()
    assert args.config_path is not None, "Invalid config_path"
    with open(args.config_path, 'r') as cfg_f:
        cfg = yaml.load(cfg_f, Loader=yaml.FullLoader)
    global conn_http
    global camera_source
    global camera_source1
    global camera_source2
    global camera_source3
    global width
    global height
    global target_fps
    global image_dir_path
    global config_file_path
    global dataSend
    global picDeleteDays
    global picDeleteSec
    global picSend
    picSend = cfg["picSend"]
    camera_source = cfg.get("camera_source")
    camera_source1 = cfg.get("camera_source1")
    camera_source2 = cfg.get("camera_source2")
    camera_source3 = cfg.get("camera_source3")
    picDeleteSec = cfg["picDeleteSec"]
    picDeleteDays = cfg["picDeleteDays"]
    dataSend = cfg["dataSend"]
    config_file_path = cfg["config_file_path"]
    conn_http = cfg["conn_http"]
    width = cfg["width"]
    height = cfg["height"]
    target_fps = cfg.get("target_fps", None)
    image_dir_path = cfg["image_dir_path"]

    return 0


def create_handler_request():
    global requests
    global countt
    should_run = True

    def start():
        global countt
        nonlocal should_run
        while should_run:
            try:
                if requests != []:
                    data = requests.pop()     
                    try:
                        r0.post(conn_http,json=data, timeout=2)
                        countt+=1
                        print("Send json to server : ", countt)
                    except:
                        print("Problem with HTTPConnection Make sure you put IP Configure file")
            except Exception as e:
                print(e)
                pass
            time.sleep(1)
        print("handleRequest done")

    def stop():
        nonlocal should_run
        should_run = False

    return {
        "start": start,
        "stop": stop,
    }


if __name__ == '__main__':
    ret = parse_args()
    if ret == 1:
        sys.exit(1)

    h = create_handler_request()
    t = threading.Thread(target = h["start"],daemon=True)
    t.start()

    try:
        main()
    except KeyboardInterrupt as e:
        pass
    except Exception as e:
        print(e)
    print("stopping !!!")
    h["stop"]()
    t.join()        

