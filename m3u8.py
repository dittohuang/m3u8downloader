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
import skimage
from pkg_resources import parse_version
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

keep_ts = False
adlist = []

def extractad(video_file):
    #out, _ = ffmpeg.input(video_file, ss=1).output('pipe:', vframes=1, format='image2', vcodec='mjpeg', loglevel='quiet').run(capture_stdout=True)
    out, _ = (
        ffmpeg
        .input(video_file)
        .filter('select', 'eq(pict_type,I)')
        .output('pipe:', vframes=1, format='image2', vcodec='mjpeg', loglevel='quiet')
        .run(capture_stdout=True)
    )
    thumbnail_data = np.frombuffer(out, np.uint8)
    thumbnail_image = cv2.imdecode(thumbnail_data, cv2.IMREAD_COLOR)
    #cv2.imwrite(video_file + ".jpg", thumbnail_image)
    thumbnail_image = cv2.resize(thumbnail_image, (240, 135))
    return thumbnail_image

def checkad(adlist, video_file):
    out, _ = (
        ffmpeg
        .input(video_file)
        .filter('select', 'eq(pict_type,I)')
        .output('pipe:', vframes=1, format='image2', vcodec='mjpeg', loglevel='error')
        .run(capture_stdout=True)
    )
    thumbnail_data = np.frombuffer(out, np.uint8)
    thumbnail_image = cv2.imdecode(thumbnail_data, cv2.IMREAD_COLOR)
    thumbnail_image = cv2.resize(thumbnail_image, (240, 135))
    max_ssim_score = 0
    use_new_ssim = parse_version(skimage.__version__) >= parse_version("0.16.2")
    for ad in adlist:
        gray1 = cv2.cvtColor(ad, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(thumbnail_image, cv2.COLOR_BGR2GRAY)
        ssim_score = skimage.metrics.structural_similarity(gray1, gray2) if use_new_ssim else skimage.measure.compare_ssim(gray1, gray2)
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

    if len(url) == 0:
        return all_ts_files, status

    urls_prefix = ''
    last_slash_index = url.rfind('/')
    if last_slash_index != -1:
        urls_prefix = url[:last_slash_index]
    else:
        print(f"URL error: {url}")
        return all_ts_files, status

    try:
        response = requests.get(url)
        if response.status_code == 200:
            lines = response.text.split('\n')
            if len(lines) > 20:
                video_urls = [line.strip() for line in lines if line.startswith('http')]
                if len(video_urls) == 0:
                    short_video_urls = [line.strip() for line in lines if line.endswith('ts')]
                    for u in short_video_urls:
                        video_urls.append(urls_prefix + '/' + u)
                return download_video(video_urls, outfolder)
            else:
                m3u8_urls = [line.strip() for line in lines if line.endswith('m3u8')]
                for m3u8 in m3u8_urls:
                    full_m3u8_urls = urls_prefix + '/' + m3u8
                    tss, status = download(full_m3u8_urls, outfolder)
                    all_ts_files.extend(tss)
                return all_ts_files, status
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
    for ts in all_ts_list:
        ts_file = outfolder + "/" + ts
        print("Checking ad: ", i, "/", len(all_ts_list), end='\r')
        i = i + 1
        if not os.path.exists(ts_file):
            continue
        if (checkad(adlist, ts_file) > 0.98):
            print("found ad: ", ts_file)
            os.remove(ts_file)
        else:
            mergelist.append(ts_file)
    print(end='')

    outputname = outfolder + "/../" + name + '.mp4'
    try:
        os.remove(outputname)
    except Exception as e:
        pass

    input_list_file = outfolder + "/merge.txt"
    with open(input_list_file, 'w') as file:
        for item in mergelist:
            file.write('file \'' + str(item.split('/')[-1]) + '\'\n')
        file.close()

    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", input_list_file,
        "-c", "copy",
        outputname
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print("Concatenation successful")
    except subprocess.CalledProcessError as e:
        print("Error during concatenation:", e)

    global keep_ts
    if os.path.exists(outputname):
        print("Download Finished:", outputname)
        if not keep_ts:
            delete_folder(outfolder)

def load_ad_list():
    adlist = []
    ad_dir = './ad'
    for filename in os.listdir(ad_dir):
        file_path = os.path.join(ad_dir, filename)
        if os.path.isfile(file_path):
            adimg = extractad(file_path)
            adlist.append(adimg)
    print("Loaded ADs:", len(adlist))
    return adlist

#Download m3u8 url to download_root.
#The URL can be: <save_name>$https://xxx.example.com/abcdeft.m3u8
#<save_name> is optional
def run(raw_url, download_root):
    if len(raw_url) == 0:
        return
    name, url = parse_url(raw_url)

    #Prepare temp folder
    outname = name
    outfolder = download_root + "/" + outname
    
    #Clean the existing folder
    delete_folder(outfolder)
    create_folder(outfolder)

    #Load the ad list
    adlist = load_ad_list()

    #Download the file
    all_ts_list, status = download(url, outfolder)
    if (status == 0):
        #Check ADs and merge the TS files
        merge_video(outfolder, name, all_ts_list, adlist)

def merge(merge_folder, download_root):
    #Load the ad list
    adlist = load_ad_list()

    outname = merge_folder
    outfolder = download_root + "/" + outname
    urls_file = outfolder + "/" + "urls.txt"
    all_ts_files = []
    if os.path.exists(urls_file):
        with open(urls_file, 'r') as file:
            for line in file:
                all_ts_files.append(line.split('/')[-1].strip('\n'))
    if len(all_ts_files) > 0:
        merge_video(outfolder, merge_folder, all_ts_files, adlist)

    return

def get_m3u8_playlist(m3u8_file):
    ts_files = []
    base_path = os.path.dirname(m3u8_file)
    with open(m3u8_file, 'r') as file:
        lines = file.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                continue
            if line.endswith('.ts'):
                ts_path = os.path.join(base_path, line)
                if os.path.exists(ts_path): 
                    ts_files.append(ts_path)
            if line.endswith('.m3u8'):
                m3u8_path = os.path.join(base_path, line)
                if os.path.exists(m3u8_path): 
                    ts_files += get_m3u8_playlist(m3u8_path)

    return ts_files

def filter_ad(ts_file):
    global adlist
    if not os.path.exists(ts_file):
        return None
    if checkad(adlist, ts_file) > 0.98:
        os.remove(ts_file)
        return ts_file
    else:
        return None

def merge_m3u8(merge_m3u8_file, out_root):
    #Load the ad list
    global adlist
    adlist = load_ad_list()

    out_filename, source = parse_url(merge_m3u8_file)
    out_filename += ".mp4"
    if not os.path.exists(source) or not source.endswith('.m3u8'):
        print("Invalid m3u8 file:", merge_m3u8_file)
        return
    all_ts_files = get_m3u8_playlist(source)
    if len(all_ts_files) < 0:
        print("No video resource found")
        return
    
    mergelist = []

    with ThreadPoolExecutor() as executor:
        results = list(tqdm(executor.map(filter_ad, all_ts_files), total=len(all_ts_files)))

    for result in results:
        if result is not None:
            mergelist.append(result)

    out_path = out_root + "/" + out_filename
    try:
        os.remove(out_path)
    except Exception as e:
        pass

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", source,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        "-f", "mp4",
        out_path
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print("Merge successful")
    except subprocess.CalledProcessError as e:
        print("Error during merging:", e)

    return

def main():
    parser = argparse.ArgumentParser(description="M3U8 Downloader")
    mutex_group = parser.add_mutually_exclusive_group(required=True)
    mutex_group.add_argument('-u', '--url', type=str, help='The m3u8 URL')
    mutex_group.add_argument('-i', '--input-file', type=str, help='The m3u8 URL file list')
    mutex_group.add_argument('-s', '--local-source', type=str, help='local m3u8 file location')
    parser.add_argument('-m', '--merge', type=str, help='The folder to be merge. only merge the TS files listed in the urls.txt')
    parser.add_argument('--download-root', default='./movie', type=str, help='Download root folder')
    parser.add_argument('-k', '--keep-ts', default=False, type=bool, help='Keep the org TS files')
    opt = parser.parse_args()

    global keep_ts
    keep_ts = opt.keep_ts

    #Create download root
    create_folder(opt.download_root)

    #read m3u8 url from file or command line
    if opt.input_file is not None:
        with open(opt.input_file, 'r') as file:
            for line_ in file:
                line = line_.strip('\n').strip()
                if line.count('//') == 0 and os.path.exists(line):
                    merge_m3u8(line, opt.download_root)
                else:
                    run(line, opt.download_root)
    elif opt.url is not None:
        run(opt.url, opt.download_root)
    elif opt.local_source is not None:
        merge_m3u8(opt.local_source, opt.download_root)
    elif opt.merge is not None:
        merge(opt.merge, opt.download_root)
    else:
        print("Nothing to download")

if __name__ == '__main__':
    main()
