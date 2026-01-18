import tkinter as tk
from tkinter import ttk

from storage import load_vocab, save_vocab
from ui_app import MainApp
from words_seed import SEED_WORDS


def ensure_seed():
    items = load_vocab()
    if items:
        return
    save_vocab(SEED_WORDS)


def main():
    ensure_seed()
    root = tk.Tk()
    root.geometry("1920x1080")

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    MainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
