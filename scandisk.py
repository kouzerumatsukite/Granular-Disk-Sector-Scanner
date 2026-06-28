import os
import sys
import time
import math
import struct
import win32con
import win32file
from PIL import Image

# --- CONFIGURATION ---
DRIVE_PATH = r"\\.\PhysicalDrive0"  # Target SSD
DRIVE_SIZE_GB = 240
SECTOR_SIZE = 4096
ERASE_BLOCK_SIZE = 2 * 1024 * 1024  # 2MB

TILES_PER_ROW = 64
CORE_GRID_SIDE_X = 32

CORE_GRID_SIDE_Y = ERASE_BLOCK_SIZE // CORE_GRID_SIDE_X // SECTOR_SIZE
TILE_SIDE_PIXELS_X = CORE_GRID_SIDE_X + 1
TILE_SIDE_PIXELS_Y = CORE_GRID_SIDE_Y + 1
SECTORS_PER_TILE = CORE_GRID_SIDE_X * CORE_GRID_SIDE_Y  # 4096 sectors
BYTES_PER_TILE = SECTORS_PER_TILE * SECTOR_SIZE     # 2,097,152 bytes

LATENCY_THRESHOLD_MS = 10.0  # Slow threshold to trigger filter
NUM_RETRIES = 3              # Verification read attempts
OUTPUT_FILE = "ssd_structural_blueprint2.png"

def get_color_for_latency(latency_ms):
    return int(math.tanh(latency_ms/256)*255)

def get_physical_disk_size(handle):
    # IOCTL_DISK_GET_DRIVE_GEOMETRY_EX control code
    # Constant value: 0x000700A0
    IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0
    
    # Allocate a buffer for the DISK_GEOMETRY_EX structure (usually 48 bytes is plenty)
    buffer_size = 64
    
    try:
        # Query the drive handle directly
        output = win32file.DeviceIoControl(
            handle,
            IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,
            None,
            buffer_size
        )
        
        # The DISK_GEOMETRY_EX structure layout contains a DISK_GEOMETRY structure first,
        # followed by a Large Integer (8 bytes) representing the DiskSize.
        # The DiskSize starts exactly at byte offset 24.
        disk_size_bytes = struct.unpack('<q', output[24:32])[0]
        return disk_size_bytes
    except Exception as e:
        print(f"Warning: Failed to automatically detect disk size via IOCTL: {e}")
        return None

