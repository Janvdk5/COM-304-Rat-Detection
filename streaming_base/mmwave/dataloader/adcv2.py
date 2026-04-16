import numpy as np
import struct 
import socket

def read_packet(rx_cnt, tx_cnt, adc_samples):
    HOST_IP = '192.168.33.30'
    DCA_IP = '192.168.33.180'
    DATA_PORT = 4098
    CONFIG_PORT = 4096
    MAX_PACKET_SIZE = 4096
    FRAME_SIZE_INT16 = rx_cnt * tx_cnt * adc_samples * 2

    cfg_dest = (DCA_IP, CONFIG_PORT)
    cfg_recv = (HOST_IP, CONFIG_PORT)
    data_recv = (HOST_IP, DATA_PORT)

    config_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
        socket.IPPROTO_UDP
    )
    data_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
        socket.IPPROTO_UDP
    )

    # data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * MAX_PACKET_SIZE)
    data_socket.settimeout(0.05)

    data_socket.bind(data_recv)
    config_socket.bind(cfg_recv)

    buffer = np.array([])

    skipped_frames = 0
    missed_cnt = 1

    last_packet_num = -1
    num_frames = 1
    # for _j in range(num_frames):
        #print(f"row is {_j}")
    timeout = False
    while len(buffer) < FRAME_SIZE_INT16:
        #start_t = time.time()
        try:
            data, _ = data_socket.recvfrom(MAX_PACKET_SIZE)
        except TimeoutError:
            timeout = True
            break
        #end_t = time.time()
        #print(f"read packet in {(end_t - start_t) * 1000} ms")
        packet_num = struct.unpack('<1l', data[:4])[0]
        #print(f"seq no {packet_num}")
        if packet_num != last_packet_num + 1 and last_packet_num != -1:
            missed_cnt += 1
            print(f"[WARNING]: Missed packet (total missed: {missed_cnt})")
            packet_data = np.zeros((728, ), dtype=np.int16)
        else:
            byte_count = struct.unpack('<1Q', data[4:10] + b'\x00\x00')[0]
            packet_data = np.frombuffer(data[10:], dtype=np.int16)

        last_packet_num = packet_num
        buffer = np.concatenate((buffer, packet_data))

    # if timeout:
    #     print("timed out")
    #     continue

    raw_frame = buffer[:FRAME_SIZE_INT16]
    ret = np.zeros(len(raw_frame) // 2, dtype=np.complex64)

    # if len(buffer) >= FRAME_SIZE_INT16:
    #     buffer = buffer[FRAME_SIZE_INT16:]

    ret[0::2] = raw_frame[0::4] + 1j * raw_frame[2::4]
    ret[1::2] = raw_frame[1::4] + 1j * raw_frame[3::4]
    raw_data = ret.reshape((tx_cnt, rx_cnt, adc_samples)) if num_frames == 1 else ret.reshape(
        (num_frames, tx_cnt, rx_cnt, adc_samples)) 
    return raw_data


