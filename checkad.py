#!/usr/bin/python
import ffmpeg
import cv2
import numpy as np
from skimage import measure

def extractad(video_file):
    out, _ = ffmpeg.input(video_file, ss=1).output('pipe:', vframes=1, format='image2', vcodec='mjpeg', loglevel='quiet').run(capture_stdout=True)
    thumbnail_data = np.frombuffer(out, np.uint8)
    thumbnail_image = cv2.imdecode(thumbnail_data, cv2.IMREAD_COLOR)
    thumbnail_image = cv2.resize(thumbnail_image, (240, 135))
    return thumbnail_image

def checkad(adlist, video_file):
    print(video_file)
    out, _ = (
        ffmpeg
        .input(video_file)
        .filter('select', 'eq(pict_type,I)')
        .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
        .run(capture_stdout=True)
    )
    thumbnail_data = np.frombuffer(out, np.uint8)
    thumbnail_image = cv2.imdecode(thumbnail_data, cv2.IMREAD_COLOR)
    thumbnail_image = cv2.resize(thumbnail_image, (240, 135))
    max_ssim_score = 0
    for ad in adlist:
        gray1 = cv2.cvtColor(ad, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(thumbnail_image, cv2.COLOR_BGR2GRAY)
        ssim_score = measure.compare_ssim(gray1, gray2)
        print(video_file, ssim_score)
        if (ssim_score > max_ssim_score):
            max_ssim_score = ssim_score

    return max_ssim_score

if __name__ == '__main__':
    adlist = []
    adimg = extractad('./ad/00289.ts')
    adlist.append(adimg)
    adimg = extractad('./ad/00288.ts')
    adlist.append(adimg)
    checkad(adlist, './download/2/c99771c1d0704b5eae821d9f946e85fecc0aa0fdd15f65de0701268450cf5eb08ee1f167bd8ccc5bc3157b919b891776bfbaa4d86c3834c77415290a1977e72cb26e226f7e76a739ae15f24a2bc516b1b4c6de39e9644b58.ts')
    #checkad(adlist, './ad/00312.ts')