import sys
import os
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, \
    QPushButton, QGraphicsView, QGraphicsScene, QMessageBox, QInputDialog, QToolBar, QAction, QDialog, QListWidget, \
    QListWidgetItem, QSizePolicy, QToolBox, QTextEdit
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
        # Transformation parameters
        self.scale_x = None
        self.scale_y = None
        self.x_offset_label = None
        self.y_offset_label = None
        self.x_offset_image = None
        self.y_offset_image = None

    def set_crop_size(self, size):
        self.crop_size = size

    def set_zoom_factor(self, zoom):
        self.zoom_factor = zoom
        self.update()

    def set_transformation_params(self, scale_x, scale_y, x_offset_label, y_offset_label, x_offset_image, y_offset_image):
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.x_offset_label = x_offset_label
        self.y_offset_label = y_offset_label
        self.x_offset_image = x_offset_image
        self.y_offset_image = y_offset_image

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
        if self.mouse_pos and self.pixmap() and self.scale_x and self.scale_y:
            painter = QPainter(self)
            painter.setPen(QPen(QColor("yellow"), 2, Qt.SolidLine))
            # todo fix problem with crop size and zoom

            label_x = self.mouse_pos.x()
            label_y = self.mouse_pos.y()

            # Adjust for label offsets
            label_x_adj = label_x - self.x_offset_label
            label_y_adj = label_y - self.y_offset_label

            # Check if the mouse is within the pixmap area
            pixmap_width = self.pixmap().width()
            pixmap_height = self.pixmap().height()
            if 0 <= label_x_adj <= pixmap_width and 0 <= label_y_adj <= pixmap_height:
                # Map mouse position to image coordinates
                image_x = label_x_adj / self.scale_x + self.x_offset_image
                image_y = label_y_adj / self.scale_y + self.y_offset_image

                # Calculate crop rectangle in image coordinates
                crop_half_size = self.crop_size / 2
                x_start = image_x - crop_half_size
                y_start = image_y - crop_half_size
                x_end = image_x + crop_half_size
                y_end = image_y + crop_half_size

                # Map crop rectangle to label coordinates
                label_x_start = (x_start - self.x_offset_image) * self.scale_x + self.x_offset_label
                label_y_start = (y_start - self.y_offset_image) * self.scale_y + self.y_offset_label
                label_x_end = (x_end - self.x_offset_image) * self.scale_x + self.x_offset_label
                label_y_end = (y_end - self.y_offset_image) * self.scale_y + self.y_offset_label

                rect = QRectF(label_x_start, label_y_start, label_x_end - label_x_start, label_y_end - label_y_start)
                painter.drawRect(rect)

                # Draw the crop size inside the yellow square
                painter.drawText(rect, Qt.AlignRight, str(self.crop_size)+"px ")

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
        self.full_image = None  # Stores the full image

        # Transformation parameters
        self.scale_x = None
        self.scale_y = None
        self.x_offset_label = None
        self.y_offset_label = None
        self.x_offset_image = None
        self.y_offset_image = None

        # Filter settings
        self.grayscale_filter = False  # Initialize the grayscale filter flag to False

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
        open_icon = QIcon('icons/image-plus-outline.svg')  # Use SVG icon for opening
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

        # Add filter action to the toolbar
        filter_icon = QIcon('icons/filter-menu-outline.svg')  # Use the filter icon
        self.toolbar_filter_action = QAction(filter_icon, 'Apply Filters', self)
        self.toolbar_filter_action.setShortcut('Ctrl+F')
        self.toolbar_filter_action.triggered.connect(self.open_filter_dialog)
        self.toolbar.addAction(self.toolbar_filter_action)

        # Add information action to the rightmost position
        self.toolbar.addSeparator()
        info_icon = QIcon('icons/information-outline.svg')
        info_action = QAction(info_icon, 'Information', self)
        info_action.triggered.connect(self.show_information)
        self.toolbar.addAction(info_action)

    def show_information(self):
        # Create and display the information dialog
        info_dialog = QDialog(self)
        info_dialog.setWindowTitle('Information')
        info_dialog.setWindowIcon(QIcon('icons/information-outline.svg'))
        info_dialog.resize(600, 400)

        layout = QVBoxLayout(info_dialog)

        # Use QToolBox for collapsible sections
        toolbox = QToolBox()
        layout.addWidget(toolbox)

        # Features section
        features_text = """
        <ul>
            <li>Open images and navigate through them.</li>
            <li>Crop specific areas of images by clicking on them.</li>
            <li>Zoom in and out to focus on details.</li>
            <li>View a mini-map of the entire image for easy navigation.</li>
            <li>Save cropped areas to a specified folder.</li>
        </ul>
        """
        features_widget = QWidget()
        features_layout = QVBoxLayout()
        features_label = QLabel(features_text)
        features_label.setWordWrap(True)
        features_layout.addWidget(features_label)
        features_widget.setLayout(features_layout)
        toolbox.addItem(features_widget, 'Features')

        # Shortcuts section
        shortcuts_text = """
        <ul>
            <li><b>Ctrl+O</b>: Open Image</li>
            <li><b>Ctrl+Shift+C</b>: Set Crop Size</li>
            <li><b>Ctrl+D</b>: Change Destination Folder</li>
            <li><b>Ctrl++</b>: Zoom In</li>
            <li><b>Ctrl+-</b>: Zoom Out</li>
            <li><b>Arrow Keys</b>: Move Image View</li>
            <li><b>Ctrl + Arrow Keys</b>: Move Image View Faster</li>
        </ul>
        """
        shortcuts_widget = QWidget()
        shortcuts_layout = QVBoxLayout()
        shortcuts_label = QLabel(shortcuts_text)
        shortcuts_label.setWordWrap(True)
        shortcuts_layout.addWidget(shortcuts_label)
        shortcuts_widget.setLayout(shortcuts_layout)
        toolbox.addItem(shortcuts_widget, 'Shortcuts')

        # Tools section
        tools_text = """
        <ul>
            <li><b>Open Image</b>: Load a new image to work with.</li>
            <li><b>Set Crop Size</b>: Define the size of the area to crop.</li>
            <li><b>Change Destination Folder</b>: Set where cropped images are saved.</li>
            <li><b>Zoom In/Out</b>: Adjust the zoom level of the image view.</li>
            <li><b>Information</b>: View application commands and functionalities.</li>
        </ul>
        """
        tools_widget = QWidget()
        tools_layout = QVBoxLayout()
        tools_label = QLabel(tools_text)
        tools_label.setWordWrap(True)
        tools_layout.addWidget(tools_label)
        tools_widget.setLayout(tools_layout)
        toolbox.addItem(tools_widget, 'Tools')

        info_dialog.exec_()

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

    def open_filter_dialog(self):
        filter_dialog = FilterDialog(self, grayscale_selected=self.grayscale_filter)
        if filter_dialog.exec_() == QDialog.Accepted:
            # Update the filter status based on the selection
            self.grayscale_filter = filter_dialog.grayscale_selected

            # Change the toolbar icon color to green if any filter is active
            if self.grayscale_filter:
                self.toolbar_filter_action.setIcon(QIcon('icons/filter-check-outline.svg'))
            else:
                self.toolbar_filter_action.setIcon(QIcon('icons/filter-menu-outline.svg'))

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
            # Load the full image once
            self.full_image = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
            if self.full_image is None:
                QMessageBox.critical(self, "Error", "Unable to open the selected image.")
                return

            self.image_size = self.full_image.shape[:2]  # (height, width)

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

        # Find the crop_folder associated with this image
        previous_crop_folder = None
        for file_info in self.recent_files:
            if file_info['path'] == image_path:
                previous_crop_folder = file_info.get('crop_folder')
                break

        if previous_crop_folder:
            # Ask the user whether to use the previous crop folder or select a new one
            reply = QMessageBox.question(self, 'Select Crop Folder',
                                         f"Do you want to use the previous destination folder for crops?\n{previous_crop_folder}",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.crop_folder = previous_crop_folder
            else:
                # Allow the user to select the destination folder
                self.crop_folder = QFileDialog.getExistingDirectory(self, "Select the destination folder for crops")
                if not self.crop_folder:
                    QMessageBox.critical(self, "Error", "No folder selected for saving crops.")
                    return
        else:
            # No previous crop folder, ask the user to select one
            self.crop_folder = QFileDialog.getExistingDirectory(self, "Select the destination folder for crops")
            if not self.crop_folder:
                QMessageBox.critical(self, "Error", "No folder selected for saving crops.")
                return

        # Load the full image once
        self.full_image = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
        if self.full_image is None:
            QMessageBox.critical(self, "Error", "Unable to open the selected image.")
            return

        self.image_size = self.full_image.shape[:2]  # (height, width)

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
            'save_time': 'N/A',  # Update when saving
            'crop_folder': self.crop_folder  # Store the crop folder used
        }
        self.recent_files.insert(0, file_info)

        # Keep only the last 5 items
        self.recent_files = self.recent_files[:5]

        # Save in settings
        self.settings.setValue('recent_files', self.recent_files)

    def display_image(self):
        if self.image_path is None or self.full_image is None:
            return

        # Get the size of the image_label in pixels
        label_width = self.image_label.width()
        label_height = self.image_label.height()

        # Calculate the size of the area to load from the image, considering the zoom factor
        display_width = int(label_width / self.zoom_factor)
        display_height = int(label_height / self.zoom_factor)

        # Ensure the display area does not exceed the image size
        display_width = min(display_width, self.image_size[1])
        display_height = min(display_height, self.image_size[0])

        # Adjust offsets if necessary
        self.x_offset = max(0, min(self.x_offset, self.image_size[1] - display_width))
        self.y_offset = max(0, min(self.y_offset, self.image_size[0] - display_height))

        # Extract the required area from the image
        img = self.full_image[self.y_offset:self.y_offset + display_height,
                              self.x_offset:self.x_offset + display_width]

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
        scaled_pixmap = pixmap.scaled(label_width, label_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Store the displayed pixmap size and offsets
        displayed_pixmap_width = scaled_pixmap.width()
        displayed_pixmap_height = scaled_pixmap.height()

        # Calculate margins (offsets)
        x_offset_label = (label_width - displayed_pixmap_width) / 2
        y_offset_label = (label_height - displayed_pixmap_height) / 2

        # Compute scale factors from image coordinates to label coordinates
        scale_x = displayed_pixmap_width / display_width
        scale_y = displayed_pixmap_height / display_height

        # Store transformation parameters
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.x_offset_label = x_offset_label
        self.y_offset_label = y_offset_label
        self.x_offset_image = self.x_offset
        self.y_offset_image = self.y_offset

        # Set transformation parameters in image label
        self.image_label.set_transformation_params(scale_x, scale_y, x_offset_label, y_offset_label,
                                                   self.x_offset_image, self.y_offset_image)

        # Set the pixmap to the image_label
        self.image_label.setPixmap(scaled_pixmap)
        self.update_mini_map()

    def update_mini_map(self):
        if self.image_path is None or self.full_image is None:
            return

        # Create a thumbnail for the mini-map
        thumb = cv2.resize(self.full_image, (300, 300))
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
        if self.image_label.pixmap() and self.scale_x and self.scale_y:
            # Adjust for label offsets
            label_x_adj = x - self.x_offset_label
            label_y_adj = y - self.y_offset_label

            # Check if the mouse is within the pixmap area
            pixmap_width = self.image_label.pixmap().width()
            pixmap_height = self.image_label.pixmap().height()
            if 0 <= label_x_adj <= pixmap_width and 0 <= label_y_adj <= pixmap_height:
                # Map mouse position to image coordinates
                image_x = label_x_adj / self.scale_x + self.x_offset_image
                image_y = label_y_adj / self.scale_y + self.y_offset_image

                # Crop at the calculated image coordinates
                self.crop_at_position(int(image_x), int(image_y))

    def crop_at_position(self, x, y):
        if self.crop_folder is None:
            QMessageBox.warning(self, "Error", "Destination folder not set.")
            return

        crop_half_size = self.crop_size // 2
        x_start = max(0, int(x - crop_half_size))
        y_start = max(0, int(y - crop_half_size))
        x_end = min(self.image_size[1], int(x + crop_half_size))
        y_end = min(self.image_size[0], int(y + crop_half_size))

        # Ensure the crop size is correct
        crop_width = x_end - x_start
        crop_height = y_end - y_start

        # Extract the crop area from the stored full image
        crop = self.full_image[y_start:y_end, x_start:x_end]

        if crop is None or crop.size == 0:
            QMessageBox.warning(self, "Error", "Unable to extract the crop.")
            return

        # Apply grayscale filter if selected
        if self.grayscale_filter:
            crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)  # Convert to grayscale

        base_name = os.path.basename(self.image_path)
        name, ext = os.path.splitext(base_name)

        crop_name = f"{name}_crop_{x}_{y}.png"
        crop_path = os.path.join(self.crop_folder, crop_name)

        # Save the crop in BGR format
        cv2.imwrite(crop_path, crop)

        # Update save time and crop folder in recent files
        from datetime import datetime
        for file_info in self.recent_files:
            if file_info['path'] == self.image_path:
                file_info['save_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                file_info['crop_folder'] = self.crop_folder  # Update crop_folder
                break
        # Save in settings
        self.settings.setValue('recent_files', self.recent_files)

        QMessageBox.information(self, "Crop", f"Crop saved as: {crop_name}")

    def resizeEvent(self, event):
        """Adjusts the image display when the window is resized"""
        self.display_image()
        super().resizeEvent(event)


class FilterDialog(QDialog):
    def __init__(self, parent=None, grayscale_selected=False):
        super().__init__(parent)
        self.setWindowTitle("Select Filters")
        self.setWindowIcon(QIcon('icons/filter-menu-outline.svg'))
        self.setFixedSize(300, 400)

        # Layout for the filters
        layout = QVBoxLayout(self)

        # Add the grayscale filter option
        self.grayscale_selected = grayscale_selected  # Track if the filter is selected

        self.grayscale_button = QPushButton()
        self.grayscale_button.setIcon(QIcon('icons/filter-outline.svg'))
        self.grayscale_button.setIconSize(QSize(32, 32))
        self.grayscale_button.setToolTip('Grayscale')
        self.grayscale_button.setStyleSheet("text-align: left; color: black; font-size: 16px;")
        self.grayscale_button.setText(" Grayscale")  # Name of the filter
        self.grayscale_button.setCheckable(True)  # Allow it to be checked
        self.grayscale_button.clicked.connect(self.toggle_grayscale_filter)

        # If grayscale is already selected, show the green checkmark and change the color to green
        if self.grayscale_selected:
            self.grayscale_button.setIcon(QIcon('icons/filter-check-outline.svg'))
            self.grayscale_button.setStyleSheet("text-align: left; color: green; font-size: 16px;")

        layout.addWidget(self.grayscale_button)

        # Add a button to confirm selection
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

    def toggle_grayscale_filter(self):
        """Toggle the grayscale filter selection."""
        self.grayscale_selected = not self.grayscale_selected
        if self.grayscale_selected:
            self.grayscale_button.setIcon(QIcon('icons/filter-check-outline.svg'))  # Set the selected icon
            self.grayscale_button.setStyleSheet("text-align: left; color: green; font-size: 16px;")  # Change color
        else:
            self.grayscale_button.setIcon(QIcon('icons/filter-outline.svg'))  # Set the unselected icon
            self.grayscale_button.setStyleSheet("text-align: left; color: black; font-size: 16px;")  # Reset color


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
        open_new_button.setIcon(QIcon('icons/image-plus-outline.svg'))
        open_new_button.clicked.connect(self.open_new_image)
        layout.addWidget(open_new_button)

        # If there are recent files, show them in a list
        if self.recent_files:
            recent_label = QLabel()
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

            # Add the "Clear History" button
            clear_history_button = QPushButton('Clear History')
            clear_history_button.setIcon(QIcon('icons/delete-sweep-outline.svg'))
            clear_history_button.clicked.connect(self.clear_history)
            layout.addWidget(clear_history_button)
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

    def clear_history(self):
        reply = QMessageBox.question(self, 'Clear History',
                                     'Are you sure you want to clear the recent images history?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.recent_files.clear()
            # Update the settings to clear the stored recent files
            settings = QSettings('YourCompany', 'ImageCropper')
            settings.setValue('recent_files', self.recent_files)
            # Remove the list widget from the layout
            self.list_widget.clear()
            # Optionally, hide the list widget and the clear history button
            self.list_widget.hide()
            self.sender().hide()  # Hide the button that called this method
            QMessageBox.information(self, 'History Cleared', 'Recent images history has been cleared.')


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
                mainWin.showMaximized()
                mainWin.open_image()
            else:
                # Open recent image
                mainWin.showMaximized()
                mainWin.open_recent_file(startup_dialog.selected_file)
        else:
            sys.exit()  # User cancelled, exit the application
    else:
        # No recent files, proceed to open a new image
        mainWin.showMaximized()
        mainWin.open_image()

    sys.exit(app.exec_())
