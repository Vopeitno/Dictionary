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


def main():
    """Оптимизированная главная функция"""
    # Загружаем данные до создания UI
    ensure_seed()
    
    # Создаем окно с минимальными настройками
    root = tk.Tk()
    root.title("LinguaFlow • Learn English")
    
    # Отключаем визуальные эффекты для производительности
    root.attributes('-alpha', 1.0)
    root.attributes('-fullscreen', 0)
    
    # Устанавливаем тему ДО создания виджетов
    sv_ttk.set_theme("dark")
    
    # Устанавливаем размеры
    root.geometry("1200x800")
    
    try:
        # Создаем приложение
        app = MainApp(root)
        
        # Обновляем интерфейс один раз
        root.update_idletasks()
        
        # Запускаем главный цикл
        root.mainloop()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()