"""
scanner.py — BarcodeScanner
Smart Barcode Attendance Management System

Encapsulates ALL scanning logic.
To migrate to ESP32/Arduino hardware:
  1. Keep this module's public interface unchanged.
  2. Replace _scan_loop() body with serial-port reads from the ESP32.
  3. The rest of the application needs zero modifications.
"""

import sys
import threading
import time
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class BarcodeScanner:
    """
    Multi-mode barcode scanner.

    Modes
    -----
    WEBCAM  – OpenCV + pyzbar reads frames from a camera.
    USB     – USB HID scanners emulate keyboards; feed the typed
              string into process_usb_input() on Enter.
    IMAGE   – Decode a single image file (useful for testing).
    SERIAL  – Placeholder for ESP32 UART output.
    """

    COOLDOWN_SECONDS = 2.5  # ignore repeated scans within this window

    def __init__(self, camera_index: int = 0):
        self.camera_index   = camera_index
        self._cap           = None
        self._is_running    = False
        self._scan_thread   = None
        self._on_scan: Callable | None = None
        self._last_code     = ""
        self._last_scan_ts  = 0.0
        self._frame_lock    = threading.Lock()
        self._latest_frame  = None
        self._camera_ok     = False

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start_webcam(self, on_scan: Callable[[str], None]) -> bool:
        """
        Start webcam scanning in a background thread.

        Parameters
        ----------
        on_scan : callable(barcode_str)
            Called on the scanner thread whenever a new barcode is decoded.
            Must be thread-safe (e.g. use root.after() to update tkinter).

        Returns True if the camera opened successfully.
        """
        if self._is_running:
            return True

        self._on_scan   = on_scan
        self._is_running = True
        self._scan_thread = threading.Thread(
            target=self._webcam_loop, daemon=True, name="BarcodeScannerThread"
        )
        self._scan_thread.start()

        # Wait for the camera thread to confirm availability or fail.
        deadline = time.time() + 1.0
        while time.time() < deadline and self._scan_thread.is_alive():
            if self._camera_ok:
                break
            time.sleep(0.05)
        return self._camera_ok

    def stop(self):
        """Stop scanning and release the camera resource."""
        self._is_running = False
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=2.0)
        self._release_camera()

    def get_latest_frame(self):
        """
        Return the most recent BGR frame captured by the camera.
        Returns None if the camera is not active.
        Thread-safe — uses a lock.
        """
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def process_usb_input(self, barcode_str: str) -> str | None:
        """
        Feed a barcode string that was typed by a USB HID scanner.
        Call this when the user presses Enter in the USB input field.
        Applies the same cooldown logic as webcam scanning.

        Returns the cleaned barcode string, or None if it should be ignored.
        """
        barcode = barcode_str.strip()
        if not barcode:
            return None

        now = time.time()
        if (barcode == self._last_code and
                now - self._last_scan_ts < self.COOLDOWN_SECONDS):
            return None  # duplicate within cooldown window

        self._last_code    = barcode
        self._last_scan_ts = now
        return barcode

    # ------------------------------------------------------------------ #
    # Static / class helpers                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def decode_image_file(image_path: str) -> str | None:
        """
        Decode the first barcode found in an image file.
        Useful for testing without physical hardware.
        """
        try:
            import cv2
            from pyzbar import pyzbar as pz
            img = cv2.imread(image_path)
            if img is None:
                return None
            barcodes = pz.decode(img)
            if barcodes:
                return barcodes[0].data.decode("utf-8")
        except Exception as e:
            logger.error("decode_image_file error: %s", e)
        return None

    @staticmethod
    def is_camera_available(index: int = 0) -> bool:
        """Quick probe — does OpenCV report a camera at this index?"""
        try:
            import cv2
            cap = cv2.VideoCapture(index)
            ok  = cap.isOpened()
            cap.release()
            return ok
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _open_camera(self):
        import cv2

        backends = [None]
        if sys.platform.startswith("win"):
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]
        elif sys.platform.startswith("linux"):
            backends = [cv2.CAP_V4L2, None]
        elif sys.platform.startswith("darwin"):
            backends = [cv2.CAP_AVFOUNDATION, None]

        for backend in backends:
            try:
                cap = (cv2.VideoCapture(self.camera_index, backend)
                       if backend is not None else
                       cv2.VideoCapture(self.camera_index))
                if cap.isOpened():
                    logger.info("Opened camera %d with backend %s", self.camera_index, backend)
                    return cap
                cap.release()
            except Exception as ex:
                logger.warning("Failed open camera %d with backend %s: %s",
                               self.camera_index, backend, ex)
        return None

    def _webcam_loop(self):
        """
        Background thread body.
        Reads frames, decodes barcodes, fires the callback.
        Replace this body with serial.readline() for ESP32 integration.
        """
        try:
            import cv2
            from pyzbar import pyzbar as pz
        except ImportError as e:
            logger.error("Missing dependency: %s — webcam scanning disabled.", e)
            self._camera_ok = False
            return

        self._cap = self._open_camera()
        if self._cap is None or not self._cap.isOpened():
            logger.warning("Could not open camera at index %d", self.camera_index)
            self._camera_ok = False
            self._release_camera()
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cap.set(cv2.CAP_PROP_FPS,          30)
        self._camera_ok = True

        logger.info("Webcam scanner started on camera index %d", self.camera_index)

        while self._is_running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # Store frame for GUI preview
            with self._frame_lock:
                self._latest_frame = frame

            # Decode barcodes in the frame
            barcodes = pz.decode(frame)
            now      = time.time()

            for bc in barcodes:
                code = bc.data.decode("utf-8").strip()
                if not code:
                    continue

                # Cooldown: skip repeated scan of same code
                if (code == self._last_code and
                        now - self._last_scan_ts < self.COOLDOWN_SECONDS):
                    continue

                self._last_code    = code
                self._last_scan_ts = now
                logger.debug("Barcode detected: %s", code)

                if self._on_scan:
                    try:
                        self._on_scan(code)
                    except Exception as cb_err:
                        logger.error("on_scan callback error: %s", cb_err)
                break  # process one barcode per frame pass

            time.sleep(0.03)   # ~30 fps

        self._release_camera()
        logger.info("Webcam scanner stopped.")

    def _release_camera(self):
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None


