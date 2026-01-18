import tkinter as tk
from ui_app import MainApp
from storage import load_vocab, save_vocab
from words_seed import SEED_WORDS

import sv_ttk


def ensure_seed():
    items = load_vocab()
    if items:
        return
    save_vocab(SEED_WORDS)


def main():
    ensure_seed()

    root = tk.Tk()
    root.geometry("1920x1080")

    sv_ttk.set_theme("dark")  

    MainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
