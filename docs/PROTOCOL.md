# Studio3 control protocol notes

The Studio3 speaks the Apple accessory protocol used by AirPods, documented by the [LibrePods](https://github.com/librepods-org/librepods) project. These notes cover what was confirmed on a Studio3 with PnP product ID `0x2009`, firmware code `0244`.

## Channel

- Service UUID `74ec2172-0bad-4d01-8f77-997b2be0722a`, L2CAP PSM `0x1001`.
- Flatpak 1.18.4 refused `AF_BLUETOOTH` sockets even with `--allow=bluetooth`, so the app registers a BlueZ `Profile1` client with that UUID and PSM. BlueZ opens the channel and passes the descriptor through `NewConnection`. Only `--system-talk-name=org.bluez` is needed.

## Frames

| Direction | Bytes | Meaning |
|---|---|---|
| Send | `00 00 04 00 01 00 02 00 00 00 00 00 00 00 00 00` | Handshake |
| Send | `04 00 04 00 0F 00 FF FF FF FF` | Subscribe to notifications |
| Send | `04 00 04 00 09 00 0D 02 00 00 00` | Noise cancelling on |
| Send | `04 00 04 00 09 00 0D 01 00 00 00` | Noise cancelling off |
| Receive | `04 00 04 00 09 00 0D <mode> 00 00 00` | Current mode: 1 off, 2 on |
| Receive | `04 00 04 00 04 00 01 01 01 <level> <status> 01` | Battery percent; status 2 is discharging |

Status 1 for charging comes from LibrePods documentation and has not been confirmed on a Studio3.

Other received frames use opcodes `0x06`, `0x0C`, `0x0E` and `0x24`. Their Studio3 meaning is not confirmed, so the app ignores them. A `0x4D` set-features request produced no device-details frame.
