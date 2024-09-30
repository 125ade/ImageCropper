import sys
import os
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, \
    QPushButton, QGraphicsView, QGraphicsScene, QMessageBox, QInputDialog, QSplashScreen, QToolBar, QAction, QStyle, \
    QDialog, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QSettings, QSize
from PyQt5.QtGui import QImage, QPixmap, QPen, QColor, QPainter, QIcon


class ImageLabel(QLabel):
    mouse_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.mouse_pos = None
        self.crop_size = 100

    def set_crop_size(self, size):
        self.crop_size = size

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.pos()
        self.update()  # Chiama paintEvent per ridisegnare il rettangolo giallo

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Emette il segnale con le coordinate del click
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
        self.setWindowIcon(QIcon('logoImageCropper.jfif'))

        # Imposta la dimensione iniziale della finestra
        self.setGeometry(100, 100, 800, 600)
        self.setFocusPolicy(Qt.StrongFocus)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Inizializza le impostazioni e i file recenti
        self.settings = QSettings('YourCompany', 'ImageCropper')
        self.recent_files = self.settings.value('recent_files', [], type=list)

        # Crea la barra degli strumenti
        self.toolbar = self.addToolBar('Main Toolbar')
        self.create_actions()

        # Crea il layout principale
        self.main_layout = QVBoxLayout(self.central_widget)

        # Crea il layout superiore per la mini-mappa
        self.top_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_layout)

        # Aggiungi la vista della mini-mappa al layout superiore
        self.map_view = QGraphicsView(self)
        self.map_view.setFixedSize(200, 200)
        self.top_layout.addWidget(self.map_view)

        self.scene = QGraphicsScene(self)
        self.map_view.setScene(self.scene)

        # Crea l'etichetta per visualizzare l'immagine
        self.image_label = ImageLabel(self)
        self.image_label.setFocusPolicy(Qt.ClickFocus)
        self.image_label.mouse_clicked.connect(self.handle_mouse_click)
        self.main_layout.addWidget(self.image_label)

        self.zoom_factor = 1.0
        self.image_path = None
        self.crop_size = 100  # Dimensione crop di default
        self.crop_folder = None  # Cartella per salvare i crop

        self.x_offset = 0
        self.y_offset = 0
        self.rect_cursor = None
        self.block_size = 800  # Dimensione iniziale del blocco
        self.image_size = None  # Dimensione dell'immagine completa
        self.current_block = None  # Memorizza il blocco dell'immagine attualmente visualizzato

        self.map_view.mousePressEvent = self.handle_mini_map_click

        self.update_image_label_size()
        # self.show()  # Mostreremo la finestra dopo il dialogo iniziale

    def create_actions(self):
        # Crea le azioni per la barra degli strumenti
        open_icon = QIcon('icons/file-edit-outline.svg')  # Utilizza l'icona SVG per l'apertura
        open_action = QAction(open_icon, 'Apri Immagine', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_image)
        self.toolbar.addAction(open_action)

    def resizeEvent(self, event):
        """Adatta la dimensione dell'etichetta dell'immagine e del blocco quando la finestra viene ridimensionata"""
        self.update_image_label_size()
        self.display_image()
        super().resizeEvent(event)

    def update_image_label_size(self):
        """Aggiorna la dimensione dell'etichetta dell'immagine in base alla dimensione corrente della finestra"""
        screen_width = self.width()
        available_width = screen_width - 220  # Considera 200px per la mini-mappa e i margini
        self.image_label.setFixedWidth(available_width - 20)  # Mantieni un margine di 10px su entrambi i lati

        # Calcola l'altezza in base al rapporto d'aspetto dell'immagine se caricata
        if self.image_size:
            aspect_ratio = self.image_size[1] / self.image_size[0]
            adjusted_height = int(
                (available_width - 20) / aspect_ratio)  # Calcola l'altezza basata sul rapporto d'aspetto
            available_height = self.height() - 250  # Altezza disponibile meno spazio per mini-mappa, pulsanti e margini
            self.image_label.setFixedHeight(
                min(adjusted_height, available_height - 20))  # Mantieni un margine di 10px in alto e in basso
        else:
            available_height = self.height() - 250  # Considera gli altri elementi
            self.image_label.setFixedHeight(available_height - 20)  # Se non c'è immagine caricata, imposta un'altezza di default

        # Aggiorna la dimensione del blocco in base alle dimensioni disponibili
        self.block_size = min(self.image_label.width(), self.image_label.height())

    def open_image(self):
        # Imposta la dimensione del crop tramite un dialogo
        crop_size, ok = QInputDialog.getInt(self, "Dimensione Crop", "Inserisci la dimensione del crop (in pixel):",
                                            value=100, min=10, max=1000)
        if ok:
            self.crop_size = crop_size
            self.image_label.set_crop_size(crop_size)  # Imposta la dimensione del crop nell'etichetta dell'immagine

        # Permetti all'utente di scegliere la cartella di destinazione
        self.crop_folder = QFileDialog.getExistingDirectory(self, "Seleziona la cartella di destinazione per i crop")
        if not self.crop_folder:
            QMessageBox.critical(self, "Errore", "Nessuna cartella selezionata per il salvataggio dei crop.")
            return

        options = QFileDialog.Options()
        self.image_path, _ = QFileDialog.getOpenFileName(self, "Seleziona un'immagine", "",
                                                         "Tutti i file (*);;File immagine (*.png;*.jpg;*.jpeg;*.bmp)",
                                                         options=options)

        if self.image_path:
            # Ottieni la dimensione dell'immagine senza caricarla interamente in memoria
            self.image_size = self.get_image_size(self.image_path)
            if self.image_size is None:
                QMessageBox.critical(self, "Errore", "Impossibile aprire l'immagine selezionata.")
                return

            # Reimposta gli offset
            self.x_offset = 0
            self.y_offset = 0
            self.display_image()
            self.setFocus()  # Assicura che la finestra principale catturi il focus

            # Aggiungi ai file recenti
            self.add_to_recent_files(self.image_path)

    def open_recent_file(self, image_path):
        self.image_path = image_path

        # Imposta la dimensione del crop tramite un dialogo
        crop_size, ok = QInputDialog.getInt(self, "Dimensione Crop", "Inserisci la dimensione del crop (in pixel):",
                                            value=100, min=10, max=1000)
        if ok:
            self.crop_size = crop_size
            self.image_label.set_crop_size(crop_size)  # Imposta la dimensione del crop nell'etichetta dell'immagine

        # Permetti all'utente di scegliere la cartella di destinazione
        self.crop_folder = QFileDialog.getExistingDirectory(self, "Seleziona la cartella di destinazione per i crop")
        if not self.crop_folder:
            QMessageBox.critical(self, "Errore", "Nessuna cartella selezionata per il salvataggio dei crop.")
            return

        # Ottieni la dimensione dell'immagine senza caricarla interamente in memoria
        self.image_size = self.get_image_size(self.image_path)
        if self.image_size is None:
            QMessageBox.critical(self, "Errore", "Impossibile aprire l'immagine selezionata.")
            return

        # Reimposta gli offset
        self.x_offset = 0
        self.y_offset = 0
        self.display_image()
        self.setFocus()  # Assicura che la finestra principale catturi il focus

        # Aggiungi ai file recenti
        self.add_to_recent_files(self.image_path)

    def add_to_recent_files(self, image_path):
        from datetime import datetime

        # Rimuovi se già esiste
        self.recent_files = [f for f in self.recent_files if f['path'] != image_path]

        # Aggiungi il nuovo file all'inizio
        file_info = {
            'path': image_path,
            'open_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'save_time': 'N/A'  # Aggiorna quando salvi
        }
        self.recent_files.insert(0, file_info)

        # Mantieni solo gli ultimi 5 elementi
        self.recent_files = self.recent_files[:5]

        # Salva nelle impostazioni
        self.settings.setValue('recent_files', self.recent_files)

    def get_image_size(self, image_path):
        # Usa OpenCV per ottenere la dimensione dell'immagine senza caricarla completamente
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is not None:
            return img.shape[:2]  # Restituisce (altezza, larghezza)
        return None

    def load_image_block(self, x_offset, y_offset, block_size):
        if not self.image_path:
            return None

        # Calcola l'area da caricare in base alla dimensione del blocco
        x_end = min(x_offset + block_size, self.image_size[1])
        y_end = min(y_offset + block_size, self.image_size[0])

        # Leggi solo la porzione necessaria dell'immagine usando OpenCV
        img = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
        img = img[y_offset:y_end, x_offset:x_end]

        if img is not None:
            # Converti da BGR a RGB per PyQt5
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return None

    def display_image(self):
        # Determina quanti blocchi caricare in base alla larghezza disponibile
        blocks_to_show = 1
        if self.image_label.width() >= 2 * self.block_size:
            blocks_to_show = 2

        # Carica il primo blocco
        block1 = self.load_image_block(self.x_offset, self.y_offset, self.block_size)
        combined_image = block1

        # Carica il secondo blocco se c'è spazio
        if blocks_to_show == 2:
            x_offset_2 = self.x_offset + self.block_size
            if x_offset_2 < self.image_size[1]:  # Assicura di non superare i limiti dell'immagine
                block2 = self.load_image_block(x_offset_2, self.y_offset, self.block_size)
                if block2 is not None:
                    combined_image = np.hstack((block1, block2))

        if combined_image is None or combined_image.size == 0:
            return

        # Converte l'immagine combinata in un formato visualizzabile da PyQt5
        height, width, channel = combined_image.shape
        bytes_per_line = 3 * width
        qimg = QImage(combined_image.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Visualizza l'immagine combinata sulla QLabel
        self.image_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio))
        self.update_mini_map(blocks_to_show)

    def update_mini_map(self, blocks_to_show):
        if self.image_path is None:
            return

        # Carica l'immagine completa come thumbnail per la mini-mappa
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

        # Aggiungi un rettangolo per mostrare la porzione visibile
        self.rect_cursor = self.scene.addRect(self.x_offset * scale_w, self.y_offset * scale_h, rect_w, rect_h,
                                              pen=QPen(QColor("red")))

    def handle_mini_map_click(self, event):
        # Calcola la posizione nell'immagine principale in base al click sulla mini-mappa
        pos = event.pos()
        map_x = pos.x()
        map_y = pos.y()

        # Converti le coordinate della mini-mappa in coordinate reali dell'immagine
        scale_w = self.image_size[1] / 200
        scale_h = self.image_size[0] / 200

        self.x_offset = int(map_x * scale_w) - self.block_size // 2
        self.y_offset = int(map_y * scale_h) - self.block_size // 2

        # Mantieni gli offset entro i limiti dell'immagine
        self.x_offset = max(0, min(self.x_offset, self.image_size[1] - self.block_size))
        self.y_offset = max(0, min(self.y_offset, self.image_size[0] - self.block_size))

        self.display_image()

    def keyPressEvent(self, event):
        """Gestisce i movimenti con le frecce e Ctrl + frecce"""
        step = 100
        if event.modifiers() & Qt.ControlModifier:
            step = 600  # Aumenta la dimensione del passo se Ctrl è premuto

        if event.key() == Qt.Key_Left:
            self.x_offset = max(0, self.x_offset - step)
        elif event.key() == Qt.Key_Right:
            self.x_offset = min(self.image_size[1] - self.block_size, self.x_offset + step)
        elif event.key() == Qt.Key_Up:
            self.y_offset = max(0, self.y_offset - step)
        elif event.key() == Qt.Key_Down:
            self.y_offset = min(self.image_size[0] - self.block_size, self.y_offset + step)

        self.display_image()  # Aggiorna la visualizzazione dell'immagine dopo il movimento

    def handle_mouse_click(self, x, y):
        # Calcola la posizione reale del click rispetto all'immagine completa
        x_real = self.x_offset + int(x / self.zoom_factor)
        y_real = self.y_offset + int(y / self.zoom_factor)
        self.crop_at_position(x_real, y_real)

    def crop_at_position(self, x, y):
        crop_half_size = self.crop_size // 2
        x_start = max(0, x - crop_half_size)
        y_start = max(0, y - crop_half_size)
        x_end = min(self.image_size[1], x + crop_half_size)
        y_end = min(self.image_size[0], y + crop_half_size)

        crop = self.load_image_block(x_start, y_start, self.crop_size)

        if crop is None or crop.size == 0:
            return

        base_name = os.path.basename(self.image_path)
        name, ext = os.path.splitext(base_name)

        crop_name = f"{name}_crop_{x}_{y}.png"
        crop_path = os.path.join(self.crop_folder, crop_name)

        cv2.imwrite(crop_path, cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))

        # Aggiorna l'orario di salvataggio nei file recenti
        from datetime import datetime
        for file_info in self.recent_files:
            if file_info['path'] == self.image_path:
                file_info['save_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                break
        # Salva nelle impostazioni
        self.settings.setValue('recent_files', self.recent_files)

        QMessageBox.information(self, "Crop", f"Crop salvato come: {crop_name}")


class StartupDialog(QDialog):
    def __init__(self, recent_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ImageCropper - Start')
        self.setWindowIcon(QIcon('logoImageCropper.jfif'))
        self.recent_files = recent_files
        self.selected_file = None

        # Imposta il layout
        layout = QVBoxLayout()

        # Aggiungi il logo in alto
        logo_pixmap = QPixmap('logoImageCropper.jfif')
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setPixmap(logo_pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(logo_label)

        # Aggiungi "Apri una nuova immagine" al centro come pulsante
        open_new_button = QPushButton('Apri una nuova immagine')
        open_new_button.setIcon(QIcon('icons/open.svg'))  # Utilizza l'icona SVG
        open_new_button.setIconSize(QSize(32, 32))
        open_new_button.clicked.connect(self.open_new_image)
        layout.addWidget(open_new_button)

        # Se ci sono file recenti, mostrali in una lista
        if self.recent_files:
            recent_label = QLabel('Immagini recenti:')
            layout.addWidget(recent_label)

            self.list_widget = QListWidget()
            for file_info in self.recent_files:
                # file_info è un dizionario con 'path', 'open_time', 'save_time'
                item = QListWidgetItem(QIcon('icons/image-outline.svg'), os.path.basename(file_info['path']))  # Icona SVG
                item.setData(Qt.UserRole, file_info['path'])
                item.setToolTip(f"Aperto: {file_info['open_time']}\nUltimo salvataggio: {file_info['save_time']}")
                self.list_widget.addItem(item)
            self.list_widget.itemClicked.connect(self.select_recent_file)
            layout.addWidget(self.list_widget)
        else:
            no_recent_label = QLabel('Nessuna immagine recente.')
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

    # # Crea e visualizza lo splash screen
    # splash_pix = QPixmap('logoImageCropper.jfif')
    #
    # # Ridimensiona l'immagine se supera 300x300 pixel
    # max_size = 300
    # screen_size = app.primaryScreen().size()
    # if splash_pix.width() > max_size or splash_pix.height() > max_size:
    #     splash_pix = splash_pix.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    # elif splash_pix.width() > screen_size.width() or splash_pix.height() > screen_size.height():
    #     splash_pix = splash_pix.scaled(screen_size.width(), screen_size.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    #
    # splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    # splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    # splash.show()
    #
    # # Centra lo splash screen sullo schermo
    # rect = splash.geometry()
    # center_point = app.primaryScreen().geometry().center()
    # rect.moveCenter(center_point)
    # splash.move(rect.topLeft())

    # Processa gli eventi
    app.processEvents()

    # Inizializza le impostazioni per ottenere i file recenti
    settings = QSettings('YourCompany', 'ImageCropper')
    recent_files = settings.value('recent_files', [], type=list)

    # Crea la finestra principale dell'applicazione ma non mostrarla ancora
    mainWin = ImageCropper()
    mainWin.hide()

    # Mostra il dialogo iniziale se ci sono file recenti
    if recent_files:
        startup_dialog = StartupDialog(recent_files)
        if startup_dialog.exec_() == QDialog.Accepted:
            if startup_dialog.selected_file == 'new':
                # Apri una nuova immagine
                mainWin.show()
                mainWin.open_image()
            else:
                # Apri immagine recente
                mainWin.show()
                mainWin.open_recent_file(startup_dialog.selected_file)
        else:
            sys.exit()  # L'utente ha annullato, esci dall'applicazione
    else:
        # Nessun file recente, procedi ad aprire una nuova immagine
        mainWin.show()
        mainWin.open_image()

    # splash.finish(mainWin)
    sys.exit(app.exec_())
