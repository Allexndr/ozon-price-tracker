import os
import tkinter as tk
from tkinter import ttk
<<<<<<< HEAD
import json
=======
>>>>>>> khan

MAX_ROWS = 10


class App(tk.Tk):
    def __init__(self):
        super().__init__()
<<<<<<< HEAD
        self.title("Ozon Parser - Добавление товаров")
        self.geometry("600x400")
=======
        self.title("GUI для товаров")
        self.geometry("500x400")
>>>>>>> khan

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.items_tab = ttk.Frame(self.notebook)
        self.ignore_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.items_tab, text="Товары")
        self.notebook.add(self.ignore_tab, text="Игнорирование")

        self.item_rows = []
        self.ignore_rows = []

        self.backup_old_files()
        self.init_items_tab()
        self.init_ignore_tab()

    def init_items_tab(self):
        self.item_container = ttk.Frame(self.items_tab)
        self.item_container.pack(pady=10, fill="x")

        self.add_item_row()

    def add_item_row(self):
        if len(self.item_rows) >= MAX_ROWS:
            return

        row = ttk.Frame(self.item_container)
        row.pack(pady=5)

        name_entry = ttk.Entry(row, width=30)
        name_entry.pack(side="left", padx=5)

        price_entry = ttk.Entry(row, width=15)
        price_entry.pack(side="left", padx=5)

        if len(self.item_rows) < MAX_ROWS - 1:
            add_button = ttk.Button(row, text="Добавить", command=self.add_item_row)
            add_button.pack(side="left", padx=5)
        else:
            add_button = None

        self.item_rows.append((name_entry, price_entry, add_button))
        self.save_items()

        self.update_item_buttons()

    def update_item_buttons(self):
        for i, (_, _, btn) in enumerate(self.item_rows):
            if btn:
                if i == len(self.item_rows) - 1 and len(self.item_rows) < MAX_ROWS:
                    btn.configure(state="normal")
                else:
                    btn.configure(state="disabled")

    def save_items(self):
        with open("list.txt", "w", encoding="utf-8") as f:
            for name_entry, price_entry, _ in self.item_rows:
                name = name_entry.get().strip()
                price = price_entry.get().strip()
                if name or price:
                    f.write(f"{name},{price}\n")

    def init_ignore_tab(self):
        self.ignore_container = ttk.Frame(self.ignore_tab)
        self.ignore_container.pack(pady=10, fill="x")

        self.add_ignore_row()

    def add_ignore_row(self):
        if len(self.ignore_rows) >= MAX_ROWS:
            return

        row = ttk.Frame(self.ignore_container)
        row.pack(pady=5)

        word_entry = ttk.Entry(row, width=40)
        word_entry.pack(side="left", padx=5)

        if len(self.ignore_rows) < MAX_ROWS - 1:
            add_button = ttk.Button(row, text="Добавить", command=self.add_ignore_row)
            add_button.pack(side="left", padx=5)
        else:
            add_button = None

        self.ignore_rows.append((word_entry, add_button))
        self.save_ignore()

        self.update_ignore_buttons()

    def update_ignore_buttons(self):
        for i, (_, btn) in enumerate(self.ignore_rows):
            if btn:
                if i == len(self.ignore_rows) - 1 and len(self.ignore_rows) < MAX_ROWS:
                    btn.configure(state="normal")
                else:
                    btn.configure(state="disabled")

    def save_ignore(self):
        with open("ignore_list.txt", "w", encoding="utf-8") as f:
            for word_entry, _ in self.ignore_rows:
                word = word_entry.get().strip()
                if word:
                    f.write(f"{word}\n")

    def backup_old_files(self):
        if os.path.exists("list.txt"):
            os.replace("list.txt", "list_old.txt")
        if os.path.exists("ignore_list.txt"):
            os.replace("ignore_list.txt", "ignore_list_old.txt")


def start_gui_app():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    start_gui_app()
