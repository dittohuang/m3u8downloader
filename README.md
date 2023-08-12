# M3U8命令行下载工具

M3U8命令行下载工具，支持广告过滤

# 环境配置

基础环境：Ubuntu，python3, aria2c

```
$ sudo apt install aria2c
```

# 安装python依赖包

```
$ pip install -r requirement.txt
```

# 下载单个链接

```
$ python m3u8.py -u 'http://www.example.com/abcdefg.m3u8'
```

默认存储路径和文件名是./download/\<timestamp\>.mp4

如果需要重命名下载后的文件，请把URL改为：\<myvideo\>$http://www.example.com/abcdefg.m3u8

最终的文件名就是myvideo.mp4

# 下载多个链接

把上述链接按行存于一个文本文件中并用下面的命令执行下载

```
$ python m3u8.py -i list.txt
```
list.txt范例：
```
1$https://m3u8.example.com/eca92e40f4e87e54cbaede7b01de91f1b101fb3659f52ecerf6fdd09a2190d919921f11e97d0da21.m3u8
2$https://m3u8.example.com/a51415c0507c74f8f179de335ed21b3d469c8ddb6fac495er16a341bd25950b79921f11e97d0da21.m3u8
3$https://m3u8.example.com/99f4b1f70f5789a26134d8b6bd39fb02496c4b2f7e2dda0er23d2219c78b51829921f11e97d0da21.m3u8
```


# 广告过滤

把广告片段（ts）文件放入ad目录下，下载时遇到相同的广告则会被排除，不会合并到最后的mp4文件中