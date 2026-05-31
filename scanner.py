"""
Smart Barcode Attendance Management System - Scanner Module
===========================================================
Handles all barcode scanning operations:
- Webcam-based scanning using OpenCV and pyzbar
- USB barcode scanner input simulation
- Image file barcode detection
- Hardware abstraction for future ESP32/Arduino migration

Architecture:
-------------
BaseScanner (abstract) -> defines the interface
    |
    +-- WebcamScanner -> OpenCV + pyzbar implementation
    +-- USBScanner -> USB HID barcode reader
    +-- ImageScanner -> Static image barcode detection

For ESP32 migration:
    +-- ESP32Scanner -> Serial/WiFi communication with ESP32
"""

import cv2
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional, List
from dataclasses import dataclass
from datetime import datetime
import os

try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    print("WARNING: pyzbar not installed. Barcode detection will be limited.")


@dataclass
class ScanResult:
    """Data class for scan results."""
    barcode_data: str
    barcode_type: str
    timestamp: str
    confidence: float = 1.0
    source: str = "unknown"


class BaseScanner(ABC):
    """
    Abstract base class for all barcode scanners.
    Defines the interface that all scanner implementations must follow.

    This abstraction allows easy swapping between:
    - Webcam scanning (current)
    - USB barcode scanner
    - ESP32/Arduino serial communication (future)
    """

    def __init__(self, on_scan_callback: Callable[[ScanResult], None] = None):
        """
        Initialize scanner with optional callback.

        Args:
            on_scan_callback: Function to call when barcode is detected
        """
        self.on_scan_callback = on_scan_callback
        self.is_scanning = False
        self.last_scan_time = 0
        self.cooldown_seconds = 2  # Prevent duplicate scans
        self.scan_history: List[ScanResult] = []

    @abstractmethod
    def start(self) -> bool:
        """Start scanning. Returns True if successful."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop scanning."""
        pass

    @abstractmethod
    def get_preview_frame(self) -> Optional:
        """Get current preview frame for display."""
        pass

    def _handle_scan(self, result: ScanResult) -> bool:
        """
        Process a scan result with cooldown and deduplication.

        Args:
            result: The scan result to process

        Returns:
            True if scan was accepted, False if rejected (cooldown/duplicate)
        """
        current_time = time.time()

        # Cooldown check
        if current_time - self.last_scan_time < self.cooldown_seconds:
            return False

        # Check if same barcode was scanned recently
        if (self.scan_history and
            self.scan_history[-1].barcode_data == result.barcode_data and
            current_time - self.last_scan_time < 5):
            return False

        self.last_scan_time = current_time
        self.scan_history.append(result)

        # Keep only last 100 scans in memory
        if len(self.scan_history) > 100:
            self.scan_history = self.scan_history[-100:]

        # Trigger callback
        if self.on_scan_callback:
            self.on_scan_callback(result)

        return True

    def get_scan_history(self) -> List[ScanResult]:
        """Get recent scan history."""
        return self.scan_history.copy()

    def clear_history(self) -> None:
        """Clear scan history."""
        self.scan_history.clear()


