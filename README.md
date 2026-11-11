# pi-lockstep

audio, video and light in lockstep on a Raspberry Pi

This repository holds no code. It explains how four small projects fit together on a
Raspberry Pi running Kodi (LibreELEC), and how to set them up as one system. Each part
works alone; together they solve one problem.

## What you get

- **Optical S/PDIF out of a bare Raspberry Pi.** A TOSLINK module on one GPIO pin, no HAT,
  with AC3/DTS passthrough to a receiver.
- **Other rooms in sync with the main one.** A second room (a Snapcast client) plays what
  Kodi plays, aligned with the sound at the Pi and therefore with the picture.
- **Light that follows the sound.** WLED effects react to the music Kodi plays, without a
  microphone, and the light is delayed so that it matches what you hear.
- **Light that follows the picture.** TV-reactive light from the edges of the video, read
  straight from Kodi's display planes, without a capture card.

### The problem

Multiroom audio with Kodi as the source usually drifts: the other room is a few hundred
milliseconds off, and the right correction depends on the network, the player, the output
device and the format. Light that reacts to sound has the same trouble in the other
direction: the analysis sees the audio *before* the sound card has played it.

The approach here is to make the copy of the audio *early by a known amount*. A plugin in
front of the sound card writes the copy into a pipe a fixed time before the same audio
comes out of the card, whatever the player's buffer size. Whoever reads the pipe (Snapcast,
the WLED sender) then only needs a fixed delay of its own, instead of a hand-tuned one per
setup.

## How the parts connect

```
                           +--> sound card --> optical S/PDIF (rpi-gpio-spdif)
                           |                   or HDMI --> receiver / TV
 Kodi --> alsa-leadtap ----+
 (PCM)    (ALSA plugin)    |
                           +--> pipe --> snapserver ----> Snapcast clients
                           |                              (other rooms)
                           |
                           +--> pipe --> wled-audiosync --UDP--> WLED --> LED strips

 Kodi video planes --> tvlight --DDP--> WLED --> LED strips
```

AC3/DTS passthrough does not go through the plugin: Kodi sends it straight to the card on
its separate passthrough device (the copy is silent for such streams anyway).

## The four parts

