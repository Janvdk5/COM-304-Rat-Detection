# os
import os, sys

# general
import re
import random
import json

# visualization
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

# ml
import numpy as np
import torchvision as tv
import torch
from PIL import Image

# data aug
import copy
import shutil
from collections import defaultdict
from urllib.request import urlretrieve

# helpers
import dataloader as dl
from pathlib import Path

sys.path.append('../streaming_base')
#from streaming_base.processing.processing import beamform_2d
from streaming_base.utils.utils import get_ant_pos_2d, plot_2d_polar_heatmap, plot_2d_heatmap
from utils.utility import read_radar_params



# Global Vars
_DEBUG = True
ROOT_DIR = "../../data/"
OUTPUT_DIR = "../submission/"

########################################################
# helper functions for data exploration notebook
########################################################

# Image funcs
# Helper functions
def load_image(infilename):
    data = mpimg.imread(infilename)
    return data


def img_float_to_uint8(img):
    rimg = img - np.min(img)
    rimg = (rimg / np.max(rimg) * 255).round().astype(np.uint8)
    return rimg


# Concatenate an image and its groundtruth
def concatenate_images(img, gt_img):
    nChannels = len(gt_img.shape)
    w = gt_img.shape[0]
    h = gt_img.shape[1]
    if nChannels == 3:
        cimg = np.concatenate((img, gt_img), axis=1)
    else:
        gt_img_3c = np.zeros((w, h, 3), dtype=np.uint8)
        gt_img8 = img_float_to_uint8(gt_img)
        gt_img_3c[:, :, 0] = gt_img8
        gt_img_3c[:, :, 1] = gt_img8
        gt_img_3c[:, :, 2] = gt_img8
        img8 = img_float_to_uint8(img)
        cimg = np.concatenate((img8, gt_img_3c), axis=1)
    return cimg


def img_crop(im, w, h):
    list_patches = []
    imgwidth = im.shape[0]
    imgheight = im.shape[1]
    is_2d = len(im.shape) < 3
    for i in range(0, imgheight, h):
        for j in range(0, imgwidth, w):
            if is_2d:
                im_patch = im[j : j + w, i : i + h]
            else:
                im_patch = im[j : j + w, i : i + h, :]
            list_patches.append(im_patch)
    return list_patches



# beamforming funcs
def beamform_2d(beat_freq_data, radar_params, x_locs):
    """
    Performs 2D beamforming along the azimuth (horizontal) dimension, this results in a bird eye view image.

    Parameters
    ----------
    beat_freq_data : np.ndarray
        The beat frequency data, typically a 3D array.
    x_locs : np.ndarray
        The x-coordinates of the antennas.
    radar_params : dict
        A dictionary containing radar parameters such as sample rate, number of range samples, etc. 

    Returns
    -------
    sph_pwr : np.ndarray
        The spherical power array after beamforming, with shape (num_phi, samples_per_chirp).
    """

    # Radar parameters
    lm = radar_params["lm"]

    # Get the azimuth angles and range indices
    phi = radar_params["phi"]
    num_phi = len(phi)
    r_idxs = radar_params["range_idx"]

    # Initialize the spherical power array 
    sph_pwr = np.zeros((num_phi, r_idxs.shape[0]), dtype=np.complex64)

    # TODO: compute array for phase shifts for angles  (size: phi x x_locs)
    # this is essentially calculating d_n * cos(phi) from the README
    angles = x_locs * np.cos(phi[:, np.newaxis])

    # TODO: compute h_phi for each phase shift (size same as angles)
    # this is calculates the complex valued h_phi from the README
    #steering_vec = np.zeros(angles.shape) 
    steering_vec = np.exp(1j*2*np.pi/lm * angles)

    # Apply the phase shifts to the beat frequency data and sum over the antennas
    for r, rval in enumerate(r_idxs):
        beat = beat_freq_data[:, r]
        beamformed_signal = beat[np.newaxis, :] * steering_vec
        sph_pwr[:, r] = np.maximum(sph_pwr[:, r], np.abs(np.sum(beamformed_signal, axis=-1)))

    return sph_pwr

def to_virtual_ant(fft):
    # fft shape: (num_chirps, num_rx, num_tx, num_range_bins)
    # sum across tx and rx to get virtual antenna signal
    chirps, num_rx, num_tx, num_range_bins = fft.shape
    fft = fft.reshape(chirps, num_rx * num_tx, num_range_bins) 
    return fft

def make_virtual_ant_dict(fft_data, names):
    virtual_ant_dict = {}
    virtual_ant_signals = [to_virtual_ant(fft) for fft in fft_data]
    
    # form dict of virt signals with names
    virtual_ant_dict = {names[i]: virtual_ant_signals[i] for i in range(len(names))}
    return virtual_ant_dict



# data loading/manipulation

def load_data(data_dir, home_dir, json_filename, args):

    folder = Path(r"../" + data_dir)
    pattern = re.compile(r"^(.*)_Raw_\d+\.bin$")


    names = []
    raw_data = []
    fft_data = []

    for file in folder.glob("*_Raw_*.bin"):
        match = pattern.match(file.name)
        if match:
            names.append(match.group(1))

    for name in names:
        raw, fft = dl.load_radar_capture(name, data_dir, home_dir, json_filename, args)
        raw_data.append(raw)
        fft_data.append(fft)

    return names, raw_data, fft_data


# data augmentation
# add augmented data

def add_noise(img, sigma=0.01):
    noise = np.random.normal(0, sigma, img.shape)
    return img + noise

def random_gain(img, low=0.9, high=1.1):
    return img * np.random.uniform(low, high)

def shift_azimuth(img, max_shift=5):
    shift = np.random.randint(-max_shift, max_shift)
    return np.roll(img, shift, axis=0)

def augment_data(X, y):
    X_aug, y_aug = [], []
    for img, label in zip(X, y):
        for _ in range(6):
            out = img.copy()

            out = add_noise(out)
            out = random_gain(out)
            out = shift_azimuth(out)

            X_aug.append(out)
            y_aug.append(label)

    X_aug = np.array(X_aug)
    y_aug = np.array(y_aug)
    return X_aug, y_aug

#print("Augmented dataset shapes - X_aug: ", X_aug.shape, ", y_aug: ", y_aug.shape)
#print(X_aug.min(), X_aug.max(), X_aug.mean())
