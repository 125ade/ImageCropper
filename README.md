
<div align="center">
  <img src="logoImageCropper.jfif" alt="ImageCropper" width="200" height="200"/>
</div>

<h1 align="center">ImageCropper</h1>

> [!WARNING]\
> Development version – more features coming soon!

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15.2-green.svg)](https://pypi.org/project/PyQt5/)
[![Version](https://img.shields.io/badge/version-dev-orange.svg)](https://github.com/your-repo/ImageCropper)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20macOS%20%7C%20linux-lightgrey.svg)](https://github.com/your-repo/ImageCropper)

---

## 📷 Introduction
**ImageCropper** is an interactive image cropping tool built with Python and PyQt5. This tool allows you to open large images, select specific areas to crop, and save them efficiently to your local storage. It's designed to handle large images efficiently, displaying blocks of the image without consuming excessive memory.



---

## 🚀 Features
- **Interactive Image Display**: Visualize large images and navigate through them seamlessly.
- **Mouse & Keyboard Controls**: Crop and move around the image using your mouse and keyboard arrows.
- **Mini-Map**: Preview the entire image and quickly jump to specific areas using the mini-map.
- **Configurable Crop Sizes**: Set custom crop sizes to capture the perfect image segment.
- **Efficient Memory Usage**: Loads only parts of the image that are visible, ensuring smooth performance.
- **Save Cropped Areas**: Save selected areas to your desired folder in real time.
- **And more are coming soon!**
---

## 🔧 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-repo/ImageCropper.git
   cd ImageCropper
   ```

2. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   > **Note**: The main dependencies are PyQt5, OpenCV, and NumPy.

3. **Run ImageCropper**:
   ```bash
   python ImageCropper.py
   ```

---

## 🎨 Usage
1. Click **"Open Image"** to select an image file.
2. Adjust the crop size using the dialog box (default is 100x100 pixels).
3. Select a destination folder for the cropped images.
4. Move around the image using the arrow keys or mini-map:
   - **Arrows** to navigate left/right/up/down.
   - **Ctrl + Arrows** to move in larger steps.
5. Click on the image to crop and save the selected portion.

---

## 📚 Shortcuts & Controls

| Action                              | Shortcut / Control     |
|--------------------------------------|------------------------|
| Open Image                           | `Open Image` button    |
| Move Left                            | `Left Arrow`           |
| Move Right                           | `Right Arrow`          |
| Move Up                              | `Up Arrow`             |
| Move Down                            | `Down Arrow`           |
| Move Faster                          | `Ctrl + Arrow Keys`    |
| Click to Crop                        | `Left Mouse Button`    |
| Adjust Crop Size                     | `Crop Size` dialog box |

---

## 📂 Project Structure


---

## 🔮 Future Enhancements
- **Advanced Editing**: Include image adjustments like brightness, contrast, and filters.
- **Support for More File Formats**: Add support for additional image file types.
- **Computer Vision Features**: Implement object detection and image segmentation.
---

## 📜 License
This project is licensed under the **MIT License**. See the [LICENSE](https://opensource.org/licenses/MIT) file for details.

