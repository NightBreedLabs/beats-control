"""Encode and decode the Apple accessory protocol frames used by Beats Studio3.

Frame shapes were confirmed against real Studio3 hardware. See docs/PROTOCOL.md.
"""
from dataclasses import dataclass

AAP_UUID = '74ec2172-0bad-4d01-8f77-997b2be0722a'
AAP_PSM = 0x1001
HANDSHAKE = bytes.fromhex('00 00 04 00 01 00 02 00 00 00 00 00 00 00 00 00')
SUBSCRIBE = bytes.fromhex('04 00 04 00 0F 00 FF FF FF FF')
HEADER = bytes.fromhex('04 00 04 00')
OP_BATTERY = 0x04
OP_CONTROL = 0x09
CONTROL_LISTENING_MODE = 0x0D
MODE_OFF = 1
MODE_ANC = 2
BATTERY_CHARGING = 1
BATTERY_DISCHARGING = 2


def set_anc(enabled):
    mode = MODE_ANC if enabled else MODE_OFF
    return HEADER + bytes((OP_CONTROL, 0, CONTROL_LISTENING_MODE, mode, 0, 0, 0))


@dataclass(frozen=True)
class HandshakeAck:
    pass


@dataclass(frozen=True)
class AncState:
    enabled: bool


@dataclass(frozen=True)
class Battery:
    level: int
    charging: bool


def parse(frame):
    """Return an event for a known frame, or None for anything else."""
    if frame[:2] == b'\x01\x00':
        return HandshakeAck()
    if frame[:4] != HEADER or len(frame) < 7:
        return None
    opcode = int.from_bytes(frame[4:6], 'little')
    if opcode == OP_CONTROL and len(frame) >= 8 and frame[6] == CONTROL_LISTENING_MODE:
        if frame[7] in (MODE_OFF, MODE_ANC):
            return AncState(frame[7] == MODE_ANC)
        return None
    if opcode == OP_BATTERY and frame[6] >= 1 and len(frame) >= 12:
        level = frame[9]
        if level <= 100:
            return Battery(level, frame[10] == BATTERY_CHARGING)
    return None
