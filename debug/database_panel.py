import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sys
import os
import sqlite3

# 添加项目根目录到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from data.database_manager import DatabaseManager
from data.config import Config


class DatabaseQueryPanel:
    def __init__(self, master=None):
        """
        数据库查询面板

        Args:
            master: Tkinter根窗口，默认为None
        """
        # 创建顶层窗口
        self.window = tk.Toplevel(master) if master else tk.Tk()
        self.window.title("数据库查询调试面板")
        self.window.geometry("1000x700")

        # 初始化数据库管理器
        config = Config()
        db_path = config.get('database.path', 'automation.db')
        self.db_manager = DatabaseManager(db_path=db_path)

        # 当前数据库
        self.current_db_path = db_path
        self.current_connection = None

        # 创建界面
        self.create_ui()

    def export_table_schema(self):
        """导出表结构"""
        # 获取选中的表名
        selection = self.table_list.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个表")
            return

        table_name = self.table_list.get(selection[0])

        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            defaultextension=".sql",
            filetypes=[("SQL文件", "*.sql"), ("CSV文件", "*.csv"), ("所有文件", "*.*")],
            initialfile=f"{table_name}_schema"
        )

        if not file_path:
            return

        try:
            # 查询表结构
            if not self.current_connection:
                messagebox.showerror("错误", "未连接到数据库")
                return

            cursor = self.current_connection.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            schema = cursor.fetchall()

            # 获取创建表的SQL语句
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            create_sql = cursor.fetchone()['sql']
            cursor.close()

            # 根据文件扩展名选择输出格式
            _, ext = os.path.splitext(file_path)

            with open(file_path, 'w', encoding='utf-8') as f:
                if ext.lower() == '.csv':
                    # CSV格式
                    f.write("id,name,type,notnull,default_value,primary_key\n")
                    for row in schema:
                        f.write(f"{row['cid']},{row['name']},{row['type']},{row['notnull']},"
                                f"\"{row['dflt_value'] or ''}\",{row['pk']}\n")
                else:
                    # SQL格式
                    f.write(f"-- {table_name} 表结构\n")
                    f.write(f"{create_sql};\n\n")
                    f.write("-- 字段说明\n")
                    for row in schema:
                        pk = "主键" if row['pk'] == 1 else ""
                        null = "NOT NULL" if row['notnull'] == 1 else "NULL"
                        default = f"DEFAULT {row['dflt_value']}" if row['dflt_value'] else ""
                        f.write(f"-- {row['name']}: {row['type']} {null} {default} {pk}\n")

            messagebox.showinfo("成功", f"表结构已导出到: {file_path}")

        except Exception as e:
            messagebox.showerror("错误", f"导出表结构失败: {str(e)}")

    def export_table_data(self):
        """导出表数据"""
        # 获取选中的表名
        selection = self.table_list.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个表")
            return

        table_name = self.table_list.get(selection[0])

        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("SQL文件", "*.sql"), ("所有文件", "*.*")],
            initialfile=f"{table_name}_data"
        )

        if not file_path:
            return

        try:
            # 查询表数据
            if not self.current_connection:
                messagebox.showerror("错误", "未连接到数据库")
                return

            cursor = self.current_connection.cursor()

            # 获取字段名
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row['name'] for row in cursor.fetchall()]

            # 获取所有数据
            cursor.execute(f"SELECT * FROM {table_name}")
            data = cursor.fetchall()
            cursor.close()

            if not data:
                messagebox.showinfo("提示", "表中没有数据可导出")
                return

            # 根据文件扩展名选择输出格式
            _, ext = os.path.splitext(file_path)

            with open(file_path, 'w', encoding='utf-8') as f:
                if ext.lower() == '.csv':
                    # CSV格式
                    f.write(",".join(columns) + "\n")
                    for row in data:
                        row_values = []
                        for col in columns:
                            value = row[col]
                            # 处理特殊字符
                            if value is None:
                                value = ""
                            elif isinstance(value, str):
                                value = '"' + value.replace('"', '""') + '"'
                            else:
                                value = str(value)
                            row_values.append(value)
                        f.write(",".join(row_values) + "\n")
                else:
                    # SQL格式
                    f.write(f"-- {table_name} 表数据\n")
                    for row in data:
                        values = []
                        for col in columns:
                            value = row[col]
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, str):
                                values.append("'" + value.replace("'", "''") + "'")
                            else:
                                values.append(str(value))
                        f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) "
                                f"VALUES ({', '.join(values)});\n")

            messagebox.showinfo("成功", f"表数据已导出到: {file_path}")

        except Exception as e:
            messagebox.showerror("错误", f"导出表数据失败: {str(e)}")

    def open_edit_table_dialog(self):
        """打开表数据编辑对话框"""
        # 获取选中的表名
        selection = self.table_list.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个表")
            return

        table_name = self.table_list.get(selection[0])

        try:
            # 创建编辑对话框
            edit_dialog = tk.Toplevel(self.window)
            edit_dialog.title(f"编辑表 - {table_name}")
            edit_dialog.geometry("900x600")

            # 创建数据编辑器
            editor = TableEditor(edit_dialog, self.current_connection, table_name)
            editor.pack(fill=tk.BOTH, expand=True)

        except Exception as e:
            messagebox.showerror("错误", f"打开编辑窗口失败: {str(e)}")

    def create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = tk.Frame(self.window)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # 数据库选择区域
        db_select_frame = tk.Frame(main_frame)
        db_select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(db_select_frame, text="当前数据库:").pack(side=tk.LEFT, padx=5)

        # 当前数据库路径显示
        self.db_path_var = tk.StringVar(value=self.current_db_path)
        db_path_entry = ttk.Entry(db_select_frame, textvariable=self.db_path_var, width=60)
        db_path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 浏览按钮
        ttk.Button(db_select_frame, text="浏览...", command=self.browse_database).pack(side=tk.LEFT, padx=5)

        # 连接按钮
        ttk.Button(db_select_frame, text="连接", command=self.connect_database).pack(side=tk.LEFT, padx=5)

        # 常用数据库选择框架
        common_db_frame = tk.Frame(main_frame)
        common_db_frame.pack(fill=tk.X, pady=5)

        ttk.Label(common_db_frame, text="快速访问:").pack(side=tk.LEFT, padx=5)

        # 主数据库按钮
        ttk.Button(common_db_frame, text="主数据库",
                   command=lambda: self.quick_connect(self.db_manager.db_path)).pack(side=tk.LEFT, padx=5)

        # 遍历任务目录，添加任务数据库按钮
        tasks_dir = os.path.join(project_root, "tasks")
        if os.path.exists(tasks_dir):
            for task_name in os.listdir(tasks_dir):
                task_dir = os.path.join(tasks_dir, task_name)
                if os.path.isdir(task_dir) and not task_name.startswith('__'):
                    # 检查任务目录中的数据库文件
                    db_files = []
                    for root, dirs, files in os.walk(task_dir):
                        for file in files:
                            if file.endswith('.db'):
                                db_files.append(os.path.join(root, file))

                    # 为每个找到的数据库添加快速访问按钮
                    for db_file in db_files:
                        db_name = os.path.basename(db_file)
                        button_text = f"{task_name}/{db_name}"
                        ttk.Button(common_db_frame, text=button_text,
                                   command=lambda f=db_file: self.quick_connect(f)).pack(side=tk.LEFT, padx=5)

        # 分隔线
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # 左侧表列表区域
        left_frame = tk.Frame(main_frame, width=200)
        left_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.Y)

        # 表列表标签
        tk.Label(left_frame, text="数据库表列表", font=('Arial', 12, 'bold')).pack(pady=5)

        # 表列表
        self.table_list = tk.Listbox(left_frame, width=30)
        self.table_list.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # 表列表滚动条
        table_scrollbar = tk.Scrollbar(left_frame)
        table_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.table_list.config(yscrollcommand=table_scrollbar.set)
        table_scrollbar.config(command=self.table_list.yview)

        # 表操作按钮框架
        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(pady=5)

        # 表操作按钮
        ttk.Button(btn_frame, text="查看表结构", command=self.show_table_schema).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="查看表数据", command=self.show_table_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="导出表结构", command=self.export_table_schema).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="导出表数据", command=self.export_table_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="编辑表数据", command=self.open_edit_table_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="执行查询", command=self.open_custom_query).pack(side=tk.LEFT, padx=2)
        # 右侧结果显示区域
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, padx=5, pady=5, fill=tk.BOTH, expand=True)

        # 结果标签
        tk.Label(right_frame, text="查询结果", font=('Arial', 12, 'bold')).pack(pady=5)

        # 结果显示表格
        self.result_tree = ttk.Treeview(right_frame)
        self.result_tree.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # 结果表格滚动条
        result_y_scrollbar = tk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        result_y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        result_x_scrollbar = tk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.result_tree.xview)
        result_x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.result_tree.configure(yscrollcommand=result_y_scrollbar.set,
                                   xscrollcommand=result_x_scrollbar.set)

        # 加载表列表
        self.connect_database()

    def browse_database(self):
        """浏览选择数据库文件"""
        # 打开文件对话框
        db_file = filedialog.askopenfilename(
            title="选择SQLite数据库文件",
            filetypes=[("SQLite数据库", "*.db"), ("所有文件", "*.*")],
            initialdir=project_root
        )

        if db_file:
            self.db_path_var.set(db_file)
            self.connect_database()

    def quick_connect(self, db_path):
        """快速连接到指定数据库"""
        if os.path.exists(db_path):
            self.db_path_var.set(db_path)
            self.connect_database()
        else:
            messagebox.showerror("错误", f"数据库文件不存在: {db_path}")

    def connect_database(self):
        """连接到当前选择的数据库"""
        db_path = self.db_path_var.get()

        # 关闭现有连接
        if self.current_connection:
            try:
                self.current_connection.close()
            except:
                pass

        try:
            # 检查文件是否存在
            if not os.path.exists(db_path):
                # 如果文件不存在，询问是否创建
                if messagebox.askyesno("提示", f"数据库文件不存在: {db_path}\n是否创建新数据库?"):
                    # 确保目录存在
                    directory = os.path.dirname(db_path)
                    if directory and not os.path.exists(directory):
                        os.makedirs(directory)
                else:
                    return

            # 连接数据库
            self.current_connection = sqlite3.connect(db_path)
            self.current_connection.row_factory = sqlite3.Row
            self.current_db_path = db_path

            # 更新窗口标题
            db_name = os.path.basename(db_path)
            self.window.title(f"数据库查询调试面板 - {db_name}")

            # 加载表列表
            self.load_table_list()

            # 成功提示
            messagebox.showinfo("连接成功", f"已连接到数据库: {db_path}")

        except Exception as e:
            messagebox.showerror("连接错误", f"连接数据库失败: {str(e)}")

    def load_table_list(self):
        """加载数据库中的表列表"""
        try:
            # 清空表列表
            self.table_list.delete(0, tk.END)

            if not self.current_connection:
                return

            # 查询所有表
            cursor = self.current_connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()

            # 填充表列表
            for table in tables:
                self.table_list.insert(tk.END, table)

        except Exception as e:
            messagebox.showerror("错误", f"加载表列表失败: {str(e)}")

    def show_table_schema(self):
        """显示选中表的表结构"""
        # 获取选中的表名
        selection = self.table_list.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个表")
            return

        table_name = self.table_list.get(selection[0])

        try:
            # 查询表结构
            if not self.current_connection:
                messagebox.showerror("错误", "未连接到数据库")
                return

            cursor = self.current_connection.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            schema = cursor.fetchall()
            cursor.close()

            # 清空之前的结果
            for i in self.result_tree.get_children():
                self.result_tree.delete(i)

            # 设置列
            self.result_tree['columns'] = ('名称', '类型', '是否非空', '默认值', '是否主键')

            # 配置列
            for col in self.result_tree['columns']:
                self.result_tree.heading(col, text=col)
                self.result_tree.column(col, anchor='center', width=100)

            # 插入数据
            for row in schema:
                self.result_tree.insert('', 'end', values=(
                    row['name'],
                    row['type'],
                    '是' if row['notnull'] == 1 else '否',
                    str(row['dflt_value'] or ''),
                    '是' if row['pk'] == 1 else '否'
                ))
        except Exception as e:
            messagebox.showerror("错误", f"查询表结构失败: {str(e)}")

    def show_table_data(self):
        """显示选中表的数据"""
        # 获取选中的表名
        selection = self.table_list.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个表")
            return

        table_name = self.table_list.get(selection[0])

        try:
            # 查询表数据
            if not self.current_connection:
                messagebox.showerror("错误", "未连接到数据库")
                return

            cursor = self.current_connection.cursor()
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 200")
            data = cursor.fetchall()
            cursor.close()

            # 清空之前的结果
            for i in self.result_tree.get_children():
                self.result_tree.delete(i)

            if not data:
                messagebox.showinfo("提示", "表中没有数据")
                return

            # 设置列
            self.result_tree['columns'] = list(data[0].keys())

            # 配置列
            for col in self.result_tree['columns']:
                self.result_tree.heading(col, text=col)
                self.result_tree.column(col, anchor='center', width=100)

            # 插入数据
            for row in data:
                values = [str(row[col]) for col in self.result_tree['columns']]
                self.result_tree.insert('', 'end', values=values)
        except Exception as e:
            messagebox.showerror("错误", f"查询表数据失败: {str(e)}")

    def open_custom_query(self):
        """打开自定义查询对话框"""
        query = simpledialog.askstring("自定义查询", "请输入SQL查询语句:",
                                       initialvalue="SELECT * FROM 表名 LIMIT 100")
        if query:
            try:
                # 执行自定义查询
                if not self.current_connection:
                    messagebox.showerror("错误", "未连接到数据库")
                    return

                cursor = self.current_connection.cursor()
                cursor.execute(query)
                data = cursor.fetchall()
                cursor.close()

                # 清空之前的结果
                for i in self.result_tree.get_children():
                    self.result_tree.delete(i)

                if not data:
                    messagebox.showinfo("提示", "查询结果为空")
                    return

                # 设置列
                self.result_tree['columns'] = list(data[0].keys())

                # 配置列
                for col in self.result_tree['columns']:
                    self.result_tree.heading(col, text=col)
                    self.result_tree.column(col, anchor='center', width=100)

                # 插入数据
                for row in data:
                    values = [str(row[col]) for col in self.result_tree['columns']]
                    self.result_tree.insert('', 'end', values=values)
            except Exception as e:
                messagebox.showerror("错误", f"自定义查询失败: {str(e)}")