| Project | What it is | Useful on its own for |
|---|---|---|
| [rpi-gpio-spdif](https://github.com/ehb/rpi-gpio-spdif) | ALSA plugin and Kodi add-on: S/PDIF output on GPIO21 (Raspberry Pi 0-4), PCM and AC3/DTS passthrough, no kernel driver | Getting digital audio out of a Pi without a HAT |
| [alsa-leadtap](https://github.com/ehb/alsa-leadtap) | ALSA plugin: passes audio to any sound card unchanged and writes a copy to a pipe a fixed time before it is audible | Anything that wants an early copy of what a player outputs: multiroom, visualisers, recording |
| [wled-audiosync](https://github.com/ehb/wled-audiosync) | Reads audio from a pipe and sends it to WLED as Audio Sync V2 (frequency bands, volume, beat), held back to match the sound | Sound-reactive WLED effects from any Linux audio source, no microphone |
| [tvlight](https://github.com/ehb/tvlight) | Kodi service add-on: edge colours of the picture to WLED over DDP | TV-reactive light on a Pi 4 with LibreELEC, no grabber |

They work independently: the S/PDIF output does not need the lead plugin, the plugin works in
front of HDMI or any other card, wled-audiosync takes any pipe, and tvlight touches no audio
at all. They share a convention (48 kHz, 16 bit, stereo copy; one `lead` time) so that they
line up when combined.

None of these projects is affiliated with Kodi, LibreELEC, WLED, Snapcast or the Raspberry
Pi Foundation.

## Shopping list and wiring

For everything:

- A Raspberry Pi 4 running LibreELEC 12 with Kodi 21 (the combination used here).
- A network the Pi, the Snapcast server host and the WLED controller share. Multicast
  helps for WLED audio sync; a unicast address works as well.

For optical S/PDIF:

- A TOSLINK transmitter module (data, Vcc, GND). Data to GPIO21 (header pin 40), Vcc to 5 V
  (pin 2 or 4, check the module), GND to pin 6. The S/PDIF output uses the Pi's I2S block, so no
  I2S DAC/HAT at the same time. Details, coax variants and a 100 nF tip in the
  rpi-gpio-spdif README.

For light:

- A WLED controller with LED strips. For sound-reactive effects the WLED build has to
  include the audioreactive usermod (ESP32 builds). tvlight only needs DDP, which WLED
  has on by default. Strip counts and start LEDs per screen edge are set in tvlight's
  settings.

For other rooms:

- A Snapcast server (it can run on the Pi or elsewhere) and a Snapcast client per room.

## Recipe

The main path installs three Kodi add-ons, all from an add-on repository, so Kodi keeps
them up to date. You need no compiler and no shell on the Pi apart from the Snapcast step.

In Kodi, allow add-ons from zip files once (Settings -> System -> Add-ons -> Unknown
sources). Download [repository.ehb-1.0.0.zip](https://ehb.github.io/pi-lockstep/repository.ehb-1.0.0.zip),
copy it to the Pi (for example into LibreELEC's `Downloads` share) and use Add-ons -> Install
from zip file. Then install rpi-gpio-spdif, alsa-leadtap and tvlight below with Add-ons -> Install from
repository -> pi-lockstep add-ons. All zips are also on the Releases page of each project.

### 1. Optical S/PDIF: service.rpi-gpio-spdif

Install it from the repository (64-bit Raspberry Pi only). It contains an ALSA plugin; there
is no kernel module and no zip per LibreELEC version, so a LibreELEC update does not break
it. It applies its own small overlay (only GPIO21; falls back to the stock `hifiberry-dac`
where that does not apply), writes its own ALSA configuration and provides the audio device
`hdmi_bmc` (shown in Kodi as "S/PDIF on GPIO21"). Restart Kodi once
after installing it. Its only setting, the extra buffer (default 80 ms), is what step 2 needs
as head start; leave it unless you know better.

Without S/PDIF (HDMI or another card), skip this step and give that card in step 2.

### 2. The plugin in front of the card: service.alsa-leadtap

Install it from the repository (64-bit Raspberry Pi only). It contains the ALSA plugin and
wled-audiosync. After installing, open its settings
(Add-ons -> My add-ons -> Services -> alsa-leadtap -> Configure):

| Setting | What to enter |
|---|---|
| Sound card (ALSA device) | the device that plays the sound; the default `hdmi_bmc` is the S/PDIF device of step 1, **with HDMI or another card it must be changed**, for HDMI for example `hdmi:CARD=vc4hdmi0,DEV=0` (see `aplay -L`) |
| Lead of the copy (ms) | how long before it is audible the copy is written, default 180 |
| Send audio sync to WLED | on, to run the bundled wled-audiosync (step 4) |
| Target address | the IPv4 address of the WLED controller, or the multicast group 239.0.0.1 (default) |
| Gain | gain of wled-audiosync, default 1.0 |

Restart Kodi once after installing it: a running Kodi does not see the new audio device.
The add-on creates the audio device `hdmi_leadtap` (shown in Kodi as "Audio with early
copy (leadtap)"). The pipes `/tmp/leadtap.fifo` (for Snapcast) and `/tmp/leadtap-sync.fifo`
(for the bundled wled-audiosync) are created by their readers. Change the lead only while
nothing is playing.

### 3. Snapcast server

The Snapcast server is not part of these add-ons (LibreELEC has `service.snapserver`, or
run one elsewhere). In `snapserver.conf`:

```
[stream]
source = pipe:///tmp/leadtap.fifo?name=Kodi&sampleformat=48000:16:2&mode=create
buffer = 130
```

Point the Snapcast clients of the other rooms at that stream. A buffer of 130 ms worked
with a client on Wi-Fi; the right value depends on your network.

### 4. Light that follows the sound

Nothing more to install: the alsa-leadtap add-on runs wled-audiosync with the same lead as
the plugin and the target address from its settings. In WLED: Config -> Sync Interfaces ->
Audio Sync, mode Receive, port 11988, then choose a sound-reactive effect.

### 5. Light that follows the picture: service.tvlight

Install it from the repository, enter the WLED
address and the number of LEDs per edge in its settings. It is active during fullscreen
video and the music visualisation.

### 6. Kodi

Settings -> System -> Audio:

- **Audio output device:** "Audio with early copy (leadtap)", i.e. `hdmi_leadtap`.
  Ordinary PCM from Kodi goes through the plugin.
- **Passthrough output device:** the device itself, here `hdmi_bmc` (HDMI:
  `hdmi:CARD=...`). Kodi only offers passthrough on devices named `iec958`, `spdif` or
  `hdmi`; `hdmi_leadtap` carries no passthrough. AC3/DTS passthrough goes directly to the
  card, without a copy. Leave E-AC3, TrueHD and DTS-HD passthrough off: Kodi offers them for an
  `hdmi` device, but they do not fit through S/PDIF.
- **Speakers configuration 2.0**, with *Dolby Digital (AC3) transcoding* enabled if the
  receiver should get surround from sources Kodi cannot pass through (AAC 5.1 and similar).
  Kodi then encodes AC3 and sends it to the passthrough device. Other rooms and the
  WLED sync hear nothing of such streams (the copy is silent for AC3 bitstreams); that is
  the price of passthrough.
- Output configuration "fixed" at 48 kHz avoids most sample-rate switches, after which
  receivers can take a second or two to lock again.

### Without the add-ons

For other systems (not LibreELEC on a Pi 4, or a Pi with another card), take the plugin and
the sender from the Releases pages as tarballs and wire them by hand. Do **not** combine
this with the service.alsa-leadtap add-on: both would define `pcm_type.leadtap`.

- Plugin: `alsa-leadtap-<version>-aarch64.tar.gz` or `-armhf.tar.gz` from
  [alsa-leadtap Releases](https://github.com/ehb/alsa-leadtap/releases). Put the library
  somewhere persistent (on LibreELEC, under `/storage`) and add this to
  `/storage/.config/asound.conf` (elsewhere `/etc/asound.conf`):

```
pcm_type.leadtap {
    lib "/storage/leadtap/libasound_module_pcm_leadtap.so"
}

pcm.spdif_early {
    type leadtap
    slave.pcm "hdmi_bmc"                   # your sound device, or hdmi:CARD=...
    lead 180                               # ms the copy is ahead of the sound
    fifo [ "/tmp/leadtap.fifo" "/tmp/leadtap-sync.fifo" ]
    hint {
        show on
        description "S/PDIF with early copy"
    }
}
```

  The slave must be given by name (a string). The plugin never creates the pipes; the
  readers do, and the plugin looks for them every 500 ms. The copy is 48 kHz, 16 bit,
  stereo. Choose `spdif_early` as Kodi's audio output device and the card itself as the
  passthrough device, as in step 6.
- Sender: `wled-audiosync-<version>-aarch64.tar.gz` or `-armhf.tar.gz` (static binaries)
  from [wled-audiosync Releases](https://github.com/ehb/wled-audiosync/releases). Run it as
  a service of your choice (on LibreELEC a unit under `/storage/.config/system.d/`):

```
wled-audiosync --pipe /tmp/leadtap-sync.fifo --lead-ms 180 --target <address of the WLED controller>
```

  `--lead-ms` is the plugin's `lead`.
- The S/PDIF plugin without the add-on: see the rpi-gpio-spdif README (tarball, overlay,
  ALSA setup).
- Snapcast and tvlight as in steps 3 and 5.

## Status

Honest summary: this runs at the author's home, on **one** Raspberry Pi 4 with LibreELEC
12.2.1, and has been tested nowhere else.

- Measured: with a 130 ms Snapcast buffer, a second room (client on Wi-Fi) played about
  20 ms early against the sound at the Pi (12 to 25 ms over several runs, no drift over two
  hours). Everything else was judged by ear and eye.
- Not tested: other Raspberry Pi models, other LibreELEC or Kodi versions, other receivers,
  Kodi with HDMI behind the plugin (only checked with `aplay`), S/PDIF on any other Pi model, USB or `dmix` slaves, other
  WLED versions and builds, other sources for wled-audiosync's pipe, HDR video for
  tvlight, long unattended runs of the whole chain, installing the add-on zips through
  Kodi's user interface on a clean system.
- The S/PDIF plugin has limits of its own: no `dmix` (one program at a time on the
  output), no keep-alive outside Kodi, the device name has to begin with `hdmi_` for
  passthrough, and on the Pi 5 only its overlay has run (by a Raspberry Pi engineer, together
  with a Pi 2). The kernel driver version (rpi-gpio-spdif
  tag v0.1.0) is the alternative if you need a real sound card.
- The add-ons have likewise been run only on that one Pi.
- Latency numbers depend on the player and the slave card; measure your own setup. A TV or
  receiver adds delay that no driver reports.

## How this was made

The code in the four projects was written by Claude Code (Anthropic); their commits carry
an `Assisted-by:` trailer. Other models reviewed it. I directed the work, made the design
decisions and tested everything on my own hardware, but I have not read the code line by
line. This repository's text was written the same way. Treat all of it like any outside
code and documentation -- issues and questions are welcome.

## License

The text of this repository is MIT licensed, see `LICENSE`. The four projects have their
own licenses.
