import random
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import sv_ttk

from storage import load_vocab, save_vocab
from grammar_online import TENSES, check_sentence, lt_online

# --- Современная цветовая палитра (Dark Theme с акцентами) ---
COLORS = {
    # Основные цвета
    "bg_primary": "#0F172A",      # Темно-синий фон
    "bg_secondary": "#1E293B",    # Вторичный фон
    "bg_card": "#334155",         # Фон карточек
    "bg_input": "#475569",        # Фон полей ввода
    "bg_accent": "#3B82F6",       # Акцентный синий
    
    # Текст
    "text_primary": "#F1F5F9",    # Основной текст
    "text_secondary": "#94A3B8",  # Вторичный текст
    "text_accent": "#60A5FA",     # Акцентный текст
    "text_success": "#10B981",    # Успех (зеленый)
    "text_error": "#EF4444",      # Ошибка (красный)
    "text_warning": "#F59E0B",    # Предупреждение (желтый)
    
    # Градиенты
    "gradient_start": "#6366F1",  # Индиго
    "gradient_end": "#3B82F6",    # Синий
    
    # Статусы
    "online": "#10B981",          # Онлайн статус
    "offline": "#EF4444",         # Офлайн статус
}

# Шрифты
FONTS = {
    "h1": ("Segoe UI", 24, "bold"),
    "h2": ("Segoe UI", 20, "bold"),
    "h3": ("Segoe UI", 18, "bold"),
    "body": ("Segoe UI", 14),
    "small": ("Segoe UI", 12),
    "mono": ("Consolas", 13),
}

class ModernButton(ttk.Button):
    """Стилизованная кнопка с градиентным эффектом"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure(
            style="Modern.TButton",
            padding=(20, 10),
            cursor="hand2"
        )

class ModernEntry(ttk.Entry):
    """Стилизованное поле ввода"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure(
            style="Modern.TEntry",
            font=FONTS["body"]
        )

