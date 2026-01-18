import sys
import random
import re
import threading
from typing import List, Set, Dict
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QTextEdit, QPushButton,
    QComboBox, QRadioButton, QGroupBox, QFrame, QMessageBox,
    QScrollArea, QGridLayout, QTreeWidget, QTreeWidgetItem,
    QDialog, QSizePolicy, QProgressBar
)
from PySide6.QtCore import (
    Qt, QSize, QThread, Signal, Slot, QTimer, QPropertyAnimation,
    QEasingCurve, QRect, QPoint
)
from PySide6.QtGui import (
    QFont, QPalette, QColor, QTextCursor, QTextCharFormat,
    QGuiApplication, QKeySequence, QShortcut, QPainter,
    QLinearGradient, QBrush, QPen, QFontMetrics, QAction
)

from grammar_online import TENSES, check_sentence, lt_online, SentenceCheckResult
from storage import load_vocab, save_vocab
from words_seed import SEED_WORDS

# ============================================================================
# Стили и цвета (аналогично tkinter версии)
# ============================================================================

class Colors:
    bg_primary = QColor("#0F172A")      # Темно-синий фон
    bg_secondary = QColor("#1E293B")    # Вторичный фон
    bg_card = QColor("#334155")         # Фон карточек
    bg_input = QColor("#475569")        # Фон полей ввода
    bg_accent = QColor("#3B82F6")       # Акцентный синий
    
    text_primary = QColor("#F1F5F9")    # Основной текст
    text_secondary = QColor("#94A3B8")  # Вторичный текст
    text_accent = QColor("#60A5FA")     # Акцентный текст
    text_success = QColor("#10B981")    # Успех (зеленый)
    text_error = QColor("#EF4444")      # Ошибка (красный)
    text_warning = QColor("#F59E0B")    # Предупреждение (желтый)

class Fonts:
    h1 = QFont("Segoe UI", 24, QFont.Weight.Bold)
    h2 = QFont("Segoe UI", 20, QFont.Weight.Bold)
    h3 = QFont("Segoe UI", 18, QFont.Weight.Bold)
    body = QFont("Segoe UI", 14)
    small = QFont("Segoe UI", 12)

# ============================================================================
# Вспомогательные функции
# ============================================================================

def _norm(s: str) -> str:
    s = str(s).strip().lower()
    s = s.replace("ё", "е")
    s = " ".join(s.split())
    return s

def _extract_variants(text: str) -> set[str]:
    s = str(text)
    s = re.sub(r"\[.*?\]|\(.*?\)", "", s)
    s = s.split(":")[0]
    s = s.replace("—", "-").replace("–", "-")
    parts = re.split(r"\s*(?:,|;|/|\||-| или | or )\s*", s, flags=re.IGNORECASE)
    return {_norm(p) for p in parts if _norm(p)}

def _ru_to_en_index(items: list) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = {}
    for it in items:
        en = _norm(it.get("en", ""))
        ru = it.get("ru", "")
        for ru_var in _extract_variants(ru):
            idx.setdefault(ru_var, set()).add(en)
    return idx

def _en_to_ru_index(items: list) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = {}
    for it in items:
        en = it.get("en", "")
        ru = it.get("ru", "")
        en_vars = _extract_variants(en)
        ru_vars = _extract_variants(ru)
        for e in en_vars:
            idx.setdefault(e, set()).update(ru_vars)
    return idx

def _card_key_words(item: dict) -> tuple[str, str, str]:
    topic = _norm(item.get("topic", "Simple words"))
    en = _norm(item.get("en", ""))
    ru = _norm(item.get("ru", ""))
    return topic, en, ru

def _word_key_sentence(item: dict) -> tuple[str, str]:
    return _norm(item.get("topic", "Simple words")), _norm(item.get("en", ""))

# ============================================================================
# Кастомные виджеты
# ============================================================================

class StyledFrame(QFrame):
    """Стилизованный фрейм с закругленными углами"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.bg_card.name()};
                border-radius: 12px;
                border: 1px solid {Colors.bg_secondary.name()};
            }}
        """)

class StyledButton(QPushButton):
    """Стилизованная кнопка"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.bg_accent.name()};
                color: {Colors.text_primary.name()};
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
            QPushButton:pressed {{
                background-color: #1d4ed8;
            }}
        """)

