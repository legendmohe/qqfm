python版qq音乐电台
==================

熬了几天夜，分析了qq电台的api，用python实现了基于http协议的qq音乐电台服务。代码共享到github上：

[https://github.com/legendmohe/qqfm/](https://github.com/legendmohe/qqfm/)

使用方式如下：

### 开启服务

    > python qqfm.py

注意，本项目依赖于 mplayer 和 tornado，要事先安装好。

### 随机下一首

    > curl http://localhost:8888/next

如果要制定类别，则：

    > curl http://localhost:8888/next?type=古典

### 暂停

    > curl http://localhost:8888/pause

### 标记当前播放

    > curl http://localhost:8888/mark

### 获取类别列表

    > curl http://localhost:8888/list

android控制端
==================

代码同样地共享到 github：

[https://github.com/legendmohe/QQFM_Android](https://github.com/legendmohe/QQFM_Android)

该版本实现了上述接口的功能。不过代码和界面都比较粗糙。

收工！
