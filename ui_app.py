import random
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import sv_ttk

from storage import load_vocab, save_vocab
from grammar_online import TENSES, check_sentence, lt_online

# --- Современная цветовая палитра ---
COLORS = {
    "bg_primary": "#0F172A",
    "bg_secondary": "#1E293B",
    "bg_card": "#334155",
    "bg_input": "#475569",
    "bg_accent": "#3B82F6",
    "text_primary": "#F1F5F9",
    "text_secondary": "#94A3B8",
    "text_accent": "#60A5FA",
    "text_success": "#10B981",
    "text_error": "#EF4444",
    "text_warning": "#F59E0B",
}

FONTS = {
    "h1": ("SF Pro Display", 28, "bold"),
    "h2": ("SF Pro Display", 22, "bold"),
    "h3": ("SF Pro Display", 18, "bold"),
    "body": ("SF Pro Text", 14),
    "small": ("SF Pro Text", 12),
}

class UltraFastText(tk.Text):
    """Сверхбыстрый текстовый виджет с оптимизациями"""
    def __init__(self, *args, **kwargs):
        # Минимальные настройки для максимальной скорости
        kwargs.setdefault('wrap', 'word')
        kwargs.setdefault('height', 3)
        kwargs.setdefault('font', ("Menlo", 12))  # Моноширинный шрифт Mac
        kwargs.setdefault('bg', COLORS["bg_input"])
        kwargs.setdefault('fg', COLORS["text_primary"])
        kwargs.setdefault('insertbackground', COLORS["text_accent"])
        kwargs.setdefault('selectbackground', COLORS["bg_accent"])
        kwargs.setdefault('selectforeground', COLORS["text_primary"])
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('borderwidth', 1)
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightcolor', COLORS["text_accent"])
        kwargs.setdefault('highlightbackground', COLORS["bg_input"])
        kwargs.setdefault('padx', 10)
        kwargs.setdefault('pady', 8)
        kwargs.setdefault('undo', True)
        kwargs.setdefault('maxundo', 100)
        kwargs.setdefault('autoseparators', True)
        kwargs.setdefault('cursor', 'ibeam')
        
        super().__init__(*args, **kwargs)
        
        # Оптимизация для macOS
        self.configure(
            insertwidth=2,
            insertborderwidth=0,
            insertofftime=0,  # Убираем мерцание курсора
            insertontime=600,
            selectborderwidth=0,
            inactiveselectbackground=COLORS["bg_input"],
            exportselection=True,
            takefocus=True,
            spacing1=0,
            spacing2=0,
            spacing3=0,
            tabs=(28, 56, 84),
            xscrollcommand=lambda *args: None,  # Отключаем горизонтальную прокрутку
        )
        
        # Минимальные теги
        self.tag_configure("sel", 
                          background=COLORS["bg_accent"],
                          foreground=COLORS["text_primary"],
                          borderwidth=0)
        
        # Связываем горячие клавиши Mac
        self._bind_mac_shortcuts()
    
    def _bind_mac_shortcuts(self):
        """Привязка горячих клавиш для Mac (английская и русская раскладки)"""
        # Английская раскладка
        self.bind("<Command-Key-a>", self.select_all)
        self.bind("<Command-Key-A>", self.select_all)
        self.bind("<Command-Key-z>", self.undo)
        self.bind("<Command-Key-Z>", self.undo)
        self.bind("<Command-Shift-Z>", self.redo)
        self.bind("<Command-Shift-z>", self.redo)
        self.bind("<Command-Key-c>", lambda e: self.event_generate("<<Copy>>"))
        self.bind("<Command-Key-C>", lambda e: self.event_generate("<<Copy>>"))
        self.bind("<Command-Key-v>", lambda e: self.event_generate("<<Paste>>"))
        self.bind("<Command-Key-V>", lambda e: self.event_generate("<<Paste>>"))
        self.bind("<Command-Key-x>", lambda e: self.event_generate("<<Cut>>"))
        self.bind("<Command-Key-X>", lambda e: self.event_generate("<<Cut>>"))
        
        # Универсальный обработчик для русской раскладки
        self.bind("<Command-KeyPress>", self._handle_mac_shortcut)
        
        # Отключаем стандартные биндинги, которые могут замедлять
        self.unbind("<Key>")
        self.unbind("<KeyPress>")
        self.unbind("<KeyRelease>")
        
        # Свой быстрый обработчик клавиш
        self.bind("<Key>", self._fast_key_handler, add=True)
    
    def _handle_mac_shortcut(self, event):
        """Обработчик комбинаций Cmd+клавиша для русской раскладки"""
        # Получаем символ нажатой клавиши
        char = event.char.lower()
        
        # Русская раскладка:
        if char == 'ф':  # Ф = A (выделить все)
            self.select_all()
            return "break"
        elif char == 'я':  # Я = Z
            if event.state & 0x0001:  # Shift нажат
                self.redo()
            else:
                self.undo()
            return "break"
        elif char == 'с':  # С = C (копировать)
            self.event_generate("<<Copy>>")
            return "break"
        elif char == 'м':  # М = V (вставить)
            self.event_generate("<<Paste>>")
            return "break"
        elif char == 'ч':  # Ч = X (вырезать)
            self.event_generate("<<Cut>>")
            return "break"
        
        # Если не русская раскладка, обрабатываем стандартно
        return None
    
    def _fast_key_handler(self, event):
        """Быстрый обработчик клавиш"""
        # Пропускаем системные комбинации
        if event.state & 0x0004:  # Control
            return
        if event.state & 0x0008:  # Meta (Cmd)
            # Уже обработано в _handle_mac_shortcut
            return "break"
        if event.state & 0x0001:  # Shift
            if event.keysym == "Return":
                self.insert("insert", "\n")
                return "break"
        
        # Enter без Shift - проверка
        if event.keysym == "Return" and not event.state & 0x0001:
            # Вызываем проверку через родительский виджет
            root = self.winfo_toplevel()
            root.event_generate("<<CheckSentences>>")
            return "break"
        
        # Все остальные клавиши обрабатываем стандартно
        return None
    
    def select_all(self, event=None):
        """Выделить весь текст"""
        self.tag_add("sel", "1.0", "end")
        return "break"
    
    def undo(self, event=None):
        """Отменить"""
        try:
            self.edit_undo()
        except:
            pass
        return "break"
    
    def redo(self, event=None):
        """Повторить"""
        try:
            self.edit_redo()
        except:
            pass
        return "break"
    
    def fast_insert(self, text):
        """Быстрая вставка текста"""
        self.insert("insert", text)
        # Автопрокрутка вниз
        self.see("insert")

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

