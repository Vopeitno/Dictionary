import tkinter as tk
import sv_ttk
from ui_app import MainApp
from storage import load_vocab, save_vocab
from words_seed import SEED_WORDS


def ensure_seed():
    """Обеспечить наличие начальных слов"""
    items = load_vocab()
    if items:
        return
    save_vocab(SEED_WORDS)


def center_window(window, width=1400, height=900):
    """Центрировать окно на экране"""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    window.geometry(f"{width}x{height}+{x}+{y}")


def main():
    """Основная функция"""
    ensure_seed()

    root = tk.Tk()
    root.title("LinguaFlow • English Learning Platform")
    
    # Установка иконки (если есть)
    try:
        root.iconbitmap("icon.ico")
    except:
        pass
    
    # Центрирование окна
    center_window(root, 1400, 900)
    
    # Создание приложения
    app = MainApp(root)
    
    # Запуск главного цикла
    root.mainloop()


if __name__ == "__main__":
    main()