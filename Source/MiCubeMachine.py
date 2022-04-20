import hub
import gc
import mcricolors_v1p0
import mcrimaps_v1p0
import mcrisolver_v1p0
import time
import binascii
import bluetooth
from micropython import const
CUBE_ARRD = 'E0:DB:31:12:6D:82'  # 魔方蓝牙地址，根据自己的魔方修改

# SERVICE_UUID =bluetooth.UUID('0000AADB-0000-1000-8000-00805F9B34FB')
SERVICE_UUID = bluetooth.UUID(0xaadb)
CHARACTERISTIC_UUID = bluetooth.UUID(0xaadc)

_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_CONNECTION_UPDATE = const(27)

if 'FLAG_INDICATE' in dir(bluetooth):
    # We're on MINDSTORMS Robot Inventor
    # New version of bluetooth
    _IRQ_SCAN_RESULT = 5
    _IRQ_SCAN_DONE = 6
    _IRQ_PERIPHERAL_CONNECT = 7
    _IRQ_PERIPHERAL_DISCONNECT = 8
    _IRQ_GATTC_SERVICE_RESULT = 9
    _IRQ_GATTC_CHARACTERISTIC_RESULT = 11
    _IRQ_GATTC_READ_RESULT = 15
    _IRQ_GATTC_READ_DONE = 16
    _IRQ_GATTC_NOTIFY = 18
    _IRQ_GATTC_CHARACTERISTIC_DONE = 12
else:
    # We're probably on SPIKE Prime
    _IRQ_SCAN_RESULT = 1 << 4
    _IRQ_SCAN_DONE = 1 << 5
    _IRQ_PERIPHERAL_CONNECT = 1 << 6
    _IRQ_PERIPHERAL_DISCONNECT = 1 << 7
    _IRQ_GATTC_SERVICE_RESULT = 1 << 8
    _IRQ_GATTC_CHARACTERISTIC_RESULT = 1 << 9
    _IRQ_GATTC_READ_RESULT = 1 << 11
    _IRQ_GATTC_NOTIFY = 1 << 13
    _IRQ_GATTC_CHARACTERISTIC_DONE = 1 << 12


class MiCubeConnectorBLEcentral:
    def __init__(self, ble=None):
        if ble == None:
            ble = bluetooth.BLE()
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        self._reset()

    def _reset(self):
        self.state = {}
        self._addr_type = None
        self._addr = None
        self._addr_show_str = None

        # Callbacks for completion of various operations.
        # These reset back to None after being invoked.
        self._scan_callback = None
        self._conn_callback = None
        self._read_callback = None

        # Persistent callback for when new data is notified from the device.
        self._notify_callback = None

        # Connected device.
        self._conn_handle = None
        self._start_handle = None
        self._end_handle = None
        self._rx_handle = None

        self._n = 0

    # Connect to the specified device (otherwise use cached address from a scan).
    def connect(self, addr_type=None, addr=None, callback=None):
        self._addr_type = addr_type or self._addr_type
        self._addr = addr or self._addr
        self._conn_callback = callback
        if self._addr_type is None or self._addr is None:
            return False
        print('Try to connect...')
        self._ble.gap_connect(self._addr_type, self._addr)
        return True

    # Returns true if we've successfully connected and discovered uart characteristics.
    def is_connected(self):
        return (
            self._conn_handle is not None
            and self._rx_handle is not None
        )

    # Disconnect from current device.
    def disconnect(self):
        if not self._conn_handle:
            return
        self._ble.gap_disconnect(self._conn_handle)
        self._reset()

    def _on_scan(self, addr_type, addr_show_addr, addr):
        if addr_type is not None:
            print("Found peripheral:", addr_show_addr)
            # time.sleep_ms(500)
            self.connect()
        else:
            self.timed_out = True
            print("No uart peripheral found.")

    # Find a device advertising the uart service.
    def scan(self, callback=None):
        self._addr_type = None
        self._addr = None
        self._addr_show_str = None
        self._scan_callback = callback
        print('Start Scan')
        self._ble.gap_scan(20000, 30000, 30000)

    def scan_connect(self):
        self.timed_out = False
        self.scan(callback=self._on_scan)
        while not self.is_connected() and not self.timed_out:
            time.sleep_ms(10)
        return not self.timed_out

    def read(self, callback=None):
        if not self.is_connected():
            return
        self._read_callback = callback
        try:
            print('Read cube Data...')
            self._ble.gattc_read(self._conn_handle, self._rx_handle)
            time.sleep_ms(500)
        except Exception as e:
            print("gattc_read failed", e)

    def _irq(self, event, data):
        self.state['lastEvent'] = event
        if event not in (
                _IRQ_SCAN_DONE, _IRQ_SCAN_RESULT, _IRQ_PERIPHERAL_CONNECT, _IRQ_PERIPHERAL_DISCONNECT, _IRQ_CONNECTION_UPDATE,
                _IRQ_GATTC_SERVICE_RESULT, _IRQ_GATTC_SERVICE_DONE, _IRQ_GATTC_CHARACTERISTIC_RESULT,
                _IRQ_GATTC_CHARACTERISTIC_DONE,
                _IRQ_GATTC_NOTIFY, _IRQ_GATTC_READ_RESULT, _IRQ_GATTC_READ_DONE):
            # print('miss event handler:', event, hex(event))
            pass

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            # Disconnect (either initiated by us or the remote end).
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                # If it was initiated by us, it'll already be reset.
                self._reset()
                # print("Disconnect from peripheral")
                self.timed_out = True

        elif event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_str = binascii.hexlify(addr).decode('utf-8')
            if addr_str == CUBE_ARRD.lower().replace(':', ''):
                # print('Found one!')
                # time.sleep_ms(500)
                self._addr_type = addr_type
                self._addr_show_str = addr_str
                # Note: addr buffer is owned by caller so need to copy it.
                self._addr = bytes(addr)
                self._ble.gap_scan(None)

        elif event == _IRQ_SCAN_DONE:
            # print('Scan Done')
            # time.sleep_ms(500)
            if self._scan_callback:
                if self._addr:
                    # print('Found a device during the scan.')
                    # time.sleep_ms(500)
                    self._scan_callback(
                        self._addr_type, self._addr_show_str, self._addr)
                    self._scan_callback = None
                else:
                    # Scan timed out.
                    self._scan_callback(None, None, None)

        # 蓝牙连接成功
        elif event == _IRQ_PERIPHERAL_CONNECT:
            # print('Connect successful.')
            time.sleep_ms(100)
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                self._conn_handle = conn_handle
                self._ble.gattc_discover_services(conn_handle)
                # print('Try to discover some services...')

        # SERVICE查找成功
        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service.
            conn_handle, start_handle, end_handle, uuid = data
            self._n += 1
            # print('_IRQ_GATTC_SERVICE_RESULT, Found service ', uuid, 'vs',SERVICE_UUID)
            if conn_handle == self._conn_handle and uuid == SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle
                # print("Discover the right service", uuid)
                time.sleep_ms(100)
                self._ble.gattc_discover_characteristics(
                    self._conn_handle, start_handle, end_handle)
                # print("Try to discover some characteristics...")

        elif event == _IRQ_GATTC_SERVICE_DONE:
            pass

        # CHARACTERISTIC连接成功
        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle == self._conn_handle:
                if uuid == CHARACTERISTIC_UUID:
                    # print("Discover the right CHARACTERISTIC ", uuid)
                    self._rx_handle = value_handle

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            pass

        # 获取到了广播数据
        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            notify_data = bytes(notify_data)
            print('notify_data', binascii.hexlify(notify_data).decode('utf-8'))

        elif event == _IRQ_GATTC_READ_RESULT:
            # A read completed successfully.
            conn_handle, value_handle, char_data = data
            # self._read_callback(value_handle,bytes(char_data))
            # print('read_data', binascii.hexlify(char_data).decode('utf-8'))
            self.state['cube_data'] = bytes(char_data)


