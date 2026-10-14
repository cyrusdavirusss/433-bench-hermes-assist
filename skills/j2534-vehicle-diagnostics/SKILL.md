---
name: j2534-vehicle-diagnostics
description: Use when diagnosing a car over J2534 or OBD. PassThru/Mini VCI link, ISO15765+UDS module scans, DTC reading, PID live data, and the dropout-logging method for intermittent faults.
version: 1.0.0
metadata:
  hermes:
    tags: [j2534, obd, uds, automotive, diagnostics, can, dtc]
    category: vehicle-diagnostics
---

# J2534 / OBD vehicle diagnostics

Diagnosing a car by talking to its ECUs directly over a J2534 PassThru adapter — no VCDS, no
ODIS, no Techstream. The tooling is a **public** repo, so it clones with no credentials:

```bash
git clone https://github.com/cyrusdavirusss/j2534-mcp-server.git ~/j2534-mcp-server
```

Read `README.md` in the clone; it is the authority on the MCP tool list. This skill carries the
method, the preconditions, and the field findings that already cost time.

## Preconditions — the work is Windows-side, and these are NOT optional

- **Windows x86/x64 host.** `MVCI32.dll` is a PE32 image, so the scripts must run under **32-bit**
  Python, e.g. `C:/Python311-32/python.exe server.py`. A 64-bit interpreter fails to load the DLL.
- **The J2534 PassThru DLL installed and registered.** Bench-proven: **Autokent MVCI MultiDriver**
  with a **Toyota Mini VCI** cable (FTDI **FT232R**). "Mini VCI clone" is the common name; the VIM
  inside behaves as a single-owner device.
- **`python-j2534` bindings** in a directory the scripts add to `sys.path` — check the
  `sys.path.insert(0, r"C:\Users\...\Python-J2534-Interface")` line at the top of every script and
  point it at wherever the bindings actually live on that machine.
- **ONE owner of the cable at a time.** The MCP server and a standalone script cannot both hold the
  device: the samplers' docstrings say so explicitly — *"Run AFTER the MCP server has closed the
  device."* A second opener does not error cleanly, it just fails to communicate.
- **A Linux/macOS instance cannot run this locally.** It drives the Windows host instead. Do not
  promise a local scan from a non-Windows box.
- Register the server in Hermes under the `mcp_servers` key (stdio transport), then restart so the
  tools register as `mcp_j2534_*`:

```yaml
mcp_servers:
  j2534:
    command: C:/Python311-32/python.exe
    args: [C:/path/to/j2534-mcp-server/server.py]
```

## The MCP tools (17)

Device: `j2534_list_devices`, `j2534_open_device`, `j2534_close_device`, `j2534_read_version`,
`j2534_read_battery_voltage`. Channel/messages: `j2534_connect_channel`, `j2534_disconnect_channel`,
`j2534_setup_ecu_filter`, `j2534_send_message`, `j2534_read_messages`, `j2534_send_and_receive`,
`j2534_clear_buffers`, `j2534_raw_command`. Vehicle-level: `j2534_read_lid` (Toyota enhanced mode
0x21), `j2534_uds_scan_ecus`, `j2534_lookup_dtc`, `j2534_decode_pid`.

`j2534_lookup_dtc` covers **12,000+ codes / 33 brands** (`dtc_data/dtc_unified.json`,
`dtc_manufacturers.json`), with Toyota tables sourced from toyota-club.net rather than a generic
list. `j2534_decode_pid` decodes raw bytes through the SAE J1979 signalset
(`dtc_data/saej1979.json`) — use it instead of hand-scaling bytes.

## The standalone scripts — pick the one that matches the question

| Script | Use it for |
|---|---|
| `link_test.py` | Is the cable talking at all? Raw write/read, one filter at a time. Run this FIRST — it separates "cable/software" from "car". |
| `toyota_scan.py` | Build the real ECU map: TesterPresent + `1902FF00` to every 7E0-7E7 plus functional 7DF, ISO-TP multi-frame reassembly. |
| `vag_scan.py` | VAG (VW/Audi/Skoda/SEAT) module sweep + DTC read + DID read + `--clear` (a WRITE). Speaks ISO15765, 500k. |
| `lid_scan.py` | Sweep Toyota enhanced mode 0x21 LIDs (`21`+LID → `61`+LID+data) to identify non-OBD parameters empirically. |
| `pid_decode.py` | Raw PID bytes → named, scaled values (`raw * mul / div + add`, or a label map). |
| `stall_sampler.py` | High-rate ECM sampler for **stall / bad-ground** faults: module voltage `0142`, rpm `010C`, coolant `0105`, ~3 Hz per PID, timestamped, **missing responses logged as empty fields**. |
| `sweep_sampler.py` | Fast APP pedal sweep: `0x49` (APP D) + `0x4A` (APP E), raw bytes + ratio to CSV. |

