import time
from threading import Thread

import cv2
from PIL import Image

from inference.core.logger import logger


class WebcamStream:
    """Class to handle webcam streaming using a separate thread.

    Attributes:
        stream_id (int): The ID of the webcam stream.
        frame_id (int): A counter for the current frame.
        vcap (VideoCapture): OpenCV video capture object.
        width (int): The width of the video frame.
        height (int): The height of the video frame.
        fps_input_stream (int): Frames per second of the input stream.
        grabbed (bool): A flag indicating if a frame was successfully grabbed.
        frame (array): The current frame as a NumPy array.
        pil_image (Image): The current frame as a PIL image.
        stopped (bool): A flag indicating if the stream is stopped.
        t (Thread): The thread used to update the stream.
    """

    def __init__(self, stream_id=0, enforce_fps=False):
        """Initialize the webcam stream.

        Args:
            stream_id (int, optional): The ID of the webcam stream. Defaults to 0.
        """
        self.stream_id = stream_id
        self.enforce_fps = enforce_fps
        self.frame_id = 0
        self.vcap = cv2.VideoCapture(self.stream_id)
        self.width = int(self.vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.file_mode = self.vcap.get(cv2.CAP_PROP_FRAME_COUNT) > 0
        if self.enforce_fps and not self.file_mode:
            logger.warn(
                "Ignoring enforce_fps flag for this stream. It is not compatible with streams and will cause the process to crash"
            )
            self.enforce_fps = False
        self.max_fps = 30
        if self.vcap.isOpened() is False:
            logger.debug("[Exiting]: Error accessing webcam stream.")
            exit(0)
        self.fps_input_stream = int(self.vcap.get(cv2.CAP_PROP_FPS))
        logger.debug(
            "FPS of webcam hardware/input stream: {}".format(self.fps_input_stream)
        )
        self.grabbed, self.frame = self.vcap.read()
        self.pil_image = Image.fromarray(cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB))
        if self.grabbed is False:
            logger.debug("[Exiting] No more frames to read")
            exit(0)
        self.stopped = True
        self.t = Thread(target=self.update, args=())
        self.t.daemon = True

    def start(self):
        """Start the thread for reading frames."""
        self.stopped = False
        self.t.start()

    def update(self):
        """Update the frame by reading from the webcam."""
        frame_id = 0
        next_frame_time = 0
        t0 = time.perf_counter()
        while True:
            t1 = time.perf_counter()
            if self.stopped is True:
                break

            self.grabbed = self.vcap.grab()
            if self.grabbed is False:
                logger.debug("[Exiting] No more frames to read")
                self.stopped = True
                break
            frame_id += 1
            # We can't retrieve each frame on nano and other lower powered devices quickly enough to keep up with the stream.
            # By default, we will only retrieve frames when we'll be ready process them (determined by self.max_fps).
            if t1 > next_frame_time or self.enforce_fps:
                ret, frame = self.vcap.retrieve()
                if frame is None:
                    logger.debug("[Exiting] Frame not available for read")
                    self.stopped = True
                    break
                logger.debug(f"video capture effective FPS: {frame_id / (t1 - t0):.2f}")
                self.frame_id = frame_id
                self.frame = frame
                next_frame_time = t1 + (1 / self.max_fps) + 0.02
            if self.file_mode:
                t2 = time.perf_counter()
                time_to_sleep = (1 / self.fps_input_stream) - (t2 - t1)
                if time_to_sleep > 0:
                    time.sleep(time_to_sleep)
        self.vcap.release()

    def read_opencv(self):
        """Read the current frame using OpenCV.

        Returns:
            array, int: The current frame as a NumPy array, and the frame ID.
        """
        return self.frame, self.frame_id

    def stop(self):
        """Stop the webcam stream."""
        self.stopped = True