# binary a + b


def byte_add(a, b):
    carry = add = 0
    while True:
        add = a ^ b
        carry = (a & b) << 1
        a = add
        b = carry
        if (carry == 0):
            break
    return add & 0xff


# binary a - b


def byte_subtract(a, b):
    return byte_add(a, byte_add(~b, 1))


def converseAngleSetSingleXfirst(cube, angleFace, p1, p2, p3, c1, c2, c3):
    result = 0
    if (angleFace == 1):
        cube[p1] = c3
        cube[p2] = c1
        cube[p3] = c2
    elif (angleFace == 2):
        cube[p1] = c2
        cube[p2] = c3
        cube[p3] = c1
    elif (angleFace == 3):
        cube[p1] = c1
        cube[p2] = c2
        cube[p3] = c3
    else:
        result = 1

    return result


def converseAngleSetSingleYfirst(cube, angleFace, p1, p2, p3, c1, c2, c3):
    result = 0
    if (angleFace == 2):
        cube[p1] = c3
        cube[p2] = c1
        cube[p3] = c2
    elif (angleFace == 1):
        cube[p1] = c2
        cube[p2] = c3
        cube[p3] = c1
    elif (angleFace == 3):
        cube[p1] = c1
        cube[p2] = c2
        cube[p3] = c3
    else:
        result = 1

    return result


def converseAngleSetXfirst(cube, angle, angleFace, f1, f2, f3):
    num = 0
    if (angle == 1):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 1, 2, 3)
    elif (angle == 2):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 1, 3, 4)
    elif (angle == 3):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 1, 4, 5)
    elif (angle == 4):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 1, 5, 2)
    elif (angle == 5):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 6, 3, 2)
    elif (angle == 6):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 6, 4, 3)
    elif (angle == 7):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 6, 5, 4)
    elif (angle == 8):
        num |= converseAngleSetSingleXfirst(
            cube, angleFace, f1, f2, f3, 6, 2, 5)
    else:
        num |= 2

    return num