def _ru_to_en_index(items: list[dict]) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = {}
    for it in items:
        en = _norm(it.get("en", ""))
        ru = it.get("ru", "")
        for ru_var in _extract_variants(ru):
            idx.setdefault(ru_var, set()).add(en)
    return idx

def _en_to_ru_index(items: list[dict]) -> dict[str, set[str]]:
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

class MainApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.master = master
        
        # Настройка окна для 1920x1080
        self.master.title("LinguaFlow • Learn English")
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        
        # Если экран меньше 1920x1080, используем масштабирование
        if screen_width >= 1920 and screen_height >= 1080:
            self.master.geometry("1920x1080")
        else:
            # Масштабируем под доступный размер
            width = min(screen_width - 100, 1920)
            height = min(screen_height - 100, 1080)
            self.master.geometry(f"{width}x{height}")
        
        # Центрируем окно
        x = (screen_width - self.master.winfo_reqwidth()) // 2
        y = (screen_height - self.master.winfo_reqheight()) // 2
        self.master.geometry(f"+{x}+{y}")
        
        # Минимальный размер
        self.master.minsize(1400, 800)
        
        # Отключаем ненужные обновления
        self.master.update_idletasks()
        
        self.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Загружаем данные
        self.items = load_vocab()
        for it in self.items:
            if "topic" not in it or not str(it["topic"]).strip():
                it["topic"] = "Simple words"
        
        # Построение UI
        self._build_ui()
        self._bind_keys()
        
        # Проверка статуса
        self.master.after(100, self._check_online_status)
    
    def _build_ui(self):
        """Построение интерфейса"""
        # Верхняя панель
        header = ttk.Frame(self)
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        # Заголовок
        title_frame = ttk.Frame(header)
        title_frame.pack(side="left")
        
        ttk.Label(
            title_frame,
            text="LINGUAFLOW",
            font=FONTS["h1"],
            foreground=COLORS["text_accent"]
        ).pack(side="left")
        
        ttk.Label(
            title_frame,
            text=" • English Learning Platform",
            font=FONTS["h3"],
            foreground=COLORS["text_secondary"]
        ).pack(side="left", padx=(10, 0))
        
        # Статус
        status_frame = ttk.Frame(header)
        status_frame.pack(side="right")
        
        ttk.Label(
            status_frame,
            text="LanguageTool:",
            font=FONTS["small"]
        ).pack(side="left")
        
        self.online_var = tk.StringVar(value="Checking...")
        ttk.Label(
            status_frame,
            textvariable=self.online_var,
            font=FONTS["small"],
            foreground=COLORS["text_accent"]
        ).pack(side="left", padx=(5, 0))
        
        # Вкладки
        self._build_tabs()
        
        # Футер
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=20, pady=(5, 15))
        
        ttk.Label(
            footer,
            text="💡 Enter = Check • Shift+Enter = New line",
            font=FONTS["small"],
            foreground=COLORS["text_secondary"]
        ).pack()
    
    def _build_tabs(self):
        """Создание вкладок"""
        # Стилизованный Notebook
        style = ttk.Style()
        style.configure("Custom.TNotebook", background=COLORS["bg_primary"])
        style.configure("Custom.TNotebook.Tab", 
                       padding=(20, 10),
                       font=FONTS["body"])
        
        self.nb = ttk.Notebook(self, style="Custom.TNotebook")
        self.nb.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        # Создаем вкладки
        self.tab_words = WordsTab(self.nb, self.items)
        self.tab_sentences = SentencesTab(self.nb, self.items, self.online_var)
        
        # Добавляем вкладки
        self.nb.add(self.tab_words, text="📚 Vocabulary Practice")
        self.nb.add(self.tab_sentences, text="✍️ Sentence Builder")
        
        # Событие для проверки предложений
        self.nb.bind("<<CheckSentences>>", lambda e: self.tab_sentences.check())
    
    def _bind_keys(self):
        """Глобальные горячие клавиши"""
        # Enter для текущей активной вкладки
        self.master.bind("<Return>", self._on_enter)
        
        # Универсальные горячие клавиши
        self.master.bind("<Command-KeyPress>", self._handle_global_mac_shortcut)
        self.master.bind("<Control-KeyPress>", self._handle_global_ctrl_shortcut)
    
    def _handle_global_mac_shortcut(self, event):
        """Глобальная обработка горячих клавиш с Cmd"""
        char = event.char.lower()
        
        # Русская раскладка:
        if char == 'т':  # Т = N (Next)
            self._next_item()
            return "break"
        elif char == 'к':  # К = R (Refresh)
            self._refresh()
            return "break"
        elif char == 'н':  # Н = Y (в английской нет аналога, но для примера)
            pass
        # Английская раскладка уже обрабатывается через стандартные биндинги
        
        return None
    
    def _handle_global_ctrl_shortcut(self, event):
        """Глобальная обработка горячих клавиш с Ctrl (Windows/Linux)"""
        char = event.char.lower()
        
        if char == 'n':  # Ctrl+N
            self._next_item()
            return "break"
        elif char == 'r':  # Ctrl+R
            self._refresh()
            return "break"
        
        return None
    
    def _on_enter(self, event=None):
        """Обработка Enter"""
        if event and event.state & 0x0001:  # Shift нажат
            return
        
        idx = self.nb.index("current")
        if idx == 0:
            self.tab_words.check()
        elif idx == 1:
            self.tab_sentences.check()
    
    def _next_item(self):
        """Следующий элемент"""
        idx = self.nb.index("current")
        if idx == 0:
            self.tab_words.next_round()
        elif idx == 1:
            self.tab_sentences.next_words()
    
    def _refresh(self):
        """Обновить"""
        idx = self.nb.index("current")
        if idx == 0:
            self.tab_words.reset_progress()
        elif idx == 1:
            self.tab_sentences.reset_progress()
    
    def _check_online_status(self):
        """Проверка статуса подключения"""
        def check():
            ok = lt_online(timeout=2)
            status = "Online" if ok else "Offline"
            self.online_var.set(status)
            self.master.after(30000, self._check_online_status)
        
        threading.Thread(target=check, daemon=True).start()

