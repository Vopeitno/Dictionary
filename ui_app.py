import random
import re
import tkinter as tk
from tkinter import ttk, messagebox

from storage import load_vocab, save_vocab
from grammar_online import TENSES, check_sentence, lt_online


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
        self.pack(fill="both", expand=True, padx=18, pady=18)

        self.items = load_vocab()
        for it in self.items:
            if "topic" not in it or not str(it["topic"]).strip():
                it["topic"] = "Simple words"

        self._build_styles()
        self._build_header()
        self._build_tabs()
        self._bind_keys()

        self._update_online_status()
        self.master.after(5000, self._tick_online)

    def _build_styles(self):
        style = ttk.Style(self.master)
        style.configure("Big.TLabel", font=("Helvetica", 18))
        style.configure("Big.TButton", font=("Helvetica", 16))
        style.configure("Big.TLabelframe.Label", font=("Helvetica", 16))

    def _build_header(self):
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(header, text="LanguageTool:", style="Big.TLabel").pack(side="left")
        self.online_var = tk.StringVar(value="Checking...")
        ttk.Label(header, textvariable=self.online_var, style="Big.TLabel").pack(
            side="left", padx=10
        )

        ttk.Button(
            header,
            text="Check connection",
            command=self._update_online_status,
            style="Big.TButton",
        ).pack(side="left", padx=10)

    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.tab_words = WordsTab(self.nb, self.items)
        self.tab_sentences = SentencesTab(
            self.nb, self.items, online_var=self.online_var
        )

        self.nb.add(self.tab_words, text="Words")
        self.nb.add(self.tab_sentences, text="Sentences")

    def _bind_keys(self):
        # Global Enter => check current tab.
        # IMPORTANT: we do NOT bind Shift-Return globally, because Shift+Enter should insert newline in Text. [web:276]
        self.master.bind_all("<Return>", self._on_enter)

    def _on_enter(self, _event=None):
        idx = self.nb.index("current")
        if idx == 0:
            self.tab_words.check()
        else:
            # In Sentences, Text widgets handle Enter themselves (call check and return "break"),
            # but this is fine for Enter pressed outside Text widgets.
            self.tab_sentences.check()

    def _update_online_status(self):
        ok = lt_online()
        self.online_var.set("Online" if ok else "Offline")

    def _tick_online(self):
        self._update_online_status()
        self.master.after(5000, self._tick_online)


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

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x")

        ttk.Label(top, text="Topic:", style="Big.TLabel").pack(side="left")
        self.topic_box = ttk.Combobox(
            top, textvariable=self.topic_var, state="readonly", width=34
        )
        self.topic_box["values"] = self._topics()
        self.topic_box.pack(side="left", padx=10, ipady=6)
        self.topic_box.bind("<<ComboboxSelected>>", lambda _e: self.next_round())

        ttk.Label(top, text="Mode:", style="Big.TLabel").pack(side="left", padx=(18, 0))
        ttk.Radiobutton(
            top,
            text="EN → RU",
            variable=self.mode,
            value="EN_TO_RU",
            command=self.next_round,
        ).pack(side="left", padx=10)
        ttk.Radiobutton(
            top,
            text="RU → EN",
            variable=self.mode,
            value="RU_TO_EN",
            command=self.next_round,
        ).pack(side="left")

        ttk.Button(
            top, text="Refresh", command=self.reset_progress, style="Big.TButton"
        ).pack(side="right")
        ttk.Button(
            top, text="Next 3", command=self.next_round, style="Big.TButton"
        ).pack(side="right", padx=10)
        ttk.Button(
            top, text="Editor", command=self.open_editor, style="Big.TButton"
        ).pack(side="right", padx=10)

        self.stats_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.stats_var, style="Big.TLabel").pack(
            anchor="w", pady=(14, 10)
        )

        cards = ttk.Frame(self)
        cards.pack(fill="both", expand=True, pady=(8, 14))

        self.prompt_vars = [tk.StringVar(), tk.StringVar(), tk.StringVar()]
        self.entry_vars = [tk.StringVar(), tk.StringVar(), tk.StringVar()]
        self.result_vars = [tk.StringVar(), tk.StringVar(), tk.StringVar()]

        wrap = 520

        for i in range(3):
            col = ttk.LabelFrame(cards, text=f"Word {i+1}", style="Big.TLabelframe")
            col.pack(side="left", fill="both", expand=True, padx=12)

            ttk.Label(
                col,
                textvariable=self.prompt_vars[i],
                wraplength=wrap,
                style="Big.TLabel",
            ).pack(anchor="w", padx=14, pady=(14, 10))
            tk.Entry(col, textvariable=self.entry_vars[i], font=("Helvetica", 20)).pack(
                fill="x", padx=14, pady=8, ipady=8
            )
            ttk.Label(
                col,
                textvariable=self.result_vars[i],
                wraplength=wrap,
                style="Big.TLabel",
            ).pack(anchor="w", padx=14, pady=(10, 14))

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Check", command=self.check, style="Big.TButton").pack(
            side="left"
        )
        ttk.Button(
            btns, text="Show answers", command=self.show_answers, style="Big.TButton"
        ).pack(side="left", padx=10)
        ttk.Button(
            btns, text="Clear", command=self.clear_inputs, style="Big.TButton"
        ).pack(side="left")

        if not self.topic_var.get():
            self.topic_var.set("All topics")
        self.topic_box.set(self.topic_var.get())

    def _refresh_stats(self):
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        self.stats_var.set(f"In topic: {total} | Done: {done} | Left: {remaining}")

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
        self.current = []
        for i in range(3):
            self.prompt_vars[i].set("END")
            self.entry_vars[i].set("")
            self.result_vars[i].set("Press Refresh to start again.")

    def next_round(self):
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
            else:
                self.prompt_vars[i].set("END")
                self.entry_vars[i].set("")
                self.result_vars[i].set("")

    def clear_inputs(self):
        for v in self.entry_vars:
            v.set("")
        for r in self.result_vars:
            r.set("")

    def show_answers(self):
        for i in range(3):
            if i >= len(self.current):
                continue
            _, expected = self._get_prompt_and_expected(self.current[i])
            self.result_vars[i].set(f"Answer: {expected}")

    def check(self):
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

            if not ok and self.mode.get() == "RU_TO_EN":
                poss_en = set()
                for ru_v in _extract_variants(prompt):
                    poss_en |= ru_index.get(ru_v, set())
                ok = user_norm in poss_en
                self.result_vars[i].set(
                    "Correct"
                    if ok
                    else f"Wrong. Accepted: {', '.join(sorted(poss_en)[:10])}"
                )

            elif not ok and self.mode.get() == "EN_TO_RU":
                poss_ru = set()
                for en_v in _extract_variants(prompt):
                    poss_ru |= en_index.get(en_v, set())
                ok = user_norm in poss_ru
                self.result_vars[i].set(
                    "Correct"
                    if ok
                    else f"Wrong. Accepted: {', '.join(sorted(poss_ru)[:10])}"
                )

            else:
                self.result_vars[i].set(
                    "Correct"
                    if ok
                    else f"Wrong. Accepted: {', '.join(sorted(expected_variants)[:8])}"
                )

            if ok:
                self.learned.add(_card_key_words(item))

        self._refresh_stats()

    def open_editor(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Editor (EN / RU / Topic)")
        win.geometry("1400x800")

        container = ttk.Frame(win, padding=12)
        container.pack(fill="both", expand=True)

        cols = ("topic", "en", "ru")
        tree = ttk.Treeview(container, columns=cols, show="headings", height=14)
        tree.heading("topic", text="Topic")
        tree.heading("en", text="English")
        tree.heading("ru", text="Russian")
        tree.column("topic", width=220)
        tree.column("en", width=260)
        tree.column("ru", width=820)
        tree.pack(fill="both", expand=True)

        def refresh_tree():
            tree.delete(*tree.get_children())
            for idx, it in enumerate(self.items):
                topic = it.get("topic", "Simple words")
                tree.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(topic, it.get("en", ""), it.get("ru", "")),
                )
            self._refresh_stats()

        form = ttk.Frame(container)
        form.pack(fill="x", pady=(12, 0))

        topic_var = tk.StringVar(value="Simple words")
        en_var = tk.StringVar()
        ru_var = tk.StringVar()

        ttk.Label(form, text="Topic:").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=topic_var, width=22).grid(
            row=0, column=1, sticky="w", padx=8
        )

        ttk.Label(form, text="EN:").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=en_var, width=26).grid(
            row=0, column=3, sticky="we", padx=8
        )

        ttk.Label(form, text="RU:").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=ru_var, width=60).grid(
            row=0, column=5, sticky="we", padx=8
        )

        form.columnconfigure(5, weight=1)

        def add_word():
            topic = topic_var.get().strip() or "Simple words"
            en = en_var.get().strip()
            ru = ru_var.get().strip()
            if not en or not ru:
                messagebox.showwarning("Error", "Fill EN and RU.")
                return
            self.items.append({"topic": topic, "en": en, "ru": ru})
            save_vocab(self.items)
            refresh_tree()
            en_var.set("")
            ru_var.set("")

        def delete_selected():
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            item = self.items[idx]
            self.learned.discard(_card_key_words(item))
            self.items.pop(idx)
            save_vocab(self.items)
            refresh_tree()

        def load_selected_into_form(_evt=None):
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            it = self.items[idx]
            topic_var.set(it.get("topic", "Simple words"))
            en_var.set(it.get("en", ""))
            ru_var.set(it.get("ru", ""))

        def update_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No selection", "Select a row.")
                return
            idx = int(sel[0])
            old_item = self.items[idx]
            self.learned.discard(_card_key_words(old_item))

            topic = topic_var.get().strip() or "Simple words"
            en = en_var.get().strip()
            ru = ru_var.get().strip()
            if not en or not ru:
                messagebox.showwarning("Error", "Fill EN and RU.")
                return

            self.items[idx] = {"topic": topic, "en": en, "ru": ru}
            save_vocab(self.items)
            refresh_tree()

        btn_row = ttk.Frame(container)
        btn_row.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_row, text="Add", command=add_word).pack(side="left")
        ttk.Button(btn_row, text="Update selected", command=update_selected).pack(
            side="left", padx=10
        )
        ttk.Button(btn_row, text="Delete selected", command=delete_selected).pack(
            side="left"
        )

        tree.bind("<<TreeviewSelect>>", load_selected_into_form)
        refresh_tree()


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

    def _adjust_text_height(
        self, widget: tk.Text, min_lines: int = 2, max_lines: int = 6
    ):
        try:
            line_count = int(widget.index("end-1c").split(".")[0])
        except Exception:
            line_count = min_lines
        new_h = max(min_lines, min(line_count, max_lines))
        widget.configure(height=new_h)

    def _on_text_enter(self, _event=None):
        # Enter => Check and DO NOT insert newline. Returning "break" stops propagation/default action. [web:276]
        self.check()
        return "break"

    def _on_text_shift_enter(self, event):
        # Shift+Enter => insert newline (manual) and stop other handlers (so it doesn't trigger global check).
        event.widget.insert("insert", "\n")
        self._adjust_text_height(event.widget)
        return "break"

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x")

        ttk.Label(top, text="Topic:", style="Big.TLabel").pack(side="left")
        self.topic_box = ttk.Combobox(
            top, textvariable=self.topic_var, state="readonly", width=30
        )
        self.topic_box["values"] = self._topics()
        self.topic_box.pack(side="left", padx=10, ipady=6)
        self.topic_box.bind("<<ComboboxSelected>>", lambda _e: self.next_words())

        ttk.Label(top, text="Tense:", style="Big.TLabel").pack(
            side="left", padx=(18, 0)
        )
        self.tense_box = ttk.Combobox(
            top, textvariable=self.tense_var, state="readonly", width=30
        )
        self.tense_box["values"] = TENSES
        self.tense_box.pack(side="left", padx=10, ipady=6)

        ttk.Button(
            top, text="Refresh", command=self.reset_progress, style="Big.TButton"
        ).pack(side="right")
        ttk.Button(
            top, text="Next 5 words", command=self.next_words, style="Big.TButton"
        ).pack(side="right", padx=10)

        self.stats_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.stats_var, style="Big.TLabel").pack(
            anchor="w", pady=(14, 10)
        )

        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True, pady=(8, 14))

        for c in range(3):
            grid.columnconfigure(c, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        wrap = 420

        for i in range(5):
            col = ttk.LabelFrame(grid, text=f"Word {i+1}", style="Big.TLabelframe")
            if i < 3:
                col.grid(row=0, column=i, sticky="nsew", padx=10, pady=10)
            else:
                col.grid(
                    row=1, column=0 if i == 3 else 2, sticky="nsew", padx=10, pady=10
                )

            ttk.Label(
                col, textvariable=self.word_vars[i], wraplength=wrap, style="Big.TLabel"
            ).pack(anchor="w", padx=12, pady=(12, 6))
            ttk.Label(
                col,
                text="Write a sentence with this word.",
                style="Big.TLabel",
                wraplength=wrap,
            ).pack(anchor="w", padx=12, pady=(0, 8))

            text_frame = ttk.Frame(col)
            text_frame.pack(fill="both", expand=True, padx=12, pady=6)

            txt = tk.Text(text_frame, wrap="word", height=2, font=("Helvetica", 16))
            scr = ttk.Scrollbar(text_frame, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=scr.set)

            txt.pack(side="left", fill="both", expand=True)
            scr.pack(side="right", fill="y")

            # Key behavior:
            # Enter => check (and prevent newline)
            # Shift+Enter => newline
            txt.bind("<Return>", self._on_text_enter)
            txt.bind("<Shift-Return>", self._on_text_shift_enter)

            txt.bind("<KeyRelease>", lambda e, w=txt: self._adjust_text_height(w))

            self.text_widgets.append(txt)

            ttk.Label(
                col,
                textvariable=self.result_vars[i],
                wraplength=wrap,
                style="Big.TLabel",
            ).pack(anchor="w", padx=12, pady=(8, 12))

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(8, 0))

        ttk.Button(btns, text="Check", command=self.check, style="Big.TButton").pack(
            side="left"
        )
        ttk.Button(
            btns, text="Show details", command=self.show_details, style="Big.TButton"
        ).pack(side="left", padx=10)
        ttk.Button(
            btns, text="Clear", command=self.clear_inputs, style="Big.TButton"
        ).pack(side="left")

        if not self.topic_var.get():
            self.topic_var.set("All topics")
        self.topic_box.set(self.topic_var.get())
        self.tense_box.set(self.tense_var.get())

    def _refresh_stats(self):
        total = len(self._topic_pool_all())
        remaining = len(self._topic_pool_remaining())
        done = total - remaining
        self.stats_var.set(f"In topic: {total} | Done: {done} | Left: {remaining}")

        cur = self.topic_var.get() or "All topics"
        self.topic_box["values"] = self._topics()
        if cur not in self.topic_box["values"]:
            cur = "All topics"
            self.topic_var.set(cur)
        self.topic_box.set(cur)

    def _show_end(self):
        self.current_words = []
        self.last_matches = [[] for _ in range(5)]
        for i in range(5):
            self.word_vars[i].set("END")
            self.result_vars[i].set("Press Refresh to start again.")
            self.text_widgets[i].delete("1.0", "end")
            self._adjust_text_height(self.text_widgets[i])

    def next_words(self):
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
            self._adjust_text_height(self.text_widgets[i])

            if i < take:
                w = self.current_words[i].get("en", "")
                self.word_vars[i].set(w)
                self.result_vars[i].set("")
            else:
                self.word_vars[i].set("END")
                self.result_vars[i].set("")

    def clear_inputs(self):
        for i in range(5):
            self.text_widgets[i].delete("1.0", "end")
            self._adjust_text_height(self.text_widgets[i])
            self.result_vars[i].set("")
        self.last_matches = [[] for _ in range(5)]

    def check(self):
        if not self.current_words:
            return

        if self.online_var.get() != "Online":
            messagebox.showwarning(
                "Offline", "LanguageTool is Offline. Grammar check won't work."
            )
            return

        tense = self.tense_var.get().strip() or TENSES[0]

        for i in range(5):
            if i >= len(self.current_words):
                continue

            item = self.current_words[i]
            word = item.get("en", "")
            sentence = self.text_widgets[i].get("1.0", "end-1c").strip()

            if not sentence:
                self.result_vars[i].set("Type a sentence.")
                self.last_matches[i] = []
                continue

            res = check_sentence(sentence=sentence, required_word=word, tense=tense)
            self.last_matches[i] = res.matches or []

            if res.ok:
                self.result_vars[i].set("Correct.")
                self.used_words.add(_word_key_sentence(item))
            else:
                self.result_vars[i].set(res.message[:180])

        self._refresh_stats()

    def show_details(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Details (LanguageTool matches)")
        win.geometry("1200x700")

        ttk.Label(win, text="Each row = one match from LanguageTool.", padding=10).pack(
            anchor="w"
        )

        cols = ("slot", "word", "rule", "message", "offset", "length", "repl")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("slot", width=50)
        tree.column("word", width=140)
        tree.column("rule", width=220)
        tree.column("message", width=520)
        tree.column("offset", width=70)
        tree.column("length", width=70)
        tree.column("repl", width=240)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def add_row(slot_idx: int, word: str, m: dict):
            rule_obj = m.get("rule", {}) or {}
            rule = rule_obj.get("id", "") or ""
            msg = m.get("message", "") or ""
            offset = m.get("offset", "")
            length = m.get("length", "")
            repls = m.get("replacements", []) or []
            repl_txt = ", ".join(
                [r.get("value", "") for r in repls[:5] if r.get("value")]
            )
            tree.insert(
                "",
                "end",
                values=(slot_idx + 1, word, rule, msg, offset, length, repl_txt),
            )

        for i in range(5):
            word = self.word_vars[i].get()
            matches = self.last_matches[i] if i < len(self.last_matches) else []
            for m in matches:
                add_row(i, word, m)

        if not tree.get_children():
            ttk.Label(
                win, text="No matches to show (try Check first).", padding=10
            ).pack(anchor="w")