def converseAngleSetYfirst(cube, angle, angleFace, f1, f2, f3):
    num = 0
    if (angle == 1):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 1, 2, 3)
    elif (angle == 2):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 1, 3, 4)
    elif (angle == 3):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 1, 4, 5)
    elif (angle == 4):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 1, 5, 2)
    elif (angle == 5):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 6, 3, 2)
    elif (angle == 6):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 6, 4, 3)
    elif (angle == 7):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 6, 5, 4)
    elif (angle == 8):
        num |= converseAngleSetSingleYfirst(
            cube, angleFace, f1, f2, f3, 6, 2, 5)
    else:
        num |= 2

    return num


def converseLineSetSingle(cube, lineFace, p1, p2, c1, c2):
    result = 0
    if (lineFace == 1):
        cube[p1] = c1
        cube[p2] = c2
    elif (lineFace == 2):
        cube[p1] = c2
        cube[p2] = c1
    else:
        result = 3

    return result


def converseLineSet(cube, line, lineFace, p1, p2):
    num = 0
    if (line == 1):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 1, 2)
    elif (line == 2):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 1, 3)
    elif (line == 3):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 1, 4)
    elif (line == 4):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 1, 5)
    elif (line == 5):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 2, 3)
    elif (line == 6):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 4, 3)
    elif (line == 7):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 4, 5)
    elif (line == 8):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 2, 5)
    elif (line == 9):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 6, 2)
    elif (line == 10):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 6, 3)
    elif (line == 11):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 6, 4)
    elif (line == 12):
        num |= converseLineSetSingle(cube, lineFace, p1, p2, 6, 5)
    else:
        num = 4

    return num


def converseChangeFaceAgain(cube, a1, a2, a3, a4):
    num = cube[a4]
    cube[a4] = cube[a3]
    cube[a3] = cube[a2]
    cube[a2] = cube[a1]
    cube[a1] = num


def converseToPaperType(cubeOutputDataDebug):
    if (len(cubeOutputDataDebug) != 20):
        return bytearray(55)
    array = bytearray(55)
    array2 = bytearray(8)
    array3 = bytearray(8)
    array4 = bytearray(12)
    array5 = bytearray(12)

    # 看上去。。。是一通手动的大小端转换
    array2[0] = cubeOutputDataDebug[0] >> 4
    array2[1] = cubeOutputDataDebug[0] & 15
    array2[2] = cubeOutputDataDebug[1] >> 4
    array2[3] = cubeOutputDataDebug[1] & 15
    array2[4] = cubeOutputDataDebug[2] >> 4
    array2[5] = cubeOutputDataDebug[2] & 15
    array2[6] = cubeOutputDataDebug[3] >> 4
    array2[7] = cubeOutputDataDebug[3] & 15
    array3[0] = cubeOutputDataDebug[4] >> 4
    array3[1] = cubeOutputDataDebug[4] & 15
    array3[2] = cubeOutputDataDebug[5] >> 4
    array3[3] = cubeOutputDataDebug[5] & 15
    array3[4] = cubeOutputDataDebug[6] >> 4
    array3[5] = cubeOutputDataDebug[6] & 15
    array3[6] = cubeOutputDataDebug[7] >> 4
    array3[7] = cubeOutputDataDebug[7] & 15
    array4[0] = cubeOutputDataDebug[8] >> 4
    array4[1] = cubeOutputDataDebug[8] & 15
    array4[2] = cubeOutputDataDebug[9] >> 4
    array4[3] = cubeOutputDataDebug[9] & 15
    array4[4] = cubeOutputDataDebug[10] >> 4
    array4[5] = cubeOutputDataDebug[10] & 15
    array4[6] = cubeOutputDataDebug[11] >> 4
    array4[7] = cubeOutputDataDebug[11] & 15
    array4[8] = cubeOutputDataDebug[12] >> 4
    array4[9] = cubeOutputDataDebug[12] & 15
    array4[10] = cubeOutputDataDebug[13] >> 4
    array4[11] = cubeOutputDataDebug[13] & 15

    if (cubeOutputDataDebug[14] & 128 != 0):
        array5[0] = 2
    else:
        array5[0] = 1

    if (cubeOutputDataDebug[14] & 64 != 0):
        array5[1] = 2
    else:
        array5[1] = 1

    if (cubeOutputDataDebug[14] & 32 != 0):
        array5[2] = 2
    else:
        array5[2] = 1

    if (cubeOutputDataDebug[14] & 16 != 0):
        array5[3] = 2
    else:
        array5[3] = 1

    if (cubeOutputDataDebug[14] & 8 != 0):
        array5[4] = 2
    else:
        array5[4] = 1

    if (cubeOutputDataDebug[14] & 4 != 0):
        array5[5] = 2
    else:
        array5[5] = 1

    if (cubeOutputDataDebug[14] & 2 != 0):
        array5[6] = 2
    else:
        array5[6] = 1

    if (cubeOutputDataDebug[14] & 1 != 0):
        array5[7] = 2
    else:
        array5[7] = 1

    if (cubeOutputDataDebug[15] & 128 != 0):
        array5[8] = 2
    else:
        array5[8] = 1

    if (cubeOutputDataDebug[15] & 64 != 0):
        array5[9] = 2
    else:
        array5[9] = 1

    if (cubeOutputDataDebug[15] & 32 != 0):
        array5[10] = 2
    else:
        array5[10] = 1

    if (cubeOutputDataDebug[15] & 16 != 0):
        array5[11] = 2
    else:
        array5[11] = 1

    array[32] = 1
    array[41] = 2
    array[50] = 3
    array[14] = 4
    array[23] = 5
    array[5] = 6

    num = 0
    num |= converseAngleSetXfirst(array, array2[0], array3[0], 34, 43, 54)
    num |= converseAngleSetYfirst(array, array2[1], array3[1], 36, 52, 18)
    num |= converseAngleSetXfirst(array, array2[2], array3[2], 30, 16, 27)
    num |= converseAngleSetYfirst(array, array2[3], array3[3], 28, 25, 45)
    num |= converseAngleSetYfirst(array, array2[4], array3[4], 1, 48, 37)
    num |= converseAngleSetXfirst(array, array2[5], array3[5], 3, 12, 46)
    num |= converseAngleSetYfirst(array, array2[6], array3[6], 9, 21, 10)
    num |= converseAngleSetXfirst(array, array2[7], array3[7], 7, 39, 19)
    num |= converseLineSet(array, array4[0], array5[0], 31, 44)
    num |= converseLineSet(array, array4[1], array5[1], 35, 53)
    num |= converseLineSet(array, array4[2], array5[2], 33, 17)
    num |= converseLineSet(array, array4[3], array5[3], 29, 26)
    num |= converseLineSet(array, array4[4], array5[4], 40, 51)
    num |= converseLineSet(array, array4[5], array5[5], 15, 49)
    num |= converseLineSet(array, array4[6], array5[6], 13, 24)
    num |= converseLineSet(array, array4[7], array5[7], 42, 22)
    num |= converseLineSet(array, array4[8], array5[8], 4, 38)
    num |= converseLineSet(array, array4[9], array5[9], 2, 47)
    num |= converseLineSet(array, array4[10], array5[10], 6, 11)
    num |= converseLineSet(array, array4[11], array5[11], 8, 20)
    converseChangeFaceAgain(array, 1, 7, 9, 3)
    converseChangeFaceAgain(array, 4, 8, 6, 2)
    converseChangeFaceAgain(array, 37, 19, 10, 46)
    converseChangeFaceAgain(array, 38, 20, 11, 47)
    converseChangeFaceAgain(array, 39, 21, 12, 48)
    converseChangeFaceAgain(array, 40, 22, 13, 49)
    converseChangeFaceAgain(array, 41, 23, 14, 50)
    converseChangeFaceAgain(array, 42, 24, 15, 51)
    converseChangeFaceAgain(array, 43, 25, 16, 52)
    converseChangeFaceAgain(array, 44, 26, 17, 53)
    converseChangeFaceAgain(array, 45, 27, 18, 54)
    converseChangeFaceAgain(array, 34, 28, 30, 36)
    converseChangeFaceAgain(array, 31, 29, 33, 35)

    if (num != 0):
        return bytearray(55)

    return array