class FastTextEdit(QTextEdit):
    """Быстрый текстовый редактор с оптимизациями"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.bg_input.name()};
                color: {Colors.text_primary.name()};
                border: 1px solid {Colors.bg_secondary.name()};
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas';
                font-size: 13px;
                selection-background-color: {Colors.bg_accent.name()};
            }}
            QTextEdit:focus {{
                border: 2px solid {Colors.text_accent.name()};
            }}
        """)
        
        # Оптимизации для быстрого ввода
        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setTabChangesFocus(False)
        
        # Настраиваем шрифт
        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

# ============================================================================
# Основное окно приложения
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.items = load_vocab()
        self.online_status = "Checking..."
        
        self._init_ui()
        self._setup_shortcuts()
        self._check_online_status()
        
    def _init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("LinguaFlow • Learn English")
        self.setGeometry(100, 100, 1920, 1080)
        
        # Центрируем окно
        screen = QGuiApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
        # Устанавливаем стиль
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Colors.bg_primary.name()};
            }}
            QLabel {{
                color: {Colors.text_primary.name()};
            }}
        """)
        
        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Верхняя панель
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Вкладки
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Colors.bg_secondary.name()};
                background-color: {Colors.bg_primary.name()};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background-color: {Colors.bg_secondary.name()};
                color: {Colors.text_secondary.name()};
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background-color: {Colors.bg_accent.name()};
                color: {Colors.text_primary.name()};
            }}
            QTabBar::tab:hover {{
                background-color: #2d3748;
            }}
        """)
        
        # Создаем вкладки
        self.words_tab = WordsTab(self.items)
        self.sentences_tab = SentencesTab(self.items, self)
        
        self.tab_widget.addTab(self.words_tab, "📚 Vocabulary Practice")
        self.tab_widget.addTab(self.sentences_tab, "✍️ Sentence Builder")
        
        main_layout.addWidget(self.tab_widget, 1)
        
        # Футер
        footer = self._create_footer()
        main_layout.addWidget(footer)
        
    def _create_header(self):
        """Создание верхней панели"""
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        title_label = QLabel("LINGUAFLOW")
        title_label.setFont(Fonts.h1)
        title_label.setStyleSheet(f"color: {Colors.text_accent.name()};")
        
        subtitle_label = QLabel("• English Learning Platform")
        subtitle_label.setFont(Fonts.h3)
        subtitle_label.setStyleSheet(f"color: {Colors.text_secondary.name()};")
        
        title_layout = QHBoxLayout()
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch()
        
        # Статус
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        
        status_label = QLabel("LanguageTool:")
        status_label.setFont(Fonts.small)
        
        self.online_label = QLabel("Checking...")
        self.online_label.setFont(Fonts.small)
        self.online_label.setStyleSheet(f"color: {Colors.text_accent.name()};")
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.online_label)
        status_layout.addStretch()
        
        # Кнопка проверки
        self.check_conn_btn = StyledButton("⟳ Check Connection")
        self.check_conn_btn.clicked.connect(self._check_online_status)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        header_layout.addWidget(status_widget)
        header_layout.addWidget(self.check_conn_btn)
        
        return header
    
    def _create_footer(self):
        """Создание нижней панели"""
        footer = QLabel("💡 Enter = Check • Shift+Enter = New line • Ctrl+N = Next • Ctrl+R = Refresh")
        footer.setFont(Fonts.small)
        footer.setStyleSheet(f"color: {Colors.text_secondary.name()}; padding: 10px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return footer
    
    def _setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # Enter для проверки
        self.check_shortcut = QShortcut(QKeySequence("Return"), self)
        self.check_shortcut.activated.connect(self._on_check_activated)
        
        # Shift+Enter для новой строки
        self.newline_shortcut = QShortcut(QKeySequence("Shift+Return"), self)
        self.newline_shortcut.activated.connect(self._on_newline_activated)
        
        # Ctrl+N для следующего
        self.next_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.next_shortcut.activated.connect(self._on_next_activated)
        
        # Ctrl+R для обновления
        self.refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.refresh_shortcut.activated.connect(self._on_refresh_activated)
        
        # Горячие клавиши для текста
        self.select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        self.select_all_shortcut.activated.connect(self._on_select_all)
        
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self._on_undo)
        
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.redo_shortcut.activated.connect(self._on_redo)
        
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(self._on_copy)
        
        self.paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.paste_shortcut.activated.connect(self._on_paste)
        
        self.cut_shortcut = QShortcut(QKeySequence("Ctrl+X"), self)
        self.cut_shortcut.activated.connect(self._on_cut)
    
    @Slot()
    def _on_check_activated(self):
        """Обработка Enter"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab == self.words_tab:
            self.words_tab.check()
        elif current_tab == self.sentences_tab:
            self.sentences_tab.check()
    
    @Slot()
    def _on_newline_activated(self):
        """Обработка Shift+Enter"""
        # В PyQt новая строка в QTextEdit добавляется автоматически
        pass
    
    @Slot()
    def _on_next_activated(self):
        """Обработка Ctrl+N"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab == self.words_tab:
            self.words_tab.next_round()
        elif current_tab == self.sentences_tab:
            self.sentences_tab.next_words()
    
    @Slot()
    def _on_refresh_activated(self):
        """Обработка Ctrl+R"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab == self.words_tab:
            self.words_tab.reset_progress()
        elif current_tab == self.sentences_tab:
            self.sentences_tab.reset_progress()
    
    @Slot()
    def _on_select_all(self):
        """Выделить все"""
        focus_widget = self.focusWidget()
        if isinstance(focus_widget, (QTextEdit, QLineEdit)):
            focus_widget.selectAll()
    
    @Slot()
    def _on_undo(self):
        """Отменить"""
        focus_widget = self.focusWidget()
        if isinstance(focus_widget, (QTextEdit, QLineEdit)):
            if focus_widget.isUndoRedoEnabled():
                focus_widget.undo()
    
    @Slot()
    def _on_redo(self):
        """Повторить"""
        focus_widget = self.focusWidget()
        if isinstance(focus_widget, (QTextEdit, QLineEdit)):
            if focus_widget.isUndoRedoEnabled():
                focus_widget.redo()
    
    @Slot()
    def _on_copy(self):
        """Копировать"""
        focus_widget = self.focusWidget()
        if isinstance(focus_widget, (QTextEdit, QLineEdit)):
            focus_widget.copy()
    
    @Slot()
    def _on_paste(self):
        """Вставить"""
        focus_widget = self.focusWidget()
        if isinstance(focus_widget, (QTextEdit, QLineEdit)):
            focus_widget.paste()
    
    @Slot()
    def _on_cut(self):
        """Вырезать"""
        focus_widget = self.focusWidget()
        if isinstance(focus_widget, (QTextEdit, QLineEdit)):
            focus_widget.cut()
    
    def _check_online_status(self):
        """Проверка статуса подключения"""
        def check():
            ok = lt_online(timeout=2)
            status = "Online" if ok else "Offline"
            color = Colors.text_success if ok else Colors.text_error
            
            self.online_label.setText(status)
            self.online_label.setStyleSheet(f"color: {color.name()};")
            
            # Планируем следующую проверку
            QTimer.singleShot(30000, self._check_online_status)
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=check, daemon=True)
        thread.start()

# ============================================================================
# Вкладка Vocabulary Practice
# ============================================================================

class WordsTab(QWidget):
    def __init__(self, items):
        super().__init__()
        self.items = items
        self.current = []
        self.learned = set()
        self.mode = "EN_TO_RU"
        self.current_topic = "All topics"
        
        self._init_ui()
        self._refresh_stats()
        self.next_round()
    
    def _init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Панель управления
        control_group = QGroupBox("Practice Settings")
        control_group.setStyleSheet(f"""
            QGroupBox {{
                font: bold 14px;
                color: {Colors.text_accent.name()};
                border: 2px solid {Colors.bg_secondary.name()};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }}
        """)
        
        control_layout = QHBoxLayout()
        
        # Выбор темы
        topic_label = QLabel("Topic:")
        topic_label.setFont(Fonts.body)
        
        self.topic_combo = QComboBox()
        self.topic_combo.setFont(Fonts.small)
        self.topic_combo.setFixedWidth(200)
        self.topic_combo.addItems(self._topics())
        self.topic_combo.setCurrentText("All topics")
        self.topic_combo.currentTextChanged.connect(self._on_topic_changed)
        
        # Выбор режима
        mode_label = QLabel("Mode:")
        mode_label.setFont(Fonts.body)
        
        self.en_to_ru_radio = QRadioButton("EN → RU")
        self.en_to_ru_radio.setFont(Fonts.body)
        self.en_to_ru_radio.setChecked(True)
        self.en_to_ru_radio.toggled.connect(self._on_mode_changed)
        
        self.ru_to_en_radio = QRadioButton("RU → EN")
        self.ru_to_en_radio.setFont(Fonts.body)
        self.ru_to_en_radio.toggled.connect(self._on_mode_changed)
        
        # Кнопки управления
        self.refresh_btn = StyledButton("🔄 Refresh Progress")
        self.refresh_btn.clicked.connect(self.reset_progress)
        
        self.next_btn = StyledButton("⏭️ Next Set")
        self.next_btn.clicked.connect(self.next_round)
        
        control_layout.addWidget(topic_label)
        control_layout.addWidget(self.topic_combo)
        control_layout.addSpacing(20)
        control_layout.addWidget(mode_label)
        control_layout.addWidget(self.en_to_ru_radio)
        control_layout.addWidget(self.ru_to_en_radio)
        control_layout.addStretch()
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(self.next_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Статистика
        self.stats_label = QLabel()
        self.stats_label.setFont(Fonts.h3)
        self.stats_label.setStyleSheet(f"color: {Colors.text_accent.name()}; padding: 10px;")
        layout.addWidget(self.stats_label)
        
        # Карточки слов
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setSpacing(15)
        
        self.prompt_labels = []
        self.entry_edits = []
        self.result_labels = []
        
        for i in range(3):
            card = self._create_word_card(i)
            cards_layout.addWidget(card)
        
        layout.addWidget(cards_widget, 1)
        
        # Панель действий
        action_layout = QHBoxLayout()
        
        self.check_btn = StyledButton("✅ Check Answers")
        self.check_btn.clicked.connect(self.check)
        
        self.show_btn = StyledButton("👁️ Show Answers")
        self.show_btn.clicked.connect(self.show_answers)
        
        self.clear_btn = StyledButton("🗑️ Clear All")
        self.clear_btn.clicked.connect(self.clear_inputs)
        
        action_layout.addWidget(self.check_btn)
        action_layout.addWidget(self.show_btn)
        action_layout.addWidget(self.clear_btn)
        action_layout.addStretch()
        
        layout.addLayout(action_layout)
    
    def _create_word_card(self, index):
        """Создание карточки для слова"""
        card = StyledFrame()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        
        # Заголовок
        title = QLabel(f"Word {index + 1}")
        title.setFont(Fonts.h3)
        title.setStyleSheet(f"color: {Colors.text_accent.name()};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)
        
        # Промпт
        prompt_label = QLabel()
        prompt_label.setFont(Fonts.h2)
        prompt_label.setStyleSheet(f"color: {Colors.text_primary.name()};")
        prompt_label.setWordWrap(True)
        prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(prompt_label)
        self.prompt_labels.append(prompt_label)
        
        # Поле ввода
        entry = QLineEdit()
        entry.setFont(Fonts.body)
        entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.bg_input.name()};
                color: {Colors.text_primary.name()};
                border: 1px solid {Colors.bg_secondary.name()};
                border-radius: 6px;
                padding: 10px;
                font-size: 16px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Colors.text_accent.name()};
            }}
        """)
        entry.returnPressed.connect(lambda: self._check_single(index))
        card_layout.addWidget(entry)
        self.entry_edits.append(entry)
        
        # Результат
        result_label = QLabel()
        result_label.setFont(Fonts.small)
        result_label.setWordWrap(True)
        result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(result_label)
        self.result_labels.append(result_label)
        
        card_layout.addStretch()
        return card
    
    def _topics(self):
        """Получение списка тем"""
        topics = sorted({str(it.get("topic", "Simple words")) for it in self.items})
        return ["All topics"] + topics
    
    def _topic_pool_all(self):
        """Все слова в выбранной теме"""
        if self.current_topic == "All topics":
            return self.items
        return [it for it in self.items if str(it.get("topic", "Simple words")) == self.current_topic]
    
    def _topic_pool_remaining(self):
        """Оставшиеся слова в теме"""
        pool = self._topic_pool_all()
        return [it for it in pool if _card_key_words(it) not in self.learned]
    
    @Slot()
    def _on_topic_changed(self, topic):
        """Обработка изменения темы"""
        self.current_topic = topic
        self._refresh_stats()
        self.next_round()
    
    @Slot()
    def _on_mode_changed(self):
        """Обработка изменения режима"""
        if self.en_to_ru_radio.isChecked():
            self.mode = "EN_TO_RU"
        else:
            self.mode = "RU_TO_EN"
        self.next_round()
    
    def _refresh_stats(self):
        """Обновление статистики"""
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        progress = (done / total * 100) if total > 0 else 0
        
        self.stats_label.setText(
            f"📊 Topic: {self.current_topic} • "
            f"Total: {total} • "
            f"Learned: {done} • "
            f"Remaining: {remaining} • "
            f"Progress: {progress:.1f}%"
        )
    
    def _get_prompt_and_expected(self, item):
        """Получение промпта и ожидаемого ответа"""
        en = item.get("en", "")
        ru = item.get("ru", "")
        return (en, ru) if self.mode == "EN_TO_RU" else (ru, en)
    
    @Slot()
    def next_round(self):
        """Следующий раунд"""
        pool = self._topic_pool_remaining()
        self._refresh_stats()
        
        if len(pool) == 0:
            for i in range(3):
                self.prompt_labels[i].setText("🎉 Congratulations!")
                self.entry_edits[i].clear()
                self.result_labels[i].setText("You've completed all words in this topic!")
                self.result_labels[i].setStyleSheet(f"color: {Colors.text_success.name()};")
            return
        
        take = min(3, len(pool))
        self.current = random.sample(pool, take)
        
        for i in range(3):
            if i < take:
                prompt, _ = self._get_prompt_and_expected(self.current[i])
                self.prompt_labels[i].setText(prompt)
                self.entry_edits[i].clear()
                self.result_labels[i].clear()
                self.result_labels[i].setStyleSheet("")
            else:
                self.prompt_labels[i].clear()
                self.entry_edits[i].clear()
                self.result_labels[i].clear()
    
    @Slot()
    def clear_inputs(self):
        """Очистка всех полей ввода"""
        for entry in self.entry_edits:
            entry.clear()
        for label in self.result_labels:
            label.clear()
            label.setStyleSheet("")
    
    @Slot()
    def show_answers(self):
        """Показать ответы"""
        for i in range(3):
            if i >= len(self.current):
                continue
            _, expected = self._get_prompt_and_expected(self.current[i])
            self.result_labels[i].setText(f"✅ Answer: {expected}")
            self.result_labels[i].setStyleSheet(f"color: {Colors.text_success.name()};")
    
    def _check_single(self, idx):
        """Проверка одного слова"""
        if idx >= len(self.current):
            return
        
        item = self.current[idx]
        prompt = self.prompt_labels[idx].text()
        _, expected = self._get_prompt_and_expected(item)
        user = self.entry_edits[idx].text()
        
        user_norm = _norm(user)
        expected_variants = _extract_variants(expected)
        ok = user_norm in expected_variants
        
        if ok:
            self.result_labels[idx].setText("✅ Correct!")
            self.result_labels[idx].setStyleSheet(f"color: {Colors.text_success.name()};")
            self.learned.add(_card_key_words(item))
            self._refresh_stats()
        else:
            self.result_labels[idx].setText("❌ Try again")
            self.result_labels[idx].setStyleSheet(f"color: {Colors.text_error.name()};")
    
    @Slot()
    def check(self):
        """Проверка всех слов"""
        if not self.current:
            return
        
        ru_index = _ru_to_en_index(self.items)
        en_index = _en_to_ru_index(self.items)
        
        for i in range(3):
            if i >= len(self.current):
                continue
            
            item = self.current[i]
            prompt = self.prompt_labels[i].text()
            _, expected = self._get_prompt_and_expected(item)
            user = self.entry_edits[i].text()
            
            user_norm = _norm(user)
            expected_variants = _extract_variants(expected)
            ok = user_norm in expected_variants
            
            if not ok:
                if self.mode == "RU_TO_EN":
                    poss_en = set()
                    for ru_v in _extract_variants(prompt):
                        poss_en |= ru_index.get(ru_v, set())
                    ok = user_norm in poss_en
                elif self.mode == "EN_TO_RU":
                    poss_ru = set()
                    for en_v in _extract_variants(prompt):
                        poss_ru |= en_index.get(en_v, set())
                    ok = user_norm in poss_ru
            
            if ok:
                self.result_labels[i].setText("✅ Correct!")
                self.result_labels[i].setStyleSheet(f"color: {Colors.text_success.name()};")
                self.learned.add(_card_key_words(item))
            else:
                self.result_labels[i].setText("❌ Incorrect - try again")
                self.result_labels[i].setStyleSheet(f"color: {Colors.text_error.name()};")
        
        self._refresh_stats()
    
    @Slot()
    def reset_progress(self):
        """Сброс прогресса"""
        self.learned.clear()
        self._refresh_stats()
        self.next_round()
        QMessageBox.information(self, "Progress Reset", "Your progress has been reset!")

