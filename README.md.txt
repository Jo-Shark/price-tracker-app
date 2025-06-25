# 🛍️ Price Tracker App

A powerful Python desktop application to track product prices in real-time with a GUI.

## ✨ Features

- GUI built with `Tkinter`
- Scrapes websites using `requests`, `BeautifulSoup`, and `Playwright`
- Auto/Manual tracking mode
- Alerts when prices drop or hit target
- Stores price history in SQLite
- Exports to JSON
- Backup & reset functionality
- Multi-tab interface with product management

## 🧰 Technologies Used

- Python 3.13
- `playwright`
- `beautifulsoup4`
- `requests`
- `sqlite3`
- `pathlib`, `shutil`, `threading`

## 🚀 How to Run

```bash
pip install -r requirements.txt
python -m playwright install
python main.py