class WebcamScanner(BaseScanner):
    """
    Webcam-based barcode scanner using OpenCV and pyzbar.

    Features:
    - Real-time webcam feed with barcode detection overlay
    - Configurable camera index and resolution
    - Auto-focus and brightness adjustment hints
    - Visual feedback when barcode is detected
    """

    def __init__(self,
                 on_scan_callback: Callable[[ScanResult], None] = None,
                 camera_index: int = 0,
                 resolution: tuple = (1280, 720)):
        """
        Initialize webcam scanner.

        Args:
            on_scan_callback: Function to call on successful scan
            camera_index: Camera device index (0 = default)
            resolution: Tuple of (width, height) for camera resolution
        """
        super().__init__(on_scan_callback)
        self.camera_index = camera_index
        self.resolution = resolution
        self.cap = None
        self.scan_thread = None
        self.current_frame = None
        self.detection_box = None
        self.barcode_count = 0

    def start(self) -> bool:
        """
        Start webcam scanning.

        Returns:
            True if camera opened successfully
        """
        if not PYZBAR_AVAILABLE:
            print("ERROR: pyzbar library required for webcam scanning")
            return False

        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print(f"ERROR: Could not open camera {self.camera_index}")
            return False

        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

        self.is_scanning = True

        # Start scanning thread
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()

        return True

    def stop(self) -> None:
        """Stop webcam scanning and release resources."""
        self.is_scanning = False

        if self.scan_thread:
            self.scan_thread.join(timeout=1)

        if self.cap:
            self.cap.release()
            self.cap = None

        self.current_frame = None

    def get_preview_frame(self) -> Optional:
        """Get current frame for display in GUI."""
        return self.current_frame

    def _scan_loop(self) -> None:
        """Main scanning loop running in background thread."""
        while self.is_scanning and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()

            if not ret:
                time.sleep(0.1)
                continue

            # Detect barcodes in frame
            barcodes = decode(frame)

            if barcodes:
                for barcode in barcodes:
                    # Get barcode data
                    barcode_data = barcode.data.decode('utf-8')
                    barcode_type = barcode.type

                    # Draw rectangle around barcode
                    points = barcode.polygon
                    if points:
                        pts = [(p.x, p.y) for p in points]
                        cv2.polylines(frame, [np.array(pts, np.int32)],
                                     True, (0, 255, 0), 3)

                    # Create scan result
                    result = ScanResult(
                        barcode_data=barcode_data,
                        barcode_type=barcode_type,
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        confidence=1.0,
                        source=f"webcam_{self.camera_index}"
                    )

                    # Handle scan (with cooldown/dedup)
                    if self._handle_scan(result):
                        self.barcode_count += 1
                        # Visual feedback - flash green border
                        h, w = frame.shape[:2]
                        cv2.rectangle(frame, (0, 0), (w-1, h-1), (0, 255, 0), 20)

            # Store frame for preview
            self.current_frame = frame.copy()

            # Small delay to prevent high CPU usage
            time.sleep(0.03)  # ~30 FPS

    def get_frame_for_tkinter(self) -> Optional[bytes]:
        """
        Convert current frame to format suitable for Tkinter display.

        Returns:
            JPEG encoded bytes or None
        """
        if self.current_frame is None:
            return None

        # Resize for display
        display_frame = cv2.resize(self.current_frame, (640, 480))

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

        # Encode as JPEG
        ret, jpeg = cv2.imencode('.jpg', rgb_frame)

        return jpeg.tobytes() if ret else None

    def capture_snapshot(self, save_path: str = None) -> Optional[str]:
        """
        Save current frame as image.

        Args:
            save_path: Path to save image, auto-generated if None

        Returns:
            Path to saved image or None
        """
        if self.current_frame is None:
            return None

        if save_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = f"assets/scan_snapshot_{timestamp}.jpg"

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, self.current_frame)

        return save_path


class USBScanner(BaseScanner):
    """
    USB barcode scanner input handler.

    USB barcode scanners typically act as keyboard input devices.
    This class captures keyboard input and assembles barcode data.

    Note: In GUI applications, this is typically handled by binding
    to keypress events on an input widget.
    """

    def __init__(self, on_scan_callback: Callable[[ScanResult], None] = None):
        super().__init__(on_scan_callback)
        self.buffer = ""
        self.last_key_time = 0
        self.buffer_timeout = 0.1  # 100ms between characters

    def start(self) -> bool:
        """USB scanner is always 'ready' - input captured via events."""
        self.is_scanning = True
        return True

    def stop(self) -> None:
        """Stop USB scanner input."""
        self.is_scanning = False
        self.buffer = ""

    def get_preview_frame(self) -> Optional:
        """USB scanner has no visual preview."""
        return None

    def on_key_input(self, key: str) -> Optional[ScanResult]:
        """
        Process individual key input from USB scanner.

        USB scanners typically send characters rapidly followed by Enter/Return.
        Call this method for each keypress in your GUI event handler.

        Args:
            key: The character received

        Returns:
            ScanResult if complete barcode detected, None otherwise
        """
        if not self.is_scanning:
            return None

        current_time = time.time()

        # Check if this is a new scan (timeout exceeded)
        if current_time - self.last_key_time > self.buffer_timeout:
            self.buffer = ""

        self.last_key_time = current_time

        # Check for Enter/Return (end of barcode)
        if key in ('\r', '\n', 'Return'):
            if len(self.buffer) >= 3:  # Minimum barcode length
                result = ScanResult(
                    barcode_data=self.buffer,
                    barcode_type="USB",
                    timestamp=datetime.now().strftime("%H:%M:%S"),
                    confidence=1.0,
                    source="usb_scanner"
                )

                self.buffer = ""

                if self._handle_scan(result):
                    return result
            self.buffer = ""
        else:
            self.buffer += key

        return None

    def process_full_input(self, barcode_data: str) -> Optional[ScanResult]:
        """
        Process complete barcode string directly.

        Args:
            barcode_data: Complete barcode string

        Returns:
            ScanResult if accepted, None if rejected
        """
        if not self.is_scanning or len(barcode_data) < 3:
            return None

        result = ScanResult(
            barcode_data=barcode_data,
            barcode_type="USB",
            timestamp=datetime.now().strftime("%H:%M:%S"),
            confidence=1.0,
            source="usb_scanner"
        )

        if self._handle_scan(result):
            return result

        return None