def cubeDataMixDecode(mixData):
    array = bytearray(20)
    array2 = bytearray([80, 175, 152, 32, 170, 119, 19, 137, 218, 230, 63, 95, 46, 130, 106, 175,
                        163, 243, 20, 7, 167, 21, 168, 232, 143, 175, 42, 125, 126, 57, 254, 87, 217, 91, 85, 215])

    if len(mixData) != 20:
        return mixData

    if mixData[18] != 167:
        return mixData

    b = mixData[19] & 15
    b2 = mixData[19] >> 4

    for i in range(19):
        array[i] = mixData[i]
        array[i] = byte_subtract(array[i], array2[b + i])
        array[i] = byte_subtract(array[i], array2[b2 + i])

    return array


def parseCube(bytes):
    mixerDataDecoded = cubeDataMixDecode(bytes)
    paperTypeCube = converseToPaperType(mixerDataDecoded)
    return paperTypeCube[1:55]


# -----------------------------------------------------------------------------
# Title:        MindCuber-RI
#
# Author:    David Gilday
#
# Copyright:    (C) 2021 David Gilday
#
# Website:    http://mindcuber.com
#
# Version:    v1p0
#
# Modified:    $Date: 2021-03-28 13:59:19 +0100 (Sun, 28 Mar 2021) $
#
# Revision:    $Revision: 7875 $
#
# Usage:
#
# This software may be used for any non-commercial purpose providing
# that the original author is acknowledged.
#
# Disclaimer:
#
# This software is provided 'as is' without warranty of any kind, either
# express or implied, including, but not limited to, the implied warranties
# of fitness for a purpose, or the warranty of non-infringement.
#
# -----------------------------------------------------------------------------
# Purpose:    Main program for MindCuber-RI robot Rubik's Cube solver
# -----------------------------------------------------------------------------


hub.display.show(hub.Image.DIAMOND)
gc.collect()


def trace(msg):
    if False:
        gc.collect()
        print("TRACE: " + msg + " mem=" + str(gc.mem_free()))


trace("loading mindcuberri_v1p0")

trace("mindcuberri")

scan_mid = 135
scan_edg = 105
scan_crn = 90
scan_awy = 40
scan_rst = -140