class ModernCombobox(ttk.Combobox):
    """Стилизованный комбобокс"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure(
            style="Modern.TCombobox",
            font=FONTS["small"]
        )

class CardFrame(ttk.Frame):
    """Карточка с закругленными углами и тенями"""
    def __init__(self, parent, title: str = "", **kwargs):
        super().__init__(parent, style="Card.TFrame")
        
        if title:
            self.header = ttk.Label(
                self,
                text=title.upper(),
                font=FONTS["small"],
                foreground=COLORS["text_accent"],
                background=COLORS["bg_card"]
            )
            self.header.pack(anchor="w", padx=20, pady=(15, 5))
        
        self.content = ttk.Frame(self, style="Card.TFrame")
        self.content.pack(fill="both", expand=True, padx=20, pady=(0, 20))

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
        
        # Настройка окна
        self.master.title("LinguaFlow • Learn English")
        self.master.geometry("1400x900")
        self.master.configure(bg=COLORS["bg_primary"])
        
        # Установка темы
        sv_ttk.set_theme("dark")
        
        self.pack(fill="both", expand=True, padx=0, pady=0)
        
        self.items = load_vocab()
        for it in self.items:
            if "topic" not in it or not str(it["topic"]).strip():
                it["topic"] = "Simple words"
        
        self._setup_styles()
        self._build_ui()
        self._bind_keys()
        
        self._update_online_status()
        self.master.after(5000, self._tick_online)
    
    def _setup_styles(self):
        """Настройка кастомных стилей"""
        style = ttk.Style()
        
        # Настройка стилей для виджетов
        style.configure(
            "Title.TLabel",
            font=FONTS["h1"],
            foreground=COLORS["text_primary"],
            background=COLORS["bg_primary"]
        )
        
        style.configure(
            "Subtitle.TLabel",
            font=FONTS["h3"],
            foreground=COLORS["text_secondary"],
            background=COLORS["bg_primary"]
        )
        
        style.configure(
            "Card.TFrame",
            background=COLORS["bg_card"],
            relief="flat",
            borderwidth=10
        )
        
        style.configure(
            "Modern.TButton",
            font=FONTS["body"],
            padding=(20, 12),
            relief="flat",
            borderwidth=0
        )
        
        style.map(
            "Modern.TButton",
            background=[("active", COLORS["bg_accent"]), ("!disabled", COLORS["bg_input"])],
            foreground=[("!disabled", COLORS["text_primary"])]
        )
        
        style.configure(
            "Modern.TEntry",
            fieldbackground=COLORS["bg_input"],
            foreground=COLORS["text_primary"],
            bordercolor=COLORS["bg_input"],
            relief="flat",
            padding=(15, 10)
        )
        
        style.map(
            "Modern.TEntry",
            fieldbackground=[("focus", COLORS["bg_input"])],
            bordercolor=[("focus", COLORS["text_accent"])]
        )
        
        style.configure(
            "Modern.TCombobox",
            fieldbackground=COLORS["bg_input"],
            foreground=COLORS["text_primary"],
            padding=(10, 8)
        )
        
        # Стиль для Notebook
        style.configure(
            "Modern.TNotebook",
            background=COLORS["bg_primary"],
            borderwidth=0
        )
        
        style.configure(
            "Modern.TNotebook.Tab",
            padding=(25, 10),
            font=FONTS["body"],
            background=COLORS["bg_secondary"],
            foreground=COLORS["text_secondary"]
        )
        
        style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", COLORS["bg_accent"])],
            foreground=[("selected", COLORS["text_primary"])]
        )
    
    def _build_ui(self):
        """Построение интерфейса"""
        # Верхняя панель с логотипом и статусом
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=30, pady=(20, 10))
        
        # Логотип и заголовок
        title_frame = ttk.Frame(header)
        title_frame.pack(side="left", fill="y")
        
        ttk.Label(
            title_frame,
            text="LINGUAFLOW",
            style="Title.TLabel",
            foreground=COLORS["text_accent"]
        ).pack(side="left")
        
        ttk.Label(
            title_frame,
            text="• English Learning Platform",
            style="Subtitle.TLabel"
        ).pack(side="left", padx=(10, 0))
        
        # Панель статуса
        status_frame = ttk.Frame(header)
        status_frame.pack(side="right", fill="y")
        
        # Статус LanguageTool
        self.status_dot = tk.Canvas(
            status_frame,
            width=12,
            height=12,
            bg=COLORS["bg_primary"],
            highlightthickness=0
        )
        self.status_dot.pack(side="left", padx=(0, 8))
        self.dot = self.status_dot.create_oval(2, 2, 10, 10, fill=COLORS["offline"])
        
        ttk.Label(
            status_frame,
            text="LanguageTool:",
            style="Subtitle.TLabel"
        ).pack(side="left")
        
        self.online_var = tk.StringVar(value="Checking...")
        ttk.Label(
            status_frame,
            textvariable=self.online_var,
            style="Subtitle.TLabel",
            font=("Segoe UI", 12, "bold")
        ).pack(side="left", padx=(5, 20))
        
        # Кнопка проверки соединения
        ModernButton(
            status_frame,
            text="⟳ Check Connection",
            command=self._update_online_status
        ).pack(side="right")
        
        # Основной контент
        self._build_tabs()
        
        # Нижняя панель с подсказками
        footer = ttk.Frame(self, style="Card.TFrame")
        footer.pack(fill="x", padx=30, pady=(10, 20))
        
        ttk.Label(
            footer,
            text="💡 Tip: Press Enter to check, Shift+Enter for new line • Ctrl+N for next • Ctrl+R to refresh",
            style="Subtitle.TLabel",
            font=FONTS["small"],
            foreground=COLORS["text_secondary"]
        ).pack()
    
    def _build_tabs(self):
        """Создание вкладок"""
        # Стилизованный Notebook
        self.nb = ttk.Notebook(self, style="Modern.TNotebook")
        self.nb.pack(fill="both", expand=True, padx=30, pady=(0, 10))
        
        # Создание вкладок
        self.tab_words = WordsTab(self.nb, self.items)
        self.tab_sentences = SentencesTab(self.nb, self.items, self.online_var)
        
        # Добавление иконок к вкладкам
        self.nb.add(self.tab_words, text="📚 Vocabulary Practice")
        self.nb.add(self.tab_sentences, text="✍️ Sentence Builder")
    
    def _bind_keys(self):
        """Привязка горячих клавиш"""
        self.master.bind("<Return>", self._on_enter)
        self.master.bind("<Control-n>", lambda e: self._next_item())
        self.master.bind("<Control-r>", lambda e: self._refresh())
    
    def _on_enter(self, event=None):
        """Обработка Enter"""
        idx = self.nb.index("current")
        if idx == 0:
            self.tab_words.check()
        elif idx == 1:
            self.tab_sentences.check()
    
    def _next_item(self):
        """Следующий элемент (Ctrl+N)"""
        idx = self.nb.index("current")
        if idx == 0:
            self.tab_words.next_round()
        elif idx == 1:
            self.tab_sentences.next_words()
    
    def _refresh(self):
        """Обновить (Ctrl+R)"""
        idx = self.nb.index("current")
        if idx == 0:
            self.tab_words.reset_progress()
        elif idx == 1:
            self.tab_sentences.reset_progress()
    
    def _update_online_status(self):
        """Обновление статуса LanguageTool"""
        ok = lt_online()
        status = "Online" if ok else "Offline"
        color = COLORS["online"] if ok else COLORS["offline"]
        
        self.online_var.set(status)
        self.status_dot.itemconfig(self.dot, fill=color)
    
    def _tick_online(self):
        """Периодическая проверка статуса"""
        self._update_online_status()
        self.master.after(10000, self._tick_online)

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
        """Построение интерфейса вкладки Words"""
        # Верхняя панель управления
        control_panel = CardFrame(self, "Practice Settings")
        control_panel.pack(fill="x", padx=20, pady=(0, 20))
        
        # Выбор темы
        topic_frame = ttk.Frame(control_panel.content)
        topic_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(
            topic_frame,
            text="Topic:",
            font=FONTS["body"],
            foreground=COLORS["text_primary"]
        ).pack(side="left", padx=(0, 10))
        
        self.topic_box = ModernCombobox(
            topic_frame,
            textvariable=self.topic_var,
            state="readonly",
            width=30
        )
        self.topic_box["values"] = self._topics()
        self.topic_box.pack(side="left", padx=(0, 30))
        self.topic_box.bind("<<ComboboxSelected>>", lambda _e: self.next_round())
        
        # Выбор режима
        mode_frame = ttk.Frame(topic_frame)
        mode_frame.pack(side="left", padx=(30, 0))
        
        ttk.Label(
            mode_frame,
            text="Mode:",
            font=FONTS["body"],
            foreground=COLORS["text_primary"]
        ).pack(side="left", padx=(0, 10))
        
        mode_inner = ttk.Frame(mode_frame)
        mode_inner.pack(side="left")
        
        ttk.Radiobutton(
            mode_inner,
            text="English → Russian",
            variable=self.mode,
            value="EN_TO_RU",
            command=self.next_round,
            style="TRadiobutton"
        ).pack(side="left", padx=(0, 15))
        
        ttk.Radiobutton(
            mode_inner,
            text="Russian → English",
            variable=self.mode,
            value="RU_TO_EN",
            command=self.next_round,
            style="TRadiobutton"
        ).pack(side="left")
        
        # Кнопки управления
        btn_frame = ttk.Frame(control_panel.content)
        btn_frame.pack(fill="x", pady=(5, 0))
        
        ModernButton(
            btn_frame,
            text="🔄 Refresh Progress",
            command=self.reset_progress
        ).pack(side="left", padx=(0, 10))
        
        ModernButton(
            btn_frame,
            text="⏭️ Next Set",
            command=self.next_round
        ).pack(side="left")
        
        # Статистика
        self.stats_frame = CardFrame(self, "Progress")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.stats_var = tk.StringVar(value="Loading statistics...")
        ttk.Label(
            self.stats_frame.content,
            textvariable=self.stats_var,
            font=FONTS["h3"],
            foreground=COLORS["text_accent"]
        ).pack(anchor="w")
        
        # Карточки для практики
        cards_container = ttk.Frame(self)
        cards_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.prompt_vars = [tk.StringVar() for _ in range(3)]
        self.entry_vars = [tk.StringVar() for _ in range(3)]
        self.result_vars = [tk.StringVar() for _ in range(3)]
        
        self.cards = []
        for i in range(3):
            card = CardFrame(cards_container, f"Word {i+1}")
            card.pack(side="left", fill="both", expand=True, padx=10)
            self.cards.append(card)
            
            # Промпт
            ttk.Label(
                card.content,
                textvariable=self.prompt_vars[i],
                font=FONTS["h3"],
                foreground=COLORS["text_primary"],
                wraplength=300
            ).pack(anchor="w", pady=(0, 15))
            
            # Поле ввода
            entry = ModernEntry(
                card.content,
                textvariable=self.entry_vars[i],
                width=30
            )
            entry.pack(fill="x", pady=(0, 10))
            
            # Результат
            ttk.Label(
                card.content,
                textvariable=self.result_vars[i],
                font=FONTS["small"],
                wraplength=300
            ).pack(anchor="w")
        
        # Панель действий
        action_panel = ttk.Frame(self)
        action_panel.pack(fill="x", padx=20, pady=(0, 20))
        
        ModernButton(
            action_panel,
            text="✅ Check Answers",
            command=self.check
        ).pack(side="left", padx=(0, 10))
        
        ModernButton(
            action_panel,
            text="👁️ Show Answers",
            command=self.show_answers
        ).pack(side="left", padx=(0, 10))
        
        ModernButton(
            action_panel,
            text="🗑️ Clear All",
            command=self.clear_inputs
        ).pack(side="left")
    
    def _refresh_stats(self):
        """Обновление статистики"""
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        progress = (done / total * 100) if total > 0 else 0
        
        self.stats_var.set(
            f"📊 Topic: {self.topic_var.get()} • "
            f"Total: {total} • "
            f"Learned: {done} • "
            f"Remaining: {remaining} • "
            f"Progress: {progress:.1f}%"
        )
        
        cur = self.topic_var.get() or "All topics"
        self.topic_box["values"] = self._topics()
        if cur not in self.topic_box["values"]:
            cur = "All topics"
            self.topic_var.set(cur)
        self.topic_box.set(cur)
    
    def _get_prompt_and_expected(self, item: dict) -> tuple[str, str]:
        en = item.get("en", "")
        ru = item.get("ru", "")
        return (en, ru) if self.mode.get() == "EN_TO_RU" else (ru, en)
    
    def _show_end(self):
        """Показать завершение темы"""
        self.current = []
        for i in range(3):
            self.prompt_vars[i].set("🎉 Congratulations!")
            self.entry_vars[i].set("")
            self.result_vars[i].set(
                "You've completed this topic!\n"
                "Click 'Refresh Progress' to start over."
            )
    
    def next_round(self):
        """Следующий раунд слов"""
        pool = self._topic_pool_remaining()
        self._refresh_stats()
        
        if len(pool) == 0:
            self._show_end()
            return
        
        take = min(3, len(pool))
        self.current = random.sample(pool, take)
        
        for i in range(3):
            if i < take:
                prompt, _ = self._get_prompt_and_expected(self.current[i])
                self.prompt_vars[i].set(prompt)
                self.entry_vars[i].set("")
                self.result_vars[i].set("")
                self.cards[i].header.configure(text=f"Word {i+1}")
            else:
                self.prompt_vars[i].set("")
                self.entry_vars[i].set("")
                self.result_vars[i].set("")
                self.cards[i].header.configure(text=f"Word {i+1}")
    
    def clear_inputs(self):
        """Очистить все поля ввода"""
        for v in self.entry_vars:
            v.set("")
        for r in self.result_vars:
            r.set("")
    
    def show_answers(self):
        """Показать правильные ответы"""
        for i in range(3):
            if i >= len(self.current):
                continue
            _, expected = self._get_prompt_and_expected(self.current[i])
            messagebox.showinfo(
                "Correct Answer",
                f"Word {i+1}: {self.prompt_vars[i].get()}\n\n"
                f"Correct translation:\n{expected}",
                icon="info"
            )
    
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
                    if user_norm in poss_en:
                        ok = True
                    else:
                        correct = ", ".join(sorted(poss_en)[:40]) if poss_en else "(not found)"
                        messagebox.showinfo(
                            "Correct Translation",
                            f"{prompt}\n\nCorrect EN: {correct}",
                            icon="info"
                        )
                
                elif self.mode.get() == "EN_TO_RU":
                    poss_ru = set()
                    for en_v in _extract_variants(prompt):
                        poss_ru |= en_index.get(en_v, set())
                    if user_norm in poss_ru:
                        ok = True
                    else:
                        correct = ", ".join(sorted(poss_ru)[:40]) if poss_ru else "(not found)"
                        messagebox.showinfo(
                            "Correct Translation",
                            f"{prompt}\n\nCorrect RU: {correct}",
                            icon="info"
                        )
            
            if ok:
                self.result_vars[i].set("✅ Correct!")
                self.result_vars[i].configure(foreground=COLORS["text_success"])
                self.learned.add(_card_key_words(item))
            else:
                self.result_vars[i].set("❌ Incorrect")
                self.result_vars[i].configure(foreground=COLORS["text_error"])
        
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
        self.text_widgets: list[tk.Text] = []
        self.word_vars = [tk.StringVar() for _ in range(5)]
        self.result_vars = [tk.StringVar() for _ in range(5)]
        
        self._resize_job = {}
        
        self._build_ui()
        self._refresh_stats()
        self.next_words()
    
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
    
    def _adjust_text_height_now(self, widget: tk.Text, min_lines: int = 2, max_lines: int = 7):
        try:
            line_count = int(widget.index("end-1c").split(".")[0])
        except Exception:
            line_count = min_lines
        widget.configure(height=max(min_lines, min(line_count, max_lines)))
    
    def _adjust_text_height_debounced(self, widget: tk.Text):
        wid = str(widget)
        job = self._resize_job.get(wid)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._resize_job[wid] = self.after(90, lambda w=widget: self._adjust_text_height_now(w))
    
    def _on_text_enter(self, _event=None):
        self.check()
        return "break"
    
    def _on_text_shift_enter(self, event):
        event.widget.insert("insert", "\n")
        self._adjust_text_height_debounced(event.widget)
        return "break"
    
    def _build_ui(self):
        """Построение интерфейса вкладки Sentences"""
        # Панель управления
        control_panel = CardFrame(self, "Sentence Builder Settings")
        control_panel.pack(fill="x", padx=20, pady=(0, 20))
        
        # Выбор темы и времени
        settings_frame = ttk.Frame(control_panel.content)
        settings_frame.pack(fill="x", pady=(0, 15))
        
        # Выбор темы
        topic_frame = ttk.Frame(settings_frame)
        topic_frame.pack(side="left", padx=(0, 30))
        
        ttk.Label(
            topic_frame,
            text="Topic:",
            font=FONTS["body"],
            foreground=COLORS["text_primary"]
        ).pack(anchor="w", pady=(0, 5))
        
        self.topic_box = ModernCombobox(
            topic_frame,
            textvariable=self.topic_var,
            state="readonly",
            width=25
        )
        self.topic_box["values"] = self._topics()
        self.topic_box.pack(fill="x")
        self.topic_box.bind("<<ComboboxSelected>>", lambda _e: self.next_words())
        
        # Выбор времени
        tense_frame = ttk.Frame(settings_frame)
        tense_frame.pack(side="left", padx=(30, 0))
        
        ttk.Label(
            tense_frame,
            text="Tense:",
            font=FONTS["body"],
            foreground=COLORS["text_primary"]
        ).pack(anchor="w", pady=(0, 5))
        
        self.tense_box = ModernCombobox(
            tense_frame,
            textvariable=self.tense_var,
            state="readonly",
            width=25
        )
        self.tense_box["values"] = TENSES
        self.tense_box.pack(fill="x")
        
        # Кнопки управления
        btn_frame = ttk.Frame(control_panel.content)
        btn_frame.pack(fill="x", pady=(5, 0))
        
        ModernButton(
            btn_frame,
            text="🔄 Refresh Progress",
            command=self.reset_progress
        ).pack(side="left", padx=(0, 10))
        
        ModernButton(
            btn_frame,
            text="⏭️ Next 5 Words",
            command=self.next_words
        ).pack(side="left")
        
        # Статистика
        self.stats_frame = CardFrame(self, "Progress")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.stats_var = tk.StringVar(value="Loading statistics...")
        ttk.Label(
            self.stats_frame.content,
            textvariable=self.stats_var,
            font=FONTS["h3"],
            foreground=COLORS["text_accent"]
        ).pack(anchor="w")
        
        # Контейнер для карточек с предложениями
        cards_container = ttk.Frame(self)
        cards_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Создаем сетку 2x3 для карточек
        for i in range(2):  # строки
            cards_container.rowconfigure(i, weight=1)
        for i in range(3):  # столбцы
            cards_container.columnconfigure(i, weight=1)
        
        # Создаем 5 карточек (первые 3 в первой строке, последние 2 во второй)
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2)]
        
        for i in range(5):
            row, col = positions[i]
            
            card = CardFrame(cards_container, f"Sentence {i+1}")
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            
            # Слово для использования
            ttk.Label(
                card.content,
                textvariable=self.word_vars[i],
                font=FONTS["h3"],
                foreground=COLORS["text_primary"],
                wraplength=300
            ).pack(anchor="w", pady=(0, 10))
            
            ttk.Label(
                card.content,
                text="Write a sentence using this word:",
                font=FONTS["small"],
                foreground=COLORS["text_secondary"]
            ).pack(anchor="w", pady=(0, 10))
            
            # Поле для ввода предложения
            text_frame = ttk.Frame(card.content)
            text_frame.pack(fill="both", expand=True)
            
            txt = tk.Text(
                text_frame,
                wrap="word",
                height=4,
                font=FONTS["body"],
                undo=True,
                bg=COLORS["bg_input"],
                fg=COLORS["text_primary"],
                insertbackground=COLORS["text_accent"],
                selectbackground=COLORS["bg_accent"],
                relief="flat",
                padx=10,
                pady=10
            )
            
            scr = ttk.Scrollbar(text_frame, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=scr.set)
            
            txt.pack(side="left", fill="both", expand=True)
            scr.pack(side="right", fill="y")
            
            txt.bind("<Return>", self._on_text_enter)
            txt.bind("<Shift-Return>", self._on_text_shift_enter)
            txt.bind("<KeyRelease>", lambda e, w=txt: self._adjust_text_height_debounced(w))
            
            self.text_widgets.append(txt)
            
            # Результат проверки
            ttk.Label(
                card.content,
                textvariable=self.result_vars[i],
                font=FONTS["small"],
                foreground=COLORS["text_secondary"],
                wraplength=300
            ).pack(anchor="w", pady=(10, 0))
        
        # Панель действий
        action_panel = ttk.Frame(self)
        action_panel.pack(fill="x", padx=20, pady=(0, 20))
        
        self.check_btn = ModernButton(
            action_panel,
            text="✅ Check Sentences",
            command=self.check
        )
        self.check_btn.pack(side="left", padx=(0, 10))
        
        ModernButton(
            action_panel,
            text="📊 Show Details",
            command=self.show_details
        ).pack(side="left", padx=(0, 10))
        
        ModernButton(
            action_panel,
            text="🗑️ Clear All",
            command=self.clear_inputs
        ).pack(side="left")
        
        self.topic_box.set(self.topic_var.get())
        self.tense_box.set(self.tense_var.get())
    
    def _refresh_stats(self):
        """Обновление статистики"""
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        progress = (done / total * 100) if total > 0 else 0
        
        self.stats_var.set(
            f"📊 Topic: {self.topic_var.get()} • "
            f"Total: {total} • "
            f"Practiced: {done} • "
            f"Remaining: {remaining} • "
            f"Progress: {progress:.1f}%"
        )
        
        cur = self.topic_var.get() or "All topics"
        self.topic_box["values"] = self._topics()
        if cur not in self.topic_box["values"]:
            cur = "All topics"
            self.topic_var.set(cur)
        self.topic_box.set(cur)
    
    def _show_end(self):
        """Показать завершение"""
        self.current_words = []
        self.last_matches = [[] for _ in range(5)]
        
        for i in range(5):
            self.word_vars[i].set("🎉 Congratulations!")
            self.result_vars[i].set(
                "You've practiced all words in this topic!\n"
                "Click 'Refresh Progress' to start over."
            )
            self.text_widgets[i].delete("1.0", "end")
            self._adjust_text_height_now(self.text_widgets[i])
    
    def next_words(self):
        """Следующий набор слов"""
        pool = self._topic_pool_remaining()
        self._refresh_stats()
        
        if len(pool) == 0:
            self._show_end()
            return
        
        take = min(5, len(pool))
        self.current_words = random.sample(pool, take)
        self.last_matches = [[] for _ in range(5)]
        
        for i in range(5):
            self.text_widgets[i].delete("1.0", "end")
            self._adjust_text_height_now(self.text_widgets[i])
            
            if i < take:
                self.word_vars[i].set(self.current_words[i].get("en", ""))
                self.result_vars[i].set("")
            else:
                self.word_vars[i].set("")
                self.result_vars[i].set("")
    
    def clear_inputs(self):
        """Очистить все поля ввода"""
        for i in range(5):
            self.text_widgets[i].delete("1.0", "end")
            self._adjust_text_height_now(self.text_widgets[i])
            self.result_vars[i].set("")
        self.last_matches = [[] for _ in range(5)]
    
    def check(self):
        """Проверить предложения"""
        if not self.current_words:
            return
        
        if self.online_var.get() != "Online":
            messagebox.showwarning(
                "⚠️ LanguageTool Offline",
                "Grammar checking requires internet connection.\n"
                "Please check your connection and try again.",
                icon="warning"
            )
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
        
        self.check_btn.configure(text="🔍 Checking...")
        self.check_btn.state(["disabled"])
        
        def worker():
            results = []
            for k, sentence in enumerate(sentences):
                if not sentence:
                    results.append((False, "Please write a sentence.", [], False))
                    continue
                try:
                    res = check_sentence(
                        sentence=sentence,
                        required_word=words[k],
                        tense=tense
                    )
                    results.append((True, res.message, res.matches or [], res.ok))
                except Exception as e:
                    results.append((False, f"Error: {str(e)[:100]}", [], False))
            
            self.after(0, lambda: self._apply_check_results(idx_map, results))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _apply_check_results(self, idx_map, results):
        """Применить результаты проверки"""
        self.check_btn.configure(text="✅ Check Sentences")
        self.check_btn.state(["!disabled"])
        
        for pos, (_has, msg, matches, ok) in zip(idx_map, results):
            self.last_matches[pos] = matches or []
            
            if ok:
                self.result_vars[pos].set("✅ Perfect! All checks passed.")
                self.result_vars[pos].configure(foreground=COLORS["text_success"])
                self.used_words.add(_word_key_sentence(self.current_words[pos]))
            else:
                self.result_vars[pos].set(f"📝 {msg[:100]}")
                self.result_vars[pos].configure(foreground=COLORS["text_warning"])
        
        self._refresh_stats()
    
    def show_details(self):
        """Показать детали проверки"""
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Grammar Check Details")
        win.geometry("1200x700")
        win.configure(bg=COLORS["bg_primary"])
        
        # Заголовок
        ttk.Label(
            win,
            text="Grammar Check Details",
            font=FONTS["h2"],
            foreground=COLORS["text_primary"],
            background=COLORS["bg_primary"]
        ).pack(anchor="w", padx=20, pady=20)
        
        ttk.Label(
            win,
            text="Each row shows one grammar suggestion from LanguageTool",
            font=FONTS["small"],
            foreground=COLORS["text_secondary"],
            background=COLORS["bg_primary"]
        ).pack(anchor="w", padx=20, pady=(0, 20))
        
        # Таблица с результатами
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        cols = ("Slot", "Word", "Issue", "Message", "Suggestion")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=20)
        
        # Настройка колонок
        tree.column("Slot", width=60)
        tree.column("Word", width=120)
        tree.column("Issue", width=200)
        tree.column("Message", width=400)
        tree.column("Suggestion", width=300)
        
        for col in cols:
            tree.heading(col, text=col)
        
        # Скроллбар
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Заполнение данными
        for i in range(5):
            word = self.word_vars[i].get()
            matches = self.last_matches[i] if i < len(self.last_matches) else []
            
            for m in matches:
                rule_obj = m.get("rule", {}) or {}
                rule_id = rule_obj.get("id", "")
                message = m.get("message", "")
                
                repls = m.get("replacements", []) or []
                suggestions = ", ".join([r.get("value", "") for r in repls[:3]])
                
                tree.insert("", "end", values=(
                    i + 1,
                    word[:20],
                    rule_id[:30],
                    message[:80],
                    suggestions[:50]
                ))
        
        if not tree.get_children():
            ttk.Label(
                win,
                text="No grammar issues found. Great job!",
                font=FONTS["body"],
                foreground=COLORS["text_success"],
                background=COLORS["bg_primary"]
            ).pack(pady=50)
        
        # Кнопка закрытия
        ModernButton(
            win,
            text="Close",
            command=win.destroy
        ).pack(pady=20)