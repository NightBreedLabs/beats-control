# Studio3 research findings

Findings from the headphones, public sources, and static analysis of the Android Beats app (`com.apple.bnd`). The app was never run. No decompiled code is kept here.

## Audio codecs

BlueZ reports two A2DP endpoints on this headset, with firmware code `0244`:

| Codec | Capabilities |
|---|---|
| SBC | Bitpool 2 to 250 |
| AAC (MPEG-2 LC) | 44.1 and 48 kHz, VBR supported, 256 kbps maximum |

There is no vendor codec endpoint, which aptX and LDAC would need. The host has both encoders installed. A decoder would have to exist in signed headphone firmware, so an app cannot add one.

## App catalog

- The bundled product catalog lists Studio3 as product `8201` (`0x2009`) with `protocol_id` 3 and the features `ANC` and `ExploreFeatures`, alongside shared defaults for details, rename, firmware and battery.
- No EQ feature exists in the catalog for this model.
- The app maps `protocol_id` 3 to its BTP protocol, while a separate device-class path selects B2P and BCD. Which one the Studio3 answers has not been confirmed.

## Serial Port channel

The app uses the Serial Port service. BTP code includes authentication, packet encryption and firmware transfer. The channel connects and stays silent until a client speaks. No commands were sent.

The BTP library names commands such as cycle count, full charge capacity, power-down timeout and low-power sound profile. That list is shared across many Beats products, so a name does not show Studio3 support.

## Not attempted

- Reversing BTP authentication or encryption.
- Sending undocumented commands, or anything on firmware paths.
- Dumping or modifying W1 firmware. This risks permanent damage, and it could not add a codec without Apple's signature.

## Battery

Apple rates the Studio3 at up to 22 hours with Pure ANC and up to 40 hours without it. Noise cancelling is the main control available from software.
