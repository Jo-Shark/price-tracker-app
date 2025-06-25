"""
Price Tracker App
A comprehensive price tracking application using tkinter, playwright, beautifulsoup, and sqlite3
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import threading
import time
import json
from datetime import datetime
from pathlib import Path
import shutil
import re

class PriceTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Price Tracker")
        self.root.geometry("1000x700")
        
        # Database setup
        self.db_path = Path("price_tracker.db")
        self.init_database()
        
        # Tracking variables
        self.tracking_active = False
        self.tracking_thread = None
        
        # Create GUI
        self.create_widgets()
        self.load_products()
        
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                target_price REAL,
                current_price REAL,
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                selector TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        
        # Price history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                price REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_widgets(self):
        """Create the main GUI widgets"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Product Management
        self.product_frame = ttk.Frame(notebook)
        notebook.add(self.product_frame, text="Products")
        self.create_product_tab()
        
        # Tab 2: Price History
        self.history_frame = ttk.Frame(notebook)
        notebook.add(self.history_frame, text="Price History")
        self.create_history_tab()
        
        # Tab 3: Settings
        self.settings_frame = ttk.Frame(notebook)
        notebook.add(self.settings_frame, text="Settings")
        self.create_settings_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken')
        status_bar.pack(side='bottom', fill='x')
    
    def create_product_tab(self):
        """Create the product management tab"""
        # Top frame for adding products
        add_frame = ttk.LabelFrame(self.product_frame, text="Add New Product", padding=10)
        add_frame.pack(fill='x', padx=5, pady=5)
        
        # Product name
        ttk.Label(add_frame, text="Product Name:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.name_entry = ttk.Entry(add_frame, width=30)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2)
        
        # Product URL
        ttk.Label(add_frame, text="Product URL:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.url_entry = ttk.Entry(add_frame, width=50)
        self.url_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=2, sticky='ew')
        
        # Target price
        ttk.Label(add_frame, text="Target Price:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.target_price_entry = ttk.Entry(add_frame, width=15)
        self.target_price_entry.grid(row=2, column=1, padx=5, pady=2, sticky='w')
        
        # Price selector (CSS selector)
        ttk.Label(add_frame, text="Price Selector:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.selector_entry = ttk.Entry(add_frame, width=30)
        self.selector_entry.grid(row=3, column=1, padx=5, pady=2)
        ttk.Label(add_frame, text="(CSS selector for price element)").grid(row=3, column=2, sticky='w', padx=5)
        
        # Buttons
        button_frame = ttk.Frame(add_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Add Product", command=self.add_product).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Test Price Detection", command=self.test_price_detection).pack(side='left', padx=5)
        
        # Product list frame
        list_frame = ttk.LabelFrame(self.product_frame, text="Tracked Products", padding=10)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Treeview for products
        columns = ('Name', 'Current Price', 'Target Price', 'Last Checked', 'Status')
        self.product_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.product_tree.heading(col, text=col)
            self.product_tree.column(col, width=150)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.product_tree.yview)
        self.product_tree.configure(yscrollcommand=scrollbar.set)
        
        self.product_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Product control buttons
        control_frame = ttk.Frame(self.product_frame)
        control_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(control_frame, text="Check Prices Now", command=self.check_prices_manual).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Start Auto Tracking", command=self.start_tracking).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Stop Auto Tracking", command=self.stop_tracking).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Delete Selected", command=self.delete_product).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Export Data", command=self.export_data).pack(side='right', padx=5)
    
    def create_history_tab(self):
        """Create the price history tab"""
        # History controls
        control_frame = ttk.Frame(self.history_frame)
        control_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(control_frame, text="Select Product:").pack(side='left', padx=5)
        self.history_product_var = tk.StringVar()
        self.history_product_combo = ttk.Combobox(control_frame, textvariable=self.history_product_var, 
                                                 width=30, state='readonly')
        self.history_product_combo.pack(side='left', padx=5)
        self.history_product_combo.bind('<<ComboboxSelected>>', self.load_price_history)
        
        ttk.Button(control_frame, text="Refresh", command=self.refresh_history_products).pack(side='left', padx=5)
        
        # History treeview
        history_columns = ('Date', 'Price', 'Change')
        self.history_tree = ttk.Treeview(self.history_frame, columns=history_columns, show='headings', height=20)
        
        for col in history_columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=200)
        
        # Scrollbar for history
        history_scrollbar = ttk.Scrollbar(self.history_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        self.history_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        history_scrollbar.pack(side='right', fill='y', pady=5)
    
    def create_settings_tab(self):
        """Create the settings tab"""
        # Tracking settings
        tracking_frame = ttk.LabelFrame(self.settings_frame, text="Tracking Settings", padding=10)
        tracking_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(tracking_frame, text="Check Interval (minutes):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.interval_var = tk.StringVar(value="60")
        ttk.Entry(tracking_frame, textvariable=self.interval_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(tracking_frame, text="User Agent:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.user_agent_var = tk.StringVar(value="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        ttk.Entry(tracking_frame, textvariable=self.user_agent_var, width=60).grid(row=1, column=1, padx=5, pady=5)
        
        # Notification settings
        notif_frame = ttk.LabelFrame(self.settings_frame, text="Notification Settings", padding=10)
        notif_frame.pack(fill='x', padx=5, pady=5)
        
        self.notify_price_drop = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame, text="Notify on price drops", variable=self.notify_price_drop).pack(anchor='w')
        
        self.notify_target_reached = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame, text="Notify when target price is reached", 
                       variable=self.notify_target_reached).pack(anchor='w')
        
        # Database settings
        db_frame = ttk.LabelFrame(self.settings_frame, text="Database Management", padding=10)
        db_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(db_frame, text="Backup Database", command=self.backup_database).pack(side='left', padx=5)
        ttk.Button(db_frame, text="Clear History", command=self.clear_history).pack(side='left', padx=5)
        ttk.Button(db_frame, text="Reset Database", command=self.reset_database).pack(side='left', padx=5)
    
    def add_product(self):
        """Add a new product to track"""
        name = self.name_entry.get().strip()
        url = self.url_entry.get().strip()
        target_price = self.target_price_entry.get().strip()
        selector = self.selector_entry.get().strip()
        
        if not name or not url:
            messagebox.showerror("Error", "Please provide both product name and URL")
            return
        
        try:
            target_price = float(target_price) if target_price else None
        except ValueError:
            messagebox.showerror("Error", "Invalid target price")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO products (name, url, target_price, selector)
                VALUES (?, ?, ?, ?)
            ''', (name, url, target_price, selector))
            conn.commit()
            conn.close()
            
            # Clear entries
            self.name_entry.delete(0, tk.END)
            self.url_entry.delete(0, tk.END)
            self.target_price_entry.delete(0, tk.END)
            self.selector_entry.delete(0, tk.END)
            
            self.load_products()
            messagebox.showinfo("Success", "Product added successfully!")
            
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "This URL is already being tracked")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add product: {str(e)}")
    
    def test_price_detection(self):
        """Test price detection for the entered URL and selector"""
        url = self.url_entry.get().strip()
        selector = self.selector_entry.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        self.status_var.set("Testing price detection...")
        
        def test_thread():
            try:
                price = self.get_price(url, selector)
                if price:
                    self.root.after(0, lambda: messagebox.showinfo("Success", f"Price detected: ${price:.2f}"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Warning", "Could not detect price"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to test: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("Ready"))
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def get_price(self, url, selector=None):
        """Extract price from URL using multiple methods"""
        try:
            # Method 1: Try with requests + BeautifulSoup
            headers = {
                'User-Agent': self.user_agent_var.get(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            price = self.extract_price_from_soup(soup, selector)
            
            if price:
                return price
            
            # Method 2: Try with Playwright for JavaScript-heavy sites
            return self.get_price_with_playwright(url, selector)
            
        except Exception as e:
            print(f"Error getting price: {e}")
            return None
    
    def extract_price_from_soup(self, soup, selector=None):
        """Extract price from BeautifulSoup object"""
        price_patterns = [
            r'\$[\d,]+\.?\d*',
            r'USD\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*USD',
            r'Price:\s*\$?[\d,]+\.?\d*',
            r'[\d,]+\.?\d*'
        ]
        
        # Try custom selector first
        if selector:
            elements = soup.select(selector)
            for element in elements:
                price = self.parse_price_text(element.get_text())
                if price:
                    return price
        
        # Try common price selectors
        common_selectors = [
            '.price', '#price', '.product-price', '.current-price',
            '[data-price]', '.price-current', '.price-now',
            '.offer-price', '.sale-price', '.final-price'
        ]
        
        for sel in common_selectors:
            elements = soup.select(sel)
            for element in elements:
                price = self.parse_price_text(element.get_text())
                if price:
                    return price
        
        # Try finding price in text content
        text = soup.get_text()
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                price = self.parse_price_text(match)
                if price and price > 0:
                    return price
        
        return None
    
    def get_price_with_playwright(self, url, selector=None):
        """Get price using Playwright for JavaScript-heavy sites"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers({
                    'User-Agent': self.user_agent_var.get()
                })
                
                page.goto(url, wait_until='networkidle')
                
                if selector:
                    try:
                        element = page.query_selector(selector)
                        if element:
                            text = element.inner_text()
                            price = self.parse_price_text(text)
                            if price:
                                browser.close()
                                return price
                    except:
                        pass
                
                # Try common selectors
                common_selectors = [
                    '.price', '#price', '.product-price', '.current-price',
                    '[data-price]', '.price-current', '.price-now'
                ]
                
                for sel in common_selectors:
                    try:
                        element = page.query_selector(sel)
                        if element:
                            text = element.inner_text()
                            price = self.parse_price_text(text)
                            if price:
                                browser.close()
                                return price
                    except:
                        continue
                
                browser.close()
                return None
                
        except Exception as e:
            print(f"Playwright error: {e}")
            return None
    
    def parse_price_text(self, text):
        """Parse price from text string"""
        if not text:
            return None
        
        # Remove common currency symbols and clean text
        text = re.sub(r'[^\d.,]', '', text.strip())
        text = re.sub(r',', '', text)
        
        try:
            # Handle different decimal formats
            if '.' in text:
                return float(text)
            else:
                return float(text)
        except:
            return None
    
    def load_products(self):
        """Load products into the treeview"""
        # Clear existing items
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, current_price, target_price, last_checked, active
            FROM products WHERE active = 1
        ''')
        
        for row in cursor.fetchall():
            name, current_price, target_price, last_checked, active = row
            
            # Format prices
            current_str = f"${current_price:.2f}" if current_price else "N/A"
            target_str = f"${target_price:.2f}" if target_price else "N/A"
            
            # Format last checked
            if last_checked:
                last_checked_dt = datetime.fromisoformat(last_checked)
                last_checked_str = last_checked_dt.strftime("%Y-%m-%d %H:%M")
            else:
                last_checked_str = "Never"
            
            # Status
            status = "Active" if active else "Inactive"
            if current_price and target_price and current_price <= target_price:
                status = "Target Reached!"
            
            self.product_tree.insert('', 'end', values=(name, current_str, target_str, last_checked_str, status))
        
        conn.close()
    
    def check_prices_manual(self):
        """Manually check prices for all products"""
        self.status_var.set("Checking prices...")
        
        def check_thread():
            try:
                self.check_all_prices()
                self.root.after(0, lambda: self.status_var.set("Price check completed"))
                self.root.after(0, self.load_products)
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
        
        threading.Thread(target=check_thread, daemon=True).start()
    
    def check_all_prices(self):
        """Check prices for all active products"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, url, selector, current_price, target_price FROM products WHERE active = 1')
        products = cursor.fetchall()
        
        for product_id, name, url, selector, old_price, target_price in products:
            try:
                new_price = self.get_price(url, selector)
                
                if new_price:
                    # Update product
                    cursor.execute('''
                        UPDATE products 
                        SET current_price = ?, last_checked = ?
                        WHERE id = ?
                    ''', (new_price, datetime.now().isoformat(), product_id))
                    
                    # Add to price history
                    cursor.execute('''
                        INSERT INTO price_history (product_id, price)
                        VALUES (?, ?)
                    ''', (product_id, new_price))
                    
                    # Check for notifications
                    if old_price and new_price < old_price and self.notify_price_drop.get():
                        self.show_notification(f"Price drop for {name}: ${new_price:.2f}")
                    
                    if target_price and new_price <= target_price and self.notify_target_reached.get():
                        self.show_notification(f"Target price reached for {name}: ${new_price:.2f}")
                
            except Exception as e:
                print(f"Error checking price for {name}: {e}")
        
        conn.commit()
        conn.close()
    
    def show_notification(self, message):
        """Show notification message"""
        self.root.after(0, lambda: messagebox.showinfo("Price Alert", message))
    
    def start_tracking(self):
        """Start automatic price tracking"""
        if self.tracking_active:
            messagebox.showinfo("Info", "Tracking is already active")
            return
        
        self.tracking_active = True
        self.tracking_thread = threading.Thread(target=self.tracking_loop, daemon=True)
        self.tracking_thread.start()
        
        self.status_var.set("Auto tracking started")
        messagebox.showinfo("Success", "Automatic price tracking started")
    
    def stop_tracking(self):
        """Stop automatic price tracking"""
        self.tracking_active = False
        self.status_var.set("Auto tracking stopped")
        messagebox.showinfo("Success", "Automatic price tracking stopped")
    
    def tracking_loop(self):
        """Main tracking loop"""
        while self.tracking_active:
            try:
                self.check_all_prices()
                self.root.after(0, self.load_products)
                
                # Wait for specified interval
                interval_minutes = int(self.interval_var.get())
                for _ in range(interval_minutes * 60):  # Convert to seconds
                    if not self.tracking_active:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Tracking error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def delete_product(self):
        """Delete selected product"""
        selection = self.product_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product to delete")
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this product?"):
            item = self.product_tree.item(selection[0])
            product_name = item['values'][0]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE products SET active = 0 WHERE name = ?', (product_name,))
            conn.commit()
            conn.close()
            
            self.load_products()
            messagebox.showinfo("Success", "Product deleted successfully")
    
    def load_price_history(self, event=None):
        """Load price history for selected product"""
        selected_product = self.history_product_var.get()
        if not selected_product:
            return
        
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ph.price, ph.timestamp
            FROM price_history ph
            JOIN products p ON ph.product_id = p.id
            WHERE p.name = ?
            ORDER BY ph.timestamp DESC
        ''', (selected_product,))
        
        history = cursor.fetchall()
        previous_price = None
        
        for price, timestamp in history:
            # Format timestamp
            dt = datetime.fromisoformat(timestamp)
            date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Calculate change
            change_str = ""
            if previous_price:
                change = price - previous_price
                if change > 0:
                    change_str = f"+${change:.2f}"
                elif change < 0:
                    change_str = f"-${abs(change):.2f}"
                else:
                    change_str = "No change"
            
            self.history_tree.insert('', 'end', values=(date_str, f"${price:.2f}", change_str))
            previous_price = price
        
        conn.close()
    
    def refresh_history_products(self):
        """Refresh the product list in history tab"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM products WHERE active = 1')
        products = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        self.history_product_combo['values'] = products
    
    def export_data(self):
        """Export tracking data to JSON file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Export products
                cursor.execute('SELECT * FROM products WHERE active = 1')
                products = cursor.fetchall()
                
                # Export price history
                cursor.execute('''
                    SELECT ph.*, p.name
                    FROM price_history ph
                    JOIN products p ON ph.product_id = p.id
                    WHERE p.active = 1
                ''')
                history = cursor.fetchall()
                
                data = {
                    'products': products,
                    'history': history,
                    'export_date': datetime.now().isoformat()
                }
                
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                
                conn.close()
                messagebox.showinfo("Success", f"Data exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export data: {str(e)}")
    
    def backup_database(self):
        """Create a backup of the database"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"price_tracker_backup_{timestamp}.db"
        
        try:
            shutil.copy2(self.db_path, backup_name)
            messagebox.showinfo("Success", f"Database backed up to {backup_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to backup database: {str(e)}")
    
    def clear_history(self):
        """Clear price history"""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all price history?"):
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM price_history')
                conn.commit()
                conn.close()
                
                self.load_price_history()
                messagebox.showinfo("Success", "Price history cleared")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear history: {str(e)}")
    
    def reset_database(self):
        """Reset the entire database"""
        if messagebox.askyesno("Confirm", "Are you sure you want to reset the entire database? This cannot be undone!"):
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('DROP TABLE IF EXISTS products')
                cursor.execute('DROP TABLE IF EXISTS price_history')
                conn.close()
                
                self.init_database()
                self.load_products()
                messagebox.showinfo("Success", "Database reset successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset database: {str(e)}")

def main():
    root = tk.Tk()
    app = PriceTracker(root)
    
    # Load products and refresh history on startup
    app.refresh_history_products()
    
    root.mainloop()

if __name__ == "__main__":
    main()