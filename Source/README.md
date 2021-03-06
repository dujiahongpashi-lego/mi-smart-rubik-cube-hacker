#### 任何问题欢迎在视频下方留言讨论
# 无需扫描的完美版乐高魔方机器人
- 基于乐高51515套
- 需要[小米智能魔方](https://www.mi.com/buy/detail?product_id=11051)，若链接失效可全网搜索“小米智能魔方”
- 小米智能魔方的姊妹产品“计客Giiker超级魔方系列”未做验证，不保证兼容性
- 请理性消费，请理性消费，请理性消费。重要的事情说三遍！

David Gilday大神的乐高魔方机器人官网在这：[mindcuber](http://mindcuber.com/)，本程序基于其使用乐高51515的搭建[MindCuber-RI](http://mindcuber.com/mindcuberri/mindcuberri.html)

------
## 源码如何用？

- 首先需要完整完成 MindCuber-RI，包括搭建，和所有代码。这中间会用到LEGO MINDSTORMS软件等等，自备即可。
- 这个过程中，MindCuber-RI原设计中的代码部分下载步骤较为复杂，可根据其原文档（英文）耐心看完然后完成操作，并使用自备的普通三阶魔方验证其功能完整性。这是你做接下来操作的基础。
- 最后一步，使用此MiCubeMachine.py代码内容，全部替换其MindCuber-RI-v1p0.lms代码内容。再加载到你的乐高51515（45678，或者叫EV4）主控。

注意，需要修改代码中魔方蓝牙地址(MiCubeMachine.py第10行)

```CUBE_ARRD = 'E0:DB:31:12:6D:82'  # 魔方蓝牙地址，根据自己的魔方修改```

你可以使用Chrome浏览器的 chrome://bluetooth-internals/#adapter 功能，或者任何你喜欢的蓝牙调试软件（如BLE调试助手APP等等），获取你的小米魔方蓝牙地址。地址格式如代码中示例。

##### 手动写明蓝牙地址的好处是省去了乐高主控扫描和过滤的步骤，这可以使连接魔方的效率有一定提升（真的并不是因为我懒的写先扫描再匹配）

------
## 如何玩？
- 此程序保留了原MindCuber-RI功能，还原魔方机器人乐高程序启动后，默认和MindCuber-RI功能一样。也是先扫描再还原魔方。
- 但是我阉掉了原MindCuber-RI其中一个功能：左右按钮无法控制托盘无法左右微调了。
- 因为此程序中，左右按钮改成了初始化乐高和魔方的蓝牙连接。
- 所以，乐高启动后，按下左右按钮其中任何一个，等待听到小米智能魔方bi一声后，即连接成功，并且机器人已经进入了无需扫描模式。
- 然后，把魔方MI字面朝前、橙色面朝上，放入还原魔方机器人。静静等待自动还原完成吧。
- 因为，如果不扫描魔方，是无法知道魔方的各面朝向的，所以才需要手动控制朝向，以保证放入的方向正确。