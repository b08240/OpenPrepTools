import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # PyMuPDF
from PIL import Image
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
                             QFileDialog, QProgressBar, QSpinBox, QHBoxLayout, QLineEdit,
                             QMessageBox, QTextEdit)


class PDFToLongImageApp(QWidget):
    VERSION = "v1.0.1"

    def __init__(self):
        super().__init__()
        self.pdf_files = []
        self.pdf_folders = []
        self.output_folder_path = ""
        self.temp_dir = tempfile.mkdtemp()

        # 设置应用程序图标和版本号
        self.setWindowIcon(QIcon('logo_6.ico'))
        self.setWindowTitle(f'PDF转长图程序 {self.VERSION} (By Hellohistory)')

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setGeometry(200, 200, 600, 500)

        layout = QVBoxLayout()

        # 显示已选择的PDF文件或文件夹路径
        self.pdf_label = QLabel('未选择PDF文件或文件夹', self)
        self.pdf_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.pdf_label)

        # 文件选择控件
        file_select_layout = QHBoxLayout()
        self.pdf_path_line_edit = QLineEdit(self)
        self.pdf_path_line_edit.setPlaceholderText("请选择或拖拽PDF文件/文件夹")
        file_select_layout.addWidget(self.pdf_path_line_edit)
        self.btn_select_pdf = QPushButton('选择PDF文件/文件夹', self)
        self.btn_select_pdf.clicked.connect(self.select_pdf_or_folder)
        file_select_layout.addWidget(self.btn_select_pdf)
        layout.addLayout(file_select_layout)

        # 图像缩放比例选择
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("图像清晰度等级(最高 5 级):", self))
        self.zoom_factor_spinbox = QSpinBox(self)
        self.zoom_factor_spinbox.setRange(1, 5)
        self.zoom_factor_spinbox.setValue(2)
        hbox.addWidget(self.zoom_factor_spinbox)
        layout.addLayout(hbox)

        # 图像张数选择
        hbox_images_per_long = QHBoxLayout()
        hbox_images_per_long.addWidget(QLabel("每张长图的图片数量:", self))
        self.images_per_long_spinbox = QSpinBox(self)
        self.images_per_long_spinbox.setRange(1, 100)
        self.images_per_long_spinbox.setValue(10)  # 默认值为10张图片拼接一张长图
        hbox_images_per_long.addWidget(self.images_per_long_spinbox)
        layout.addLayout(hbox_images_per_long)

        # 保存文件夹选择
        file_save_layout = QHBoxLayout()
        self.save_path_line_edit = QLineEdit(self)
        self.save_path_line_edit.setPlaceholderText("请选择保存文件夹")
        file_save_layout.addWidget(self.save_path_line_edit)
        self.btn_save_as = QPushButton('选择保存文件夹', self)
        self.btn_save_as.clicked.connect(self.select_save_folder)
        file_save_layout.addWidget(self.btn_save_as)
        layout.addLayout(file_save_layout)

        # 日志框
        self.log_text_edit = QTextEdit(self)
        self.log_text_edit.setReadOnly(True)
        layout.addWidget(self.log_text_edit)

        # 进度条和按钮
        self.progress_and_button_layout = QHBoxLayout()

        # 进度条
        self.progress = QProgressBar(self)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress_and_button_layout.addWidget(self.progress)

        # 开始转换按钮
        self.btn_start = QPushButton('开始转换', self)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.batch_convert_pdf_to_image)
        self.progress_and_button_layout.addWidget(self.btn_start)

        layout.addLayout(self.progress_and_button_layout)

        self.setLayout(layout)

        # 设置窗口接受拖拽
        self.setAcceptDrops(True)

        self.setStyleSheet("""
            QWidget {
                background-color: #f7f3e9;
                font-family: Arial;
            }
            QLabel {
                color: #4a4a4a;
                font-size: 14px;
            }
            QLineEdit, QSpinBox, QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                background-color: #ffffff;
                color: #4a4a4a;
            }
            QPushButton {
                background-color: #6bbf59;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #52934b;
            }
            QProgressBar {
                text-align: center;
                background-color: #e0e0e0;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #47a1a2;
                border-radius: 5px;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.handle_dropped_files(files)

    def handle_dropped_files(self, files):
        pdf_files = []
        pdf_folders = []

        for file in files:
            if os.path.isdir(file):
                for root, _, filenames in os.walk(file):
                    for filename in filenames:
                        if filename.endswith(".pdf"):
                            pdf_files.append(os.path.join(root, filename))
                pdf_folders.append(file)
            elif file.endswith(".pdf"):
                pdf_files.append(file)

        if pdf_files:
            self.pdf_files = pdf_files
            self.pdf_label.setText(f'已选择{len(pdf_files)}个PDF文件')
            self.pdf_path_line_edit.setText("; ".join(pdf_files))
            self.check_ready_to_start()
        elif pdf_folders:
            self.pdf_folders = pdf_folders
            self.pdf_label.setText(f'已选择{len(pdf_folders)}个文件夹')
            self.pdf_path_line_edit.setText("; ".join(pdf_folders))
            self.check_ready_to_start()

    def select_pdf_or_folder(self):
        options = QFileDialog.Options()
        pdf_path = QFileDialog.getExistingDirectory(self,
                                                    "选择PDF文件夹") if self.sender().text() == '选择PDF文件/文件夹' else None
        if pdf_path:
            self.pdf_label.setText(f'已选择文件夹: {os.path.basename(pdf_path)}')
            self.pdf_path_line_edit.setText(pdf_path)
            self.pdf_folders.append(pdf_path)
            self.check_ready_to_start()

    def select_save_folder(self):
        save_path = QFileDialog.getExistingDirectory(self, '选择保存文件夹')
        if save_path:
            self.save_path_line_edit.setText(save_path)
            self.output_folder_path = save_path
            self.check_ready_to_start()

    def check_ready_to_start(self):
        if self.pdf_path_line_edit.text() and self.save_path_line_edit.text():
            self.btn_start.setEnabled(True)

    def batch_convert_pdf_to_image(self):
        output_folder_path = self.save_path_line_edit.text()
        if not os.path.exists(output_folder_path):
            QMessageBox.warning(self, '错误', '所选的保存文件夹不存在！', QMessageBox.Ok)
            return

        pdf_files = self.pdf_files if self.pdf_files else []
        for folder in self.pdf_folders:
            for root, _, filenames in os.walk(folder):
                for filename in filenames:
                    if filename.endswith(".pdf"):
                        pdf_files.append(os.path.join(root, filename))

        if not pdf_files:
            QMessageBox.warning(self, '错误', '没有找到PDF文件！', QMessageBox.Ok)
            return

        zoom_factor = self.zoom_factor_spinbox.value()

        self.btn_start.setEnabled(False)
        self.log_text_edit.clear()

        # 启动后台线程进行批量PDF转长图
        self.thread = BatchConvertThread(pdf_files, output_folder_path, zoom_factor, self.temp_dir, self.images_per_long_spinbox.value())
        self.thread.update_progress.connect(self.progress.setValue)
        self.thread.log_message.connect(self.log_text_edit.append)
        self.thread.completed.connect(self.on_batch_conversion_completed)
        self.thread.start()

    def on_batch_conversion_completed(self, summary):
        if summary['failed']:
            QMessageBox.critical(self, '转换失败', f'部分文件转换失败：{summary["failed"]}', QMessageBox.Ok)
        else:
            QMessageBox.information(self, '转换完成', '批量PDF转换为长图成功！', QMessageBox.Ok)
        self.btn_start.setEnabled(True)

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.save_path_line_edit.setText(settings.get("save_path", ""))
                self.zoom_factor_spinbox.setValue(settings.get("zoom_factor", 2))
        except FileNotFoundError:
            pass

    def save_settings(self):
        settings = {
            "save_path": self.save_path_line_edit.text(),
            "zoom_factor": self.zoom_factor_spinbox.value(),
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()


def concatenate_images_vertically(image_paths, output_image_base_path, images_per_long):
    MAX_IMAGE_DIMENSION = 65500  # Pillow的最大支持尺寸

    total_images = len(image_paths)
    part = 0

    for i in range(0, total_images, images_per_long):
        part += 1
        current_images = image_paths[i:i + images_per_long]

        total_height = sum(Image.open(img).height for img in current_images)
        max_width = max(Image.open(img).width for img in current_images)

        # 如果总高度超过最大值，则分割处理
        if total_height > MAX_IMAGE_DIMENSION:
            current_part_images = []
            current_part_height = 0
            sub_part = 1

            for img_path in current_images:
                img_height = Image.open(img_path).height
                if current_part_height + img_height > MAX_IMAGE_DIMENSION:
                    # 保存当前分片
                    long_image = Image.new("RGB", (max_width, current_part_height))
                    y_offset = 0
                    for part_img in current_part_images:
                        img = Image.open(part_img)
                        long_image.paste(img, (0, y_offset))
                        y_offset += img.height
                    output_image_path = f"{output_image_base_path}_part{part}_sub{sub_part}.jpg"
                    long_image.save(output_image_path)
                    sub_part += 1
                    current_part_images.clear()
                    current_part_height = 0

                # 添加图片到当前分片
                current_part_images.append(img_path)
                current_part_height += img_height

            # 保存最后的分片
            if current_part_images:
                long_image = Image.new("RGB", (max_width, current_part_height))
                y_offset = 0
                for part_img in current_part_images:
                    img = Image.open(part_img)
                    long_image.paste(img, (0, y_offset))
                    y_offset += img.height
                output_image_path = f"{output_image_base_path}_part{part}_sub{sub_part}.jpg"
                long_image.save(output_image_path)

        else:
            # 正常处理
            long_image = Image.new("RGB", (max_width, total_height))

            y_offset = 0
            for img_path in current_images:
                img = Image.open(img_path)
                long_image.paste(img, (0, y_offset))
                y_offset += img.height

            output_image_path = f"{output_image_base_path}_part{part}.jpg"
            long_image.save(output_image_path)

        # 清理临时文件
        for img_path in current_images:
            os.remove(img_path)


def process_page(pdf_doc, page_num, zoom_matrix, temp_dir):
    try:
        page = pdf_doc.load_page(page_num)
        pix = page.get_pixmap(matrix=zoom_matrix)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        # 使用数字序列命名每个页面的图片，避免复杂命名
        image_path = os.path.join(temp_dir, f"{page_num + 1}.png")
        img.save(image_path, format='PNG')
        return image_path
    except Exception as e:
        return None, f"页面 {page_num} 处理失败: {e}"


def extract_images_from_pdf(pdf_path, zoom_factor, temp_dir, log_func):
    try:
        log_func(f"开始处理文件: {pdf_path}")
        pdf_doc = fitz.open(pdf_path)
        zoom_matrix = fitz.Matrix(zoom_factor, zoom_factor)

        # 创建一个字典用于存储页面的图片路径和对应的页码
        images_with_page_num = []
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = {
                executor.submit(process_page, pdf_doc, page_num, zoom_matrix, temp_dir): page_num
                for page_num in range(len(pdf_doc))}
            for future in as_completed(futures):
                result = future.result()
                page_num = futures[future]
                if result:
                    # 将页码和图片路径一起存储
                    images_with_page_num.append((page_num, result))
                else:
                    log_func(f"页面 {page_num} 处理失败")
        log_func(f"文件处理完成: {pdf_path}")

        # 按页码排序
        images_with_page_num.sort(key=lambda x: x[0])

        # 只返回图片路径的列表
        return [img_path for _, img_path in images_with_page_num]
    except Exception as e:
        log_func(f"处理PDF失败: {e}")
        return []


class BatchConvertThread(QThread):
    update_progress = pyqtSignal(int)
    log_message = pyqtSignal(str)
    completed = pyqtSignal(dict)

    def __init__(self, pdf_files, output_folder_path, zoom_factor, temp_dir, images_per_long):
        super().__init__()
        self.pdf_files = pdf_files
        self.output_folder_path = output_folder_path
        self.zoom_factor = zoom_factor
        self.temp_dir = temp_dir
        self.images_per_long = images_per_long

    def run(self):
        total_files = len(self.pdf_files)
        failed_files = []

        for i, pdf_file in enumerate(self.pdf_files):
            try:
                # 长图文件名使用原PDF文件名
                output_image_base_path = os.path.join(self.output_folder_path,
                                                      os.path.splitext(os.path.basename(pdf_file))[0])

                images = extract_images_from_pdf(pdf_file, self.zoom_factor, self.temp_dir, self.log_message.emit)
                if images:
                    concatenate_images_vertically(images, output_image_base_path, self.images_per_long)
                    self.log_message.emit(f"文件转换成功: {pdf_file}")
                else:
                    raise ValueError("未生成图像")
            except Exception as e:
                failed_files.append(pdf_file)
                self.log_message.emit(f"文件 {pdf_file} 转换失败: {e}")

            progress_value = int((i + 1) / total_files * 100)
            self.update_progress.emit(progress_value)

        summary = {
            "failed": failed_files,
        }
        self.completed.emit(summary)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PDFToLongImageApp()
    ex.show()
    sys.exit(app.exec_())
