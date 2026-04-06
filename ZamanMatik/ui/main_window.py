import os
import sys
import re
import requests
import webbrowser
from datetime import datetime, timedelta
from requests.exceptions import ConnectTimeout, ConnectionError, Timeout, RequestException

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QMainWindow, QMessageBox, QTableWidgetItem,
    QHeaderView, QFileDialog, QListWidgetItem, QMenuBar, QAction,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QTextBrowser
)
from PyQt5.QtCore import QDate, Qt, QDateTime, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPalette, QBrush, QFont, QIcon

from logic.calculator import LimitationCalculator
from models.case_data import CaseData
from utils.date_utils import date_to_qdate, qdate_to_date, format_date, format_number

CURRENT_VERSION = "1.4" #Sürüm Numarası
VERSION_URL = "https://cezamatik.blogspot.com/p/zamansurum.html"
DOWNLOAD_PAGE = "https://cezamatik.blogspot.com/p/zamanmatik-nasl-guncellenir.html"
GITHUB_URL = "https://github.com/cezateknik/zmnmtk/tree/main"

class TurkishTextEdit(QTextEdit):
    """Türkçe dil destekli QTextEdit widget'ı"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()

        actions = menu.actions()

        action_translations = {
            "&Undo": "&Geri Al",
            "&Redo": "&Yinele",
            "Cu&t": "K&es",
            "&Copy": "&Kopyala",
            "&Paste": "Ya&pıştır",
            "Delete": "Sil",
            "Select All": "Tümünü Seç"
        }

        for action in actions:
            if action.text() in action_translations:
                action.setText(action_translations[action.text()])

        menu.exec_(event.globalPos())

class JudgmentDialog(QDialog):
    """Hüküm metni gösterme dialog penceresi"""

    def __init__(self, judgment_text, parent=None):
        super().__init__(parent)
        self.judgment_text = judgment_text
        self.setWindowTitle("Hüküm Metni")
        self.setMinimumSize(900, 700)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("Hüküm Metni")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #1e40af; padding: 10px;")
        layout.addWidget(title_label)

        info_label = QLabel("Aşağıdaki metni kopyalayabilir veya düzenleyebilirsiniz:")
        info_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(info_label)

        self.text_edit = TurkishTextEdit()
        self.text_edit.setPlainText(self.judgment_text)
        self.text_edit.setReadOnly(False)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #8b5cf6;
                border-radius: 6px;
                background-color: #faf5ff;
                padding: 15px;
                font-family: 'Courier New', monospace;
                font-size: 11pt;
                line-height: 1.6;
            }
        """)
        self.text_edit.setFont(QFont("Courier New", 11))
        layout.addWidget(self.text_edit)

        button_layout = QHBoxLayout()

        copy_btn = QPushButton("Tümünü Kopyala")
        copy_btn.setFixedHeight(35)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        copy_btn.clicked.connect(self.copy_all_text)
        button_layout.addWidget(copy_btn)

        save_btn = QPushButton("Dosyaya Kaydet")
        save_btn.setFixedHeight(35)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        save_btn.clicked.connect(self.save_to_file)
        button_layout.addWidget(save_btn)

        close_btn = QPushButton("Kapat")
        close_btn.setFixedHeight(35)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def copy_all_text(self):
        """Tüm metni panoya kopyala"""
        text = self.text_edit.toPlainText()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Bilgi", "Hüküm metni panoya kopyalandı.")

    def save_to_file(self):
        """Metni dosyaya kaydet"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Hüküm Metnini Kaydet", "", "Metin Dosyası (*.txt);;Tüm Dosyalar (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.text_edit.toPlainText())

                QMessageBox.information(self, "Bilgi", "Hüküm metni başarıyla kaydedildi.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi: {str(e)}")

class UpdateCheckThread(QThread):
    updateAvailable = pyqtSignal(str)
    noUpdateAvailable = pyqtSignal()
    errorOccurred = pyqtSignal(str)

    def __init__(self, timeout_seconds=15, silent_errors=False, parent=None):
        super().__init__(parent)
        self.timeout_seconds = timeout_seconds
        self.silent_errors = silent_errors

    def run(self):
        try:
            response = requests.get(VERSION_URL, timeout=self.timeout_seconds)
            if response.status_code == 200:
                html_content = response.text

                version_pattern = r'v\.(\d+\.\d+(?:\.\d+)?)'
                matches = re.findall(version_pattern, html_content, re.IGNORECASE)

                if not matches:
                    version_pattern = r'(\d+\.\d+(?:\.\d+)?)'
                    matches = re.findall(version_pattern, html_content)

                if matches:
                    latest_version = matches[0].strip()

                    if self.compare_versions(latest_version, CURRENT_VERSION):
                        self.updateAvailable.emit(latest_version)
                    else:
                        self.noUpdateAvailable.emit()
                else:
                    if not self.silent_errors:
                        self.errorOccurred.emit("⚠️ Sürüm bilgisi bulunamadı")
            else:
                if not self.silent_errors:
                    self.errorOccurred.emit("⚠️ Sürüm bilgisi alınamadı")
        except (ConnectTimeout, Timeout):
            if not self.silent_errors:
                self.errorOccurred.emit("⏰ Zamanaşımına uğradı\n\nKurum ağı dışında mobil veya ev internetinde deneyiniz!")
        except ConnectionError as e:
            if not self.silent_errors:
                if "timed out" in str(e).lower():
                    self.errorOccurred.emit("⏰ Bağlantı zamanaşımına uğradı\n\nKurum ağı dışında mobil veya ev internetinde deneyiniz!")
                else:
                    self.errorOccurred.emit("🌐 İnternet bağlantı hatası\n\nİnternet bağlantınızı kontrol ediniz!")
        except RequestException as e:
            if not self.silent_errors:
                if "timeout" in str(e).lower():
                    self.errorOccurred.emit("⏰ İstek zamanaşımına uğradı\n\nKurum ağı dışında mobil veya ev internetinde deneyiniz!")
                else:
                    self.errorOccurred.emit("🚫 Güncelleme kontrolü başarısız\n\nDaha sonra tekrar deneyiniz!")
        except Exception as e:
            if not self.silent_errors:
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["timeout", "timed out", "connection"]):
                    self.errorOccurred.emit("⏰ Bağlantı zamanaşımına uğradı\n\nKurum ağı dışında mobil veya ev internetinde deneyiniz!")
                else:
                    self.errorOccurred.emit("🚫 Güncelleme kontrolü başarısız\n\nDaha sonra tekrar deneyiniz!")

    def compare_versions(self, version1, version2):
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]

            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))

            return v1_parts > v2_parts
        except:
            return False

class UpdateHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Güncelleme Geçmişi")
        self.setMinimumSize(600, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("Güncelleme Geçmişi")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        self.history_table = QtWidgets.QTableWidget()
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["Sürüm", "Tarih", "Açıklama"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                gridline-color: #e2e8f0;
            }
            QHeaderView::section {
                background-color: #1e40af;
                color: white;
                padding: 5px;
                border: none;
            }
            QTableWidget::item {
                padding: 8px;
            }
        """)

        self.populate_history()
        layout.addWidget(self.history_table)

        close_button = QPushButton("Kapat")
        close_button.setFixedHeight(35)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def populate_history(self):
        history_data = [
            ("v1.1", "07.06.2025", "İlk sürüm yayınlandı"),
            ("v1.2", "12.01.2026", "Hata düzeltmeleri ve performans iyileştirmeleri"),
            ("v1.3", "15.01.2026", "Hüküm kur özelliği ve hata düzeltmeleri"),
            ("v1.4", "06.04.2026", "\"Kesilme ekle\" butonu eklendi, yardım ve bilgi pencerelerinde arayüz iyileştirmeleri yapıldı"),
        ]

        self.history_table.setRowCount(len(history_data))

        for row, (version, date, description) in enumerate(history_data):
            version_item = QTableWidgetItem(version)
            version_item.setForeground(QColor("#1e40af"))
            font = version_item.font()
            font.setBold(True)
            version_item.setFont(font)

            date_item = QTableWidgetItem(date)
            desc_item = QTableWidgetItem(description)

            self.history_table.setItem(row, 0, version_item)
            self.history_table.setItem(row, 1, date_item)
            self.history_table.setItem(row, 2, desc_item)

            self.history_table.setRowHeight(row, 35)

class CalculationLogicDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hesaplama Mantığı")
        self.setMinimumSize(700, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
            }
        """)

        content_widget = QtWidgets.QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)

        html_content = """
        <div style="font-family: Arial, sans-serif; line-height: 1.8; color: #1e293b;">
            <h2 style="color: #1e40af; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-bottom: 20px;">
                Hesaplama Mantığı
            </h2>

            <h3 style="color: #1e40af; margin-top: 20px; margin-bottom: 10px;">1. Temel İlke - Hukuk Mantığına Uygun Ay Hesabı</h3>
            <div style="background-color: #f0f9ff; border-left: 4px solid #3b82f6; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                <p><strong>Önemli:</strong> Türk ceza hukuku uygulamalarında, zamanaşımı hesaplamaları yapılırken her ay <strong>mutlak 30 gün</strong> olarak kabul edilir.</p>
                <ul>
                    <li>1 ay = her zaman 30 gün (sabittir)</li>
                    <li>Takvim ayı uzunluğuna (28-29-30-31) göre değişmez</li>
                    <li>Şubat ayının 28 veya 29 çekmesi hesabı etkilemez</li>
                </ul>
            </div>

            <h3 style="color: #1e40af; margin-top: 20px; margin-bottom: 10px;">2. Hesaplama Adımları</h3>

            <div style="background-color: #faf5ff; border-left: 4px solid #7c3aed; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                <h4 style="margin-top: 0; color: #6d28d9;">Adım 1: Temel Zamanaşımı Süresi (TCK 66/1)</h4>
                <p>Ceza türüne göre temel zamanaşımı süresi belirlenir:</p>
                <ul>
                    <li><strong>Ağırlaştırılmış müebbet:</strong> 30 yıl</li>
                    <li><strong>Müebbet:</strong> 25 yıl</li>
                    <li><strong>20 yıl ve üzeri hapis:</strong> 20 yıl</li>
                    <li><strong>5 yıldan fazla - 20 yıldan az hapis:</strong> 15 yıl</li>
                    <li><strong>5 yıl veya daha az hapis:</strong> 8 yıl</li>
                    <li><strong>Adlî para cezası:</strong> 8 yıl</li>
                </ul>
            </div>

            <div style="background-color: #eff6ff; border-left: 4px solid #0284c7; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                <h4 style="margin-top: 0; color: #0369a1;">Adım 2: Çocuk Fail İndirimi (TCK 66/2)</h4>
                <p>Suç tarihinde 18 yaşından küçük olan failin yaşına göre indirim uygulanır:</p>
                <ul>
                    <li><strong>12-15 yaş arası:</strong> Sürenin yarısı (÷ 2)</li>
                    <li><strong>15-18 yaş arası:</strong> Sürenin üçte ikisi (× 2/3)</li>
                    <li><strong>18 yaş ve üzeri:</strong> İndirim yok</li>
                </ul>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #475569;"><em>Örnek: 8 yıl cezada 12-15 yaş arası fail → 8 ÷ 2 = 4 yıl</em></p>
            </div>

            <div style="background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                <h4 style="margin-top: 0; color: #15803d;">Adım 3: Maksimum Süre Sınırlaması (TCK 67/4)</h4>
                <p>Zamanaşımı kesilse bile, toplam süre <strong>asıl sürenin 1.5 katını geçemez</strong>:</p>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #475569;"><em>Örnek: 8 yıl cezada 8 × 1.5 = 12 yıl maksimum</em></p>
            </div>

            <div style="background-color: #fefce8; border-left: 4px solid #ca8a04; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                <h4 style="margin-top: 0; color: #92400e;">Adım 4: Başlangıç Tarihinin Belirlenmesi</h4>
                <p><strong>Eğer zamanaşımı kesilmediyse:</strong> Suç tarihi başlangıç tarihi olur</p>
                <p><strong>Eğer zamanaşımı kesilmişse:</strong> Son kesilme tarihi başlangıç tarihi olur (zamanaşımı yeniden başlar)</p>
            </div>

            <div style="background-color: #fce7f3; border-left: 4px solid #ec4899; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                <h4 style="margin-top: 0; color: #be185d;">Adım 5: Zamanaşımının Durması (TCK 67/1)</h4>
                <p>Başlangıç tarihine, durma sürelerinin toplam yıl, ay ve günleri eklenir.</p>
                <p><strong>Durma Süresi Hesaplanması (HUKUK MANTIĞINA UYGUN):</strong></p>
                <ul>
                    <li>Tarih A'dan Tarih B'ye kadar geçen süre hesaplanır</li>
                    <li>Önce tam aylar sayılır, sonra kalan kısım gün olarak</li>
                    <li>Gün hesabında her ay 30 gün kabul edilir</li>
                </ul>
                <p style="margin: 10px 0 0 0; font-size: 13px; background-color: rgba(255,255,255,0.8); padding: 8px; border-radius: 3px;">
                    <strong>Örnek:</strong> 04.11.2009 - 11.02.2010<br>
                    • 04.11 → 04.02 = 3 ay (doğru)<br>
                    • 04.02 → 11.02 = 7 gün (doğru)<br>
                    • Sonuç: 3 ay 7 gün ✓
                </p>
            </div>

            <div style="background-color: #f3e8ff; border-left: 4px solid #a855f7; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                <h4 style="margin-top: 0; color: #7c3aed;">Adım 6: Nihai Bitiş Tarihi</h4>
                <p>Başlangıç tarihi + Temel süre + Durma süresi</p>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #475569;">
                    <em>Ancak maksimum sınırlamayı aşmayacak</em>
                </p>
            </div>

            <h3 style="color: #1e40af; margin-top: 25px; margin-bottom: 10px;">3. Detaylı Hesaplama Örneği</h3>
            <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                <p><strong>Veri:</strong></p>
                <ul style="margin: 5px 0;">
                    <li>Ceza: 5 yıl hapis</li>
                    <li>Suç tarihi: 01.01.2014</li>
                    <li>Bugün: 12.01.2026</li>
                    <li>Son Kesilme: 01.01.2020</li>
                    <li>Durma: 15.03.2018 - 15.06.2018 (3 ay)</li>
                </ul>

                <p style="margin-top: 15px;"><strong>Hesaplama:</strong></p>
                <ol style="margin: 5px 0;">
                    <li>Temel süre: 8 yıl</li>
                    <li>Çocuk indirimi: Yok (18 yaş üzeri)</li>
                    <li>Maksimum: 8 × 1.5 = 12 yıl</li>
                    <li>Son Kesilme: 01.01.2020</li>
                    <li>Durma: 3 ay ekle → 01.04.2020</li>
                    <li>Bitiş: 01.04.2026</li>
                    <li>Kalan: 79 GÜN (Zamanaşımı dolmamış)</li>
                </ol>
            </div>

            <h3 style="color: #1e40af; margin-top: 25px; margin-bottom: 10px;">4. Önemli Notlar</h3>
            <ul style="background-color: #faf5ff; border-left: 4px solid #7c3aed; padding: 12px; border-radius: 4px;">
                <li><strong>Her ay 30 gün kabul edilir:</strong> Hiçbir koşulda takvim ay uzunlukları kullanılmaz</li>
                <li><strong>Kesilme sürelerini kesen olaylar:</strong> Sorgu, tutuklama, iddianame, mahkûmiyet kararı vb.</li>
                <li><strong>Duran süre:</strong> Zamanaşımı süresine eklenir, olağanüstü zamanaşımı süresi sınırına tabii değildir.</li>
                <li><strong>En erken bitiş tarihi geçerli:</strong> Temel süreden hesaplanan ve maksimum süreden hesaplanan tarihlerden hangisi erkense o esas alınır</li>
                <li><strong>Olağanüstü zamanaşımı</strong> TCK m.67/4 esasına göre hesaplanır. Örneğin 15-18 yaş grubu için 5 yıl 4 ay × 1.5 = <strong>7 yıl 12 ay</strong> şeklinde bulunur. "8 yıl" ibaresi yanlıştır. </li>
            </ul>
            <h3 style="color: #dc2626; margin-top: 25px; margin-bottom: 10px;">5. Yasal Dayanaklar</h3>
            <ul>
                <li><strong>TCK Madde 66:</strong> Dava zamanaşımı süreleri</li>
                <li><strong>TCK Madde 67:</strong> Zamanaşımının durması ve kesilmesi</li>
            </ul>

            <div style="background-color: #fee2e2; border-left: 4px solid #dc2626; padding: 12px; border-radius: 4px; margin-top: 20px;">
                <p style="margin: 0;"><strong>Yasal Uyarı:</strong> Bu açıklamalar bilgilendirme amaçlıdır. Hesaplama sonuçlarının doğruluğu mutlak değildir. Manuel hesaplamayı doğrulama amaçlı kullanılması tavsiye edilir.</p>
            </div>
        </div>
        """

        text_edit = QtWidgets.QTextEdit()
        text_edit.setHtml(html_content)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("""
            QTextEdit {
                border: none;
                background-color: white;
            }
        """)
        content_layout.addWidget(text_edit)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        close_button = QPushButton("Kapat")
        close_button.setFixedHeight(35)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Güncelleme Kontrolü")
        self.setMinimumSize(450, 250)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.update_thread = None
        self.latest_version = None
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("Güncelleme Kontrolü")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        version_label = QLabel(f"Mevcut Sürüm: {CURRENT_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        self.status_label = QLabel("Güncelleme kontrolü için butona tıklayın")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.new_version_label = QLabel()
        self.new_version_label.setAlignment(Qt.AlignCenter)
        self.new_version_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.new_version_label.hide()
        layout.addWidget(self.new_version_label)

        button_layout = QHBoxLayout()

        self.check_button = QPushButton("Güncellemeleri Kontrol Et")
        self.check_button.setFixedHeight(35)
        self.check_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.check_button.clicked.connect(self.check_for_updates)
        button_layout.addWidget(self.check_button)

        self.update_button = QPushButton("Güncelle")
        self.update_button.setFixedHeight(35)
        self.update_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.update_button.clicked.connect(self.open_download_page)
        self.update_button.hide()
        button_layout.addWidget(self.update_button)

        close_button = QPushButton("Kapat")
        close_button.setFixedHeight(35)
        close_button.setFixedWidth(80)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def check_for_updates(self):
        self.check_button.setEnabled(False)
        self.update_button.hide()
        self.new_version_label.hide()
        self.status_label.setText("🔍 Güncelleme kontrol ediliyor...")

        self.update_thread = UpdateCheckThread()
        self.update_thread.updateAvailable.connect(self.on_update_available)
        self.update_thread.noUpdateAvailable.connect(self.on_no_update)
        self.update_thread.errorOccurred.connect(self.on_error)
        self.update_thread.finished.connect(self.on_check_finished)
        self.update_thread.start()

    def on_update_available(self, latest_version):
        self.latest_version = latest_version
        self.status_label.setText("🔔 Yeni sürüm mevcut!")
        self.new_version_label.setText(f"Yeni Sürüm: {latest_version}")
        self.new_version_label.show()
        self.update_button.show()

    def on_no_update(self):
        self.status_label.setText("✅ Uygulamanız güncel.")
        self.update_button.hide()
        self.new_version_label.hide()

    def on_error(self, error_message):
        self.status_label.setText(error_message)
        self.update_button.hide()
        self.new_version_label.hide()

    def on_check_finished(self):
        self.check_button.setEnabled(True)

    def open_download_page(self):
        try:
            webbrowser.open(DOWNLOAD_PAGE)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Güncelleme sayfası açılamadı: {str(e)}")


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lisans")
        self.setMinimumSize(720, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Lisans ve Üçüncü Taraf Bileşenler")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        text = QTextBrowser()
        text.setReadOnly(True)
        text.setOpenExternalLinks(True)
        text.setStyleSheet("""
            QTextBrowser {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-size: 12px;
            }
        """)
        text.setHtml("""
            <h3>Bu uygulamada kullanılan arayüz kütüphanesi</h3>
            <p>
              Bu uygulama <b>PyQt5 / Qt</b> kullanır.
              PyQt5, Riverbank Computing tarafından GPL veya ticari lisans modeliyle sunulan bir üçüncü taraf kütüphanedir.
            </p>

            <h3>Kısa lisans notu</h3>
            <p>
              Projede yer alan uygulama kodu kök dizindeki <b>LICENSE</b> dosyasında belirtilen lisans metni ile paylaşılır.
              Kullanılan <b>PyQt5 / Qt</b> bileşenlerine ilişkin üçüncü taraf notları ise <b>THIRD_PARTY.md</b> dosyasında ayrıca belirtilmiştir.
              Projenin dağıtımı değerlendirilirken hem proje lisansı hem de kullanılan PyQt5 / Qt bileşenlerine ilişkin lisans koşulları birlikte dikkate alınmalıdır.
            </p>

            <h3>PyQt5 / Qt için resmi bağlantılar</h3>
            <ul>
              <li><b>PyQt lisans bilgisi:</b> <a href="https://riverbankcomputing.com/commercial/">https://riverbankcomputing.com/commercial/</a></li>
              <li><b>PyQt5 PyPI paketi:</b> <a href="https://pypi.org/project/PyQt5/">https://pypi.org/project/PyQt5/</a></li>
              <li><b>Qt lisanslama:</b> <a href="https://doc.qt.io/qt-5/licensing.html">https://doc.qt.io/qt-5/licensing.html</a></li>
              <li><b>Qt belgeleri:</b> <a href="https://doc.qt.io/qt-5/">https://doc.qt.io/qt-5/</a></li>
            </ul>

            <h3>Kaynak ve Lisans Dosyaları</h3>
            <ul>
              <li><b>GitHub kod bağlantısı:</b> <a href="https://github.com/cezateknik/zmnmtk/tree/main">https://github.com/cezateknik/zmnmtk/tree/main</a></li>
              <li><b>LICENSE</b>: Proje lisans metni</li>
              <li><b>THIRD_PARTY.md</b>: Üçüncü taraf bileşen ve lisans notları</li>
            </ul>

            <h3>Not</h3>
            <p>
              Bu ekran bilgilendirme amaçlıdır. Gerekli durumlarda resmi lisans metinleri ve ilgili sağlayıcıların resmi sayfaları esas alınmalıdır.
            </p>
        """)
        layout.addWidget(text)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_button = QPushButton("Kapat")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        button_row.addStretch()
        layout.addLayout(button_row)


class RichInfoDialog(QDialog):
    def __init__(self, title, html_content, parent=None, min_size=(680, 520)):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(*min_size)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.html_content = html_content
        self.setup_ui(title)

    def setup_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #1e293b;")
        layout.addWidget(title_label)

        text = QTextBrowser()
        text.setReadOnly(True)
        text.setOpenExternalLinks(True)
        text.setHtml(self.html_content)
        text.setStyleSheet("""
            QTextBrowser {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                selection-background-color: #bfdbfe;
            }
            QTextBrowser a {
                color: #2563eb;
                text-decoration: none;
            }
        """)
        layout.addWidget(text)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_button = QPushButton("Kapat")
        close_button.setFixedWidth(110)
        close_button.setMinimumHeight(34)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.interruption_date_edits = []
        self.suspension_dates = []
        self.setupUi()
        self.calculator = LimitationCalculator()
        self.setup_connections()
        self.setup_styles()
        self.setup_menu()
        self.setup_window_icon()
        self.set_default_info_text()
        self.create_desktop_shortcut()

    def create_desktop_shortcut(self):
        try:
            import winshell
            from win32com.client import Dispatch

            desktop = winshell.desktop()
            shortcut_name = "ZamanMat'ik.lnk"
            shortcut_path = os.path.join(desktop, shortcut_name)

            if os.path.exists(shortcut_path):
                return

            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])

            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = exe_path
            shortcut.WorkingDirectory = os.path.dirname(exe_path)
            shortcut.IconLocation = exe_path
            shortcut.Description = "ZamanMatik - Türk Ceza Kanunu Dava Zamanaşımı Hesaplama Programı"
            shortcut.save()

        except ImportError:
            self.create_shortcut_alternative()
        except Exception as e:
            self.create_shortcut_alternative()

    def create_shortcut_alternative(self):
        try:
            import subprocess

            possible_desktop_paths = [
                os.path.join(os.path.expanduser("~"), "Desktop"),
                os.path.join(os.path.expanduser("~"), "Masaüstü"),
                os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
                os.path.join(os.path.expanduser("~"), "OneDrive", "Masaüstü")
            ]

            desktop = None
            for path in possible_desktop_paths:
                if os.path.exists(path):
                    desktop = path
                    break

            if not desktop:
                return

            shortcut_name = "ZamanMatik.lnk"
            shortcut_path = os.path.join(desktop, shortcut_name)

            if os.path.exists(shortcut_path):
                return

            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])

            exe_path_escaped = exe_path.replace("\\", "\\\\")
            working_dir_escaped = os.path.dirname(exe_path).replace("\\", "\\\\")
            shortcut_path_escaped = shortcut_path.replace("\\", "\\\\")

            ps_command = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path_escaped}")
$Shortcut.TargetPath = "{exe_path_escaped}"
$Shortcut.WorkingDirectory = "{working_dir_escaped}"
$Shortcut.Description = "ZamanMatik - Türk Ceza Kanunu Dava Zamanaşımı Hesaplama Programı"
$Shortcut.Save()
'''

            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode != 0:
                self.create_shortcut_vbscript(shortcut_path, exe_path)

        except Exception as e:
            try:
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                if not os.path.exists(desktop):
                    desktop = os.path.join(os.path.expanduser("~"), "Masaüstü")

                if os.path.exists(desktop):
                    shortcut_path = os.path.join(desktop, "ZamanMatik.lnk")
                    if getattr(sys, 'frozen', False):
                        exe_path = sys.executable
                    else:
                        exe_path = os.path.abspath(sys.argv[0])

                    self.create_shortcut_vbscript(shortcut_path, exe_path)
            except:
                pass

    def create_shortcut_vbscript(self, shortcut_path, exe_path):
        try:
            import tempfile
            import subprocess

            vbs_content = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{exe_path}"
oLink.WorkingDirectory = "{os.path.dirname(exe_path)}"
oLink.Description = "ZamanMatik - Türk Ceza Kanunu Dava Zamanaşımı Hesaplama Programı"
oLink.Save
'''

            with tempfile.NamedTemporaryFile(mode='w', suffix='.vbs', delete=False, encoding='utf-8') as f:
                f.write(vbs_content)
                vbs_file = f.name

            subprocess.run(
                ["cscript", "//NoLogo", vbs_file],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            try:
                os.unlink(vbs_file)
            except:
                pass

        except Exception:
            pass

    def setup_window_icon(self):
        icon_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'assets', 'icon.ico'),
            os.path.join(os.path.dirname(__file__), '..', 'assets', 'icon.png'),
            os.path.join(os.path.dirname(__file__), '..', 'icon.ico'),
            os.path.join(os.path.dirname(__file__), '..', 'icon.png'),
            'assets/icon.ico',
            'assets/icon.png',
            'icon.ico',
            'icon.png'
        ]

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    return

        self.create_default_icon()

    def create_default_icon(self):
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtGui.QColor(30, 58, 138))

        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.setFont(QtGui.QFont("Arial", 20, QtGui.QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "Z")
        painter.end()

        icon = QIcon(pixmap)
        self.setWindowIcon(icon)

    def setupUi(self):
        self.setWindowTitle("Dava Zamanaşımı Hesaplama Programı - ZamanMat'ik")
        self.setMinimumSize(1000, 800)

        self.centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralwidget)
        self.main_layout = QtWidgets.QVBoxLayout(self.centralwidget)

        self.header = QtWidgets.QLabel("Dava Zamanaşımı Hesaplama Modülü")
        self.header.setAlignment(Qt.AlignCenter)
        font = QtGui.QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.header.setFont(font)
        self.header.setStyleSheet("color: #ffffff; background-color: #1e3a8a; padding: 15px;")
        self.main_layout.addWidget(self.header)

        self.content_widget = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QHBoxLayout(self.content_widget)

        self.input_panel = QtWidgets.QGroupBox("Girdi Parametreleri")
        self.input_panel.setFixedWidth(450)
        self.input_panel_layout = QtWidgets.QVBoxLayout(self.input_panel)
        self.input_panel_layout.setContentsMargins(0, 8, 2, 0)
        self.input_panel_layout.setSpacing(0)
        self.input_scroll = QtWidgets.QScrollArea()
        self.input_scroll.setWidgetResizable(True)
        self.input_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.input_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.input_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input_scroll.setBackgroundRole(QPalette.Base)
        self.input_scroll.setAutoFillBackground(True)
        self.input_scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                height: 0;
                background: transparent;
            }
        """)
        scroll_palette = self.input_scroll.viewport().palette()
        scroll_palette.setColor(QPalette.Base, QColor("#ffffff"))
        scroll_palette.setColor(QPalette.Window, QColor("#ffffff"))
        self.input_scroll.viewport().setPalette(scroll_palette)
        self.input_scroll.viewport().setAutoFillBackground(True)
        self.input_scroll.setPalette(scroll_palette)
        self.input_scroll_widget = QtWidgets.QWidget()
        self.input_scroll_widget.setPalette(scroll_palette)
        self.input_scroll_widget.setAutoFillBackground(True)
        self.input_layout = QtWidgets.QVBoxLayout(self.input_scroll_widget)
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setAlignment(Qt.AlignTop)
        self.input_scroll.setWidget(self.input_scroll_widget)
        self.input_panel_layout.addWidget(self.input_scroll)
        self.setup_input_panel()
        self.content_layout.addWidget(self.input_panel)

        self.results_panel = QtWidgets.QGroupBox("Hesaplama Sonuçları")
        self.results_layout = QtWidgets.QVBoxLayout(self.results_panel)
        self.setup_results_panel()
        self.content_layout.addWidget(self.results_panel)

        self.main_layout.addWidget(self.content_widget)

        self.footer = QtWidgets.QWidget()
        self.footer_layout = QtWidgets.QHBoxLayout(self.footer)

        self.calculate_btn = QtWidgets.QPushButton("Hesapla")
        self.calculate_btn.setMinimumHeight(40)
        self.export_btn = QtWidgets.QPushButton("Sonuçları Dışa Aktar")
        self.export_btn.setMinimumHeight(40)
        self.clear_btn = QtWidgets.QPushButton("Formu Temizle")
        self.clear_btn.setMinimumHeight(40)

        self.footer_layout.addWidget(self.calculate_btn)
        self.footer_layout.addWidget(self.export_btn)
        self.footer_layout.addWidget(self.clear_btn)

        self.main_layout.addWidget(self.footer)

        self.copyright_label = QtWidgets.QLabel("© 2025 İ.K | Tüm hakları saklıdır.")
        self.copyright_label.setAlignment(Qt.AlignCenter)
        self.copyright_label.setStyleSheet("color: #64748b; font-size: 10px; padding: 5px; background-color: #f1f5f9;")
        self.main_layout.addWidget(self.copyright_label)

    def setup_menu(self):
        menubar = self.menuBar()

        options_menu = menubar.addMenu('Seçenekler')

        logic_action = QAction('Hesaplama Mantığı', self)
        logic_action.triggered.connect(self.show_calculation_logic)
        options_menu.addAction(logic_action)

        options_menu.addSeparator()

        usage_guide_action = QAction('Kullanım Kılavuzu', self)
        usage_guide_action.triggered.connect(self.show_usage_guide)
        options_menu.addAction(usage_guide_action)

        about_action = QAction('Hakkında', self)
        about_action.triggered.connect(self.show_about)
        options_menu.addAction(about_action)

        license_action = QAction('Lisans', self)
        license_action.triggered.connect(self.show_license_dialog)
        options_menu.addAction(license_action)

        updates_menu = menubar.addMenu('Güncellemeler')

        check_updates_action = QAction('Güncelleme Kontrolü', self)
        check_updates_action.triggered.connect(self.show_update_dialog)
        updates_menu.addAction(check_updates_action)

        history_action = QAction('Güncelleme Geçmişi', self)
        history_action.triggered.connect(self.show_update_history)
        updates_menu.addAction(history_action)

        help_menu = menubar.addMenu('Yardım')

        help_action = QAction('Yardım', self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

    def setup_input_panel(self):
        form_layout = QtWidgets.QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(10, 20, 10, 10)

        self.ceza_turu_combo = QtWidgets.QComboBox()
        self.ceza_turu_combo.addItems([
            "Ağırlaştırılmış müebbet",
            "Müebbet",
            "20 yıl ve üzeri hapis",
            "5 yıldan fazla - 20 yıldan az hapis",
            "5 yıl veya daha az hapis",
            "Adlî para cezası"
        ])
        self.ceza_turu_combo.setCurrentText("5 yıl veya daha az hapis")
        form_layout.addRow("Ceza Türü:", self.ceza_turu_combo)

        self.fail_yasi_combo = QtWidgets.QComboBox()
        self.fail_yasi_combo.addItems([
            "12-15 yaş arası",
            "15-18 yaş arası",
            "18 yaş ve üzeri"
        ])
        self.fail_yasi_combo.setCurrentText("18 yaş ve üzeri")
        form_layout.addRow("Failin Yaşı (Suç Tarihinde):", self.fail_yasi_combo)

        self.suc_tarihi_date = QtWidgets.QDateEdit()
        self.suc_tarihi_date.setDisplayFormat("dd.MM.yyyy")
        self.suc_tarihi_date.setDate(QDate.currentDate().addYears(-1))
        self.suc_tarihi_date.setCalendarPopup(True)
        form_layout.addRow("Suç Tarihi:", self.suc_tarihi_date)

        self.bugun_date = QtWidgets.QDateEdit()
        self.bugun_date.setDisplayFormat("dd.MM.yyyy")
        self.bugun_date.setDate(QDate.currentDate())
        self.bugun_date.setCalendarPopup(True)
        form_layout.addRow("Bugünkü Tarih:", self.bugun_date)

        self.durma_check = QtWidgets.QCheckBox("Zamanaşımı durdu mu?")
        form_layout.addRow("", self.durma_check)

        self.durma_container = QtWidgets.QWidget()
        self.durma_layout = QtWidgets.QVBoxLayout(self.durma_container)
        self.durma_layout.setContentsMargins(20, 0, 0, 0)
        self.durma_layout.setSpacing(4)

        durma_dates_widget = QtWidgets.QWidget()
        durma_dates_layout = QtWidgets.QGridLayout(durma_dates_widget)
        durma_dates_layout.setContentsMargins(0, 0, 0, 0)
        durma_dates_layout.setVerticalSpacing(3)
        durma_dates_layout.setHorizontalSpacing(5)
        durma_dates_layout.setColumnStretch(0, 0)
        durma_dates_layout.setColumnStretch(1, 1)

        durma_dates_layout.addWidget(QtWidgets.QLabel("Başlangıç:"), 0, 0)
        self.durma_baslangic_date = QtWidgets.QDateEdit()
        self.durma_baslangic_date.setDisplayFormat("dd.MM.yyyy")
        self.durma_baslangic_date.setCalendarPopup(True)
        durma_dates_layout.addWidget(self.durma_baslangic_date, 0, 1)

        durma_dates_layout.addWidget(QtWidgets.QLabel("Bitiş:"), 1, 0)
        self.durma_bitis_date = QtWidgets.QDateEdit()
        self.durma_bitis_date.setDisplayFormat("dd.MM.yyyy")
        self.durma_bitis_date.setCalendarPopup(True)
        durma_dates_layout.addWidget(self.durma_bitis_date, 1, 1)

        self.durma_ekle_btn = QtWidgets.QPushButton("Ekle")
        self.durma_ekle_btn.setMinimumHeight(28)
        self.durma_ekle_btn.setMaximumHeight(28)
        durma_dates_layout.addWidget(self.durma_ekle_btn, 2, 0, 1, 2)

        self.durma_layout.addWidget(durma_dates_widget)

        self.durma_list = QtWidgets.QListWidget()
        self.durma_list.setMaximumHeight(68)
        self.durma_sil_btn = QtWidgets.QPushButton("Seçili Tarihi Sil")
        self.durma_sil_btn.setMinimumHeight(30)
        self.durma_sil_btn.setMaximumHeight(30)

        self.durma_layout.addWidget(self.durma_list)
        self.durma_layout.addWidget(self.durma_sil_btn)

        self.durma_container.setVisible(False)
        form_layout.addRow("", self.durma_container)

        self.kesilme_date = QtWidgets.QDateEdit()
        self.kesilme_date.setDisplayFormat("dd.MM.yyyy")
        self.kesilme_date.setCalendarPopup(True)
        self.kesilme_date.setDate(QDate.currentDate())
        self.kesilme_label = QtWidgets.QLabel("Zamanaşımı Kesilme Tarihi:")
        self.kesilme_primary_widget = QtWidgets.QWidget()
        self.kesilme_primary_layout = QtWidgets.QHBoxLayout(self.kesilme_primary_widget)
        self.kesilme_primary_layout.setContentsMargins(0, 0, 0, 0)
        self.kesilme_primary_layout.setSpacing(6)
        self.kesilme_primary_number_label = QtWidgets.QLabel("1.")
        self.kesilme_primary_number_label.setFixedWidth(22)
        self.kesilme_primary_number_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.kesilme_primary_number_label.setVisible(False)
        self.kesilme_primary_layout.addWidget(self.kesilme_primary_number_label)
        self.kesilme_primary_layout.addWidget(self.kesilme_date, 1)
        form_layout.addRow(self.kesilme_label, self.kesilme_primary_widget)

        self.kesilme_toggle_btn = QtWidgets.QPushButton("+ Başka kesilme tarihi ekle")
        self.kesilme_toggle_btn.setMinimumHeight(28)
        self.kesilme_toggle_btn.setMaximumHeight(28)
        self.update_interruption_add_button()
        form_layout.addRow("", self.kesilme_toggle_btn)

        self.kesilme_container = QtWidgets.QWidget()
        self.kesilme_container.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Maximum
        )
        self.kesilme_layout = QtWidgets.QVBoxLayout(self.kesilme_container)
        self.kesilme_layout.setContentsMargins(0, 0, 0, 0)
        self.kesilme_layout.setSpacing(4)

        self.kesilme_rows_widget = QtWidgets.QWidget()
        self.kesilme_rows_layout = QtWidgets.QVBoxLayout(self.kesilme_rows_widget)
        self.kesilme_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.kesilme_rows_layout.setSpacing(6)
        self.kesilme_layout.addWidget(self.kesilme_rows_widget)

        self.kesilme_container.setVisible(False)
        form_layout.addRow("", self.kesilme_container)

        for date_edit in [self.suc_tarihi_date, self.bugun_date,
                         self.durma_baslangic_date, self.durma_bitis_date,
                         self.kesilme_date]:
            date_edit.setCalendarPopup(True)
            date_edit.setDisplayFormat("dd.MM.yyyy")
            date_edit.setMinimumWidth(120)

        self.ceza_turu_combo.setEditable(False)
        self.fail_yasi_combo.setEditable(False)
        self.ceza_turu_combo.setMinimumWidth(220)
        self.fail_yasi_combo.setMinimumWidth(220)

        self.input_layout.addLayout(form_layout)

    def setup_results_panel(self):
        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(300)
        self.results_layout.addWidget(self.result_text)

        self.final_result = QtWidgets.QLabel("Hesaplama sonucu burada görüntülenecek")
        self.final_result.setAlignment(Qt.AlignCenter)
        self.final_result.setWordWrap(True)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.final_result.setFont(font)
        self.final_result.setStyleSheet("padding: 15px; margin-top: 10px;")
        self.results_layout.addWidget(self.final_result)

        self.hukum_kur_btn = QtWidgets.QPushButton("HÜKÜM KUR")
        self.hukum_kur_btn.setMinimumHeight(40)
        self.hukum_kur_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
            QPushButton:pressed {
                background-color: #6d28d9;
            }
        """)
        self.hukum_kur_btn.hide()
        self.results_layout.addWidget(self.hukum_kur_btn)

        self.current_result = None

    def set_default_info_text(self):
        default_html = """
    <div style="font-family: Arial, sans-serif; padding: 16px; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9;">
    <p style="font-size: 15px; font-weight: bold; text-decoration: underline; margin-bottom: 12px;">
        BİLGİ NOTU:
    </p>

    <ul style="font-size: 13px; margin-left: 20px; margin-bottom: 16px;">
        <li style="margin-bottom: 6px;">Cezanın <strong>üst sınırı</strong> esas alınır. Cezayı artıran nitelikli haller dikkate alınır. Ancak <strong>TCK m.22/3, 43, 31, 35, 29  </strong> vs. dikkate alınmaz.</li>
    </ul>

    <p style="font-size: 13px; font-weight: bold; margin-bottom: 8px;">
        Zamanaşımını kesen hâller:
    </p>

    <ul style="font-size: 13px; margin-left: 20px; margin-bottom: 16px; line-height: 1.6;">
        <li>Şüpheli/sanığın <strong>savcı huzurunda ifadesinin alınması</strong></li>
        <li>Şüpheli/sanığın <strong>sorguya çekilmesi</strong></li>
        <li><strong>Tutuklama</strong> kararı verilmesi</li>
        <li><strong>İddianame düzenlenmesi</strong> <em>(kabûl edilmek şartıyla)</em></li>
        <li><strong>Mahkûmiyet kararı</strong> verilmesi</li>
    </ul>

    <div style="background-color: #fff3cd; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 8px;">
        🟡 Her kesilmede, zamanaşımı süresi <strong>yeniden başlar</strong>.
    </div>


    <p style="font-size: 13px; font-weight: bold; margin-bottom: 8px;">
        Diğer Hususlar:
    </p>

    <ul style="font-size: 13px; margin-left: 20px; line-height: 1.6;">
        <li><strong>HAGB kararı</strong>, zamanaşımını <u>kesmez</u>. <em> (Mahkûmiyet değil.)</em></li>
        <li><strong>HAGB kararının kesinleşmesiyle</strong> denetim süresince zamanaşımı <u>durur</u>. <em>(CMK m.231/8)</em></li>
        <li>HAGB denetim süresinde <strong>suç işlenirse</strong>, zamanaşımı <u>yeni suç tarihine kadar durur</u>.<em>(Yeni suçun kesinleşmesi gerekir.)</em></li>
        <li><strong>Bozma üzerine yapılan sorgu</strong>, zamanaşımını <u>kesmez</u>.</li>
        <li><strong>İzin, ön mesele, karar, uzlaştırma, kaçaklık(CMK m.247), HAGB, KDAE vb.</strong> zamanaşımını <u>durdurur</u>.</li>
    </ul>

    <div style="background-color: #f8d7da; color: #721c24; padding: 10px 14px; border-left: 4px solid #f5c6cb; border-radius: 6px; font-size: 13px; margin-top: 6px;">
        ⚠️ <strong>Yasal Uyarı:</strong> Hesaplama hataları içerebilir. Sorumluluk kabul edilmez.
    </div>