## Findings from the bench — do not re-derive these

**VAG addressing is not derivable — sweep, never assume a map.** On VAG the physical diagnostic CAN
IDs are not a function of the module address: engine/trans sit on the OBD-mandated `0x7E0`/`0x7E1`
pair, while body/comfort modules use per-platform IDs (a `0x7XX` request with the response at either
`+8` or `+0x6A`). Probe candidates and report what actually answers on THAT car.

**The clone VIM accepts one ISO15765 flow-control filter at a time.** Every candidate needs
clear-filters → install filter → send → read. On a 2010-era A4 (B8/8K) run, exactly **three modules
answered**: `01 Engine` (7E0/7E8), `02 Auto Trans` (7E1/7E9), `15 Airbags` (715/77F), all three
returning VIN `22F190`, part number `22F187`, SW `22F189`, HW `22F191` (+ serial `22F18C` where
present) — i.e. module identity without Techstream. **Eleven further modules had their filter
rejected** (TV Tuner, Lane Assist, Information Electr., Door Rear Left, Tire Pressure, Voice Control,
Trailer, Back-up Cam, Door Rear Right, Park Assist 2, Telephone) and are recorded as
`filter rejected (rx=… req=…)` in the scan JSON's `notes`. A rejected filter is a **tooling** limit,
not proof the module is absent — do not report it as "no such ECU".

**`7F 19 13` is a refusal, not "no codes".** Every VAG module in that run answered `7F 19 13` to
`ReadDTCByStatusMask` — the ECU rejecting the request under that addressing. It is **not** an
all-clear, and reporting it as one is the classic way to miss a real DTC. Read codes with the
addressing that module expects.

**Mode 06 needs no interpretation to be captured.** The A4 run holds raw `06A0`–`06A5` responses;
stored as raw because turning them into pass/fail needs the OEM monitor tables, which are not in the
tool. Capture them raw, then look them up.

**Pending codes exist without confirmed ones.** The same car showed `P0300`, `P0301`, `P0302` as
**pending** with an empty **confirmed** list. Pending-only misfires are a real result — report the
split, never collapse it to "3 misfire codes".

**A dropout during cranking is the finding, not an error.** `stall_sampler.py` exists because an
intermittent supply/ground fault shows up as the ECM leaving the bus. In the bench crank log (280
samples over 44.968 s) there is **one empty row at t=1.426 s** and then a **5.1 s hole** before
sampling resumes at 6.535 s with module voltage at **10.2 V** and rpm climbing 244 → 1540 as the
engine caught. Logging blank fields rather than skipping them is what makes that visible — keep that
behaviour in any sampler you write.

## Rules that cost time if broken

- **Run `link_test.py` before believing any vehicle-level result.** It separates a dead cable from a
  dead car in seconds.
- **One filter at a time on the clone VIM**, and re-install it per candidate rather than assuming
  filters stack.
- **Never leave the MCP server holding the device while a sampler runs** — single owner, always.
- **Mode/address conventions are per-brand and per-platform.** Do not carry a Toyota ID pair onto a
  VAG car or vice versa; the OBD-mandated `7E0`/`7E8` pair is the only part that generalises.
- **`--clear` is a WRITE.** Clearing a module erases stored DTCs, freeze frames and readiness
  monitors. Capture the codes to a file before clearing anything, and treat a clear as a
  deliberate, recorded action.
- **A blank field in a log is data.** Never drop it in post-processing.
- **Voltage is a diagnostic, not decoration.** A module voltage that sags into the ~10 V range under
  crank is the evidence for a supply-side fault; sample it alongside rpm every time.
- **Keep the raw response bytes.** Every decoded value in this toolchain is derived from raw bytes
  that were recorded — that is what lets a later session re-check a decode that turns out wrong.

## Open

- **The Toyota ECU map is not established.** `toyota_scan.json` records `filters: 8` with EMPTY
  `probes` and `functional` objects — the addressing was installed but nothing answered in that run.
  That is an unresolved run, not a negative result about the car; re-run with the link verified
  first.
- Mode 06 decoding, the pedal-sweep correlation, and the stall conclusion all await the OEM tables
  or more runs. Say which, rather than presenting a hypothesis as a diagnosis.