scan_speed = 75
scan_pwr = 80

turn_mul = 60
turn_div = 20
turn_3 = int(turn_mul * 3 / turn_div)
turn_45 = int(turn_mul * 45 / turn_div)
turn_90 = int(turn_mul * 90 / turn_div)

FACE = hub.Image('60990:60990:00000:60990:60990')
FACE_LEFT = hub.Image('60990:60990:00000:06099:06099')
FACE_RIGHT = hub.Image('06099:06099:00000:60990:60990')
FACE_BLNK0 = hub.Image('60060:60060:00000:60060:60060')
FACE_BLNK1 = hub.Image('60000:60000:00000:60000:60000')

mi_cube = None


def GetPorts():
    global c, cm, portscan
    global sensor_dist, sensor_color, motor_scan, motor_turn, motor_tilt
    mcrisolver_v1p0.init(mcricolors_v1p0, mcrimaps_v1p0)
    c = mcrisolver_v1p0.cube()
    cm = mcrisolver_v1p0.cm
    c.alloc_colors()
    hub.led(0, 0, 0)
    hub.display.clear()
    portscan = True
    while portscan:
        time.sleep_ms(100)
        portscan = False
        sensor_dist = check_port(hub.port.A, False, [62], 0, 0)
        sensor_color = check_port(hub.port.C, False, [61], 0, 2)
        motor_scan = check_port(hub.port.E, True, [48, 75], 0, 4)
        motor_turn = check_port(hub.port.D, True, [48, 75], 4, 2)
        motor_tilt = [
            check_port(hub.port.B, True, [48, 75], 4, 0),
            check_port(hub.port.F, True, [48, 75], 4, 4)
        ]


def check_port(port, motor, t, x, y):
    if motor:
        dev = port.motor
    else:
        dev = port.device
    if dev != None and (port.info()['type'] in t):
        hub.display.pixel(x, y, 0)
    else:
        if dev != None:
            print("check_port: " + str(port.info()['type']))
        global portscan
        portscan = True
        hub.display.pixel(x, y, 9)
    return dev


def Position(mot):
    return mot.get()[1]


def run_wt(mot, pos, off):
    while abs(mot.get()[1] - pos) > off:
        time.sleep_ms(1)


def run_wt_up(mot, pos):
    while mot.get()[1] < pos:
        time.sleep_ms(1)


def run_wt_dn(mot, pos):
    while mot.get()[1] > pos:
        time.sleep_ms(1)


def run_wt_dir(mot, pos, off):
    if off < 0:
        while mot.get()[1] < pos:
            time.sleep_ms(1)
    else:
        while mot.get()[1] > pos:
            time.sleep_ms(1)


def run_nw(mot, pos, speed):
    mot.run_to_position(pos, speed=speed, max_power=speed, stall=False,
                        acceleration=100, deceleration=100, stop=mot.STOP_HOLD)


def run_to(mot, pos, speed):
    mot.run_to_position(pos, speed=speed, max_power=speed, stall=False,
                        acceleration=100, deceleration=100, stop=mot.STOP_HOLD)
    run_wt(mot, pos, 3)


def ScanReset():
    ColorOff()
    motor_scan.pwm(55)
    pos1 = Position(motor_scan)
    pos0 = pos1 - 100
    while pos1 > pos0:
        time.sleep_ms(100)
        pos0 = pos1
        pos1 = Position(motor_scan)
    global motor_scan_base
    motor_scan_base = Position(motor_scan) + scan_rst
    run_to(motor_scan, motor_scan_base, scan_pwr)
    motor_scan.brake()


def ScanPiece(spos, tpos, f, o, i, back=False):
    global slower
    spos += motor_scan_base
    run_nw(motor_scan, spos, 100)
    pos = Position(motor_scan)
    ScanDisp(i)
    if back:
        run_wt_dn(motor_turn, tpos + 3)
    else:
        run_wt_up(motor_turn, tpos - 3)
    ScanRGB(f, o)
    off = Position(motor_scan) - spos
    if pos < spos:
        if off < -5:
            slower += 1
    else:
        if off > 5:
            slower += 1


def TurnReset():
    global motor_turn_base
    motor_turn_base = Position(motor_turn)
    motor_turn.brake()


def TurnRotate(rot):
    TiltAway()
    global motor_turn_base
    motor_turn_base = motor_turn_base + turn_90 * rot
    run_nw(motor_turn, motor_turn_base, 100)
    run_wt(motor_turn, motor_turn_base, turn_45)


def TurnTurn(rot, rotn):
    extra = turn_3 * 4
    extran = turn_3
    if rot < 0:
        extra = -extra
    if rotn < 0:
        extra -= extran
    elif rotn > 0:
        extra += extran
    global motor_turn_base
    motor_turn_base = motor_turn_base + turn_90 * rot
    pos = motor_turn_base + extra
    run_nw(motor_turn, pos, 100)
    time.sleep_ms(20)
    TiltHold()
    run_wt(motor_turn, pos, 3)
    run_nw(motor_turn, motor_turn_base, 100)