</div>


        """
        self.result_text.setHtml(default_html)

    def setup_connections(self):
        self.calculate_btn.clicked.connect(self.calculate)
        self.export_btn.clicked.connect(self.export_results)
        self.clear_btn.clicked.connect(self.clear_form)
        self.durma_check.stateChanged.connect(self.toggle_durma_inputs)
        self.durma_ekle_btn.clicked.connect(self.add_suspension_date)
        self.durma_sil_btn.clicked.connect(self.remove_suspension_date)
        self.kesilme_toggle_btn.clicked.connect(self.add_interruption_date)
        self.hukum_kur_btn.clicked.connect(self.generate_hukum)

    def setup_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                margin-top: 10px;
                background-color: #ffffff;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: black;
                selection-background-color: #e0e7ff;
                selection-color: blue;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #1e40af;
            }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            #calculate_btn {
                background-color: #10b981;
            }
            #calculate_btn:hover {
                background-color: #059669;
            }
            #clear_btn {
                background-color: #ef4444;
            }
            #clear_btn:hover {
                background-color: #dc2626;
            }
            QComboBox, QSpinBox, QDateEdit {
                padding: 4px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: white;
                min-height: 20px;
            }
            QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                padding: 8px;
            }
            QLabel {
                color: #1e293b;
            }
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                padding: 4px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QMenuBar {
                background-color: #f1f5f9;
                color: #1e293b;
                border-bottom: 1px solid #cbd5e1;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background-color: #e2e8f0;
            }
            QMenu {
                background-color: white;
                border: 1px solid #cbd5e1;
                color: #1e293b;
            }
            QMenu::item {
                padding: 6px 12px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: white;
            }
        """)

        self.calculate_btn.setObjectName("calculate_btn")
        self.clear_btn.setObjectName("clear_btn")

    def toggle_durma_inputs(self, state):
        self.durma_container.setVisible(state == Qt.Checked)

    def add_suspension_date(self):
        start_date = self.durma_baslangic_date.date().toPyDate()
        end_date = self.durma_bitis_date.date().toPyDate()

        if start_date >= end_date:
            QMessageBox.warning(self, "Uyarı", "Başlangıç tarihi bitiş tarihinden önce olmalıdır!")
            return

        date_range = f"{format_date(start_date)} - {format_date(end_date)}"

        if date_range not in [self.durma_list.item(i).text() for i in range(self.durma_list.count())]:
            self.durma_list.addItem(date_range)
            self.suspension_dates.append((start_date, end_date))
            self.suspension_dates.sort()

    def remove_suspension_date(self):
        selected_items = self.durma_list.selectedItems()
        if selected_items:
            for item in selected_items:
                row = self.durma_list.row(item)
                self.durma_list.takeItem(row)
                if row < len(self.suspension_dates):
                    self.suspension_dates.pop(row)

    def add_interruption_date(self):
        self.kesilme_container.setVisible(True)

        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        number_label = QtWidgets.QLabel("")
        number_label.setFixedWidth(22)
        number_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        date_edit = QtWidgets.QDateEdit()
        date_edit.setDisplayFormat("dd.MM.yyyy")
        date_edit.setCalendarPopup(True)
        date_edit.setDate(self.kesilme_date.date())
        date_edit.setMinimumWidth(120)

        remove_btn = QtWidgets.QPushButton("Sil")
        remove_btn.setMinimumHeight(28)
        remove_btn.setMaximumHeight(28)
        remove_btn.setMaximumWidth(52)
        remove_btn.clicked.connect(lambda _, widget=row_widget: self.remove_interruption_date(widget))

        row_layout.addWidget(number_label)
        row_layout.addWidget(date_edit, 1)
        row_layout.addWidget(remove_btn)

        self.kesilme_rows_layout.addWidget(row_widget)
        self.interruption_date_edits.append((row_widget, number_label, date_edit))
        self.renumber_interruption_dates()

    def remove_interruption_date(self, row_widget):
        for index, (widget, _, _) in enumerate(self.interruption_date_edits):
            if widget is row_widget:
                self.kesilme_rows_layout.removeWidget(widget)
                widget.deleteLater()
                self.interruption_date_edits.pop(index)
                break

        if not self.interruption_date_edits:
            self.kesilme_container.setVisible(False)

        self.renumber_interruption_dates()

    def renumber_interruption_dates(self):
        for index, (_, number_label, _) in enumerate(self.interruption_date_edits, start=2):
            number_label.setText(f"{index}.")

        self.kesilme_primary_number_label.setVisible(bool(self.interruption_date_edits))

        self.update_interruption_add_button()

    def update_interruption_add_button(self):
        next_index = len(self.interruption_date_edits) + 2
        self.kesilme_toggle_btn.setText(f"+ {next_index}. kesilme ekle")

    def show_calculation_logic(self):
        dialog = CalculationLogicDialog(self)
        dialog.exec_()

    def show_usage_guide(self):
        guide_text = """
        <h4>1. Temel Bilgiler</h4>
        <p>Bu program Türk Ceza Kanunu'nun 66. ve 67. maddelerine göre dava zamanaşımı hesaplaması yapar.</p>

        <h4>2. Veri Girişi</h4>
        <p><b>Ceza Türü:</b> Suça karşılık gelen ceza türünü seçin.</p>
        <p><b>Failin Yaşı:</b> Suç tarihindeki yaş aralığını seçin.</p>
        <p><b>Suç Tarihi:</b> Suçun işlendiği tarihi girin.</p>
        <p><b>Bugünkü Tarih:</b> Hesaplama yapılacak tarihi girin.</p>

        <h4>3. Zamanaşımının Durması</h4>
        <p>Eğer zamanaşımı durmuşsa, "Zamanaşımı durdu mu?" kutusunu işaretleyin ve durma tarih aralıklarını ekleyin.</p>

        <h4>4. Zamanaşımının Kesilmesi</h4>
        <p>İlk kesilme tarihini ana "Zamanaşımı Kesilme Tarihi" alanından girin.</p>
        <p>Birden fazla tarih varsa "+ Başka kesilme tarihi ekle" butonuna tıklayın. Her tıklamada 2., 3., 4. şeklinde yeni tarih kutuları oluşur.</p>
        <h4>5. Hesaplama</h4>
        <p>"Hesapla" butonuna tıklayarak sonuçları görüntüleyin.</p>

        <h4>6. Sonuçları Kaydetme</h4>
        <p>"Sonuçları Dışa Aktar" butonu ile hesaplama sonuçlarını dosyaya kaydedebilirsiniz.</p>
        """
        dialog = RichInfoDialog("Kullanım Kılavuzu", guide_text, self)
        dialog.exec_()

    def show_about(self):
        about_text = """
        <p><b>Sürüm:</b> 1.4</p>
        <p><b>Geliştirme Tarihi:</b> 2025</p>
        <p><b>Geliştirici:</b> İshak KOCATEPE</p>

        <h4>Amaç</h4>
        <p>Bu program, Türk Ceza Kanunu'nun 66. ve 67. maddelerine göre ceza davalarında zamanaşımı sürelerinin hesaplanması için geliştirilmiştir.</p>

        <h4>Yasal Dayanak</h4>
        <p>• TCK Madde 66: Dava zamanaşımı süreleri</p>
        <p>• TCK Madde 67: Zamanaşımının durması ve kesilmesi</p>

        <h4>Özellikler</h4>
        <p>• Çocuk fail indirimleri</p>
        <p>• Zamanaşımının durması hesaplaması</p>
        <p>• Zamanaşımının kesilmesi hesaplaması</p>
        <p>• Maksimum süre sınırlaması (1.5 katı kuralı)</p>
        <p>• Detaylı hesaplama raporu</p>

        <h4>Lisans ve Kullanım Koşulları</h4>
        <p>• Bu yazılım tamamen ücretsizdir.</p>
        <p>• Herhangi bir şekilde ticari amaçla satılamaz, ücret karşılığı dağıtılamaz.</p>
        <p>• Eğitim, kişisel kullanım ve hukuk alanında yardımcı araç olarak kullanılmak üzere geliştirilmiştir.</p>
        <p>• Uygulamanın meslektaşlar dahilinde ticari olmayan biçimde paylaşılması serbesttir, ancak güvenlik nedeniyle resmi web sitesi dışında bir yere yüklemek ve dağıtmak yasaktır.</p>
        <p>• Ayrıntılı lisans metni için LICENSE, üçüncü taraf notları için THIRD_PARTY.md dosyasına bakılmalıdır.</p>
        <p>• Kaynak kod: <a href="https://github.com/cezateknik/zmnmtk/tree/main">https://github.com/cezateknik/zmnmtk/tree/main</a></p>

        <h4>Yasal Uyarı</h4>
        <p>Bu program yalnızca bilgilendirme amaçlıdır. Kullanıcı hesaplamayı manuel doğrulamalıdır. Hesaplama hataları içerebilir. Hesaplama hatalarından doğan sorumluluk kullanıcıya aittir.</p>
        """
        dialog = RichInfoDialog("Hakkında", about_text, self, min_size=(660, 500))
        dialog.exec_()

    def show_license_dialog(self):
        dialog = LicenseDialog(self)
        dialog.exec_()

    def show_update_dialog(self):
        dialog = UpdateDialog(self)
        dialog.exec_()

    def show_update_history(self):
        dialog = UpdateHistoryDialog(self)
        dialog.exec_()

    def show_help(self):
        help_text = """
        <h4>Sık Karşılaşılan Sorunlar</h4>

        <p><b>S: Hesaplama sonucu yanlış görünüyor?</b></p>
        <p>C: Tüm tarihlerin doğru girildiğinden emin olun. Suç tarihi bugünden sonra olamaz.</p>

        <p><b>S: Durma tarihleri nasıl eklenir?</b></p>
        <p>C: "Zamanaşımı durdu mu?" kutusunu işaretleyin, başlangıç ve bitiş tarihlerini girin, "Ekle" butonuna tıklayın.</p>

        <p><b>S: Birden fazla durma dönemi ekleyebilir miyim?</b></p>
        <p>C: Evet, her durma dönemi için ayrı ayrı tarih aralığı ekleyebilirsiniz.</p>

        <p><b>S: Kesilme tarihi nasıl belirlenir?</b></p>
        <p>C: İlk tarihi ana kesilme alanına girin. Ek tarihler için "+ 2. kesilme ekle" butonuna tıklayın; yeni tarih kutuları numaralı şekilde eklenecektir.</p>

        <p><b>S: Sonuçları nasıl kaydederim?</b></p>
        <p>C: Hesaplama yaptıktan sonra "Sonuçları Dışa Aktar" butonunu kullanın.</p>

        <h4>İletişim</h4>
        <p>Daha fazla yardım, istek ve öneri için:</p>
        <p><b>Email:</b> <a href="mailto:adliyeishak@gmail.com">adliyeishak@gmail.com</a></p>
        <p><b>Web:</b> <a href="https://cezamatik.blogspot.com/">https://cezamatik.blogspot.com/</a></p>
        <p><b>GitHub:</b> <a href="https://github.com/cezateknik/zmnmtk/tree/main">https://github.com/cezateknik/zmnmtk/tree/main</a></p>

        """
        dialog = RichInfoDialog("Yardım", help_text, self, min_size=(680, 520))
        dialog.exec_()

    def get_fail_yasi(self):
        age_text = self.fail_yasi_combo.currentText()
        if age_text == "12-15 yaş arası":
            return 13
        elif age_text == "15-18 yaş arası":
            return 16
        else:
            return 18

    def get_form_data(self):
        ceza_turu = self.ceza_turu_combo.currentText()
        fail_yasi = self.get_fail_yasi()
        suc_tarihi = self.suc_tarihi_date.date().toPyDate()
        bugun = self.bugun_date.date().toPyDate()

        zamanasimi_durdu_mu = self.durma_check.isChecked()
        suspension_periods = self.suspension_dates if zamanasimi_durdu_mu else []

        kesilme_tarihleri = [self.kesilme_date.date().toPyDate()]
        if self.interruption_date_edits:
            kesilme_tarihleri.extend(date_edit.date().toPyDate() for _, _, date_edit in self.interruption_date_edits)
        kesilme_tarihleri = sorted(set(kesilme_tarihleri))

        return CaseData(
            ceza_turu=ceza_turu,
            fail_yasi=fail_yasi,
            suc_tarihi=suc_tarihi,
            bugun=bugun,
            zamanasimi_durdu_mu=zamanasimi_durdu_mu,
            suspension_periods=suspension_periods,
            kesilme_tarihleri=kesilme_tarihleri
        )

    def calculate(self):
        try:
            case_data = self.get_form_data()

            if case_data.suc_tarihi > case_data.bugun:
                QMessageBox.warning(self, "Uyarı", "Suç tarihi bugünden sonra olamaz!")
                return

            for start_date, end_date in case_data.suspension_periods:
                if start_date < case_data.suc_tarihi:
                    QMessageBox.warning(self, "Uyarı",
                        f"Durma başlangıç tarihi ({format_date(start_date)}) suç tarihinden önce olamaz!")
                    return

                if end_date <= start_date:
                    QMessageBox.warning(self, "Uyarı",
                        f"Durma bitiş tarihi ({format_date(end_date)}) başlangıç tarihinden ({format_date(start_date)}) sonra olmalıdır!")
                    return

                if end_date > case_data.bugun:
                    QMessageBox.warning(self, "Uyarı",
                        f"Durma bitiş tarihi ({format_date(end_date)}) bugünden sonra olamaz!")
                    return

            for kesilme_tarihi in case_data.kesilme_tarihleri:
                if kesilme_tarihi <= case_data.suc_tarihi:
                    QMessageBox.warning(self, "Uyarı",
                        f"Kesilme tarihi ({format_date(kesilme_tarihi)}) suç tarihinden sonra olmalıdır!")
                    return

                if kesilme_tarihi > case_data.bugun:
                    QMessageBox.warning(self, "Uyarı",
                        f"Kesilme tarihi ({format_date(kesilme_tarihi)}) bugünden sonra olamaz!")
                    return

            result = self.calculator.calculate(case_data)
            self.display_results(result, case_data)

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Hesaplama sırasında bir hata oluştu: {str(e)}")

    def display_results(self, result, case_data):
        self.result_text.clear()
        self.result_text.setHtml(result['detailed_html'])

        self.current_result = result

        is_expired = result['is_expired']
        if is_expired:
            self.final_result.setText("SONUÇ: Zamanaşımı nedeniyle kamu davası düşmüştür.")
            self.final_result.setStyleSheet("background-color: #fecaca; color: #b91c1c; padding: 15px; border-radius: 4px;")
            self.hukum_kur_btn.show()
        else:
            remaining_days = format_number(result['remaining_days'])
            self.final_result.setText(f"SONUÇ: Zamanaşımı dolmamıştır. Kalan süre: {remaining_days} gün")
            self.final_result.setStyleSheet("background-color: #bbf7d0; color: #166534; padding: 15px; border-radius: 4px;")
            self.hukum_kur_btn.hide()

    def export_results(self):
        if self.result_text.toPlainText() == "":
            QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak sonuç bulunamadı. Lütfen önce hesaplama yapın.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Sonuçları Kaydet", "", "Metin Dosyası (*.txt);;HTML Dosyası (*.html);;Tüm Dosyalar (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    if file_path.endswith('.html'):
                        file.write(self.result_text.toHtml())
                    else:
                        file.write(self.result_text.toPlainText())

                QMessageBox.information(self, "Bilgi", "Sonuçlar başarıyla dışa aktarıldı.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dışa aktarma sırasında bir hata oluştu: {str(e)}")

    def clear_form(self):
        self.ceza_turu_combo.setCurrentText("5 yıl veya daha az hapis")
        self.fail_yasi_combo.setCurrentText("18 yaş ve üzeri")
        self.suc_tarihi_date.setDate(QDate.currentDate().addYears(-1))
        self.bugun_date.setDate(QDate.currentDate())
        self.durma_check.setChecked(False)
        self.durma_baslangic_date.setDate(QDate.currentDate())
        self.durma_bitis_date.setDate(QDate.currentDate())
        self.durma_list.clear()
        self.suspension_dates = []
        self.kesilme_date.setDate(QDate.currentDate())
        while self.interruption_date_edits:
            widget, _, _ = self.interruption_date_edits.pop()
            self.kesilme_rows_layout.removeWidget(widget)
            widget.deleteLater()
        self.kesilme_container.setVisible(False)
        self.update_interruption_add_button()

        self.set_default_info_text()
        self.final_result.setText("Hesaplama sonucu burada görüntülenecek")
        self.final_result.setStyleSheet("padding: 15px; margin-top: 10px;")

        self.hukum_kur_btn.hide()
        self.current_result = None

    def generate_hukum(self):
        """Hüküm metnini üret ve yeni pencerede göster"""
        if self.current_result is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce hesaplama yapın.")
            return

        if not self.current_result['is_expired']:
            QMessageBox.warning(self, "Uyarı", "Hüküm metni sadece zamanaşımı dolmuş davalar için üretilebilir.")
            return

        case_data = self.current_result['case_data']

        judgment_text = self.calculator.generate_judgment_text(self.current_result, case_data)

        dialog = JudgmentDialog(judgment_text, self)
        dialog.exec_()


if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
