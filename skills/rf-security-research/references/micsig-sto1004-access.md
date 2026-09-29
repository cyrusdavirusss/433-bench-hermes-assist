# Micsig STO1004 — how to get at it, and what not to send it

Operator's scope: **Micsig STO1004**, serial 330012028, at **192.168.1.108** (Wi-Fi, DHCP — re-discover
by scanning the /24 for port 111 or 5025).

Spec: 4 channels, 100 MHz, 1 GSa/s, **70 Mpts**, 8-bit, 8" 800×600 touchscreen, 32 GB internal
storage, Wi-Fi / USB 3.0 host / USB-C / HDMI / trigger-out, built-in 5 h battery. Waveform capture
rate 130k wfms/s. Remote control officially supports **SCPI, PC software, and iOS/Android apps**.

## Five ways in (ordered by usefulness here)

1. **SCPI over VXI-11** — `pyvisa` resource `TCPIP0::192.168.1.108::INSTR` (port 111 rpcbind). This is
   the scripting path. One client only: opening a second session while another is live fails, and
   rapid connect/disconnect churn is associated with trouble. Port 5025 (raw socket) is open but did
   not answer `*IDN?` with plain LF framing — use VXI-11.
2. **Web UI, port 80** — a file browser: `/files` (saved setups: `default`, `refwave`,
   `refdefault`), `/pictures` (`Screenshots`, `.thumbnails`), `/movies`, plus `/screensize`
   (`{"width":800,"height":600}`). **This is the data path**: nothing here touches SCPI.
3. **RemotePlay, port 8081** — a WebSocket carrying both the live screen and touch input:
   - send `{"t":"open","c":"chX","v":"NA"}` → the scope streams **raw H.264** (~300 KB/s) which
     `ffmpeg -f h264` decodes to 800×600 frames;
   - touch events go back as JSON: `{"type":"onmousedown"|"onmousemove"|"onmouseup","clientX":x,"clientY":y}`
     in screen coordinates.
   - Opening it pops a **transient consent toast** ("Do you agree to remotely control the device?")
     that auto-fades in about a second. It needs no tap and is not an error.
   - Ports 9003 (print screen) and 9004 (standard commands) appear in the scope's own `config.js` but
     are **closed** on this firmware.
4. **USB** — the side panel has USB-C (device) and USB 3.0 host ports. USBTMC would need
   `modprobe usbtmc`; a **mouse or keyboard on the USB host port drives the UI** and makes the scope
   act like an Android tablet.
5. **PC software / phone app** — Micsig's own tools, Windows-centric; the web UI above covers the
   same ground without installing anything.

## Commands that work (STO dialect, from Micsig's own SCPI manual, which covers the STO series)

    *IDN?                        -> Micsig,STO1004,330012028,3
    :CHANnel<N>:SCALe?           -> e.g. 0.5000        (V/div works as expected)
    :TRIGger:STATus?             -> WAIT | RUN | STOP  (what a capture loop polls)
    :TRIGger:MODE <AUTO|NORMal>, :TRIGger:EDGE:SOURce/SLOPe/LEVel, :TRIGger:HOLDoff
    :TIMebase:EXTent <seconds>   <- the time window; there is NO :TIMebase:SCALe on this model
    :TIMebase:POSition, :TIMebase:MODE, :TIMebase:ZOOm:SCALe
    :MEASure:OPEN <item>[,src]   then query :MEASure:<item>?
    :MEASure:STATistic:{MEAN|MAX|MIN|DEV|CURRent|COUNt}:VIEW?   (statistics, useful for averaging)
    :ACQuire:TYPE, :ACQuire:DEPTh?, :AUTO:SET:*, :AUTO:RANge:*
    :WAVeform:{XINCrement?|XORigin?|XREFerence?|YINCrement?|YORigin?|YREFerence?}  (field by field)
    :STORage:SAVE:{SOURce|LOCAtion|TYPE|FILename} then :STORage:SAVE:START      <- SAFE SAVE
    :STORage:LOAD <ref><bool>,<filename>
    :STORage:CAPTure:STARt / :TIMEstamp / INCOlor                               <- SCREEN CAPTURE
    :STORage:CONSave / :STORage:CONLoad:FILename                                (setup save/load)

`:SYSTem:ERRor?` is **not implemented** — it answers `Error:SCPI Command error!`, which makes a
working command look broken if you poll it.

## What crashes it — do not send these

**`:WAVeform:MODE`/`PREamble?`/`DATA?` closed the scope application twice on 2026-09-29** (once
during a 70 Mpts NORMal download, once on the SOURce/FORMat/MODE/PREamble sequence). Each time the
SCPI service kept answering `*IDN?` while the app died, so it read as a plumbing fault. The commands
are documented, so this is firmware fragility, not misuse of an unknown command.

Use instead: **`:STORage:SAVE:START`** to write the capture to internal storage, then fetch the file
over HTTP from `/files/refwave/<name>`. For an image, `:STORage:CAPTure:STARt` then fetch from
`/pictures/Screenshots/<name>`. Neither goes anywhere near `:WAVeform:DATA?`.

House rules that came out of this:
- one SCPI client at a time (the MCP server's session is the one);
- no second pyvisa session from the terminal while it is connected;
- never pull bulk data over SCPI — the scope's Wi-Fi + transfer path cannot take it;
- if SCPI stops answering but `*IDN?` still works, the *app* has died, not the link. Check the screen
  over RemotePlay rather than guessing.

## Saved-file container (partial, being pinned down)

A `:STORage:SAVE` waveform is fetched as (reported) `audio/x-wav` but is **not** audio:

    first u32        0x20180411       (looks like a dated format version)
    u32 @ 0x04       1,  u32 @ 0x08  7000,  u32 @ 0x0c  4,  u32 @ 0x18  699,  u32 @ 0x2c  188
    double @ 96      0.02            (timebase, 20 ms/div)
    double @ 112     250000000       (sample rate, 250 MSa/s)
    sample data      from ~offset 256 (constant pattern visible when idle)

Screenshots are plain PNG (800×600) — no reverse engineering needed.

The parse must be validated against **on-screen ground truth**: take a capture whose readings are
known (e.g. Freq 43.52 Hz, PK-PK 130.1 mV, RMS 23.16 mV), decode it, and require the numbers to
match. Until that check passes, treat the field meanings above as provisional.