def TiltReset():
    mot0 = motor_tilt[0]
    mot1 = motor_tilt[1]
    mot0.pwm(-40)
    mot1.pwm(40)
    pos1 = [Position(mot0), Position(mot1)]
    pos0 = [pos1[0] + 100, pos1[1] - 100]
    while pos1[0] < pos0[0] or pos1[1] > pos0[1]:
        time.sleep_ms(200)
        pos0 = pos1
        pos1 = [Position(mot0), Position(mot1)]
    bwd0 = Position(mot0)
    bwd1 = Position(mot1)
    mot0 = motor_tilt[0]
    mot1 = motor_tilt[1]
    mot0.pwm(40)
    mot1.pwm(-40)
    pos1 = [Position(mot0), Position(mot1)]
    pos0 = [pos1[0] - 100, pos1[1] + 100]
    while pos1[0] > pos0[0] or pos1[1] < pos0[1]:
        time.sleep_ms(200)
        pos0 = pos1
        pos1 = [Position(mot0), Position(mot1)]
    fwd0 = Position(mot0) - 3
    fwd1 = Position(mot1) + 3
    global motor_tilt_fwd, motor_tilt_hld, motor_tilt_bwd
    motor_tilt_fwd = [fwd0, fwd1]
    motor_tilt_hld = [fwd0 - 32, fwd1 + 32]
    motor_tilt_bwd = [fwd0 - 67, fwd1 + 67]
    trace("tilt " + str(motor_tilt_fwd) + " " +
          str(motor_tilt_hld) + " " + str(motor_tilt_bwd))
    trace("bwd " + str([bwd0, bwd1]))
    if fwd0 - bwd0 < 60 or bwd1 - fwd1 < 60:
        fatal_error()
    TiltAway()


def TiltAway():
    run_nw(motor_tilt[0], motor_tilt_bwd[0], 100)
    run_nw(motor_tilt[1], motor_tilt_bwd[1], 100)
    run_wt_dn(motor_tilt[0], motor_tilt_hld[0] - 6)
    run_wt_up(motor_tilt[1], motor_tilt_hld[1] + 6)


def TiltHold():
    run_nw(motor_tilt[0], motor_tilt_hld[0], 100)
    run_nw(motor_tilt[1], motor_tilt_hld[1], 100)


def TiltTilt(mid0, scan=False):
    mid1 = 1 - mid0
    pwr = 100
    pwra = -40
    bwd = -20
    fwd = -10
    hld = 10
    if mid0 == 1:
        pwr = -pwr
        pwra = -pwra
        bwd = -bwd
        fwd = -fwd
        hld = -hld
    run_nw(motor_tilt[mid1], motor_tilt_bwd[mid1], 100)
    if abs(Position(motor_tilt[mid0]) - motor_tilt_hld[mid0]) > 10:
        run_to(motor_tilt[mid0], motor_tilt_hld[mid0], 100)
    run_wt_dir(motor_tilt[mid1], motor_tilt_bwd[mid1] + bwd, bwd)
    motor_tilt[mid0].pwm(pwr)
    run_wt_dir(motor_tilt[mid0], motor_tilt_fwd[mid0] + fwd, fwd)
    time.sleep_ms(100)
    motor_tilt[mid1].pwm(-pwr)
    time.sleep_ms(10)
    motor_tilt[mid0].pwm(pwra)
    if scan:
        run_nw(motor_scan, motor_scan_base + scan_mid, scan_pwr)
    run_wt_dir(motor_tilt[mid1], motor_tilt_hld[mid1] + hld, hld)
    run_nw(motor_tilt[mid0], motor_tilt_hld[mid0], 100)
    run_nw(motor_tilt[mid1], motor_tilt_hld[mid1], 100)


def ColorOff():
    sensor_color.mode(2)


def ColorOn():
    sensor_color.mode(5)


def CubeWait(img):
    global wait_count
    if wait_count <= 0:
        Show(img)
        Eyes(0, 0, 3, 3)
        wait_count = 200
    elif wait_count == 180 or wait_count == 20:
        hub.display.clear()
        Eyes()
    elif wait_count == 160:
        Show(FACE)
    wait_count -= 1


def CubeSense():
    cm = sensor_dist.get(sensor_dist.FORMAT_SI)[0]
    # print(cm)
    return cm != None and cm < 6


def CubeRemove():
    global wait_count
    wait_count = 0
    count = 0
    while count < 150:
        count += 1
        if CubeSense():
            count = 0
        CubeWait(hub.Image.ARROW_W)
        time.sleep_ms(10)
    Show(FACE)
    Eyes()


def CubeInsert():
    global motor_turn_base
    global wait_count
    global mi_cube
    wait_count = 0
    hub.button.left.presses()
    hub.button.right.presses()
    count = 0
    sel = 0
    while count < 150:
        count += 1
        if not CubeSense():
            count = 0
        CubeWait(hub.Image.ARROW_E)
        if hub.button.left.presses() > 0 or hub.button.right.presses() > 0:
            if mi_cube == None:
                print("starting BLE")
                mi_cube = MiCubeConnectorBLEcentral()
                found = mi_cube.scan_connect()
                if not found:
                    print("Scanning timed out")
                    del (mi_cube)
                    continue
                print("Connected")

            else:
                mi_cube.disconnect()
                del (mi_cube)
                mi_cube = None
                print("Disconnected")

        time.sleep_ms(10)
    Show(FACE)
    Eyes()