# ──────────────────────────────────────────────────────────────────────
# ESP32 / Arduino Compatibility Stub
# ──────────────────────────────────────────────────────────────────────

class SerialBarcodeScanner(BarcodeScanner):
    """
    Drop-in replacement for BarcodeScanner that reads from a serial port
    (e.g. ESP32 UART).

    Usage
    -----
    scanner = SerialBarcodeScanner(port="COM3", baud=9600)
    scanner.start_webcam(on_scan_callback)   # same interface!

    ESP32 Arduino sketch (pseudo-code):
        void loop() {
            String code = barcode_reader.read();
            if (code.length() > 0) {
                Serial.println(code);
            }
        }
    """

    def __init__(self, port: str = "COM3", baud: int = 9600, **kwargs):
        super().__init__(**kwargs)
        self._port = port
        self._baud = baud

    def _webcam_loop(self):
        """Override: read from serial instead of OpenCV."""
        try:
            import serial
        except ImportError:
            logger.error("pyserial not installed. Install with: pip install pyserial")
            return

        try:
            ser = serial.Serial(self._port, self._baud, timeout=1)
            self._camera_ok = True
            logger.info("Serial scanner opened on %s @ %d baud", self._port, self._baud)

            while self._is_running:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line and self._on_scan:
                    cleaned = self.process_usb_input(line)
                    if cleaned:
                        self._on_scan(cleaned)

            ser.close()
        except Exception as e:
            logger.error("Serial scanner error: %s", e)
            self._camera_ok = False