class WordsTab(ttk.Frame):
    def __init__(self, master, items: list[dict]):
        super().__init__(master)
        self.items = items
        
        self.current: list[dict] = []
        self.mode = tk.StringVar(value="EN_TO_RU")
        self.topic_var = tk.StringVar(value="All topics")
        self.learned: set[tuple[str, str, str]] = set()
        
        self._build_ui()
        self._refresh_stats()
        self.next_round()
    
    def _topics(self) -> list[str]:
        topics = sorted({str(it.get("topic", "Simple words")) for it in self.items})
        return ["All topics"] + topics
    
    def _topic_pool_all(self) -> list[dict]:
        sel = self.topic_var.get()
        if sel == "All topics":
            return self.items
        return [it for it in self.items if str(it.get("topic", "Simple words")) == sel]
    
    def _topic_pool_remaining(self) -> list[dict]:
        pool = self._topic_pool_all()
        return [it for it in pool if _card_key_words(it) not in self.learned]
    
    def reset_progress(self):
        self.learned.clear()
        self._refresh_stats()
        self.next_round()
        messagebox.showinfo("Progress Reset", "Your progress has been reset!")
    
    def _build_ui(self):
        """Построение интерфейса для слов"""
        # Панель управления
        control_frame = ttk.LabelFrame(self, text="Practice Settings", padding=15)
        control_frame.pack(fill="x", padx=20, pady=(10, 15))
        
        # Тема
        ttk.Label(control_frame, text="Topic:", font=FONTS["body"]).grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        self.topic_combo = ttk.Combobox(
            control_frame,
            textvariable=self.topic_var,
            state="readonly",
            width=30,
            font=FONTS["body"]
        )
        self.topic_combo["values"] = self._topics()
        self.topic_combo.grid(row=0, column=1, padx=(0, 30))
        self.topic_combo.bind("<<ComboboxSelected>>", lambda e: self.next_round())
        
        # Режим
        ttk.Label(control_frame, text="Mode:", font=FONTS["body"]).grid(row=0, column=2, sticky="w", padx=(30, 10))
        
        mode_frame = ttk.Frame(control_frame)
        mode_frame.grid(row=0, column=3)
        
        ttk.Radiobutton(
            mode_frame,
            text="EN → RU",
            variable=self.mode,
            value="EN_TO_RU",
            command=self.next_round,
            style="TRadiobutton"
        ).pack(side="left", padx=(0, 15))
        
        ttk.Radiobutton(
            mode_frame,
            text="RU → EN",
            variable=self.mode,
            value="RU_TO_EN",
            command=self.next_round,
            style="TRadiobutton"
        ).pack(side="left")
        
        # Кнопки
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=0, column=4, padx=(30, 0))
        
        ttk.Button(
            btn_frame,
            text="🔄 Refresh Progress",
            command=self.reset_progress,
            padding=(12, 8)
        ).pack(side="left", padx=(0, 10))
        
        ttk.Button(
            btn_frame,
            text="⏭️ Next Set",
            command=self.next_round,
            padding=(12, 8)
        ).pack(side="left")
        
        # Статистика
        self.stats_var = tk.StringVar(value="Loading statistics...")
        stats_label = ttk.Label(
            self,
            textvariable=self.stats_var,
            font=FONTS["h2"],
            foreground=COLORS["text_accent"]
        )
        stats_label.pack(anchor="w", padx=25, pady=(10, 15))
        
        # Карточки
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.prompt_vars = [tk.StringVar() for _ in range(3)]
        self.entry_vars = [tk.StringVar() for _ in range(3)]
        self.result_vars = [tk.StringVar() for _ in range(3)]
        
        # Создаем 3 карточки
        for i in range(3):
            card = ttk.LabelFrame(cards_frame, text=f"Word {i+1}", padding=20)
            card.pack(side="left", fill="both", expand=True, padx=10)
            
            # Промпт
            ttk.Label(
                card,
                textvariable=self.prompt_vars[i],
                font=FONTS["h2"],
                wraplength=400,
                foreground=COLORS["text_primary"]
            ).pack(anchor="w", pady=(0, 15))
            
            # Поле ввода
            entry_frame = ttk.Frame(card)
            entry_frame.pack(fill="x", pady=(0, 10))
            
            entry = ttk.Entry(
                entry_frame,
                textvariable=self.entry_vars[i],
                font=FONTS["body"]
            )
            entry.pack(fill="x", ipady=10)
            
            # Привязываем Enter для быстрой проверки
            entry.bind("<Return>", lambda e, idx=i: self._check_single(idx))
            
            # Горячие клавиши для Entry
            self._bind_entry_shortcuts(entry)
            
            # Результат
            ttk.Label(
                card,
                textvariable=self.result_vars[i],
                font=FONTS["body"],
                wraplength=400,
                foreground=COLORS["text_secondary"]
            ).pack(anchor="w")
        
        # Панель действий
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        ttk.Button(
            action_frame,
            text="✅ Check Answers",
            command=self.check,
            padding=(15, 10)
        ).pack(side="left", padx=(0, 10))
        
        ttk.Button(
            action_frame,
            text="👁️ Show Answers",
            command=self.show_answers,
            padding=(15, 10)
        ).pack(side="left", padx=(0, 10))
        
        ttk.Button(
            action_frame,
            text="🗑️ Clear All",
            command=self.clear_inputs,
            padding=(15, 10)
        ).pack(side="left")
    
    def _bind_entry_shortcuts(self, entry):
        """Привязка горячих клавиш для Entry"""
        # Английская раскладка
        entry.bind("<Command-Key-a>", lambda e: e.widget.select_range(0, tk.END))
        entry.bind("<Command-Key-A>", lambda e: e.widget.select_range(0, tk.END))
        entry.bind("<Command-Key-c>", lambda e: e.widget.event_generate("<<Copy>>"))
        entry.bind("<Command-Key-C>", lambda e: e.widget.event_generate("<<Copy>>"))
        entry.bind("<Command-Key-v>", lambda e: e.widget.event_generate("<<Paste>>"))
        entry.bind("<Command-Key-V>", lambda e: e.widget.event_generate("<<Paste>>"))
        entry.bind("<Command-Key-x>", lambda e: e.widget.event_generate("<<Cut>>"))
        entry.bind("<Command-Key-X>", lambda e: e.widget.event_generate("<<Cut>>"))
        
        # Русская раскладка
        entry.bind("<Command-KeyPress>", self._handle_entry_mac_shortcut)
    
    def _handle_entry_mac_shortcut(self, event):
        """Обработчик горячих клавиш для Entry с русской раскладкой"""
        widget = event.widget
        char = event.char.lower()
        
        if char == 'ф':  # Ф = A (выделить все)
            widget.select_range(0, tk.END)
            return "break"
        elif char == 'с':  # С = C (копировать)
            widget.event_generate("<<Copy>>")
            return "break"
        elif char == 'м':  # М = V (вставить)
            widget.event_generate("<<Paste>>")
            return "break"
        elif char == 'ч':  # Ч = X (вырезать)
            widget.event_generate("<<Cut>>")
            return "break"
        
        return None
    
    def _check_single(self, idx):
        """Быстрая проверка одного слова"""
        if idx >= len(self.current):
            return
        
        item = self.current[idx]
        prompt = self.prompt_vars[idx].get()
        _, expected = self._get_prompt_and_expected(item)
        user = self.entry_vars[idx].get()
        
        user_norm = _norm(user)
        expected_variants = _extract_variants(expected)
        ok = user_norm in expected_variants
        
        if ok:
            self.result_vars[idx].set("✅ Correct!")
            self.learned.add(_card_key_words(item))
            self._refresh_stats()
        else:
            self.result_vars[idx].set("❌ Try again")
    
    def _refresh_stats(self):
        """Обновление статистики"""
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        progress = (done / total * 100) if total > 0 else 0
        
        self.stats_var.set(f"📊 Progress: {done}/{total} words • {progress:.1f}% complete")
    
    def _get_prompt_and_expected(self, item: dict) -> tuple[str, str]:
        en = item.get("en", "")
        ru = item.get("ru", "")
        return (en, ru) if self.mode.get() == "EN_TO_RU" else (ru, en)
    
    def next_round(self):
        """Следующий раунд"""
        pool = self._topic_pool_remaining()
        self._refresh_stats()
        
        if len(pool) == 0:
            for i in range(3):
                self.prompt_vars[i].set("🎉 Congratulations!")
                self.entry_vars[i].set("")
                self.result_vars[i].set("You've completed all words in this topic!")
            return
        
        take = min(3, len(pool))
        self.current = random.sample(pool, take)
        
        for i in range(3):
            if i < take:
                prompt, _ = self._get_prompt_and_expected(self.current[i])
                self.prompt_vars[i].set(prompt)
                self.entry_vars[i].set("")
                self.result_vars[i].set("")
            else:
                self.prompt_vars[i].set("")
                self.entry_vars[i].set("")
                self.result_vars[i].set("")
    
    def clear_inputs(self):
        """Очистить поля"""
        for v in self.entry_vars:
            v.set("")
        for r in self.result_vars:
            r.set("")
    
    def show_answers(self):
        """Показать ответы"""
        for i in range(3):
            if i >= len(self.current):
                continue
            _, expected = self._get_prompt_and_expected(self.current[i])
            self.result_vars[i].set(f"✅ Answer: {expected}")
    
    def check(self):
        """Проверить ответы"""
        if not self.current:
            return
        
        ru_index = _ru_to_en_index(self.items)
        en_index = _en_to_ru_index(self.items)
        
        for i in range(3):
            if i >= len(self.current):
                continue
            
            item = self.current[i]
            prompt = self.prompt_vars[i].get()
            _, expected = self._get_prompt_and_expected(item)
            user = self.entry_vars[i].get()
            
            user_norm = _norm(user)
            expected_variants = _extract_variants(expected)
            ok = user_norm in expected_variants
            
            if not ok:
                if self.mode.get() == "RU_TO_EN":
                    poss_en = set()
                    for ru_v in _extract_variants(prompt):
                        poss_en |= ru_index.get(ru_v, set())
                    ok = user_norm in poss_en
                elif self.mode.get() == "EN_TO_RU":
                    poss_ru = set()
                    for en_v in _extract_variants(prompt):
                        poss_ru |= en_index.get(en_v, set())
                    ok = user_norm in poss_ru
            
            if ok:
                self.result_vars[i].set("✅ Correct!")
                self.learned.add(_card_key_words(item))
            else:
                self.result_vars[i].set("❌ Incorrect - try again")
        
        self._refresh_stats()

