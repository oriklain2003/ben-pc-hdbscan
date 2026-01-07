import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

class SQLiteBrowserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python SQLite Browser")
        self.root.geometry("1000x700")

        self.conn = None
        self.cursor = None
        self.current_db_path = None

        # --- Styles ---
        style = ttk.Style()
        style.theme_use('clam')

        # --- Layout Containers ---
        # Top Control Panel
        self.top_frame = ttk.Frame(self.root, padding="10")
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        self.btn_load = ttk.Button(self.top_frame, text="Open Database", command=self.load_database)
        self.btn_load.pack(side=tk.LEFT, padx=5)

        self.lbl_status = ttk.Label(self.top_frame, text="No database loaded", foreground="red")
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # Main Paned Window (Split Left/Right)
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- LEFT SIDE: Table List ---
        self.left_frame = ttk.Labelframe(self.paned, text="Tables", padding="5")
        self.paned.add(self.left_frame, weight=1)

        self.list_tables = tk.Listbox(self.left_frame, selectmode=tk.SINGLE)
        self.list_tables.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_tables.bind('<<ListboxSelect>>', self.on_table_select)

        # Scrollbar for table list
        self.scroll_tables = ttk.Scrollbar(self.left_frame, orient="vertical", command=self.list_tables.yview)
        self.scroll_tables.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_tables.config(yscrollcommand=self.scroll_tables.set)

        # --- RIGHT SIDE: Tabs (Data, SQL, Schema) ---
        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=4)

        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Data Browser
        self.tab_data = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_data, text="Browse Data")
        self.setup_data_tab()

        # Tab 2: SQL Terminal
        self.tab_sql = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_sql, text="SQL Terminal")
        self.setup_sql_tab()

        # Tab 3: Schema Viewer
        self.tab_schema = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_schema, text="Schema Info")
        self.setup_schema_tab()

    def setup_data_tab(self):
        """Sets up the Treeview for browsing table data."""
        # Container for Treeview and Scrollbars
        frame = ttk.Frame(self.tab_data)
        frame.pack(fill=tk.BOTH, expand=True)

        self.tree_data = ttk.Treeview(frame, show='headings')
        self.tree_data.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree_data.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll = ttk.Scrollbar(self.tab_data, orient="horizontal", command=self.tree_data.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree_data.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    def setup_sql_tab(self):
        """Sets up the SQL input area and result view."""
        # Input Area
        input_frame = ttk.LabelFrame(self.tab_sql, text="SQL Query", padding="5")
        input_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        self.txt_sql = scrolledtext.ScrolledText(input_frame, height=5, font=("Consolas", 10))
        self.txt_sql.pack(fill=tk.BOTH, expand=True)

        btn_run = ttk.Button(input_frame, text="Execute Query (Ctrl+Enter)", command=self.run_custom_query)
        btn_run.pack(side=tk.RIGHT, pady=5)

        # Bind Ctrl+Enter to run query
        self.txt_sql.bind('<Control-Return>', lambda e: self.run_custom_query())

        # Results Area
        result_frame = ttk.LabelFrame(self.tab_sql, text="Results", padding="5")
        result_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree_sql = ttk.Treeview(result_frame, show='headings')
        self.tree_sql.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree_sql.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll = ttk.Scrollbar(result_frame, orient="horizontal", command=self.tree_sql.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree_sql.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    def setup_schema_tab(self):
        """Sets up a text area to show schema details."""
        self.txt_schema = scrolledtext.ScrolledText(self.tab_schema, font=("Consolas", 10))
        self.txt_schema.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # --- Logic ---

    def load_database(self):
        filepath = filedialog.askopenfilename(filetypes=[("SQLite Files", "*.db *.sqlite *.sqlite3"), ("All Files", "*.*")])
        if not filepath:
            return

        try:
            if self.conn:
                self.conn.close()
            
            self.conn = sqlite3.connect(filepath)
            self.cursor = self.conn.cursor()
            self.current_db_path = filepath
            
            self.lbl_status.config(text=f"Loaded: {filepath}", foreground="green")
            self.refresh_tables()
            
            # Clear previous views
            self.clear_tree(self.tree_data)
            self.clear_tree(self.tree_sql)
            self.txt_schema.delete(1.0, tk.END)

        except Exception as e:
            messagebox.showerror("Error", f"Could not open database:\n{e}")

    def refresh_tables(self):
        self.list_tables.delete(0, tk.END)
        # Query to get all table names (excluding sqlite internals)
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        self.cursor.execute(query)
        tables = self.cursor.fetchall()
        for table in tables:
            self.list_tables.insert(tk.END, table[0])

    def on_table_select(self, event):
        selection = self.list_tables.curselection()
        if not selection:
            return
        
        table_name = self.list_tables.get(selection[0])
        
        # Update Data Tab
        self.load_table_data(table_name)
        # Update Schema Tab
        self.load_table_schema(table_name)

    def load_table_data(self, table_name):
        self.clear_tree(self.tree_data)
        try:
            # Get columns
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = self.cursor.fetchall()
            col_names = [info[1] for info in columns_info]

            self.tree_data["columns"] = col_names
            for col in col_names:
                self.tree_data.heading(col, text=col)
                self.tree_data.column(col, width=100, anchor="w")

            # Get data
            self.cursor.execute(f"SELECT * FROM {table_name}")
            rows = self.cursor.fetchall()
            for row in rows:
                self.tree_data.insert("", tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Error loading table data:\n{e}")

    def load_table_schema(self, table_name):
        self.txt_schema.delete(1.0, tk.END)
        try:
            # Get CREATE statement
            self.cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            create_stmt = self.cursor.fetchone()
            
            # Get detailed column info
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            col_info = self.cursor.fetchall()

            display_text = f"=== CREATE STATEMENT ===\n\n{create_stmt[0]}\n\n"
            display_text += "=== COLUMN DETAILS (CID, Name, Type, NotNull, Default, PK) ===\n\n"
            for col in col_info:
                display_text += str(col) + "\n"

            self.txt_schema.insert(tk.END, display_text)
            
        except Exception as e:
            self.txt_schema.insert(tk.END, f"Error loading schema: {e}")

    def run_custom_query(self):
        if not self.conn:
            messagebox.showwarning("Warning", "Please load a database first.")
            return

        query = self.txt_sql.get(1.0, tk.END).strip()
        if not query:
            return

        self.clear_tree(self.tree_sql)

        try:
            self.cursor.execute(query)
            
            # If query is a SELECT, fetch results
            if self.cursor.description:
                col_names = [description[0] for description in self.cursor.description]
                self.tree_sql["columns"] = col_names
                
                for col in col_names:
                    self.tree_sql.heading(col, text=col)
                    self.tree_sql.column(col, width=100)

                rows = self.cursor.fetchall()
                for row in rows:
                    self.tree_sql.insert("", tk.END, values=row)
                
                # Switch to SQL tab to show results if not already there
                self.notebook.select(self.tab_sql)
            else:
                # For INSERT, UPDATE, DELETE
                self.conn.commit()
                messagebox.showinfo("Success", f"Query executed successfully.\nRows affected: {self.cursor.rowcount}")
                self.refresh_tables() # Refresh in case a table was created/dropped

        except sqlite3.Error as e:
            messagebox.showerror("SQL Error", f"An error occurred:\n{e}")

    def clear_tree(self, tree):
        tree.delete(*tree.get_children())
        tree["columns"] = []

if __name__ == "__main__":
    root = tk.Tk()
    app = SQLiteBrowserApp(root)
    root.mainloop()