def main():
    # 1. Open Handle with NO SOFTWARE/HARDWARE BUFFERING CACHE
    try:
        handle = win32file.CreateFile(
            DRIVE_PATH,
            win32con.GENERIC_READ,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_ATTRIBUTE_NORMAL | win32con.FILE_FLAG_NO_BUFFERING | win32con.FILE_FLAG_WRITE_THROUGH,
            None
        )
    except Exception as e:
        sys.exit(f"Run terminal as Administrator. Error: {e}")

    # hardcoded limit layout calculation
    total_bytes = DRIVE_SIZE_GB * 1000 * 1000 * 1000
    
    # --- AUTOMATIC SIZE DETECTION ---
    detected_bytes = get_physical_disk_size(handle)
    if detected_bytes:
        total_bytes = detected_bytes
        print(f"Detected Physical Drive Size: {total_bytes / (1024**3):.2f} GiB ({total_bytes:,} bytes)")
    else:
        # Fallback to hardcoded size if IOCTL query fails
        print("Falling back to hardcoded drive size mapping...",total_bytes,"bytes")

    total_tiles = math.ceil(total_bytes / BYTES_PER_TILE)
    
    tiles_per_row = TILES_PER_ROW
    total_rows = math.ceil(total_tiles / tiles_per_row)
    
    img_width = tiles_per_row * TILE_SIDE_PIXELS_X
    img_height = total_rows * TILE_SIDE_PIXELS_Y
    
    output_image = Image.new("L", (img_width, img_height), 128)
    pixels = output_image.load()

    print(f"Starting Hardware-Isolated Tile Scan...")
    print(f"Canvas Layout Size: {img_width}x{img_height}")
    print()
    for tile_idx in range(total_tiles):
        print("Sectors",tile_idx,"/",total_tiles,"scanned",end="\r")
        tile_x = (tile_idx % tiles_per_row) * TILE_SIDE_PIXELS_X
        tile_y = (tile_idx // tiles_per_row) * TILE_SIDE_PIXELS_Y
        tile_byte_offset = tile_idx * BYTES_PER_TILE

        if tile_y >= img_height:
            break

        # A structure to temporarily hold the core 64x64 raw numbers for projection math
        tile_latencies = [[0.0 for _ in range(CORE_GRID_SIDE_X)] for _ in range(CORE_GRID_SIDE_Y)]

        # --- PHASE 1: MACRO READ (1x1 TOP-LEFT) ---
        win32file.SetFilePointer(handle, tile_byte_offset, win32con.FILE_BEGIN)
        
        bytes_remaining = total_bytes - tile_byte_offset
        macro_read_size = min(ERASE_BLOCK_SIZE, bytes_remaining)
        
        start_macro = time.perf_counter()
        try:
            _, _ = win32file.ReadFile(handle, macro_read_size)
            end_macro = time.perf_counter()
            pages_read = math.ceil(macro_read_size / SECTOR_SIZE)
            macro_latency = ((end_macro - start_macro) * 1000) / max(1, pages_read)
        except Exception as e:
            # Check if Windows threw a hardware out-of-bounds error
            # e.winerror 38 = EOF, 27 = Sector Not Found
            if hasattr(e, 'winerror') and e.winerror in (27, 38):
                print(f"\n[!] Physical end of disk reached cleanly at tile {tile_idx} (Estimated ceiling hit).")
                break # Stop scanning entirely and go to final save
                
            macro_latency = 9999.0
            
        pixels[tile_x, tile_y] = get_color_for_latency(macro_latency)

        # --- PHASE 2: CORE SECTOR READS (64x64 BOTTOM-RIGHT) ---
        for py in range(CORE_GRID_SIDE_Y):
            for px in range(CORE_GRID_SIDE_X):
                pixel_index = (py * CORE_GRID_SIDE_X) + px
                global_sector = (tile_idx * SECTORS_PER_TILE) + pixel_index
                byte_offset = global_sector * SECTOR_SIZE

                if byte_offset >= total_bytes:
                    break

                win32file.SetFilePointer(handle, byte_offset, win32con.FILE_BEGIN)
                start_sector = time.perf_counter()
                try:
                    _, _ = win32file.ReadFile(handle, SECTOR_SIZE)
                    end_sector = time.perf_counter()
                    latency_ms = (end_sector - start_sector) * 1000
                except Exception as e:
                    # If an individual sector hits the true physical boundary
                    if hasattr(e, 'winerror') and e.winerror in (27, 38):
                        tile_latencies[py][px] = 9999.0
                        pixels[tile_x + 1 + px, tile_y + 1 + py] = 255 # Paint white
                        break # Break this tile's sector loop
                        
                    latency_ms = 9999.0

                # Conditional Retry logic to filter software hitching
                if LATENCY_THRESHOLD_MS < latency_ms < 9999.0:
                    retry_latencies = []
                    for _ in range(NUM_RETRIES):
                        win32file.SetFilePointer(handle, byte_offset, win32con.FILE_BEGIN)
                        r_start = time.perf_counter()
                        try:
                            _, _ = win32file.ReadFile(handle, SECTOR_SIZE)
                            r_end = time.perf_counter()
                            retry_latencies.append((r_end - r_start) * 1000)
                        except:
                            retry_latencies.append(9999.0)
                    latency_ms = min(latency_ms, min(retry_latencies))

                tile_latencies[py][px] = latency_ms
                pixels[tile_x + 1 + px, tile_y + 1 + py] = get_color_for_latency(latency_ms)

        # --- PHASE 3: COMPUTE SHADOW PROJECTIONS (TOP & LEFT BORDERS) ---
        # Top-Right Header (1x64): Column averages
        for col in range(CORE_GRID_SIDE_X):
            col_avg = sum(tile_latencies[row][col] for row in range(CORE_GRID_SIDE_Y)) / CORE_GRID_SIDE_Y
            pixels[tile_x + 1 + col, tile_y] = get_color_for_latency(col_avg)

        # Bottom-Left Margin (64x1): Row averages
        for row in range(CORE_GRID_SIDE_Y):
            row_avg = sum(tile_latencies[row][col] for col in range(CORE_GRID_SIDE_X)) / CORE_GRID_SIDE_X
            pixels[tile_x, tile_y + 1 + row] = get_color_for_latency(row_avg)

        # Intermittent progressive save on completed row steps
        if (tile_idx + 1) % tiles_per_row == 0:
            print(f"Row { (tile_idx + 1) // tiles_per_row }/{total_rows} drawn. Saving footprint safely...")
            output_image.save(OUTPUT_FILE)

    print("Sectors",total_tiles,"/",total_tiles,"scanned")
    win32file.CloseHandle(handle)
    output_image.save(OUTPUT_FILE)
    print("Complete! Structural layout map rendered.")

if __name__ == "__main__":
    main()