class ImageScanner(BaseScanner):
    """
    Scan barcodes from static image files.
    Useful for testing or processing saved barcode images.
    """

    def __init__(self, on_scan_callback: Callable[[ScanResult], None] = None):
        super().__init__(on_scan_callback)
        self.last_image_path = None

    def start(self) -> bool:
        """Image scanner is always ready."""
        self.is_scanning = True
        return True

    def stop(self) -> None:
        """Stop image scanner."""
        self.is_scanning = False

    def get_preview_frame(self) -> Optional:
        """Return last scanned image."""
        if self.last_image_path and os.path.exists(self.last_image_path):
            return cv2.imread(self.last_image_path)
        return None

    def scan_image(self, image_path: str) -> List[ScanResult]:
        """
        Scan barcodes in an image file.

        Args:
            image_path: Path to image file

        Returns:
            List of detected barcodes
        """
        if not PYZBAR_AVAILABLE:
            print("ERROR: pyzbar library required for image scanning")
            return []

        if not os.path.exists(image_path):
            print(f"ERROR: Image not found: {image_path}")
            return []

        self.last_image_path = image_path

        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"ERROR: Could not load image: {image_path}")
            return []

        # Detect barcodes
        barcodes = decode(image)
        results = []

        for barcode in barcodes:
            barcode_data = barcode.data.decode('utf-8')
            barcode_type = barcode.type

            result = ScanResult(
                barcode_data=barcode_data,
                barcode_type=barcode_type,
                timestamp=datetime.now().strftime("%H:%M:%S"),
                confidence=1.0,
                source=f"image:{image_path}"
            )

            if self._handle_scan(result):
                results.append(result)

        return results


