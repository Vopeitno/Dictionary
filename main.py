import tkinter as tk
import sv_ttk

from ui_app import MainApp
from storage import load_vocab, save_vocab
from words_seed import SEED_WORDS


def ensure_seed():
    items = load_vocab()
    if items:
        return
    save_vocab(SEED_WORDS)


def main():
    ensure_seed()

    root = tk.Tk()
    root.title("DictionaryApp")
    root.geometry("1920x1080")

    sv_ttk.set_theme("dark")  # must be after root is created [web:599]

    MainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
