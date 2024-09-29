import sys
import os
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, \
    QPushButton, QGraphicsView, QGraphicsScene, QMessageBox, QInputDialog
from PyQt5.QtGui import QImage, QPixmap, QPen, QColor, QPainter
from PyQt5.QtCore import Qt, QRectF, pyqtSignal


class ImageLabel(QLabel):
    mouse_clicked = pyqtSignal(int, int)  # Signal to communicate mouse clicks to the main class

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.mouse_pos = None
        self.crop_size = 100

    def set_crop_size(self, size):
        self.crop_size = size

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.pos()
        self.update()  # Calls paintEvent to redraw the yellow rectangle

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Emit the signal with the click coordinates
            self.mouse_clicked.emit(event.x(), event.y())

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.mouse_pos:
            painter = QPainter(self)
            painter.setPen(QPen(QColor("yellow"), 2, Qt.SolidLine))

            x, y = self.mouse_pos.x(), self.mouse_pos.y()
            crop_half_size = self.crop_size // 2
            rect = QRectF(x - crop_half_size, y - crop_half_size, self.crop_size, self.crop_size)
            painter.drawRect(rect)
            painter.end()


class ImageCropper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ImageCropper")

        # Set the initial size of the window to 500x500
        self.setGeometry(100, 100, 500, 500)
        self.setFocusPolicy(Qt.StrongFocus)  # Ensure the main window can capture keyboard events
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Create the main layout
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create the top layout for the button and mini-map
        self.top_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_layout)

        # Add the "Open Image" button to the top layout
        self.open_button = QPushButton("Open Image", self)
        self.open_button.clicked.connect(self.open_image)
        self.top_layout.addWidget(self.open_button)

        # Add the mini-map view to the top layout
        self.map_view = QGraphicsView(self)
        self.map_view.setFixedSize(200, 200)
        self.top_layout.addWidget(self.map_view)

        self.scene = QGraphicsScene(self)
        self.map_view.setScene(self.scene)

        # Create the label to display the image
        self.image_label = ImageLabel(self)
        self.image_label.setFocusPolicy(Qt.ClickFocus)  # Allow the label to capture focus when clicked
        self.image_label.mouse_clicked.connect(self.handle_mouse_click)  # Connect the signal to the event
        self.main_layout.addWidget(self.image_label)

        self.zoom_factor = 1.0
        self.image_path = None
        self.crop_size = 100  # Default crop size
        self.crop_folder = None  # Folder to save crops

        self.x_offset = 0
        self.y_offset = 0
        self.rect_cursor = None
        self.block_size = 800  # Initial block size
        self.image_size = None  # Size of the complete image
        self.current_block = None  # Stores the currently displayed image block

        self.map_view.mousePressEvent = self.handle_mini_map_click

        self.update_image_label_size()  # Adjust the size of the image label based on the window size
        self.show()

    def resizeEvent(self, event):
        """Adjust the size of the image label and block when the window is resized"""
        self.update_image_label_size()
        self.display_image()
        super().resizeEvent(event)

    def update_image_label_size(self):
        """Update the size of the image label based on the current window size"""
        screen_width = self.width()
        available_width = screen_width - 220  # Account for 200px of the mini-map and button, plus 20px margin
        self.image_label.setFixedWidth(available_width - 20)  # Maintain a 10px margin on both sides

        # Calculate height based on image aspect ratio if image is loaded
        if self.image_size:
            aspect_ratio = self.image_size[1] / self.image_size[0]
            adjusted_height = int(
                (available_width - 20) / aspect_ratio)  # Calculate the height based on the aspect ratio
            available_height = self.height() - 250  # Available height minus space for mini-map, button, and margins
            self.image_label.setFixedHeight(
                min(adjusted_height, available_height - 20))  # Maintain a 10px margin at the top and bottom
        else:
            available_height = self.height() - 250  # Account for other elements
            self.image_label.setFixedHeight(available_height - 20)  # If no image is loaded, set a default height

        # Update the block size based on the available dimensions
        self.block_size = min(self.image_label.width(), self.image_label.height())

    def open_image(self):
        # Set the crop size through a dialog
        crop_size, ok = QInputDialog.getInt(self, "Crop Size", "Enter the crop size (in pixels):", value=100, min=10,
                                            max=1000)
        if ok:
            self.crop_size = crop_size
            self.image_label.set_crop_size(crop_size)  # Set the crop size in the image label

        # Let the user choose the destination folder
        self.crop_folder = QFileDialog.getExistingDirectory(self, "Select the destination folder for crops")
        if not self.crop_folder:
            QMessageBox.critical(self, "Error", "No folder selected for saving crops.")
            return

        options = QFileDialog.Options()
        self.image_path, _ = QFileDialog.getOpenFileName(self, "Select an image", "",
                                                         "All Files (*);;Image Files (*.png;*.jpg;*.jpeg;*.bmp)",
                                                         options=options)

        if self.image_path:
            # Get the image size without loading it entirely into memory
            self.image_size = self.get_image_size(self.image_path)
            if self.image_size is None:
                QMessageBox.critical(self, "Error", "Unable to open the selected image.")
                return

            # Reset offsets
            self.x_offset = 0
            self.y_offset = 0
            self.display_image()
            self.setFocus()  # Ensure the main window captures focus

    def get_image_size(self, image_path):
        # Use OpenCV to get the image size without fully loading it
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is not None:
            return img.shape[:2]  # Returns (height, width)
        return None

    def load_image_block(self, x_offset, y_offset, block_size):
        if not self.image_path:
            return None

        # Calculate the area to be loaded based on the block size
        x_end = min(x_offset + block_size, self.image_size[1])
        y_end = min(y_offset + block_size, self.image_size[0])

        # Read only the necessary portion of the image using OpenCV
        img = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
        img = img[y_offset:y_end, x_offset:x_end]

        if img is not None:
            # Convert from BGR to RGB for PyQt5
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return None

    def display_image(self):
        # Determine how many blocks to load based on available width
        blocks_to_show = 1
        if self.image_label.width() >= 2 * self.block_size:
            blocks_to_show = 2

        # Load the first block
        block1 = self.load_image_block(self.x_offset, self.y_offset, self.block_size)
        combined_image = block1

        # Load the second block if space allows
        if blocks_to_show == 2:
            x_offset_2 = self.x_offset + self.block_size
            if x_offset_2 < self.image_size[1]:  # Ensure we don't exceed image bounds
                block2 = self.load_image_block(x_offset_2, self.y_offset, self.block_size)
                if block2 is not None:
                    combined_image = np.hstack((block1, block2))

        if combined_image is None or combined_image.size == 0:
            return

        # Convert the combined image into a format displayable by PyQt5
        height, width, channel = combined_image.shape
        bytes_per_line = 3 * width
        qimg = QImage(combined_image.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Display the combined image on the QLabel
        self.image_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio))
        self.update_mini_map(blocks_to_show)

    def update_mini_map(self, blocks_to_show):
        if self.image_path is None:
            return

        # Load the full image as a thumbnail for the mini-map
        img = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
        thumb = cv2.resize(img, (200, 200))
        thumb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)

        qthumb = QImage(thumb.data, thumb.shape[1], thumb.shape[0], thumb.strides[0], QImage.Format_RGB888)
        pixmap_thumb = QPixmap.fromImage(qthumb)
        self.scene.clear()
        self.scene.addPixmap(pixmap_thumb)

        scale_w = 200 / self.image_size[1]
        scale_h = 200 / self.image_size[0]

        rect_w = int(self.block_size * scale_w) * blocks_to_show
        rect_h = int(self.block_size * scale_h)

        # Add a rectangle to show the visible portion
        self.rect_cursor = self.scene.addRect(self.x_offset * scale_w, self.y_offset * scale_h, rect_w, rect_h,
                                              pen=QPen(QColor("red")))

    def handle_mini_map_click(self, event):
        # Calculate the position in the main image based on the click on the mini-map
        pos = event.pos()
        map_x = pos.x()
        map_y = pos.y()

        # Convert mini-map coordinates to real image coordinates
        scale_w = self.image_size[1] / 200
        scale_h = self.image_size[0] / 200

        self.x_offset = int(map_x * scale_w) - self.block_size // 2
        self.y_offset = int(map_y * scale_h) - self.block_size // 2

        # Keep offsets within image limits
        self.x_offset = max(0, min(self.x_offset, self.image_size[1] - self.block_size))
        self.y_offset = max(0, min(self.y_offset, self.image_size[0] - self.block_size))

        self.display_image()

    def keyPressEvent(self, event):
        """Handle arrow key and Ctrl + arrow key movements"""
        step = 100
        if event.modifiers() & Qt.ControlModifier:
            step = 600  # Increase step size if Ctrl is pressed

        if event.key() == Qt.Key_Left:
            self.x_offset = max(0, self.x_offset - step)
        elif event.key() == Qt.Key_Right:
            self.x_offset = min(self.image_size[1] - self.block_size, self.x_offset + step)
        elif event.key() == Qt.Key_Up:
            self.y_offset = max(0, self.y_offset - step)
        elif event.key() == Qt.Key_Down:
            self.y_offset = min(self.image_size[0] - self.block_size, self.y_offset + step)

        self.display_image()  # Update the image display after moving

    def handle_mouse_click(self, x, y):
        # Calculate the actual click position relative to the full image
        x_real = self.x_offset + int(x / self.zoom_factor)
        y_real = self.y_offset + int(y / self.zoom_factor)
        self.crop_at_position(x_real, y_real)

    def crop_at_position(self, x, y):
        crop_half_size = self.crop_size // 2
        x_start = max(0, x - crop_half_size)
        y_start = max(0, y - crop_half_size)
        x_end = min(self.image_size[1], x + crop_half_size)
        y_end = min(self.image_size[0], y + crop_half_size)

        # Load only the portion to be cropped
        crop = self.load_image_block(x_start, y_start, self.crop_size)

        if crop is None or crop.size == 0:
            return

        base_name = os.path.basename(self.image_path)
        name, ext = os.path.splitext(base_name)

        crop_name = f"{name}_crop_{x}_{y}.png"
        crop_path = os.path.join(self.crop_folder, crop_name)

        # Save the crop, converting back to BGR for OpenCV
        cv2.imwrite(crop_path, cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))

        QMessageBox.information(self, "Crop", f"Crop saved as: {crop_name}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = ImageCropper()
    mainWin.show()
    sys.exit(app.exec_())