def Init():
    GetPorts()
    Show(FACE)
    ScanReset()
    if CubeSense():
        CubeRemove()
    TiltReset()
    TurnReset()


def Eyes(a=0, b=0, c=0, d=0):
    sensor_dist.mode(5, b'' + chr(a * 9) + chr(b * 9) +
                     chr(c * 9) + chr(d * 9))


def Show(img):
    hub.display.show(img)


def Show3x3(s):
    hub.display.show(
        hub.Image('00000:0' + s[0:3] + '0:0' +
                  s[3:6] + '0:0' + s[6:9] + '0:00000')
    )


def ScanDisp(p):
    Show3x3(('900000000', '009000000', '000000009', '000000900',
            '090000000', '000009000', '000000090', '000900000',
             '000090000')[p])


def ScanRGB(f, o):
    rgb = sensor_color.get()
    c.set_rgb(f, o, rgb)
    rgb = ((2, 0, 0),
           (2, 0, 0),
           (2, 1, 0),
           (2, 2, 0),
           (0, 2, 0),
           (0, 2, 0),
           (0, 0, 2),
           (0, 0, 2),
           (2, 2, 2))[c.get_clr(f, o)]
    hub.led(rgb[0] * 125, rgb[1] * 20, rgb[2] * 20)


def ScanFace(f, o, tilt=1, back=False):
    global slower, scan_speed
    global motor_turn_base
    dir = scan_mid
    mid = True
    if f > 0:
        run_nw(motor_scan, motor_scan_base + scan_awy, scan_pwr)
        TiltTilt(tilt, True)
        dir -= scan_awy
        mid = False
    scanning = True
    while scanning:
        # print("FACE "+str(f))
        slower = 0
        if mid:
            run_nw(motor_scan, motor_scan_base + scan_mid, scan_pwr)
        TiltAway()
        ScanDisp(8)
        if dir > 0:
            run_wt_up(motor_scan, motor_scan_base + scan_mid - 3)
        else:
            run_wt_dn(motor_scan, motor_scan_base + scan_mid + 3)
        ScanRGB(f, 8)
        if back:
            motor_turn_base -= turn_90
            run_nw(motor_turn, motor_turn_base + turn_45, scan_speed)
        else:
            run_nw(motor_turn, motor_turn_base + turn_90 * 4, scan_speed)
        for i in range(4):
            ScanPiece(scan_crn, motor_turn_base + turn_45, f, o, i, back)
            if back:
                back = False
                run_nw(motor_turn, motor_turn_base + turn_90 * 4, scan_speed)
            motor_turn_base += turn_90
            ScanPiece(scan_edg, motor_turn_base, f, o + 1, i + 4)
            o += 2
            if o > 7:
                o = 0
        if slower > 4:
            dir = scan_mid - scan_edg
            mid = True
            scan_speed -= 1
            print("Scan speed " + str(slower) + " " + str(scan_speed))
        scanning = False
    hub.display.clear()


tiltd = 0


