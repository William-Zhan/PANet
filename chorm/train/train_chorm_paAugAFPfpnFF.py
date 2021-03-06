import os
import sys
import random
import math
import re
import time
import yaml
import json
from PIL import Image
import numpy as np
import cv2
import matplotlib
import matplotlib.pyplot as plt
import skimage.draw

import tensorflow as tf

# Root directory of the project
ROOT_DIR = os.path.abspath("../")
iter_num=0
# Import Mask RCNN
sys.path.append(ROOT_DIR)  # To find local version of the library
from mrcnn.config import Config
from mrcnn import utils
import mrcnn.panetmodelAugAfpfpnFFFF as modellib
from mrcnn import visualize
from mrcnn.model import log

#%matplotlib inline

# Directory to save logs and trained model
MODEL_DIR = os.path.join(ROOT_DIR, "logs")

# Local path to trained weights file
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")
# Download COCO trained weights from Releases if needed
if not os.path.exists(COCO_MODEL_PATH):
    utils.download_trained_weights(COCO_MODEL_PATH)


class ShapesConfig(Config):
    """Configuration for training on the toy shapes dataset.
    Derives from the base Config class and overrides values specific
    to the toy shapes dataset.
    """
    # Give the configuration a recognizable name
    NAME = "chorm_pa_AugAfpfpnFF"
    BACKBONE = "resnet101"
    # Train on 1 GPU and 8 images per GPU. We can put multiple images on each
    # GPU because the images are small. Batch size is 8 (GPUs * images/GPU).
    GPU_COUNT = 1
    IMAGES_PER_GPU = 4

    # Number of classes (including background)
    NUM_CLASSES = 2  # background + 3 shapes

    # Use small images for faster training. Set the limits of the small side
    # the large side, and that determines the image shape.
    #IMAGE_MIN_DIM = 448
    #IMAGE_MAX_DIM = 512
    IMAGE_MIN_DIM = 448
    IMAGE_MAX_DIM = 512
    # Use smaller anchors because our image and objects are small
    RPN_ANCHOR_SCALES = (16, 32, 64, 128, 256)  # anchor side in pixels

    # Reduce training ROIs per image because the images are small and have
    # few objects. Aim to allow ROI sampling to pick 33% positive ROIs.
    TRAIN_ROIS_PER_IMAGE = 100

    # Use a small epoch since the data is simple
    STEPS_PER_EPOCH = 494

    # use small validation steps since the epoch is small
    VALIDATION_STEPS = 1


config = ShapesConfig()
config.display()

#def get_ax(rows=1, cols=1, size=8):
#    """Return a Matplotlib Axes array to be used in
#    all visualizations in the notebook. Provide a
#    central point to control graph sizes.
#
#    Change the default size attribute to control the size
#    of rendered images
#    """
#    _, ax = plt.subplots(rows, cols, figsize=(size * cols, size * rows))
#    return ax