class TableEditor(tk.Frame):
    """表数据编辑器"""

    def __init__(self, master, connection, table_name):
        super().__init__(master)
        self.master = master
        self.connection = connection
        self.table_name = table_name

        # 获取表结构
        self.cursor = self.connection.cursor()
        self.cursor.execute(f"PRAGMA table_info({self.table_name})")
        self.columns = [row['name'] for row in self.cursor.fetchall()]
        self.pk_columns = [row['name'] for row in self.cursor.fetchall() if row['pk'] == 1]

        # 如果没有主键，使用所有列
        if not self.pk_columns:
            self.pk_columns = self.columns

        # 创建UI
        self.create_ui()

        # 加载数据
        self.load_data()

    def create_ui(self):
        """创建用户界面"""
        # 工具栏
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, pady=5)

        ttk.Button(toolbar, text="刷新", command=self.load_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="添加行", command=self.add_row).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="删除选中行", command=self.delete_row).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="保存更改", command=self.save_changes).pack(side=tk.LEFT, padx=5)

        # 过滤区域
        filter_frame = tk.Frame(self)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="过滤:").pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=50)
        filter_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(filter_frame, text="应用过滤", command=self.apply_filter).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="清除过滤", command=self.clear_filter).pack(side=tk.LEFT, padx=5)

        # 创建表格
        self.tree = ttk.Treeview(self)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # 滚动条
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # 状态栏
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 设置列
        self.tree["columns"] = self.columns

        # 配置列
        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        # 设置单元格编辑功能
        self.tree.bind("<Double-1>", self.on_cell_double_click)

    def load_data(self, filter_condition=None):
        """加载表数据"""
        # 清空现有数据
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            # 构建查询
            query = f"SELECT * FROM {self.table_name}"
            params = ()

            if filter_condition:
                query += f" WHERE {filter_condition}"

            query += " LIMIT 1000"  # 限制返回行数

            # 执行查询
            self.cursor.execute(query, params)
            data = self.cursor.fetchall()

            # 填充数据
            for row in data:
                values = [row[col] for col in self.columns]
                self.tree.insert("", "end", values=values)

            # 更新状态
            self.status_var.set(f"共加载 {len(data)} 行数据")

        except Exception as e:
            messagebox.showerror("错误", f"加载数据失败: {str(e)}")

    def apply_filter(self):
        """应用过滤条件"""
        filter_text = self.filter_var.get()
        if not filter_text:
            self.load_data()
            return

        try:
            # 验证过滤条件语法
            test_query = f"SELECT 1 FROM {self.table_name} WHERE {filter_text} LIMIT 1"
            self.cursor.execute(test_query)

            # 加载过滤后的数据
            self.load_data(filter_text)

        except Exception as e:
            messagebox.showerror("错误", f"过滤条件无效: {str(e)}")

    def clear_filter(self):
        """清除过滤条件"""
        self.filter_var.set("")
        self.load_data()

    def on_cell_double_click(self, event):
        """单元格双击事件"""
        # 获取点击的行和列
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        if not column:
            return

        # 列索引从#1开始
        column_index = int(column[1:]) - 1
        if column_index < 0 or column_index >= len(self.columns):
            return

        column_name = self.columns[column_index]

        # 获取当前值
        item = self.tree.focus()
        if not item:
            return

        current_value = self.tree.item(item, "values")[column_index]

        # 创建编辑框
        cell_editor = tk.Toplevel(self)
        cell_editor.title(f"编辑 {column_name}")
        cell_editor.geometry("400x200")

        # 输入框
        ttk.Label(cell_editor, text=f"编辑 {column_name}:").pack(pady=10)

        value_var = tk.StringVar(value=str(current_value) if current_value is not None else "")
        entry = ttk.Entry(cell_editor, textvariable=value_var, width=40)
        entry.pack(pady=10, padx=20)
        entry.select_range(0, tk.END)
        entry.focus_set()

        # 按钮
        btn_frame = tk.Frame(cell_editor)
        btn_frame.pack(pady=10)

        def save_value():
            # 更新表格中的值
            values = list(self.tree.item(item, "values"))
            values[column_index] = value_var.get()
            self.tree.item(item, values=values)
            cell_editor.destroy()

        def cancel():
            cell_editor.destroy()

        ttk.Button(btn_frame, text="保存", command=save_value).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=cancel).pack(side=tk.LEFT, padx=10)

    def add_row(self):
        """添加新行"""
        # 创建新行编辑框
        row_editor = tk.Toplevel(self)
        row_editor.title(f"添加新行 - {self.table_name}")
        row_editor.geometry("500x400")

        # 创建编辑字段
        frame = ttk.Frame(row_editor)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 为每个列创建输入框
        entries = {}
        for i, col in enumerate(self.columns):
            ttk.Label(frame, text=f"{col}:").grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(frame, width=40)
            entry.grid(row=i, column=1, sticky=tk.W + tk.E, pady=5)
            entries[col] = entry

        # 按钮
        btn_frame = tk.Frame(row_editor)
        btn_frame.pack(pady=10)

        def save_row():
            # 获取所有值
            values = {}
            for col, entry in entries.items():
                value = entry.get()
                if value == "":
                    values[col] = None
                else:
                    values[col] = value

            # 插入树
            self.tree.insert("", "end", values=[values.get(col) for col in self.columns])
            row_editor.destroy()

        def cancel():
            row_editor.destroy()

        ttk.Button(btn_frame, text="保存", command=save_row).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=cancel).pack(side=tk.LEFT, padx=10)

    def delete_row(self):
        """删除选中行"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要删除的行")
            return

        if not messagebox.askyesno("确认", "确定要删除选中的行吗?"):
            return

        # 删除选中行
        for item in selected:
            self.tree.delete(item)

    def save_changes(self):
        """保存所有更改到数据库"""
        if not messagebox.askyesno("确认", "确定要保存所有更改到数据库吗?"):
            return

        try:
            # 获取当前数据
            current_data = []
            for item in self.tree.get_children():
                values = self.tree.item(item, "values")
                row = {col: values[i] for i, col in enumerate(self.columns)}
                current_data.append(row)

            # 获取原始数据
            self.cursor.execute(f"SELECT * FROM {self.table_name}")
            original_data = [dict(row) for row in self.cursor.fetchall()]

            # 开始事务
            self.connection.execute("BEGIN TRANSACTION")

            # 删除所有原始数据
            self.cursor.execute(f"DELETE FROM {self.table_name}")

            # 插入新数据
            for row in current_data:
                cols = []
                vals = []
                for col, val in row.items():
                    cols.append(col)
                    if val == "":
                        vals.append(None)
                    else:
                        vals.append(val)

                placeholders = ", ".join(["?" for _ in vals])
                self.cursor.execute(
                    f"INSERT INTO {self.table_name} ({', '.join(cols)}) VALUES ({placeholders})",
                    vals
                )

            # 提交事务
            self.connection.execute("COMMIT")

            messagebox.showinfo("成功", "更改已保存到数据库")

            # 重新加载数据
            self.load_data()

        except Exception as e:
            # 回滚事务
            self.connection.execute("ROLLBACK")
            messagebox.showerror("错误", f"保存更改失败: {str(e)}")

def run(self):
    """运行数据库查询面板"""
    # 如果是顶层窗口，直接显示
    if isinstance(self.window, tk.Toplevel):
        self.window.grab_set()  # 设置模态
        self.window.focus_set()
    else:
        self.window.mainloop()