# Future ESP32 Scanner placeholder
class ESP32Scanner(BaseScanner):
    """
    Future implementation for ESP32/Arduino barcode scanner.

    This class provides the interface for communicating with an ESP32
    or Arduino-based barcode scanner over serial or WiFi.

    Protocol (planned):
    - Serial: USB/UART communication
    - WiFi: HTTP/WebSocket endpoints
    - Data format: JSON with barcode data and metadata
    """

    def __init__(self,
                 on_scan_callback: Callable[[ScanResult], None] = None,
                 connection_type: str = "serial",  # "serial" or "wifi"
                 port: str = "/dev/ttyUSB0",
                 baudrate: int = 115200,
                 wifi_ip: str = "192.168.1.100"):
        super().__init__(on_scan_callback)
        self.connection_type = connection_type
        self.port = port
        self.baudrate = baudrate
        self.wifi_ip = wifi_ip
        self.serial_conn = None

    def start(self) -> bool:
        """
        Start ESP32 scanner connection.

        TODO: Implement serial/WiFi connection logic
        """
        if self.connection_type == "serial":
            try:
                import serial
                self.serial_conn = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=1
                )
                self.is_scanning = True

                # Start listening thread
                self.scan_thread = threading.Thread(
                    target=self._serial_listen_loop, daemon=True
                )
                self.scan_thread.start()
                return True
            except ImportError:
                print("ERROR: pyserial library required for serial connection")
                return False
            except Exception as e:
                print(f"ERROR: Could not open serial port: {e}")
                return False

        elif self.connection_type == "wifi":
            # TODO: Implement WiFi connection
            print("WiFi connection not yet implemented")
            return False

        return False

    def stop(self) -> None:
        """Stop ESP32 scanner connection."""
        self.is_scanning = False

        if self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None

    def get_preview_frame(self) -> Optional:
        """ESP32 may provide camera feed in future."""
        return None

    def _serial_listen_loop(self) -> None:
        """Listen for data from ESP32 over serial."""
        while self.is_scanning and self.serial_conn:
            try:
                if self.serial_conn.in_waiting:
                    data = self.serial_conn.readline().decode('utf-8').strip()

                    if data:
                        result = ScanResult(
                            barcode_data=data,
                            barcode_type="ESP32",
                            timestamp=datetime.now().strftime("%H:%M:%S"),
                            confidence=1.0,
                            source=f"esp32_{self.port}"
                        )
                        self._handle_scan(result)
            except Exception as e:
                print(f"Serial communication error: {e}")
                time.sleep(1)

    def send_command(self, command: str) -> bool:
        """
        Send command to ESP32 device.

        Args:
            command: Command string to send

        Returns:
            True if sent successfully
        """
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(f"{command}\n".encode())
                return True
            except Exception as e:
                print(f"Error sending command: {e}")
        return False


class ScannerFactory:
    """
    Factory for creating scanner instances.
    Central point for scanner configuration and instantiation.
    """

    @staticmethod
    def create_scanner(scanner_type: str = "webcam",
                       on_scan_callback: Callable = None,
                       **kwargs) -> BaseScanner:
        """
        Create a scanner instance of the specified type.

        Args:
            scanner_type: 'webcam', 'usb', 'image', or 'esp32'
            on_scan_callback: Callback for scan events
            **kwargs: Additional scanner-specific parameters

        Returns:
            Configured scanner instance
        """
        if scanner_type == "webcam":
            return WebcamScanner(
                on_scan_callback=on_scan_callback,
                camera_index=kwargs.get('camera_index', 0),
                resolution=kwargs.get('resolution', (1280, 720))
            )
        elif scanner_type == "usb":
            return USBScanner(on_scan_callback=on_scan_callback)
        elif scanner_type == "image":
            return ImageScanner(on_scan_callback=on_scan_callback)
        elif scanner_type == "esp32":
            return ESP32Scanner(
                on_scan_callback=on_scan_callback,
                connection_type=kwargs.get('connection_type', 'serial'),
                port=kwargs.get('port', '/dev/ttyUSB0'),
                baudrate=kwargs.get('baudrate', 115200)
            )
        else:
            raise ValueError(f"Unknown scanner type: {scanner_type}")


# Convenience function for quick scanning
def quick_scan_webcam(timeout: int = 30) -> Optional[ScanResult]:
    """
    Quick webcam scan - opens camera, waits for barcode, returns result.

    Args:
        timeout: Maximum seconds to wait

    Returns:
        ScanResult or None if timeout
    """
    if not PYZBAR_AVAILABLE:
        print("pyzbar not installed")
        return None

    result_container = [None]

    def callback(scan_result):
        result_container[0] = scan_result

    scanner = WebcamScanner(on_scan_callback=callback)

    if not scanner.start():
        return None

    print(f"Scanning for {timeout} seconds...")

    start_time = time.time()
    while result_container[0] is None and (time.time() - start_time) < timeout:
        time.sleep(0.1)

    scanner.stop()
    return result_container[0]


# Import numpy for OpenCV operations
try:
    import numpy as np
except ImportError:
    np = None


if __name__ == "__main__":
    # Test scanner module
    print("Testing Scanner Module...")

    # Test USB scanner simulation
    usb = USBScanner()
    usb.start()

    # Simulate typing a barcode
    test_barcode = "STU123456"
    for char in test_barcode:
        result = usb.on_key_input(char)

    result = usb.on_key_input('\r')  # Enter key

    if result:
        print(f"Scanned: {result.barcode_data}")

    usb.stop()
    print("Scanner test complete.")