def SolveCube():
    global tiltd
    global mi_cube
    CubeInsert()
    scan = 0
    found = False
    while not found and scan < 3:
        ColorOn()
        ms = time.ticks_ms()
        if mi_cube == None:
            scan += 1
            tiltd += 1
            ScanFace(0, 2)
            ScanFace(4, 4, 0)
            ScanFace(2, 4, 0, True)
            ScanFace(3, 2, 0, True)
            ScanFace(5, 6)
            ScanFace(1, 6)
            ColorOff()
            hub.led(0, 0, 0)
            Show3x3('968776897')
            run_nw(motor_scan, motor_scan_base, scan_pwr)
            TiltHold()
            Show(FACE_LEFT)
            sms = int((time.ticks_ms() - ms) / 100)
            print("SCAN: " + str(int(sms / 10)) + "." + str(sms % 10) + "s")

        else:
            mi_cube.read()
            # Face Order/面序
            # 如果魔方有字能区别正反，扫描前首面/文字面朝上，字底对准主控；复原前首面/文字面正面超前，字底朝下
            # 正经魔方（例）：
            #    |橙|
            # |黄|绿|白|蓝|
            #    |红|
            #
            # 本程序乐高魔方扫描序：
            #    |6|
            # |3|2|1|5|
            #    |4|
            #
            # 本程序数据存储序：
            #    |1|
            # |2|4|0|5|
            #    |3|
            #
            # 数据片序（每一面从双数（序号块）开始扫描，因此双数是角块）
            #        |456|
            #        |387|
            #        |210|
            # |012|670|456|234|
            # |783|581|387|185|
            # |654|432|210|076|
            #        |456|
            #        |387|
            #        |210|
            #
            # 因此，0-53号数据
            #                |13 14 15|
            #                |12 17 16|
            #                |11 10 09|
            # |18 19 20|42 43 36|04 05 06|47 48 49|
            # |25 26 21|41 44 37|03 08 07|46 53 50|
            # |24 23 22|40 39 38|02 01 00|45 52 51|
            #                |31 32 33|
            #                |30 35 34|
            #                |29 28 27|
            print(mi_cube.state['cube_data'])
            print('parse mockdata', parseCube(mi_cube.state['cube_data']))

            mi_cube_colors = parseCube(mi_cube.state['cube_data'])

            RGB_COLOR_RED = [255, 0, 0]
            RGB_COLOR_GREEN = [0, 255, 0]
            RGB_COLOR_BLUE = [0, 0, 255]
            RGB_COLOR_WRITE = [255, 255, 255]
            RGB_COLOR_YELLOW = [255, 255, 0]
            RGB_COLOR_ORANGE = [255, 128, 0]
            color_map = {
                1: RGB_COLOR_GREEN,
                2: RGB_COLOR_YELLOW,
                3: RGB_COLOR_RED,
                4: RGB_COLOR_WRITE,
                5: RGB_COLOR_ORANGE,
                6: RGB_COLOR_BLUE,
            }
            mi_cube_color_order_to_robot_color_order = [47, 50, 53, 52, 51, 48, 45, 46, 49,
                                                        11, 14, 17, 16, 15, 12, 9, 10, 13,
                                                        20, 23, 26, 25, 24, 21, 18, 19, 22,
                                                        38, 41, 44, 43, 42, 39, 36, 37, 40,
                                                        35, 34, 33, 30, 27, 28, 29, 32, 31,
                                                        0, 1, 2, 5, 8, 7, 6, 3, 4]
            for current_face in range(6):
                for current_o in range(9):
                    c.set_rgb(current_face, current_o,
                              color_map[mi_cube_colors[mi_cube_color_order_to_robot_color_order[current_face*9+current_o]]])
        t = -1
        for i in range(12):
            # print("TYPE "+str(i))
            valid = c.determine_colors(i)
            # c.display()
            if valid:
                t = i
                # print("Valid: "+str(t))
                valid = c.valid_positions()
                if valid:
                    found = True
                    break
        if not found and scan == 3 and t >= 0:
            found = c.determine_colors(t)
            # c.display()
            # print("Invalid? "+str(t))
    # }
    if found:
        # print("Solving...")
        Show(FACE_RIGHT)
        c.solve(2000)
        # c.solve_apply()
        # c.display()
        Show(FACE)
        # Cube orientation after scan
        d = 3
        f = 0
        for mv in range(c.mv_n):
            md = c.mv_f[mv]
            mr = c.mv_r[mv]
            # print("Move ["+str(md)+" "+str(mr)+"]")
            # print("["+str(d)+" "+str(f)+"]")
            while d != md:
                rm = cm.get_remap(d, f)
                if md == rm.fm[1] or md == rm.fm[3]:
                    Show(FACE_BLNK0)
                    TiltAway()
                    Show(FACE_BLNK1)
                    if (md == rm.fm[1]) != (tiltd > 0):
                        TurnRotate(1)
                        f = rm.fm[4]
                    else:
                        TurnRotate(-1)
                        f = rm.fm[5]
                    Show(FACE_BLNK0)
                elif md == rm.fm[4] or (md == rm.fm[2] and tiltd > 0):
                    if mv % 4 == 0:
                        Show(FACE_LEFT)
                    TiltTilt(0)
                    tiltd -= 1
                    d = rm.fm[4]
                    # print("tiltd = "+str(tiltd))
                else:  # md == rm.fm[5]
                    if mv % 4 == 2:
                        Show(FACE_RIGHT)
                    TiltTilt(1)
                    tiltd += 1
                    d = rm.fm[5]
                    # print("tiltd = "+str(tiltd))
                if d != md:
                    # Wait to ensure double tilt is reliable
                    time.sleep_ms(150)
            # }
            # print("["+str(d)+" "+str(f)+"]")
            mrn = 0
            mvn = mv + 1
            while mvn < c.mv_n:
                if cm.adjacent(c.mv_f[mvn], md):
                    mrn = c.mv_r[mvn]
                    break
                mvn += 1
            # }
            Show(FACE)
            TurnTurn(mr, mrn)
        # }
        ms = int((time.ticks_ms() - ms) / 100)
        print("SOLVED: " + str(c.mv_n) + " turns " +
              str(int(ms / 10)) + "." + str(ms % 10) + "s")
        TiltAway()
        time.sleep_ms(500)
        if c.mv_n > 0:
            TurnRotate(-6)
    # }
    else:
        run_nw(motor_scan, motor_scan_base, scan_pwr)
        TiltAway()
    while (motor_scan.busy(1) or
           motor_turn.busy(1) or
           motor_tilt[0].busy(1) or
           motor_tilt[1].busy(1)):
        time.sleep_ms(1)
    motor_scan.brake()
    motor_turn.brake()
    motor_tilt[0].brake()
    motor_tilt[1].brake()
    CubeRemove()


# -----------------------------------------------------------------------------

def main():
    trace("main()")
    Init()
    while True:
        SolveCube()


trace("loaded")

# -----------------------------------------------------------------------------

main()

# END
