# odoo-zplflow

**Universal Label Bridge for Odoo WMS to Zebra and thermal printers.**

`odoo-zplflow` is a free, open-source Odoo module that lets your warehouse send
raw ZPL (Zebra Programming Language) label streams straight from Odoo to Zebra
and other thermal label printers — instantly, without any middleware, print
server, CUPS installation or Odoo IoT Box.

Whether you run a brand-new Zebra Link-OS printer with modern firmware or a
veteran ZPL workhorse from a decade ago, the module speaks the right protocol
for it. Out of the box it supports three independent transport layers, chosen
per printer from a single configuration form.

---

## Table of contents

- [What is odoo-zplflow?](#what-is-odoo-zplflow)
- [Supported protocols](#supported-protocols)
- [No CUPS and no IoT Box required](#no-cups-and-no-iot-box-required)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
  - [1. Global settings](#1-global-settings)
  - [2. Register a printer](#2-register-a-printer)
  - [3. Assign a printer to an operation type or transfer](#3-assign-a-printer-to-an-operation-type-or-transfer)
  - [4. Printing a label](#4-printing-a-label)
- [Protocol reference](#protocol-reference)
  - [Zebra Link-OS IPPS (port 631, TLS)](#zebra-link-os-ipps-port-631-tls)
  - [Raw TCP socket (port 9100 / 9001)](#raw-tcp-socket-port-9100--9001)
  - [Direct Linux USB character device](#direct-linux-usb-character-device)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)
- [License](#license)

---

## What is odoo-zplflow?

`odoo-zplflow` — *Universal Label Bridge for Odoo WMS to Zebra and thermal
printers* — is an Odoo Inventory/Delivery extension that turns Odoo into a
first-class thermal label printing station.

Traditional Odoo thermal printing setups are painful: you need CUPS on the Odoo
server, a driver that understands ZPL, a print queue per printer, and often an
Odoo IoT Box (a paid subscription per device) just to bridge the web client to
the hardware. `odoo-zplflow` removes every one of those layers. It builds the
ZPL/IPP payload itself and pushes the bytes directly over the network or over a
local USB character device.

Highlights:

- **Three transports, one module** — IPPS over TLS, raw TCP sockets, and
  direct Linux USB character devices.
- **Native ZPL** — no rasterisation, no PDF conversion, no driver dependency.
  Barcodes and text stay crisp at 203 or 300 DPI.
- **Zero external services** — no CUPS daemon, no `cups` Python bindings, no
  IoT Box, no print server.
- **Standard protocols** — the IPPS transport emits a real RFC 8010 binary IPP
  `Print-Job` request, which is exactly what Zebra Link-OS firmware expects.
- **Configurable per printer** — mix IPPS, legacy TCP and USB printers in the
  same database.
- **Free tier on zplflow.com** — 6,000 label tokens per month, no credit card.

---

## Supported protocols

### Zebra Link-OS IPPS (Port 631 TLS, RFC 8010 compliant binary framing)

Designed for **Zebra Link-OS firmware V89.21.46Z and later**, which exposes a
secure Internet Printing Protocol endpoint at `ipps://<printer>:631/ipp/print`.
The module encodes the request as a standards-compliant RFC 8010 binary IPP
attribute stream (`Print-Job` operation, IPP 2.0) and appends the raw ZPL
document as the job payload.

- Encrypted end-to-end with TLS on port 631.
- No CUPS client library required — the binary framing is generated in pure
  Python using `struct`.
- Self-signed printer certificates are supported by disabling certificate
  verification per printer.
- Job status is read back from the IPP response status code.

### Raw TCP Socket (Port 9100 / 9001) for legacy Zebra printers and print servers

The industry-standard "JetDirect" raw printing port. Works with virtually every
Zebra printer ever shipped, plus third-party print servers and Wi-Fi/Ethernet
adapter boxes that map port 9100 to the attached device.

- Unencrypted, low-latency, dependency-free byte stream.
- Also supports port 9001 and any other custom port.
- Ideal for older ZPL-only firmware that has no IPP stack.

### Direct Linux USB character device (`/dev/usb/lp0`)

When the printer is plugged straight into the machine running Odoo, the module
can write ZPL bytes directly to the USB printer character device.

- No print spooler, no `usblp` filtering, no driver.
- Path is configurable, so `/dev/usb/lp1`, `/dev/usb/lp2`, … are all usable.
- The Odoo system user must be a member of the `lp` group (see
  [Configuration](#configuration)).

---

## No CUPS or IoT Box required

This module deliberately depends on **nothing** in the printing stack:

| Component | Needed? |
| --- | --- |
| CUPS server / `cupsd` | ❌ No |
| `pycups` / CUPS Python bindings | ❌ No |
| Odoo IoT Box subscription | ❌ No |
| Odoo Enterprise | ❌ No — works on Odoo Community |
| Vendor driver / PPD file | ❌ No |
| External print agent | ❌ No |

The only runtime dependency for the IPPS transport is the widely available
[`requests`](https://pypi.org/project/requests/) library (already used by many
Odoo deployments). The raw TCP and USB transports use only the Python standard
library.

---

## Requirements

- Odoo 18.0 (Community or Enterprise)
- Python 3.10 or newer
- `requests` (for the IPPS transport)
- `stock` and `delivery` Odoo modules (installed automatically as dependencies)
- Network reachability from the Odoo server to the printer on the chosen port,
  or membership of the Odoo system user in the `lp` group for USB printing

---

## Installation

1. **Copy the module** into your Odoo addons path:

   ```bash
   git clone https://github.com/zplflow/odoo-zplflow.git
   cp -r odoo-zplflow/odoo_zplflow_bridge /opt/odoo/addons/
   ```

2. **Install the Python dependency** (if not already present):

   ```bash
   pip install requests
   ```

3. **Restart the Odoo service** so the new addon is discovered:

   ```bash
   sudo systemctl restart odoo
   ```

4. **Update the apps list** in Odoo: *Apps → Update Apps List* (enable
   developer mode first).

5. **Install the module**: search for *Zebra & Thermal Label Printing via
   ZplFlow* and click **Activate**.

6. **Grant USB access** (only if you plan to print via `/dev/usb/lpX`):

   ```bash
   sudo usermod -aG lp <odoo-system-user>
   sudo systemctl restart odoo
   ```

---

## Configuration

### 1. Global settings

Open *Settings → General Settings* and scroll to the **ZplFlow** section:

| Setting | Description |
| --- | --- |
| **ZplFlow API URL** | Base URL of the ZplFlow service. Default: `https://api.zplflow.io`. |
| **ZplFlow API Key** | Your personal API key from [zplflow.com](https://zplflow.com). Required only for cloud-assisted label generation. |
| **Default Pipeline ID** | Fallback ZplFlow pipeline used when a printer has no pipeline of its own. |

The free plan includes **6,000 tokens per month** — enough for thousands of
shipping labels.

### 2. Register a printer

Go to *Inventory → Configuration → Thermal Printers (ZplFlow)* and create a
record:

| Field | Description |
| --- | --- |
| **Printer Name** | Human-readable name, e.g. *Shipping Zebra ZT411*. |
| **Protocol** | `Zebra Link-OS IPPS (Port 631 TLS)`, `Raw Socket TCP (Port 9100 / 9001)` or `Direct USB (/dev/usb/lpX)`. |
| **IP Address / Hostname** | Printer hostname or IP, e.g. `192.168.1.100`. Hidden for USB printers. |
| **Port** | `631` for IPPS, `9100` or `9001` for raw TCP. Hidden for USB printers. |
| **Verify TLS Certificate** | Leave unchecked for printers with self-signed certificates (the common case). |
| **USB Device Path** | Path to the character device, default `/dev/usb/lp0`. |
| **DPI** | `203` or `300` DPI — must match the print head resolution. |
| **Default ZplFlow Pipeline ID** | Optional pipeline used to generate ZPL for this printer. |
| **Active** | Uncheck to disable the printer without deleting it. |

### 3. Assign a printer to an operation type or transfer

Open any inventory transfer (*Inventory → Operations → Transfers*), go to the
**Other Info** tab and pick the **ZplFlow Thermal Printer** you registered. The
assignment is stored on the transfer, so automated workflows (receipts,
deliveries, internal transfers) can each target a different physical printer.

### 4. Printing a label

From a transfer form, click **Print Thermal Label (ZplFlow)**. The module:

1. Builds (or receives) the raw ZPL stream `^XA ... ^XZ`.
2. Routes it through the transport selected on the printer record.
3. Reports any printer-level error back to the user as a clear Odoo message.

You can also call the printer directly from server actions or automated rules:

```python
printer = env['zplflow.printer'].search([('name', '=', 'Shipping Zebra ZT411')], limit=1)
printer.print_zpl_stream("^XA^FO50,50^FDHello Odoo^FS^XZ")
```

---

## Protocol reference

### Zebra Link-OS IPPS (port 631, TLS)

```text
POST https://<host>:631/ipp/print
Content-Type: application/ipp

[ 8-byte IPP header: version 0x0200 | operation 0x0002 | request-id ]
[ 0x01  operation-attributes-tag
  0x47  attributes-charset            "utf-8"
  0x48  attributes-natural-language   "en"
  0x45  printer-uri                   "ipps://<host>:631/ipp/print"
  0x42  job-name                      "odoo-print-job"
  0x49  document-format               "application/vnd.zebra"
  0x03  end-of-attributes-tag ]
[ raw ZPL document bytes ]
```

Requires firmware **V89.21.46Z or newer**. Earlier firmware versions do not
expose the IPP endpoint — use raw TCP instead.

### Raw TCP socket (port 9100 / 9001)

```text
connect(<host>, 9100) -> write(raw ZPL bytes) -> close()
```

No framing, no handshake, no response body. This is the fastest and most
compatible path for legacy hardware and print servers.

### Direct Linux USB character device

```text
open("/dev/usb/lp0", "wb") -> write(raw ZPL bytes) -> close()
```

Bypasses the kernel's line-printer filtering entirely. Only works when Odoo
runs on the same host that the printer is plugged into.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `Failed IPPS print ... Connection refused` | Printer firmware older than V89.21.46Z, or IPP disabled on the printer. Switch to raw TCP. |
| `Zebra IPP error code: 0x0401` | The printer rejected the attributes — check the printer URI matches the configured host and port. |
| SSL/TLS error | Uncheck **Verify TLS Certificate** for self-signed printer certificates. |
| `Failed TCP print ... timed out` | Host unreachable, wrong port, or a firewall blocking 9100/9001. |
| `Failed USB print ... Permission denied` | Add the Odoo user to the `lp` group and restart Odoo. |
| Nothing prints but no error | Check **DPI** matches the print head and that the ZPL starts with `^XA` and ends with `^XZ`. |
| Garbled output | The printer is not in ZPL mode — change the printer's command language to ZPL. |

Enable Odoo debug logging for the `zplflow` logger to see detailed transport
errors.

---

## Security notes

- IPPS encrypts label traffic in transit. Where your printers support it, keep
  **Verify TLS Certificate** enabled.
- Raw TCP (9100) and USB transports are unencrypted by design; run them on an
  isolated warehouse VLAN whenever possible.
- API keys are stored as Odoo system parameters and are never exposed to the
  web client through the printer views.
- Printing is restricted by the module's access-control rules
  (`security/ir.model.access.csv`); only users with Inventory configuration
  rights should manage printer records.

---

## License

This module is licensed under the **GNU Lesser General Public License v3.0**
(LGPL-3.0). See the [`LICENSE`](LICENSE) file for the full text.

```text
odoo-zplflow — Universal Label Bridge for Odoo WMS to Zebra and thermal printers
Copyright (C) zplflow

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Lesser General Public License for more details.
```