class ChromsomeDataset(utils.Dataset):
    def get_obj_index(self, image):
        n = np.max(image)
        return n

    def get_obj(self, path):
        s = path.split('\\')
        path1 = 'H:\\Data\\chromosome_refine\\img_json\\'
        s = s[4]
        img_num = s.split('.')
        img_num = img_num[0]
        imgfile = path1 + img_num + '_json\\' + 'label.png'
        img = cv2.imread(imgfile)
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, binary = cv2.threshold(gray_img, 10, 255, cv2.THRESH_BINARY)
        image, contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        n = len(contours)
        return n

    def get_obj_num(self, path):
        s = path.split('\\')
        path1 = 'H:\\Data\\chromosome_refine\\json\\'
        s = s[4]
        img_num = s.split('.')
        img_num = img_num[0]
        annotations = json.load(open(path1 + img_num + '.json'))

        annotations = list(annotations.values())  # don't need the dict keys
        # for a in annotations:

        n = len(annotations[2])
        return n


    def from_yaml_get_class(self, image_id):
        info = self.image_info[image_id]
        with open(info['yaml_path']) as f:
            temp = yaml.load(f.read())
            labels = temp['label_names']
            del labels[0]
        return labels

    def draw_mask(self, mask, path):
        s = path.split('\\')
        path1 = 'H:\\Data\\chromosome_refine\\json\\'
        s = s[4]
        img_num = s.split('.')
        img_num = img_num[0]
        with open(path1 + img_num + '.json', "r", encoding='utf-8') as json_file:
            data = json.load(json_file)
            a = data['shapes']

            for i in range(len(a)):
                points_x = []
                points_y = []
                for x, y in a[i]['points']:
                    points_x.append(x)
                    points_y.append(y)
                    # print(x)
                    # print(y)
                # print(points_x)
                # print(points_y)
                #print(b['points'])
                X = np.array(points_x)
                Y = np.array(points_y)
                rr, cc = skimage.draw.polygon(Y, X)
                mask[rr, cc, i] = 1
        return mask


    def load_shapes(self, count, img_floder,mask_floder,imglist,dataset_root_path):
        """Generate the requested number of synthetic images.
        count: number of images to generate.
        height, width: the size of the generated images.
        """
        # Add classes
        self.add_class("shapes", 1, "impurity")
        #random.shuffle(imglist)
        for i in range(count):
            filestr = imglist[i].split(".png")[0]
            mask_path = mask_floder + "\\" + filestr + ".png"
            yaml_path = dataset_root_path +'img_json\\' + filestr + "_json\\info.yaml"
            image = Image.open(dataset_root_path +'img_json\\'+ filestr + "_json\\img.png")
            w, h = image.size
            self.add_image("shapes", image_id=i, path=img_floder + "\\" + imglist[i],
                           width=w, height=h, mask_path=mask_path, yaml_path=yaml_path)


    def load_mask(self, image_id):
          """Generate instance masks for shapes of the given image ID.
          """
          global iter_num
          #print("self.image_info", self.image_info)
          info = self.image_info[image_id]
          count = self.get_obj_num(info['path']) # number of object
          #print(info)
          #img = Image.open(info['mask_path'])
         # global count_num
         # count_num = count_num + 1
         # print(count_num)
          mask = np.zeros([info['height'], info['width'], count], dtype=np.uint8)
          mask = self.draw_mask(mask, info['path'])
          #for i in range(count):
          #    mask1 = mask[:,:,i]
          #    cv2.imshow("s", mask1)
          #    cv2.waitKey()

          labels=[]
          labels=self.from_yaml_get_class(image_id)
          labels_form=[]
          for i in range(count):
                labels_form.append("impurity")

          class_ids = np.array([self.class_names.index(s) for s in labels_form])
          #print(class_ids)
          return mask.astype(np.bool), class_ids.astype(np.int32)

    def get_ax(rows=1, cols=1, size=8):
        """Return a Matplotlib Axes array to be used in
        all visualizations in the notebook. Provide a
        central point to control graph sizes.

        Change the default size attribute to control the size
        of rendered images
        """
        _, ax = plt.subplots(rows, cols, figsize=(size * cols, size * rows))
        return ax

#基础设置
dataset_root_path="H:\\Data\\chromosome_refine\\"
img_floder = dataset_root_path + "train"
mask_floder = dataset_root_path + "mask"
#yaml_floder = dataset_root_path
imglist = os.listdir(img_floder)
count = len(imglist)


#train与val数据集准备
dataset_train = ChromsomeDataset()
dataset_train.load_shapes(count, img_floder,mask_floder,imglist,dataset_root_path)
dataset_train.prepare()

#print("dataset_train-->",dataset_train._image_ids)
count_num = 0
dataset_val = ChromsomeDataset()
dataset_val.load_shapes(count, img_floder, mask_floder, imglist,dataset_root_path)
dataset_val.prepare()

#print("dataset_val-->",dataset_val._image_ids)

# Load and display random samples
#image_ids = np.random.choice(dataset_train.image_ids, 4)
#for image_id in image_ids:
#    image = dataset_train.load_image(image_id)
#    mask, class_ids = dataset_train.load_mask(image_id)
#    visualize.display_top_masks(image, mask, class_ids, dataset_train.class_names)

# Create model in training mode
model = modellib.MaskRCNN(mode="training", config=config,
                          model_dir=MODEL_DIR)

# Which weights to start with?
init_with = "coco"  # imagenet, coco, or last

if init_with == "imagenet":
    model.load_weights(model.get_imagenet_weights(), by_name=True)
elif init_with == "coco":
    # Load weights trained on MS COCO, but skip layers that
    # are different due to the different number of classes
    # See README for instructions to download the COCO weights
    model.load_weights(COCO_MODEL_PATH, by_name=True,
                       exclude=["mrcnn_class_logits", "mrcnn_bbox_fc",
                                "mrcnn_bbox", "mrcnn_mask"])
elif init_with == "last":
    # Load the last model you trained and continue training
    model.load_weights(model.find_last()[1], by_name=True)

# Train the head branches
# Passing layers="heads" freezes all layers except the head
# layers. You can also pass a regular expression to select
# which layers to train by name pattern.
model.train(dataset_train, dataset_val,
            learning_rate=config.LEARNING_RATE,
            epochs=5,
            layers='heads')
model.train(dataset_train, dataset_val,
            learning_rate=config.LEARNING_RATE,
            epochs=20,
            layers='all')




# Fine tune all layers
# Passing layers="all" trains all layers. You can also
# pass a regular expression to select which layers to
# train by name pattern.
#model.train(dataset_train, dataset_val,
#            learning_rate=config.LEARNING_RATE,
#            epochs=200,
#            layers="all")
#





