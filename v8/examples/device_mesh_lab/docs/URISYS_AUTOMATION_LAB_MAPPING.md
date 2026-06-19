# Mapping `urisys-automation-lab` flows to `urirun`

Source flows:

```txt
/home/tom/github/tellmesh/urisys-automation-lab/flows/*
```

## Core migration rule

Old style:

```yaml
- shell://sudo:
    args: ["apt-get", "update"]
- kvm://local/monitor/primary/query/screenshot
```

New style:

```yaml
- id: desktop_health
  uri: env://desktop/runtime/query/health
  payload: {}
```

In the new style, the target device is part of the URI authority:

```txt
scheme://device/capability/action/type
```

The controller does not assume that `local` has KVM, OCR, RDP, browser control,
or root access. It discovers `/routes` from each device and compiles the registry
from those routes.

## Flow-by-flow status

| old flow | direct in this example | required adapter for full parity |
|----------|------------------------|----------------------------------|
| `01_install_browser` | partial via `shell://device/command/which` and `browser://device/page/command/open` | package manager adapter, e.g. `pkg://device/apt/command/install` with policy |
| `02_update_system_tui` | partial via `env://device/runtime/query/health` and `shell://device/command/uname` | package manager adapter with explicit approval |
| `03_open_browser_gui` | intent route exists: `browser://device/page/command/open` | real browser adapter or desktop session agent |
| `04_browser_download_file` | browser open intent only | browser automation adapter with download observation |
| `05_fill_form_gui` | not executable by default | KVM + OCR + HIM adapters |
| `06_terminal_htop_tui` | process visibility via `proc://device/process/query/list` | terminal/HIM adapter if visual terminal control is needed |
| `07_edit_config_nano_tui` | not executable by default | file-edit adapter or guarded shell template |
| `08_voice_command_to_kvm` | NL to URI flow is implemented | STT + KVM adapter for voice/desktop execution |
| `09_webrtc_video_chat_rdp` | not executable by default | WebRTC/RDP transport adapter |
| `10_full_maintenance_rdp` | safe version implemented in `flows/automation_lab_safe.uri.flow.yaml` | package manager + browser + KVM + OCR + RDP adapters |

## Why this is more reliable

The old flow format named an intended URI, but there was no universal guarantee
that the runtime existed on the target machine. In the `urirun` version:

1. each computer exposes `/routes`,
2. the controller builds a registry from real routes,
3. payloads are validated before dispatch,
4. LLM-generated flows are rejected if they reference a missing URI,
5. missing GUI/KVM/OCR/RDP capabilities are shown as installable items.

## Next adapters to add

Add these when you want full parity with the old lab:

```txt
pkg://<device>/apt/command/install
pkg://<device>/apt/command/update
kvm://<device>/monitor/primary/query/screenshot
him://<device>/keyboard/command/type-text
him://<device>/keyboard/command/hotkey
ocr://<device>/image/latest/query/text
browser://<device>/page/query/dom
browser://<device>/page/query/screenshot
rdp://<device>/display/query/status
stt://<device>/session/main/query/transcript
webrtc://<device>/session/main/command/start
```

Each adapter should be narrow and explicit. Avoid a generic
`shell://device/terminal/command/run` endpoint for LLM-generated flows.
