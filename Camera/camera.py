#
# Created on Mar 7, 2017
#
# @author: dpascualhe
#
# Based on @nuriaoyaga code:
# https://github.com/RoboticsURJC-students/2016-tfg-nuria-oyaga/blob/
#     master/camera/camera.py
#
# And @Javii91 code:
# https://github.com/Javii91/Domotic/blob/master/Others/cameraview.py
#

import sys
import random
import traceback
import threading

import cv2
import numpy as np
import easyiceconfig as EasyIce
from PIL import Image
from jderobot import CameraPrx
from keras.models import load_model
from keras import backend


class Camera:

    def __init__ (self):
        ''' Camera class gets images from live video and transform them
        in order to predict the digit in the image.
        '''
        self.model = load_model("/home/dpascualhe/workspace/" 
                                + "2016-tfg-david-pascual/Net/net.h5")
        
        status = 0
        ic = None
        
        # Initializing the Ice run-time.
        ic = EasyIce.initialize(sys.argv)

        properties = ic.getProperties()
        self.ad_thresh = properties.getProperty("Digitclassifier.AdThresh")
        
        self.lock = threading.Lock()
    
        try:        
            # We obtain a proxy for the camera.
            obj = ic.propertyToProxy("Digitclassifier.Camera.Proxy")
            
            # We get the first image and print its description.
            self.cam = CameraPrx.checkedCast(obj)
            if self.cam:
                self.im = self.cam.getImageData("RGB8")
                self.im_height = self.im.description.height
                self.im_width = self.im.description.width
                print(self.im.description)
            else: 
                print("Interface camera not connected")
                    
        except:
            traceback.print_exc()
            exit()
            status = 1

    def getImage(self):
        ''' Gets the image from the webcam and returns the original
        image with a ROI draw over it and the transformed image that
        we're going to use to make the prediction.
        '''      
        if self.cam:            
            self.lock.acquire()
            
            im = np.zeros((self.im_height, self.im_width, 3), np.uint8)
            im = np.frombuffer(self.im.pixelData, dtype=np.uint8)
            im.shape = self.im_height, self.im_width, 3
            im_trans = self.trasformImage(im)
            # It prints the ROI over the live video
            cv2.rectangle(im, (218, 138), (422, 342), (0, 0, 255), 2)
            ims = [im, im_trans]
            
            self.lock.release()
            
            return ims
    
    def update(self):
        ''' Updates the camera every time the thread changes. '''
        if self.cam:
            self.lock.acquire()
            
            self.im = self.cam.getImageData("RGB8")
            self.im_height = self.im.description.height
            self.im_width = self.im.description.width
            
            self.lock.release()

    def trasformImage(self, im):
        ''' Transforms the image into a 28x28 pixel grayscale image and
        applies a sobel filter (both x and y directions).
        ''' 
        im_crop = im [140:340, 220:420]
        im_gray = cv2.cvtColor(im_crop, cv2.COLOR_BGR2GRAY)
        im_blur = cv2.GaussianBlur(im_gray, (5, 5), 0) # Noise reduction.
        
        # Handmade adaptive threshold.
        avg = np.average(im_blur)
        if self.ad_thresh != "0":
            if avg < 120:
                (thr, im_bw) = cv2.threshold(im_blur, 255-(avg*0.75), 255,
                                               cv2.THRESH_BINARY)
            else:
                (thr, im_bw) = cv2.threshold(im_blur, avg*0.75, 255,
                                               cv2.THRESH_BINARY_INV)
            im_blur = im_bw     
                   
        im_res = cv2.resize(im_blur, (28, 28))

        # Edge extraction.
        im_sobel_x = cv2.Sobel(im_res, cv2.CV_32F, 1, 0, ksize=5)
        im_sobel_y = cv2.Sobel(im_res, cv2.CV_32F, 0, 1, ksize=5)
        im_edges = cv2.add(abs(im_sobel_x), abs(im_sobel_y))
        im_edges = cv2.normalize(im_edges, None, 0, 255, cv2.NORM_MINMAX)
        im_edges = np.uint8(im_edges)
        
        return im_edges
    
    def classification(self, im):
        ''' Adapts image shape depending on Keras backend (TensorFlow
        or Theano) and returns a prediction.
        '''
        if backend.image_dim_ordering() == 'th':
            im = im.reshape(1, 1, im.shape[0], im.shape[1])            
        else:      
            im = im.reshape(1, im.shape[0], im.shape[1], 1)            
        
        dgt = np.where(self.model.predict(im) == 1)
        print("Keras CNN prediction: ", self.model.predict(im))
        print("Prediction index: ", dgt)
        print("--------------------------------------------------------------")
        if dgt[1].size == 1:
            self.digito = dgt
        else:
            self.digito = (([0]), (["none"]))
        return self.digito[1][0]
        
