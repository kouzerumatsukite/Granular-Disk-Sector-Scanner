# Granular-Disk-Sector-Scanner

# Low-Level SSD Structural Latency Blueprint Scanner

A highly granular, bare-metal storage diagnostic tool written in Python. This script bypasses both Windows software caching layers and storage controller hardware buffering to perform a true physical block-by-block, page-by-page read latency scan.

The tool organizes the drive's geometry into distinct 2MB physical erase block tiles, mapping latencies onto a dynamically scaled grayscale blueprint image using a hyperbolic tangent ($\tanh$) compression curve. It also calculates interactive horizontal and vertical "shadow" borders showing row and column sub-averages for fast visual triage of flash wear topologies.

---

## Technical Architecture Overview

Unlike standard disk utilities that read via the OS filesystem driver, this suite operates directly at the physical media layer:

* **Hardware Cache Isolation:** Uses strict Win32 file flags (`FILE_FLAG_NO_BUFFERING` and `FILE_FLAG_WRITE_THROUGH`) to force the SSD controller to read directly from the physical NAND cells rather than serving cached copies from its internal DRAM/SRAM.
* **Dynamic Geometry Detection:** Queries the hardware subsystem via low-level IOCTL commands (`IOCTL_DISK_GET_DRIVE_GEOMETRY_EX`) to find the precise byte size, automatically protecting the script against end-of-disk hardware boundary stalls.
* **Custom Tile Matrix:** Each 2MB block is isolated into an asymmetry-optimized $32 \times 16$ grid mapping native 4KB flash pages, framed by a 1x1 overall macro average cell and 1D column/row average shadow lines.
* **Hyperbolic Scaling:** Fits latencies cleanly into an 8-bit grayscale canvas format (`"L"` mode, values `0` to `255`), preventing out-of-bounds float anomalies when encountering heavy LDPC error correction pauses or hard block timeouts.

---

## Installation Guide (From Ground Up)

Follow these step-by-step instructions to set up your environment on a fresh Windows system.

### Step 1: Install Python
1. Download the latest stable release of Python 3 from the official website: [python.org/downloads](https://www.python.org/downloads/).
2. Run the installer executable.
3. **CRITICAL:** Check the box that says **"Add python.exe to PATH"** at the bottom of the installer window before clicking install.
4. Complete the installation wizard.

### Step 2: Install Required Components
Open a standard command prompt or Windows PowerShell window and execute the following `pip` commands to install the required imaging and low-level Win32 API bindings:

```bash
pip install Pillow
pip install pywin32
```

## How to Launch and Run the Scanner

Because this script opens a direct raw handle to a primary hardware storage device (`\\.\PhysicalDrive0`), Windows security policies mandate full administrative privileges to interact with the media layer.

### 1. Open an Administrator Terminal
* Press the **Windows Key** on your keyboard.
* Type `cmd` (Command Prompt) or `PowerShell`.
* Right-click the application icon and select **"Run as Administrator"**.

### 2. Navigate to your Script Directory
Use the change directory (`cd`) command to move to the folder where you saved your Python file. For example, if it is saved to your desktop:

```powershell
cd C:\Users\YourUsername\Desktop
```

### 3. Execute the Script
Launch the script by passing the file name directly to the Python interpreter:

```powershell
python gemini-code-1782599647188.py
```

## Interacting with the Map (Live Progress)

You do not need to wait hours for the entire drive scan to hit 100% to analyze your drive's state. 

* **In-Place Console Output:** The terminal updates your current sector index and total tile progress on a single, clean line using active carriage returns (`\r`), preventing console spam.
* **Progressive Image Flushing:** The script automatically flushes the canvas data directly to the disk array at every completed tile-row milestone. 
* **Real-Time Inspection:** You can safely open `ssd_structural_blueprint2.png` in any image viewer while the script is running. Simply refresh or re-open the image to watch the underlying hardware topology paint its layout grid line-by-line.

---

## Technical Mapping & Layout Reference

The output image translates low-level physical traits into explicit visual landmarks using an 8-bit grayscale format (`"L"` mode):

| Canvas Feature | Physical Interpretation | Visual Appearance |
| :--- | :--- | :--- |
| **Top-Left Corner Pixels** | 2MB macro-block sequential read latency (Normalized per-page). | Baseline shading anchoring the tile. |
| **Top Header Bar (1x32)** | Calculated projection average of columns within the block. | Reveals vertical latency anomalies. |
| **Left Margin Bar (16x1)** | Calculated projection average of rows within the block. | Reveals horizontal latency anomalies. |
| **Core Inner Grid (32x16)** | Native **4KB physical NAND pages** checked via uncached I/O handles. | Dense structural matrix map. |
| **Dark / Near-Black Pixels** | Optimal, blazing-fast response time from healthy cells. | Solid drive health baseline. |
| **Bright Silver / White Pixels**| High response latency or hardware block timeouts (`9999.0` ms). | Pinpoints heavy LDPC error correction or degraded cells. |

---

## File System Structure Reference
* `gemini-code-1782599647188.py` - Core hardware scanner script.
* `ssd_structural_blueprint2.png` - Resulting real-time high-density visual grayscale map asset.

---

## License
This project is open-source. Feel free to modify, fork, or adjust the tile dimensions and data-mapping scales to explore custom hardware profiles!