class SentencesTab(ttk.Frame):
    def __init__(self, master, items: list[dict], online_var: tk.StringVar):
        super().__init__(master)
        self.items = items
        self.online_var = online_var
        
        self.topic_var = tk.StringVar(value="All topics")
        self.tense_var = tk.StringVar(value=TENSES[0])
        
        self.current_words: list[dict] = []
        self.used_words: set[tuple[str, str]] = set()
        
        self.last_matches: list[list[dict]] = [[] for _ in range(5)]
        self.text_widgets: list[UltraFastText] = []
        self.word_vars = [tk.StringVar() for _ in range(5)]
        self.result_vars = [tk.StringVar() for _ in range(5)]
        
        self._build_ui()
        self._refresh_stats()
        self.master.after(50, self.next_words)
    
    def _topics(self) -> list[str]:
        topics = sorted({str(it.get("topic", "Simple words")) for it in self.items})
        return ["All topics"] + topics
    
    def _topic_pool_all(self) -> list[dict]:
        sel = self.topic_var.get()
        if sel == "All topics":
            return self.items
        return [it for it in self.items if str(it.get("topic", "Simple words")) == sel]
    
    def _topic_pool_remaining(self) -> list[dict]:
        pool = self._topic_pool_all()
        return [it for it in pool if _word_key_sentence(it) not in self.used_words]
    
    def reset_progress(self):
        self.used_words.clear()
        self._refresh_stats()
        self.next_words()
        messagebox.showinfo("Progress Reset", "Your sentence practice has been reset!")
    
    def _build_ui(self):
        """Построение интерфейса для предложений"""
        # Панель управления
        control_frame = ttk.LabelFrame(self, text="Sentence Builder Settings", padding=15)
        control_frame.pack(fill="x", padx=20, pady=(10, 15))
        
        # Тема
        ttk.Label(control_frame, text="Topic:", font=FONTS["body"]).grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        
        self.topic_combo = ttk.Combobox(
            control_frame,
            textvariable=self.topic_var,
            state="readonly",
            width=25,
            font=FONTS["body"]
        )
        self.topic_combo["values"] = self._topics()
        self.topic_combo.grid(row=0, column=1, sticky="ew", padx=(0, 30))
        self.topic_combo.bind("<<ComboboxSelected>>", lambda e: self.next_words())
        
        # Время
        ttk.Label(control_frame, text="Tense:", font=FONTS["body"]).grid(
            row=0, column=2, sticky="w", padx=(30, 10))
        
        self.tense_combo = ttk.Combobox(
            control_frame,
            textvariable=self.tense_var,
            state="readonly",
            width=25,
            font=FONTS["body"]
        )
        self.tense_combo["values"] = TENSES
        self.tense_combo.grid(row=0, column=3, sticky="ew")
        
        # Кнопки
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=0, column=4, padx=(30, 0))
        
        ttk.Button(
            btn_frame,
            text="🔄 Refresh Progress",
            command=self.reset_progress,
            padding=(12, 8)
        ).pack(side="left", padx=(0, 10))
        
        ttk.Button(
            btn_frame,
            text="⏭️ Next 5 Words",
            command=self.next_words,
            padding=(12, 8)
        ).pack(side="left")
        
        # Статистика
        self.stats_var = tk.StringVar(value="Loading statistics...")
        ttk.Label(
            self,
            textvariable=self.stats_var,
            font=FONTS["h2"],
            foreground=COLORS["text_accent"]
        ).pack(anchor="w", padx=25, pady=(10, 15))
        
        # Карточки для предложений
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Сетка 2x3
        for i in range(2):
            cards_frame.rowconfigure(i, weight=1, uniform="row")
        for i in range(3):
            cards_frame.columnconfigure(i, weight=1, uniform="col")
        
        # Позиции для 5 карточек
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2)]
        
        for i in range(5):
            row, col = positions[i]
            
            card = ttk.LabelFrame(cards_frame, text=f"Sentence {i+1}", padding=20)
            card.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            
            # Слово
            ttk.Label(
                card,
                textvariable=self.word_vars[i],
                font=FONTS["h2"],
                wraplength=350,
                foreground=COLORS["text_primary"]
            ).pack(anchor="w", pady=(0, 10))
            
            ttk.Label(
                card,
                text="Write a sentence using this word:",
                font=FONTS["body"],
                foreground=COLORS["text_secondary"]
            ).pack(anchor="w", pady=(0, 10))
            
            # Текстовое поле с прокруткой
            text_frame = ttk.Frame(card)
            text_frame.pack(fill="both", expand=True)
            
            # Используем UltraFastText
            txt = UltraFastText(text_frame, height=4)
            
            # Скроллбар
            scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=scrollbar.set)
            
            txt.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Фокус на первый виджет
            if i == 0:
                txt.focus_set()
            
            self.text_widgets.append(txt)
            
            # Результат
            ttk.Label(
                card,
                textvariable=self.result_vars[i],
                font=FONTS["body"],
                wraplength=350,
                foreground=COLORS["text_secondary"]
            ).pack(anchor="w", pady=(10, 0))
        
        # Панель действий
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        self.check_btn = ttk.Button(
            action_frame,
            text="✅ Check Sentences",
            command=self.check,
            padding=(15, 10)
        )
        self.check_btn.pack(side="left", padx=(0, 10))
        
        ttk.Button(
            action_frame,
            text="📊 Show Details",
            command=self.show_details,
            padding=(15, 10)
        ).pack(side="left", padx=(0, 10))
        
        ttk.Button(
            action_frame,
            text="🗑️ Clear All",
            command=self.clear_inputs,
            padding=(15, 10)
        ).pack(side="left")
        
        # Инициализация
        self.topic_combo.set(self.topic_var.get())
        self.tense_combo.set(self.tense_var.get())
    
    def _refresh_stats(self):
        """Обновление статистики"""
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        progress = (done / total * 100) if total > 0 else 0
        
        self.stats_var.set(f"📊 Progress: {done}/{total} sentences • {progress:.1f}% complete")
    
    def next_words(self):
        """Следующий набор слов"""
        pool = self._topic_pool_remaining()
        self._refresh_stats()
        
        if len(pool) == 0:
            for i in range(5):
                self.word_vars[i].set("🎉 Congratulations!")
                self.result_vars[i].set("You've practiced all words in this topic!")
                self.text_widgets[i].delete("1.0", "end")
            return
        
        take = min(5, len(pool))
        self.current_words = random.sample(pool, take)
        
        for i in range(5):
            if i < take:
                self.word_vars[i].set(self.current_words[i].get("en", ""))
                self.result_vars[i].set("")
            else:
                self.word_vars[i].set("")
                self.result_vars[i].set("")
            
            # Очищаем поле
            self.text_widgets[i].delete("1.0", "end")
        
        # Фокус на первый текстовый виджет
        if self.text_widgets:
            self.text_widgets[0].focus_set()
    
    def clear_inputs(self):
        """Очистить все поля"""
        for i in range(5):
            self.text_widgets[i].delete("1.0", "end")
            self.result_vars[i].set("")
        
        # Фокус на первый виджет
        if self.text_widgets:
            self.text_widgets[0].focus_set()
    
    def check(self):
        """Проверить предложения"""
        if not self.current_words:
            return
        
        if self.online_var.get() != "Online":
            messagebox.showwarning("Offline", "Grammar check requires internet connection.")
            return
        
        tense = self.tense_var.get().strip() or TENSES[0]
        
        words, sentences, idx_map = [], [], []
        for i in range(5):
            if i >= len(self.current_words):
                continue
            word = self.current_words[i].get("en", "")
            sentence = self.text_widgets[i].get("1.0", "end-1c").strip()
            words.append(word)
            sentences.append(sentence)
            idx_map.append(i)
        
        # Визуальная обратная связь
        self.check_btn.configure(text="Checking...")
        
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
            
            self.master.after(0, lambda: self._apply_check_results(idx_map, results))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _apply_check_results(self, idx_map, results):
        """Применить результаты"""
        self.check_btn.configure(text="✅ Check Sentences")
        
        for pos, (_has, msg, matches, ok) in zip(idx_map, results):
            self.last_matches[pos] = matches or []
            
            if ok:
                self.result_vars[pos].set("✅ Perfect! All checks passed.")
                self.used_words.add(_word_key_sentence(self.current_words[pos]))
            else:
                self.result_vars[pos].set(f"📝 {msg[:100]}")
        
        self._refresh_stats()
    
    def show_details(self):
        """Показать детали проверки"""
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Grammar Check Details")
        win.geometry("1000x600")
        
        # Центрируем окно
        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
        y = (win.winfo_screenheight() - win.winfo_reqheight()) // 2
        win.geometry(f"+{x}+{y}")
        
        ttk.Label(
            win,
            text="Grammar Check Details",
            font=FONTS["h2"],
            foreground=COLORS["text_accent"]
        ).pack(pady=20)
        
        # Простой текстовый виджет для отображения
        text_frame = ttk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        text_widget = UltraFastText(text_frame, height=20)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Заполняем
        has_issues = False
        for i in range(5):
            matches = self.last_matches[i] if i < len(self.last_matches) else []
            if matches:
                has_issues = True
                text_widget.fast_insert(f"\n{'='*60}\n")
                text_widget.fast_insert(f"Sentence {i+1}: {self.word_vars[i].get()}\n")
                text_widget.fast_insert(f"{'='*60}\n\n")
                for m in matches[:5]:  # Показываем до 5 ошибок
                    message = m.get("message", "Unknown error")
                    rule = m.get("rule", {}).get("id", "unknown")
                    text_widget.fast_insert(f"• {message}\n")
                    text_widget.fast_insert(f"  Rule: {rule}\n\n")
        
        if not has_issues:
            text_widget.fast_insert("🎉 No grammar issues found! Perfect sentences!\n")
        
        ttk.Button(
            win,
            text="Close",
            command=win.destroy,
            padding=(15, 10)
        ).pack(pady=20)