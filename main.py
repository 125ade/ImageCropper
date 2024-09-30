import sys
import os
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, \
    QPushButton, QGraphicsView, QGraphicsScene, QMessageBox, QInputDialog, QToolBar, QAction, QDialog, QListWidget, \
    QListWidgetItem, QSizePolicy
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QSettings, QSize
from PyQt5.QtGui import QImage, QPixmap, QPen, QColor, QPainter, QIcon


class ImageLabel(QLabel):
    mouse_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.mouse_pos = None
        self.crop_size = 100
        self.zoom_factor = 1.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)

    def set_crop_size(self, size):
        self.crop_size = size

    def set_zoom_factor(self, zoom):
        self.zoom_factor = zoom
        self.update()

    def mouseMoveEvent(self, event):
        # Update mouse position
        self.mouse_pos = event.pos()
        self.update()  # Redraw the yellow rectangle

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Emit signal with click coordinates
            self.mouse_clicked.emit(event.x(), event.y())

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.mouse_pos and self.pixmap():
            painter = QPainter(self)
            painter.setPen(QPen(QColor("yellow"), 2, Qt.SolidLine))

            x, y = self.mouse_pos.x(), self.mouse_pos.y()

            # Calculate scale factors between pixmap and label
            pixmap_size = self.pixmap().size()
            label_size = self.size()
            scale_x = pixmap_size.width() / label_size.width()
            scale_y = pixmap_size.height() / label_size.height()

            # Adjust crop rectangle size according to the display scale
            crop_width = self.crop_size * scale_x
            crop_height = self.crop_size * scale_y
            crop_half_width = crop_width / 2
            crop_half_height = crop_height / 2

            rect = QRectF(x - crop_half_width, y - crop_half_height, crop_width, crop_height)
            painter.drawRect(rect)
            painter.end()


