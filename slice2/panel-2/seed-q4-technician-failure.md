### 1. Proprietary IP Camera Auth Mismatch
**Real-world case**: A technician installs a 2024 Hikvision PoE camera that uses standard RTSP port 554 but requires a custom digest auth realm (`HikvisionIPCamera instead of the generic `RTSP Server` realm the platform’s generic RTSP converter expects.
**Broken promise**: The one-wiring-model promise assumes all RTSP cameras work with the pre-built generic converter, but this device has a non-standard auth realm the generic converter rejects outright.
**Technician experience**: Runs the platform’s add-source wizard, enters the camera’s LAN IP, and gets only a generic "connection failed" error with no context. They cannot distinguish auth failure, port block, or network drop, and must SSH into the Thor to pull raw debug logs not included in the basic service pack to diagnose.
**Fix feature**: A device-specific converter library + debug overlay: The add-source wizard surfaces the exact auth/realm mismatch in plain language, and includes pre-built Hikvision-specific RTSP converters to avoid manual auth config.

---

### 2. VLAN-Segmented Network Discovery
**Real-world case**: A security-focused homeowner splits their LAN into two VLANs: a trusted main house LAN and an IoT VLAN for cameras/tuners. The technician plugs the camera into the IoT VLAN, but the platform’s default discovery tools only listen on the trusted LAN interface, so the wizard cannot detect the camera.
**Broken promise**: The one-wiring-model promise assumes all LAN devices are discoverable via default network listeners, but VLAN segmentation blocks this without manual config.
**Technician experience**: The wizard shows "no devices found" when scanning for RTSP sources, even after confirming the camera is powered and connected. The technician must edit the platform’s network config via SSH to add the IoT VLAN interface, a step not covered in the basic service guide.
**Fix feature**: A LAN interface selector in the add-source flow: The wizard lets the technician pick which network interface the platform uses for discovery, plus a manual IP entry mode that skips broadcast discovery entirely, so the technician can enter the device’s static IP directly without broadcast scans.

---

### 3. Custom MQTT Topic Mapping
**Real-world case**: A technician installs a budget smart mic that sends raw PCM audio over MQTT to a custom topic path `house/kitchen/mic/raw instead of the standard `confluence/audio/mic/raw that the platform’s generic MQTT audio converter expects.
**Broken promise**: The one-wiring-model promise assumes all MQTT audio sources use standard topic prefixes, but this device uses a custom path the generic converter does not map correctly.
**Technician experience**: Adds the MQTT source via the wizard, but no audio events appear in the feed. They must use a third-party MQTT client to confirm the device is sending messages, but cannot adjust the topic filter in the platform’s UI without command-line access.
**Fix feature**: A custom topic filter editor with live test: The add-source MQTT wizard includes a text field for the topic filter, plus a live subscribe test button that shows incoming messages in real time, so the technician can adjust the filter until it matches the device’s exact topic path without SSH access.
