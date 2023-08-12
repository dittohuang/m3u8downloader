#!/usr/bin/python

import argparse
import os
import shutil
import time
import requests
import subprocess
import re
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
    out, _ = (
        ffmpeg
        .input(video_file)
        .filter('select', 'eq(pict_type,I)')
        .output('pipe:', vframes=1, format='image2', vcodec='mjpeg', loglevel='quiet')
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
        if (ssim_score > max_ssim_score):
            max_ssim_score = ssim_score
    return max_ssim_score

def delete_folder(directory):
    shutil.rmtree(directory, ignore_errors=True)

def create_folder(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)

def run_download(urls_file, outfolder):
    cmdline = f"aria2c -x 8 -c -d {outfolder} -i {urls_file}"
    command = cmdline.split(' ')

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    total_count = 0
    done_count = 0
    for line in process.stdout:
        if 'Downloading' in line:
            match = re.search(r'Downloading (\d+) item\(s\)', line)
            if match:
                total_count = int(match.group(1))
                print(line, end='')
        if 'Download complete:' in line:
            done_count = done_count + 1
            print("Progress:", done_count, "/", total_count, end='\r')

    process.wait()

    return process.returncode

def download_video(video_urls, outfolder):
    urls_file = outfolder + "/" + "urls.txt"
    all_ts_files = []
    if os.path.exists(urls_file):
        with open(urls_file, 'r') as file:
            for line in file:
                all_ts_files.append(line.split('/')[-1].strip('\n'))
        return all_ts_files, 0
    else:
        with open(urls_file, 'w') as file:
            for index, url in enumerate(video_urls, start=1):
                ts_files = url.split('/')[-1]
                if (ts_files.endswith('.ts')):
                    file.write(f"{url}\n")
                    all_ts_files.append(ts_files)
    return all_ts_files, run_download(urls_file, outfolder)

def download(url, outfolder):
    all_ts_files = []
    status = -1
    try:
        response = requests.get(url)
        if response.status_code == 200:
            lines = response.text.split('\n')
            video_urls = [line.strip() for line in lines if line.startswith('http')]
            all_ts_files, status = download_video(video_urls, outfolder)
        else:
            print(f"Download error, HTTP ErrCode: {response.status_code}")
    except Exception as e:
        print(f"Download failed: {e}")
    return all_ts_files, status

def parse_url(url):
    parts = url.split('$')
    if len(parts) == 2:
        name = parts[0]
        url = parts[1]
    elif len(parts) == 1:
        name = str(int(time.time()))
        url = parts[0]
    else:
        print("Invalid URL:", url)
    
    return name, url

def merge_video(outfolder, name, all_ts_list, adlist):
    mergelist = []
    i = 1
    found = False
    for ts in all_ts_list:
        ts_file = outfolder + "/" + ts
        print("Checking ad: ", i, "/", len(all_ts_list), end='\r')
        i = i + 1
        if (checkad(adlist, ts_file) > 0.98):
            print("found ad: ", ts_file)
            found = True
        else:
            mergelist.append(ts_file)
    print(end='')

    outputname = outfolder + "/../" + name + '.mp4'
    (
        ffmpeg
        .input('concat:' + '|'.join(mergelist))
        .output(outputname, c='copy', loglevel='quiet')
        .run()
    )

    if os.path.exists(outputname):
        print("Download Finished:", outputname)
        if found:
            delete_folder(outfolder)

def run(raw_url, download_root):
    name, url = parse_url(raw_url)

    #Prepare temp folder
    outname = name
    outfolder = download_root + "/" + outname
    delete_folder(outfolder)
    create_folder(outfolder)

    #Prepare ad list
    adlist = []
    ad_dir = './ad'
    for filename in os.listdir(ad_dir):
        file_path = os.path.join(ad_dir, filename)
        if os.path.isfile(file_path):
            adimg = extractad(file_path)
            adlist.append(adimg)
    print("AD Lists:", len(adlist))

    all_ts_list, status = download(url, outfolder)
    if (status == 0):
        merge_video(outfolder, name, all_ts_list, adlist)

def main():
    parser = argparse.ArgumentParser(description="M3U8 Downloader")
    parser.add_argument('-u', '--url', type=str, help='The m3u8 URL')
    parser.add_argument('-i', '--input-file', type=str, help='The m3u8 URL file list')
    parser.add_argument('--download-root', default='./download', type=str, help='The m3u8 URL')
    opt = parser.parse_args()

    create_folder(opt.download_root)

    if (opt.input_file is not None):
        with open(opt.input_file, 'r') as file:
            for line in file:
                run(line.strip('\n'), opt.download_root)
    elif(opt.url is not None):
        run(opt.url, opt.download_root)

if __name__ == '__main__':
    main()