class ImageCropper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ImageCropper")
        self.setWindowIcon(QIcon('logoImageCropper.jfif'))

        # Initialize variables
        self.zoom_factor = 1.0
        self.image_path = None
        self.crop_size = 100  # Default crop size

        self.crop_folder = None  # Initialize destination folder

        self.x_offset = 0
        self.y_offset = 0
        self.rect_cursor = None
        self.block_size = 800  # Initial block size
        self.image_size = None  # Size of the full image
        self.current_block = None  # Stores the currently displayed image block

        # Initialize settings and recent files
        self.settings = QSettings('YourCompany', 'ImageCropper')
        self.recent_files = self.settings.value('recent_files', [], type=list)

        # Create the toolbar
        self.toolbar = self.addToolBar('Main Toolbar')
        self.create_actions()

        # Create the main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create the central layout for mini-map and image
        self.central_layout = QHBoxLayout()
        self.main_layout.addLayout(self.central_layout)

        # Add the mini-map view to the central layout
        self.map_view = QGraphicsView(self)
        self.map_view.setFixedSize(300, 300)
        self.central_layout.addWidget(self.map_view)

        self.scene = QGraphicsScene(self)
        self.map_view.setScene(self.scene)

        # Create the label to display the image
        self.image_label = ImageLabel(self)
        self.image_label.setFocusPolicy(Qt.ClickFocus)
        self.image_label.mouse_clicked.connect(self.handle_mouse_click)
        self.central_layout.addWidget(self.image_label)

        # Set stretch factors
        self.central_layout.setStretch(0, 0)  # Mini-map
        self.central_layout.setStretch(1, 1)  # Image

        # Set initial crop size and zoom factor
        self.image_label.set_crop_size(self.crop_size)
        self.image_label.set_zoom_factor(self.zoom_factor)

        self.map_view.mousePressEvent = self.handle_mini_map_click

    def create_actions(self):
        # Create actions for the toolbar
        open_icon = QIcon('icons/file-edit-outline.svg')  # Use SVG icon for opening
        open_action = QAction(open_icon, 'Open Image', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_image)
        self.toolbar.addAction(open_action)

        # Add action to set crop size
        crop_icon = QIcon('icons/crop.svg')  # Updated icon name
        crop_action = QAction(crop_icon, 'Set Crop Size', self)
        crop_action.setShortcut('Ctrl+Shift+C')  # You can choose another shortcut
        crop_action.triggered.connect(self.set_crop_size)
        self.toolbar.addAction(crop_action)

        # Add action to change destination folder
        folder_icon = QIcon('icons/folder-edit-outline.svg')
        folder_action = QAction(folder_icon, 'Change Destination Folder', self)
        folder_action.setShortcut('Ctrl+D')
        folder_action.triggered.connect(self.change_destination_folder)
        self.toolbar.addAction(folder_action)

        # Add zoom in action
        zoom_in_icon = QIcon('icons/magnify-plus-outline.svg')
        zoom_in_action = QAction(zoom_in_icon, 'Zoom In', self)
        zoom_in_action.setShortcut('Ctrl++')
        zoom_in_action.triggered.connect(self.zoom_in)
        self.toolbar.addAction(zoom_in_action)

        # Add zoom percentage label
        self.zoom_label = QLabel(f"{int(self.zoom_factor * 100)}%")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.toolbar.addWidget(self.zoom_label)

        # Add zoom out action
        zoom_out_icon = QIcon('icons/magnify-minus-outline.svg')
        zoom_out_action = QAction(zoom_out_icon, 'Zoom Out', self)
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.triggered.connect(self.zoom_out)
        self.toolbar.addAction(zoom_out_action)

    def set_crop_size(self):
        # Open a dialog to set the crop size
        crop_size, ok = QInputDialog.getInt(self, "Crop Size", "Enter the crop size (in pixels):",
                                            value=self.crop_size, min=10, max=1000)
        if ok:
            self.crop_size = crop_size
            self.image_label.set_crop_size(crop_size)  # Update crop size in image label

    def change_destination_folder(self):
        # Open a dialog to select a new destination folder
        new_folder = QFileDialog.getExistingDirectory(self, "Select the destination folder for crops")
        if new_folder:
            self.crop_folder = new_folder
            QMessageBox.information(self, "Folder Updated",
                                    f"Destination folder updated to:\n{self.crop_folder}")
        else:
            QMessageBox.warning(self, "Operation Cancelled", "The destination folder was not changed.")

    def zoom_in(self):
        self.zoom_factor *= 1.2  # Increase zoom factor by 20%
        self.image_label.set_zoom_factor(self.zoom_factor)
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
        self.display_image()

    def zoom_out(self):
        self.zoom_factor /= 1.2  # Decrease zoom factor by 20%
        self.image_label.set_zoom_factor(self.zoom_factor)
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
        self.display_image()

    def open_image(self):
        # Allow the user to select the destination folder
        self.crop_folder = QFileDialog.getExistingDirectory(self, "Select the destination folder for crops")
        if not self.crop_folder:
            QMessageBox.critical(self, "Error", "No folder selected for saving crops.")
            return

        options = QFileDialog.Options()
        self.image_path, _ = QFileDialog.getOpenFileName(self, "Select an image", "",
                                                         "All Files (*);;Image Files (*.png;*.jpg;*.jpeg;*.bmp)",
                                                         options=options)

        if self.image_path:
            # Get image size without loading it entirely into memory
            self.image_size = self.get_image_size(self.image_path)
            if self.image_size is None:
                QMessageBox.critical(self, "Error", "Unable to open the selected image.")
                return

            # Reset offsets and zoom factor
            self.x_offset = 0
            self.y_offset = 0
            self.zoom_factor = 1.0
            self.image_label.set_zoom_factor(self.zoom_factor)
            self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
            self.display_image()
            self.setFocus()  # Ensure main window captures focus

            # Add to recent files
            self.add_to_recent_files(self.image_path)

    def open_recent_file(self, image_path):
        self.image_path = image_path

        # Allow the user to select the destination folder
        self.crop_folder = QFileDialog.getExistingDirectory(self, "Select the destination folder for crops")
        if not self.crop_folder:
            QMessageBox.critical(self, "Error", "No folder selected for saving crops.")
            return

        # Get image size without loading it entirely into memory
        self.image_size = self.get_image_size(self.image_path)
        if self.image_size is None:
            QMessageBox.critical(self, "Error", "Unable to open the selected image.")
            return

        # Reset offsets and zoom factor
        self.x_offset = 0
        self.y_offset = 0
        self.zoom_factor = 1.0
        self.image_label.set_zoom_factor(self.zoom_factor)
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
        self.display_image()
        self.setFocus()  # Ensure main window captures focus

        # Add to recent files
        self.add_to_recent_files(self.image_path)

    def add_to_recent_files(self, image_path):
        from datetime import datetime

        # Remove if already exists
        self.recent_files = [f for f in self.recent_files if f['path'] != image_path]

        # Add the new file at the beginning
        file_info = {
            'path': image_path,
            'open_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'save_time': 'N/A'  # Update when saving
        }
        self.recent_files.insert(0, file_info)

        # Keep only the last 5 items
        self.recent_files = self.recent_files[:5]

        # Save in settings
        self.settings.setValue('recent_files', self.recent_files)

    def get_image_size(self, image_path):
        # Use OpenCV to get image size without loading it completely
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is not None:
            return img.shape[:2]  # Returns (height, width)
        return None

    def display_image(self):
        if self.image_path is None:
            return

        # Get the size of the image_label in pixels
        label_width = self.image_label.width()
        label_height = self.image_label.height()

        # Calculate the size of the area to load from the image, considering the zoom factor
        display_width = int(label_width / self.zoom_factor)
        display_height = int(label_height / self.zoom_factor)

        # Ensure the display area does not exceed the image size
        if display_width > self.image_size[1]:
            display_width = self.image_size[1]
        if display_height > self.image_size[0]:
            display_height = self.image_size[0]

        # Adjust offsets if necessary
        self.x_offset = max(0, min(self.x_offset, self.image_size[1] - display_width))
        self.y_offset = max(0, min(self.y_offset, self.image_size[0] - display_height))

        # Load the required area from the image
        img = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
        img = img[self.y_offset:self.y_offset+display_height, self.x_offset:self.x_offset+display_width]

        if img is None or img.size == 0:
            return

        # Convert image to RGB format
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Convert the image to a QImage
        height, width, channel = img.shape
        bytes_per_line = 3 * width
        qimg = QImage(img.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Scale the QImage according to the zoom factor
        pixmap = QPixmap.fromImage(qimg)
        scaled_pixmap = pixmap.scaled(label_width, label_height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        # Set the pixmap to the image_label
        self.image_label.setPixmap(scaled_pixmap)
        self.update_mini_map()

    def update_mini_map(self):
        if self.image_path is None:
            return

        # Load the full image and create a thumbnail for the mini-map
        img = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
        thumb = cv2.resize(img, (300, 300))
        thumb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)

        qthumb = QImage(thumb.data, thumb.shape[1], thumb.shape[0], thumb.strides[0], QImage.Format_RGB888)
        pixmap_thumb = QPixmap.fromImage(qthumb)
        self.scene.clear()
        self.scene.addPixmap(pixmap_thumb)

        scale_w = 300 / self.image_size[1]
        scale_h = 300 / self.image_size[0]

        # Calculate the size of the display area in terms of the original image
        label_width = self.image_label.width()
        label_height = self.image_label.height()
        display_width = int(label_width / self.zoom_factor)
        display_height = int(label_height / self.zoom_factor)

        rect_w = display_width * scale_w
        rect_h = display_height * scale_h

        # Add a rectangle to show the visible portion
        self.rect_cursor = self.scene.addRect(self.x_offset * scale_w, self.y_offset * scale_h, rect_w, rect_h,
                                              pen=QPen(QColor("red")))

    def handle_mini_map_click(self, event):
        if self.image_path is None:
            return

        # Calculate the position in the main image based on the click on the mini-map
        pos = event.pos()
        map_x = pos.x()
        map_y = pos.y()

        # Convert mini-map coordinates to real image coordinates
        scale_w = self.image_size[1] / 300
        scale_h = self.image_size[0] / 300

        # Calculate the size of the display area in terms of the original image
        label_width = self.image_label.width()
        label_height = self.image_label.height()
        display_width = int(label_width / self.zoom_factor)
        display_height = int(label_height / self.zoom_factor)

        self.x_offset = int(map_x * scale_w) - display_width // 2
        self.y_offset = int(map_y * scale_h) - display_height // 2

        # Keep the offsets within the image boundaries
        self.x_offset = max(0, min(self.x_offset, self.image_size[1] - display_width))
        self.y_offset = max(0, min(self.y_offset, self.image_size[0] - display_height))

        self.display_image()

    def keyPressEvent(self, event):
        """Handles movement with arrow keys and Ctrl + arrow keys"""
        label_width = self.image_label.width()
        label_height = self.image_label.height()
        display_width = int(label_width / self.zoom_factor)
        display_height = int(label_height / self.zoom_factor)

        step = int(100 / self.zoom_factor)
        if event.modifiers() & Qt.ControlModifier:
            step = int(600 / self.zoom_factor)  # Increase step size if Ctrl is pressed

        if event.key() == Qt.Key_Left:
            self.x_offset = max(0, self.x_offset - step)
        elif event.key() == Qt.Key_Right:
            self.x_offset = min(self.image_size[1] - display_width, self.x_offset + step)
        elif event.key() == Qt.Key_Up:
            self.y_offset = max(0, self.y_offset - step)
        elif event.key() == Qt.Key_Down:
            self.y_offset = min(self.image_size[0] - display_height, self.y_offset + step)

        self.display_image()  # Update the image display after moving

    def handle_mouse_click(self, x, y):
        if self.image_label.pixmap():
            # Calculate the real position of the click relative to the full image
            pixmap_size = self.image_label.pixmap().size()
            label_size = self.image_label.size()
            scale_x = pixmap_size.width() / label_size.width()
            scale_y = pixmap_size.height() / label_size.height()

            x_real = self.x_offset + int(x * scale_x)
            y_real = self.y_offset + int(y * scale_y)
            self.crop_at_position(x_real, y_real)

    def crop_at_position(self, x, y):
        if self.crop_folder is None:
            QMessageBox.warning(self, "Error", "Destination folder not set.")
            return

        crop_half_size = self.crop_size // 2
        x_start = max(0, x - crop_half_size)
        y_start = max(0, y - crop_half_size)
        x_end = min(self.image_size[1], x + crop_half_size)
        y_end = min(self.image_size[0], y + crop_half_size)

        # Ensure the crop size is correct
        crop_width = x_end - x_start
        crop_height = y_end - y_start

        # Load the crop area
        img = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
        crop = img[y_start:y_end, x_start:x_end]

        if crop is None or crop.size == 0:
            return

        base_name = os.path.basename(self.image_path)
        name, ext = os.path.splitext(base_name)

        crop_name = f"{name}_crop_{x}_{y}.png"
        crop_path = os.path.join(self.crop_folder, crop_name)

        cv2.imwrite(crop_path, crop)

        # Update save time in recent files
        from datetime import datetime
        for file_info in self.recent_files:
            if file_info['path'] == self.image_path:
                file_info['save_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                break
        # Save in settings
        self.settings.setValue('recent_files', self.recent_files)

        QMessageBox.information(self, "Crop", f"Crop saved as: {crop_name}")

    def resizeEvent(self, event):
        """Adjusts the image display when the window is resized"""
        self.display_image()
        super().resizeEvent(event)


class StartupDialog(QDialog):
    def __init__(self, recent_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ImageCropper - Start')
        self.setWindowIcon(QIcon('logoImageCropper.jfif'))
        self.recent_files = recent_files
        self.selected_file = None

        # Set up the layout
        layout = QVBoxLayout()

        # Add the logo at the top
        logo_pixmap = QPixmap('logoImageCropper.jfif')
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setPixmap(logo_pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(logo_label)

        # Add "Open a new image" button in the center
        open_new_button = QPushButton('Open a new image')
        open_new_button.setIcon(QIcon('icons/open.svg'))  # Use SVG icon
        open_new_button.setIconSize(QSize(32, 32))
        open_new_button.clicked.connect(self.open_new_image)
        layout.addWidget(open_new_button)

        # If there are recent files, show them in a list
        if self.recent_files:
            recent_label = QLabel('Recent images:')
            layout.addWidget(recent_label)

            self.list_widget = QListWidget()
            for file_info in self.recent_files:
                # file_info is a dictionary with 'path', 'open_time', 'save_time'
                item = QListWidgetItem(QIcon('icons/image-outline.svg'),
                                       os.path.basename(file_info['path']))  # SVG icon
                item.setData(Qt.UserRole, file_info['path'])
                item.setToolTip(
                    f"Opened: {file_info['open_time']}\nLast save: {file_info['save_time']}")
                self.list_widget.addItem(item)
            self.list_widget.itemClicked.connect(self.select_recent_file)
            layout.addWidget(self.list_widget)
        else:
            no_recent_label = QLabel('No recent images.')
            layout.addWidget(no_recent_label)

        self.setLayout(layout)

    def open_new_image(self):
        self.selected_file = 'new'
        self.accept()

    def select_recent_file(self, item):
        self.selected_file = item.data(Qt.UserRole)
        self.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Process events
    app.processEvents()

    # Initialize settings to get recent files
    settings = QSettings('YourCompany', 'ImageCropper')
    recent_files = settings.value('recent_files', [], type=list)

    # Create the main application window but do not show it yet
    mainWin = ImageCropper()
    mainWin.hide()

    # Show the startup dialog if there are recent files
    if recent_files:
        startup_dialog = StartupDialog(recent_files)
        if startup_dialog.exec_() == QDialog.Accepted:
            if startup_dialog.selected_file == 'new':
                # Open a new image
                mainWin.show()
                mainWin.open_image()
            else:
                # Open recent image
                mainWin.show()
                mainWin.open_recent_file(startup_dialog.selected_file)
        else:
            sys.exit()  # User cancelled, exit the application
    else:
        # No recent files, proceed to open a new image
        mainWin.show()
        mainWin.open_image()

    sys.exit(app.exec_())