# ============================================================================
# Вкладка Sentence Builder
# ============================================================================

class SentencesTab(QWidget):
    def __init__(self, items, main_window):
        super().__init__()
        self.items = items
        self.main_window = main_window
        self.current_words = []
        self.used_words = set()
        self.current_topic = "All topics"
        self.current_tense = TENSES[0]
        self.last_matches = [[] for _ in range(5)]
        
        self._init_ui()
        self._refresh_stats()
        QTimer.singleShot(50, self.next_words)
    
    def _init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Панель управления
        control_group = QGroupBox("Sentence Builder Settings")
        control_group.setStyleSheet(f"""
            QGroupBox {{
                font: bold 14px;
                color: {Colors.text_accent.name()};
                border: 2px solid {Colors.bg_secondary.name()};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }}
        """)
        
        control_layout = QHBoxLayout()
        
        # Выбор темы
        topic_label = QLabel("Topic:")
        topic_label.setFont(Fonts.body)
        
        self.topic_combo = QComboBox()
        self.topic_combo.setFont(Fonts.small)
        self.topic_combo.setFixedWidth(200)
        self.topic_combo.addItems(self._topics())
        self.topic_combo.setCurrentText("All topics")
        self.topic_combo.currentTextChanged.connect(self._on_topic_changed)
        
        # Выбор времени
        tense_label = QLabel("Tense:")
        tense_label.setFont(Fonts.body)
        
        self.tense_combo = QComboBox()
        self.tense_combo.setFont(Fonts.small)
        self.tense_combo.setFixedWidth(200)
        self.tense_combo.addItems(TENSES)
        self.tense_combo.currentTextChanged.connect(self._on_tense_changed)
        
        # Кнопки управления
        self.refresh_btn = StyledButton("🔄 Refresh Progress")
        self.refresh_btn.clicked.connect(self.reset_progress)
        
        self.next_btn = StyledButton("⏭️ Next 5 Words")
        self.next_btn.clicked.connect(self.next_words)
        
        control_layout.addWidget(topic_label)
        control_layout.addWidget(self.topic_combo)
        control_layout.addSpacing(20)
        control_layout.addWidget(tense_label)
        control_layout.addWidget(self.tense_combo)
        control_layout.addStretch()
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(self.next_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Статистика
        self.stats_label = QLabel()
        self.stats_label.setFont(Fonts.h3)
        self.stats_label.setStyleSheet(f"color: {Colors.text_accent.name()}; padding: 10px;")
        layout.addWidget(self.stats_label)
        
        # Карточки для предложений
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(15)
        
        self.word_labels = []
        self.text_edits = []
        self.result_labels = []
        
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2)]
        
        for i, (row, col) in enumerate(positions):
            card = self._create_sentence_card(i)
            grid_layout.addWidget(card, row, col)
        
        layout.addWidget(grid_widget, 1)
        
        # Панель действий
        action_layout = QHBoxLayout()
        
        self.check_btn = StyledButton("✅ Check Sentences")
        self.check_btn.clicked.connect(self.check)
        
        self.details_btn = StyledButton("📊 Show Details")
        self.details_btn.clicked.connect(self.show_details)
        
        self.clear_btn = StyledButton("🗑️ Clear All")
        self.clear_btn.clicked.connect(self.clear_inputs)
        
        action_layout.addWidget(self.check_btn)
        action_layout.addWidget(self.details_btn)
        action_layout.addWidget(self.clear_btn)
        action_layout.addStretch()
        
        layout.addLayout(action_layout)
    
    def _create_sentence_card(self, index):
        """Создание карточки для предложения"""
        card = StyledFrame()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        
        # Заголовок
        title = QLabel(f"Sentence {index + 1}")
        title.setFont(Fonts.h3)
        title.setStyleSheet(f"color: {Colors.text_accent.name()};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)
        
        # Слово
        word_label = QLabel()
        word_label.setFont(Fonts.h2)
        word_label.setStyleSheet(f"color: {Colors.text_primary.name()};")
        word_label.setWordWrap(True)
        word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(word_label)
        self.word_labels.append(word_label)
        
        # Инструкция
        instruction = QLabel("Write a sentence using this word:")
        instruction.setFont(Fonts.small)
        instruction.setStyleSheet(f"color: {Colors.text_secondary.name()};")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(instruction)
        
        # Текстовое поле
        text_edit = FastTextEdit()
        text_edit.setMaximumHeight(120)
        card_layout.addWidget(text_edit)
        self.text_edits.append(text_edit)
        
        # Результат
        result_label = QLabel()
        result_label.setFont(Fonts.small)
        result_label.setWordWrap(True)
        result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(result_label)
        self.result_labels.append(result_label)
        
        card_layout.addStretch()
        return card
    
    def _topics(self):
        """Получение списка тем"""
        topics = sorted({str(it.get("topic", "Simple words")) for it in self.items})
        return ["All topics"] + topics
    
    def _topic_pool_all(self):
        """Все слова в выбранной теме"""
        if self.current_topic == "All topics":
            return self.items
        return [it for it in self.items if str(it.get("topic", "Simple words")) == self.current_topic]
    
    def _topic_pool_remaining(self):
        """Оставшиеся слова в теме"""
        pool = self._topic_pool_all()
        return [it for it in pool if _word_key_sentence(it) not in self.used_words]
    
    @Slot()
    def _on_topic_changed(self, topic):
        """Обработка изменения темы"""
        self.current_topic = topic
        self._refresh_stats()
        self.next_words()
    
    @Slot()
    def _on_tense_changed(self, tense):
        """Обработка изменения времени"""
        self.current_tense = tense
    
    def _refresh_stats(self):
        """Обновление статистики"""
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        progress = (done / total * 100) if total > 0 else 0
        
        self.stats_label.setText(
            f"📊 Topic: {self.current_topic} • "
            f"Total: {total} • "
            f"Practiced: {done} • "
            f"Remaining: {remaining} • "
            f"Progress: {progress:.1f}%"
        )
    
    @Slot()
    def next_words(self):
        """Следующий набор слов"""
        pool = self._topic_pool_remaining()
        self._refresh_stats()
        
        if len(pool) == 0:
            for i in range(5):
                self.word_labels[i].setText("🎉 Congratulations!")
                self.result_labels[i].setText("You've practiced all words in this topic!")
                self.result_labels[i].setStyleSheet(f"color: {Colors.text_success.name()};")
                self.text_edits[i].clear()
            return
        
        take = min(5, len(pool))
        self.current_words = random.sample(pool, take)
        
        for i in range(5):
            if i < take:
                self.word_labels[i].setText(self.current_words[i].get("en", ""))
                self.result_labels[i].clear()
                self.result_labels[i].setStyleSheet("")
            else:
                self.word_labels[i].clear()
                self.result_labels[i].clear()
            
            self.text_edits[i].clear()
        
        # Фокус на первый текстовый редактор
        if self.text_edits:
            self.text_edits[0].setFocus()
    
    @Slot()
    def clear_inputs(self):
        """Очистка всех полей ввода"""
        for text_edit in self.text_edits:
            text_edit.clear()
        for label in self.result_labels:
            label.clear()
            label.setStyleSheet("")
        
        # Фокус на первый редактор
        if self.text_edits:
            self.text_edits[0].setFocus()
    
    @Slot()
    def check(self):
        """Проверка предложений"""
        if not self.current_words:
            return
        
        # Проверка онлайн-статуса
        if self.main_window.online_label.text() != "Online":
            QMessageBox.warning(self, "Offline", "Grammar check requires internet connection.")
            return
        
        tense = self.current_tense.strip() or TENSES[0]
        
        words, sentences, idx_map = [], [], []
        for i in range(5):
            if i >= len(self.current_words):
                continue
            word = self.current_words[i].get("en", "")
            sentence = self.text_edits[i].toPlainText().strip()
            words.append(word)
            sentences.append(sentence)
            idx_map.append(i)
        
        # Визуальная обратная связь
        self.check_btn.setText("Checking...")
        self.check_btn.setEnabled(False)
        
        def worker():
            results = []
            for k, sentence in enumerate(sentences):
                if not sentence:
                    results.append((False, "Please write a sentence", [], False))
                    continue
                try:
                    res = check_sentence(
                        sentence=sentence,
                        required_word=words[k],
                        tense=tense
                    )
                    results.append((True, res.message, res.matches or [], res.ok))
                except Exception as e:
                    results.append((False, f"Error: {str(e)[:50]}", [], False))
            
            # Возвращаемся в главный поток для обновления UI
            self._apply_check_results(idx_map, results)
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def _apply_check_results(self, idx_map, results):
        """Применение результатов проверки"""
        self.check_btn.setText("✅ Check Sentences")
        self.check_btn.setEnabled(True)
        
        for pos, (_has, msg, matches, ok) in zip(idx_map, results):
            self.last_matches[pos] = matches or []
            
            if ok:
                self.result_labels[pos].setText("✅ Perfect! All checks passed.")
                self.result_labels[pos].setStyleSheet(f"color: {Colors.text_success.name()};")
                self.used_words.add(_word_key_sentence(self.current_words[pos]))
            else:
                self.result_labels[pos].setText(f"📝 {msg[:100]}")
                self.result_labels[pos].setStyleSheet(f"color: {Colors.text_warning.name()};")
        
        self._refresh_stats()
    
    @Slot()
    def show_details(self):
        """Показать детали проверки"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Grammar Check Details")
        dialog.setGeometry(100, 100, 1000, 600)
        
        layout = QVBoxLayout(dialog)
        
        title = QLabel("Grammar Check Details")
        title.setFont(Fonts.h2)
        title.setStyleSheet(f"color: {Colors.text_accent.name()};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Each row shows one grammar suggestion from LanguageTool")
        subtitle.setFont(Fonts.small)
        subtitle.setStyleSheet(f"color: {Colors.text_secondary.name()};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        # Таблица с результатами
        tree = QTreeWidget()
        tree.setHeaderLabels(["Slot", "Word", "Issue", "Message", "Suggestion"])
        tree.setColumnWidth(0, 60)
        tree.setColumnWidth(1, 120)
        tree.setColumnWidth(2, 200)
        tree.setColumnWidth(3, 400)
        tree.setColumnWidth(4, 300)
        
        has_issues = False
        for i in range(5):
            word = self.word_labels[i].text()
            matches = self.last_matches[i] if i < len(self.last_matches) else []
            
            for m in matches:
                has_issues = True
                rule_obj = m.get("rule", {}) or {}
                rule_id = rule_obj.get("id", "")
                message = m.get("message", "")
                
                repls = m.get("replacements", []) or []
                suggestions = ", ".join([r.get("value", "") for r in repls[:3]])
                
                item = QTreeWidgetItem([
                    str(i + 1),
                    word[:20],
                    rule_id[:30],
                    message[:80],
                    suggestions[:50]
                ])
                tree.addTopLevelItem(item)
        
        if not has_issues:
            no_issues_label = QLabel("No grammar issues found! Great job! 🎉")
            no_issues_label.setFont(Fonts.body)
            no_issues_label.setStyleSheet(f"color: {Colors.text_success.name()};")
            no_issues_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_issues_label)
        else:
            layout.addWidget(tree)
        
        close_btn = StyledButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    @Slot()
    def reset_progress(self):
        """Сброс прогресса"""
        self.used_words.clear()
        self._refresh_stats()
        self.next_words()
        QMessageBox.information(self, "Progress Reset", "Your sentence practice has been reset!")

# ============================================================================
# Точка входа
# ============================================================================

def ensure_seed():
    """Обеспечить наличие начальных слов"""
    items = load_vocab()
    if items:
        return
    save_vocab(SEED_WORDS)

def main():
    """Главная функция"""
    ensure_seed()
    
    app = QApplication(sys.argv)
    app.setApplicationName("LinguaFlow")
    app.setOrganizationName("LinguaFlow")
    
    # Настройка стиля приложения
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()