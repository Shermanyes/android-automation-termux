"""
状态管理面板
提供状态识别测试和管理功能
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
import json
import time

from .utils import pil_to_tk, save_config, load_config, generate_timestamp_filename

class StatePanel(ttk.Frame):
    """状态管理和测试面板"""
    
    def __init__(self, parent, state_manager, screen_recognizer, screen_panel, device_controller, **kwargs):
        """初始化状态管理面板
        
        Args:
            parent: 父窗口
            state_manager: 状态管理器实例
            screen_recognizer: 屏幕识别器实例
            screen_panel: 屏幕面板实例
            device_controller: 设备控制器实例
        """
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.state_manager = state_manager
        self.recognizer = screen_recognizer
        self.screen_panel = screen_panel
        self.device = device_controller
        
        self.states = {}  # 状态列表
        self.current_state = None  # 当前识别的状态
        
        self._setup_ui()
        self.load_states()
    
    def _setup_ui(self):
        """设置UI组件"""
        # 主分区
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧状态列表
        list_frame = ttk.Frame(main_paned)
        main_paned.add(list_frame, weight=1)
        
        # 状态列表
        list_label_frame = ttk.LabelFrame(list_frame, text="状态列表")
        list_label_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 搜索框
        search_frame = ttk.Frame(list_label_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=2)
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 绑定搜索事件
        def on_search(*args):
            self.filter_states()
        
        self.search_var.trace_add("write", on_search)
        
        # 状态列表和滚动条
        list_scroll = ttk.Scrollbar(list_label_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.state_listbox = tk.Listbox(
            list_label_frame, 
            yscrollcommand=list_scroll.set,
            selectmode=tk.SINGLE,
            height=15,
            font=("Arial", 10)
        )
        self.state_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        list_scroll.config(command=self.state_listbox.yview)
        
        # 绑定选择事件
        self.state_listbox.bind("<<ListboxSelect>>", self.on_state_selected)
        
        # 状态操作按钮
        button_frame = ttk.Frame(list_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="识别当前状态", 
                  command=self.recognize_current_state).pack(fill=tk.X, pady=2)
        
        ttk.Button(button_frame, text="刷新状态列表", 
                  command=self.load_states).pack(fill=tk.X, pady=2)
        
        ttk.Separator(list_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=5)
        
        # 创建和管理状态
        manage_frame = ttk.LabelFrame(list_frame, text="状态管理")
        manage_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(manage_frame, text="创建新状态", 
                  command=self.create_new_state).pack(fill=tk.X, pady=2)
        
        ttk.Button(manage_frame, text="编辑选中状态", 
                  command=self.edit_selected_state).pack(fill=tk.X, pady=2)
        
        ttk.Button(manage_frame, text="删除选中状态", 
                  command=self.delete_selected_state).pack(fill=tk.X, pady=2)
        
        ttk.Separator(manage_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(manage_frame, text="导入状态配置", 
                  command=self.import_state_config).pack(fill=tk.X, pady=2)
                  
        ttk.Button(manage_frame, text="导出选中状态", 
                  command=self.export_selected_state).pack(fill=tk.X, pady=2)
        
        # 右侧状态详情
        detail_frame = ttk.Frame(main_paned)
        main_paned.add(detail_frame, weight=2)
        
        # 状态信息
        info_frame = ttk.LabelFrame(detail_frame, text="状态信息")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # 第一行
        ttk.Label(info_grid, text="状态ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.state_id_label = ttk.Label(info_grid, text="")
        self.state_id_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(info_grid, text="应用ID:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        self.app_id_label = ttk.Label(info_grid, text="")
        self.app_id_label.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)
        
        # 第二行
        ttk.Label(info_grid, text="状态名称:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.state_name_label = ttk.Label(info_grid, text="")
        self.state_name_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(info_grid, text="状态类型:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        self.state_type_label = ttk.Label(info_grid, text="")
        self.state_type_label.grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)
        
        # 状态内容
        content_frame = ttk.LabelFrame(detail_frame, text="状态配置")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 配置内容滚动区域
        content_scroll = ttk.Scrollbar(content_frame)
        content_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.config_text = tk.Text(content_frame, wrap=tk.WORD, yscrollcommand=content_scroll.set)
        self.config_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content_scroll.config(command=self.config_text.yview)
        
        # 状态操作
        action_frame = ttk.LabelFrame(detail_frame, text="状态操作")
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        action_buttons = ttk.Frame(action_frame)
        action_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(action_buttons, text="测试状态识别", 
                  command=self.test_state_recognition).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)
                  
        ttk.Button(action_buttons, text="导航到此状态", 
                  command=self.navigate_to_state).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)
        
        # 状态转换管理
        transition_frame = ttk.LabelFrame(detail_frame, text="状态转换")
        transition_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(transition_frame, text="添加/编辑状态转换", 
                  command=self.manage_state_transitions).pack(fill=tk.X, padx=5, pady=5)
        
        # 初始状态
        self.show_empty_state()
    
    def show_empty_state(self):
        """显示空状态信息"""
        self.state_id_label.config(text="")
        self.app_id_label.config(text="")
        self.state_name_label.config(text="")
        self.state_type_label.config(text="")
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(tk.END, "请从左侧列表选择状态或创建新状态")
    
    def load_states(self):
        """从数据库加载状态列表"""
        try:
            # 清空状态列表
            self.states = {}
            self.state_listbox.delete(0, tk.END)
            
            # 查询数据库获取状态
            states_data = self.state_manager.db.fetch_all("SELECT * FROM recognition_states ORDER BY app_id, name")
            
            if not states_data:
                self.state_listbox.insert(tk.END, "暂无状态")
                return
                
            # 填充列表
            for state in states_data:
                state_id = state['state_id']
                self.states[state_id] = state
                display_name = f"{state['name']} ({state_id})"
                self.state_listbox.insert(tk.END, display_name)
                
        except Exception as e:
            messagebox.showerror("错误", f"加载状态列表失败: {str(e)}")
    
    def filter_states(self):
        """根据搜索条件过滤状态列表"""
        search_text = self.search_var.get().lower()
        
        # 清空列表
        self.state_listbox.delete(0, tk.END)
        
        # 如果没有状态
        if not self.states:
            self.state_listbox.insert(tk.END, "暂无状态")
            return
            
        # 筛选并显示
        has_results = False
        for state_id, state in self.states.items():
            display_name = f"{state['name']} ({state_id})"
            
            if (search_text in state_id.lower() or 
                search_text in state['name'].lower() or
                search_text in state['app_id'].lower()):
                self.state_listbox.insert(tk.END, display_name)
                has_results = True
                
        if not has_results:
            self.state_listbox.insert(tk.END, "无匹配结果")
    
    def on_state_selected(self, event):
        """状态选择事件处理"""
        selection = self.state_listbox.curselection()
        if not selection:
            return
            
        # 获取选中的状态名称
        selected_text = self.state_listbox.get(selection[0])
        
        # 如果是提示文本，则返回
        if selected_text in ["暂无状态", "无匹配结果"]:
            return
            
        # 提取状态ID (假设格式为 "名称 (ID)")
        state_id = selected_text.split('(')[-1].strip(')')
        
        if state_id in self.states:
            self.show_state_details(state_id)
    
    def show_state_details(self, state_id):
        """显示状态详情
        
        Args:
            state_id: 状态ID
        """
        state = self.states[state_id]
        
        # 更新状态信息
        self.state_id_label.config(text=state_id)
        self.app_id_label.config(text=state['app_id'])
        self.state_name_label.config(text=state['name'])
        self.state_type_label.config(text=state['type'])
        
        # 获取并显示配置
        try:
            config = json.loads(state['config'])
            config_str = json.dumps(config, indent=4, ensure_ascii=False)
            
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(tk.END, config_str)
        except Exception as e:
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(tk.END, f"配置解析错误: {str(e)}\n\n原始配置:\n{state['config']}")
    
    def recognize_current_state(self):
        """识别当前屏幕状态"""
        try:
            # 获取当前截图
            image = self.screen_panel.get_current_image()
            if image is None:
                messagebox.showinfo("提示", "请先在屏幕面板获取截图")
                return
            
            # 显示加载消息
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(tk.END, "正在识别状态...")
            self.update()  # 强制更新UI
            
            # 执行状态识别
            state_id = self.state_manager.recognize_current_scene()
            
            if state_id:
                # 更新当前状态
                self.current_state = state_id
                
                # 选中对应状态
                self.select_state_in_list(state_id)
                
                # 显示识别结果
                messagebox.showinfo("识别结果", f"当前状态: {state_id}")
            else:
                messagebox.showinfo("识别结果", "无法识别当前状态")
                self.show_empty_state()
                self.config_text.delete(1.0, tk.END)
                self.config_text.insert(tk.END, "无法识别当前状态")
                
        except Exception as e:
            messagebox.showerror("错误", f"状态识别失败: {str(e)}")
    
    def select_state_in_list(self, state_id):
        """在列表中选中指定状态
        
        Args:
            state_id: 状态ID
        """
        # 清除当前选择
        self.state_listbox.selection_clear(0, tk.END)
        
        # 查找并选择指定状态
        for i in range(self.state_listbox.size()):
            item_text = self.state_listbox.get(i)
            if f"({state_id})" in item_text:
                self.state_listbox.selection_set(i)
                self.state_listbox.see(i)
                self.show_state_details(state_id)
                break
    
    def test_state_recognition(self):
        """测试选中状态的识别"""
        # 获取选中的状态ID
        state_id = self.state_id_label.cget("text")
        if not state_id:
            messagebox.showinfo("提示", "请先选择一个状态")
            return
            
        # 获取当前截图
        image = self.screen_panel.get_current_image()
        if image is None:
            messagebox.showinfo("提示", "请先在屏幕面板获取截图")
            return
            
        try:
            # 获取状态配置
            state = self.states[state_id]
            state_type = state['type']
            config = json.loads(state['config'])
            
            # 根据状态类型执行不同的识别逻辑
            result = None
            if state_type == 'text':
                result = self.recognizer.find_text(
                    config.get('target_text'),
                    config.get('lang'),
                    config.get('config'),
                    config.get('roi'),
                    config.get('threshold', 0.6)
                )
            elif state_type == 'image':
                result = self.recognizer.find_image(
                    config.get('template_path'),
                    config.get('threshold', 0.8),
                    config.get('roi')
                )
            elif state_type == 'complex':
                # 复杂状态识别，需要满足多个条件
                elements = config.get('elements', [])
                matches = 0
                required = config.get('required_matches', len(elements))
                
                for element in elements:
                    element_type = element.get('type')
                    element_result = None
                    
                    if element_type == 'text':
                        element_result = self.recognizer.find_text(
                            element.get('target_text'),
                            element.get('lang'),
                            element.get('config'),
                            element.get('roi'),
                            element.get('threshold', 0.6)
                        )
                    elif element_type == 'image':
                        element_result = self.recognizer.find_image(
                            element.get('template_path'),
                            element.get('threshold', 0.8),
                            element.get('roi')
                        )
                    
                    if element_result:
                        matches += 1
                
                result = matches >= required
            
            # 显示结果
            if result:
                messagebox.showinfo("测试结果", f"成功识别状态: {state_id}")
            else:
                messagebox.showinfo("测试结果", f"无法识别状态: {state_id}")
                
        except Exception as e:
            messagebox.showerror("错误", f"状态识别测试失败: {str(e)}")
    
    def navigate_to_state(self):
        """导航到选中状态"""
        # 获取选中的状态ID
        state_id = self.state_id_label.cget("text")
        if not state_id:
            messagebox.showinfo("提示", "请先选择一个状态")
            return
            
        try:
            # 显示加载消息
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(tk.END, f"正在导航到状态: {state_id}...")
            self.update()  # 强制更新UI
            
            # 执行导航
            result = self.state_manager.navigate_to_state(state_id, self.device)
            
            if result:
                messagebox.showinfo("导航结果", f"成功导航到状态: {state_id}")
            else:
                messagebox.showinfo("导航结果", f"导航失败: 无法达到状态 {state_id}")
                
        except Exception as e:
            messagebox.showerror("错误", f"状态导航失败: {str(e)}")
    
    def create_new_state(self):
        """创建新状态"""
        # 打开状态创建对话框
        dialog = StateCreateDialog(self)
        if not dialog.result:
            return
            
        # 提取对话框结果
        state_data = dialog.result
        
        try:
            # 注册状态
            success = self.state_manager.register_state(
                state_data['state_id'],
                state_data['app_id'],
                state_data['recognition_config']
            )
            
            if success:
                messagebox.showinfo("成功", f"已创建状态: {state_data['state_id']}")
                
                # 刷新状态列表
                self.load_states()
                
                # 选中新创建的状态
                self.select_state_in_list(state_data['state_id'])
            else:
                messagebox.showerror("错误", "创建状态失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"创建状态失败: {str(e)}")
    
    def edit_selected_state(self):
        """编辑选中的状态"""
        # 获取选中的状态ID
        state_id = self.state_id_label.cget("text")
        if not state_id:
            messagebox.showinfo("提示", "请先选择一个状态")
            return
            
        # 获取状态数据
        state = self.states[state_id]
        
        # 打开状态编辑对话框
        dialog = StateEditDialog(self, state)
        if not dialog.result:
            return
            
        # 提取对话框结果
        state_data = dialog.result
        
        try:
            # 更新状态
            success = self.state_manager.register_state(
                state_data['state_id'],
                state_data['app_id'],
                state_data['recognition_config']
            )
            
            if success:
                messagebox.showinfo("成功", f"已更新状态: {state_data['state_id']}")
                
                # 刷新状态列表
                self.load_states()
                
                # 选中编辑的状态
                self.select_state_in_list(state_data['state_id'])
            else:
                messagebox.showerror("错误", "更新状态失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"更新状态失败: {str(e)}")
    
    def delete_selected_state(self):
        """删除选中的状态"""
        # 获取选中的状态ID
        state_id = self.state_id_label.cget("text")
        if not state_id:
            messagebox.showinfo("提示", "请先选择一个状态")
            return
            
        # 确认删除
        if not messagebox.askyesno("确认", f"确定要删除状态 '{state_id}' 吗？"):
            return
            
        try:
            # 删除状态
            success = self.state_manager.unregister_state(state_id)
            
            if success:
                messagebox.showinfo("成功", f"已删除状态: {state_id}")
                
                # 刷新状态列表
                self.load_states()
                
                # 清空详情
                self.show_empty_state()
            else:
                messagebox.showerror("错误", "删除状态失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"删除状态失败: {str(e)}")
    
    def import_state_config(self):
        """导入状态配置"""
        # 选择配置文件
        filepath = filedialog.askopenfilename(
            title="选择状态配置文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if not filepath:
            return
            
        try:
            # 加载配置
            config = load_config(filepath)
            
            if not config:
                messagebox.showerror("错误", "配置文件为空或格式错误")
                return
                
            # 处理多状态导入
            if 'states' in config:
                # 批量导入
                states = config['states']
                imported = 0
                
                for state_data in states:
                    success = self.state_manager.register_state(
                        state_data['state_id'],
                        state_data.get('app_id', 'default'),
                        state_data['recognition_config']
                    )
                    
                    if success:
                        imported += 1
                
                if imported > 0:
                    messagebox.showinfo("成功", f"已导入 {imported}/{len(states)} 个状态")
                else:
                    messagebox.showwarning("警告", "没有成功导入任何状态")
            else:
                # 单状态导入
                state_id = config.get('state_id')
                app_id = config.get('app_id', 'default')
                recognition_config = config.get('recognition_config')
                
                if not state_id or not recognition_config:
                    messagebox.showerror("错误", "配置文件缺少必要字段")
                    return
                    
                success = self.state_manager.register_state(
                    state_id,
                    app_id,
                    recognition_config
                )
                
                if success:
                    messagebox.showinfo("成功", f"已导入状态: {state_id}")
                else:
                    messagebox.showerror("错误", "导入状态失败")
            
            # 刷新状态列表
            self.load_states()
            
        except Exception as e:
            messagebox.showerror("错误", f"导入状态配置失败: {str(e)}")
    
    def export_selected_state(self):
        """导出选中的状态"""
        # 获取选中的状态ID
        state_id = self.state_id_label.cget("text")
        if not state_id:
            messagebox.showinfo("提示", "请先选择一个状态")
            return
            
        # 获取状态数据
        state = self.states[state_id]
        
        try:
            # 构建导出数据
            export_data = {
                'state_id': state_id,
                'app_id': state['app_id'],
                'name': state['name'],
                'type': state['type'],
                'recognition_config': json.loads(state['config'])
            }
            
            # 选择保存路径
            filepath = filedialog.asksaveasfilename(
                title="保存状态配置",
                defaultextension=".json",
                filetypes=[("JSON文件", "*.json")]
            )
            
            if not filepath:
                return
                
            # 保存配置
            save_config(export_data, filepath)
            
            messagebox.showinfo("成功", f"已导出状态配置到: {filepath}")
            
        except Exception as e:
            messagebox.showerror("错误", f"导出状态配置失败: {str(e)}")
    
    def manage_state_transitions(self):
        """管理状态转换"""
        # 获取选中的状态ID
        state_id = self.state_id_label.cget("text")
        if not state_id:
            messagebox.showinfo("提示", "请先选择一个状态")
            return
            
        # 打开状态转换管理对话框
        dialog = StateTransitionDialog(self, self.state_manager, state_id, self.states)
        # 对话框会处理转换的添加和编辑，不需要额外处理


class StateCreateDialog:
    """状态创建对话框"""
    
    def __init__(self, parent):
        """初始化状态创建对话框
        
        Args:
            parent: 父窗口
        """
        self.parent = parent
        self.result = None
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("创建新状态")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._setup_ui()
        
        # 等待对话框关闭
        parent.wait_window(self.dialog)
    
    def _setup_ui(self):
        """设置对话框UI"""
        # 主框架
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 基本信息
        info_frame = ttk.LabelFrame(main_frame, text="基本信息")
        info_frame.pack(fill=tk.X, pady=5)
        
        # 状态ID
        ttk.Label(info_frame, text="状态ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.state_id_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.state_id_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 应用ID
        ttk.Label(info_frame, text="应用ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.app_id_var = tk.StringVar(value="default")
        ttk.Entry(info_frame, textvariable=self.app_id_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 状态名称
        ttk.Label(info_frame, text="状态名称:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.state_name_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.state_name_var, width=30).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 状态类型
        ttk.Label(info_frame, text="状态类型:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.state_type_var = tk.StringVar(value="text")
        type_combo = ttk.Combobox(info_frame, textvariable=self.state_type_var, 
                                  values=["text", "image", "complex"])
        type_combo.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 类型变更事件
        def on_type_change(*args):
            self.update_config_panel()
        
        self.state_type_var.trace_add("write", on_type_change)
        
        # 配置面板
        self.config_frame = ttk.LabelFrame(main_frame, text="识别配置")
        self.config_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 初始化配置UI
        self.text_config_frame = None
        self.image_config_frame = None
        self.complex_config_frame = None
        
        # 初始化文本配置UI
        self.create_text_config_ui()
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="取消", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="创建", command=self.create_state).pack(side=tk.RIGHT, padx=5)
        
        # 更新配置面板
        self.update_config_panel()
    
    def create_text_config_ui(self):
        """创建文本识别配置UI"""
        self.text_config_frame = ttk.Frame(self.config_frame)
        
        # 目标文本
        ttk.Label(self.text_config_frame, text="目标文本:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_text_var = tk.StringVar()
        ttk.Entry(self.text_config_frame, textvariable=self.target_text_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # OCR语言
        ttk.Label(self.text_config_frame, text="OCR语言:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.ocr_lang_var = tk.StringVar(value="chi_sim+eng")
        ttk.Combobox(self.text_config_frame, textvariable=self.ocr_lang_var, 
                    values=["chi_sim", "eng", "chi_sim+eng"]).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 识别阈值
        ttk.Label(self.text_config_frame, text="识别阈值:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        threshold_frame = ttk.Frame(self.text_config_frame)
        threshold_frame.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.text_threshold_var = tk.DoubleVar(value=0.6)
        ttk.Scale(threshold_frame, from_=0.1, to=1.0, orient=tk.HORIZONTAL, 
                 variable=self.text_threshold_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.text_threshold_label = ttk.Label(threshold_frame, text="0.60")
        self.text_threshold_label.pack(side=tk.LEFT, padx=5)
        
        # 更新阈值标签
        def update_threshold_label(*args):
            self.text_threshold_label.config(text=f"{self.text_threshold_var.get():.2f}")
        
        self.text_threshold_var.trace_add("write", update_threshold_label)
        
        # ROI区域
        ttk.Label(self.text_config_frame, text="ROI区域:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        roi_frame = ttk.Frame(self.text_config_frame)
        roi_frame.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.text_use_roi_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(roi_frame, text="使用ROI", variable=self.text_use_roi_var).pack(side=tk.LEFT)
        
        self.text_roi_var = tk.StringVar()
        ttk.Entry(roi_frame, textvariable=self.text_roi_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(roi_frame, text="格式: x1,y1,x2,y2").pack(side=tk.LEFT)
    
    def create_image_config_ui(self):
        """创建图像识别配置UI"""
        self.image_config_frame = ttk.Frame(self.config_frame)
        
        # 模板路径
        ttk.Label(self.image_config_frame, text="模板图像:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        template_frame = ttk.Frame(self.image_config_frame)
        template_frame.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.template_path_var = tk.StringVar()
        ttk.Entry(template_frame, textvariable=self.template_path_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(template_frame, text="浏览", command=self.browse_template).pack(side=tk.LEFT, padx=2)
        
        # 识别阈值
        ttk.Label(self.image_config_frame, text="识别阈值:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        threshold_frame = ttk.Frame(self.image_config_frame)
        threshold_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.image_threshold_var = tk.DoubleVar(value=0.8)
        ttk.Scale(threshold_frame, from_=0.1, to=1.0, orient=tk.HORIZONTAL, 
                 variable=self.image_threshold_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.image_threshold_label = ttk.Label(threshold_frame, text="0.80")
        self.image_threshold_label.pack(side=tk.LEFT, padx=5)
        
        # 更新阈值标签
        def update_threshold_label(*args):
            self.image_threshold_label.config(text=f"{self.image_threshold_var.get():.2f}")
        
        self.image_threshold_var.trace_add("write", update_threshold_label)
        
        # ROI区域
        ttk.Label(self.image_config_frame, text="ROI区域:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        roi_frame = ttk.Frame(self.image_config_frame)
        roi_frame.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.image_use_roi_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(roi_frame, text="使用ROI", variable=self.image_use_roi_var).pack(side=tk.LEFT)
        
        self.image_roi_var = tk.StringVar()
        ttk.Entry(roi_frame, textvariable=self.image_roi_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(roi_frame, text="格式: x1,y1,x2,y2").pack(side=tk.LEFT)
    
    def create_complex_config_ui(self):
        """创建复杂识别配置UI"""
        self.complex_config_frame = ttk.Frame(self.config_frame)
        
        # 说明标签
        ttk.Label(self.complex_config_frame, text="复杂状态由多个识别元素组成，通过JSON配置管理").pack(fill=tk.X, padx=5, pady=5)
        
        # 配置编辑器
        config_editor_frame = ttk.LabelFrame(self.complex_config_frame, text="配置编辑器")
        config_editor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 滚动条
        editor_scroll = ttk.Scrollbar(config_editor_frame)
        editor_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.complex_config_text = tk.Text(config_editor_frame, wrap=tk.WORD, yscrollcommand=editor_scroll.set)
        self.complex_config_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        editor_scroll.config(command=self.complex_config_text.yview)
        
        # 设置默认配置模板
        default_config = {
            "elements": [
                {
                    "type": "text",
                    "target_text": "示例文本",
                    "lang": "chi_sim+eng",
                    "threshold": 0.6
                },
                {
                    "type": "image",
                    "template_path": "templates/example.png",
                    "threshold": 0.8
                }
            ],
            "required_matches": 1  # 要求匹配的元素数量
        }
        
        self.complex_config_text.insert(tk.END, json.dumps(default_config, indent=4, ensure_ascii=False))
    
    def update_config_panel(self):
        """根据选择的状态类型更新配置面板"""
        state_type = self.state_type_var.get()
        
        # 清空当前配置面板
        for widget in self.config_frame.winfo_children():
            widget.pack_forget()
        
        # 根据类型显示对应的配置面板
        if state_type == "text":
            if not self.text_config_frame:
                self.create_text_config_ui()
            self.text_config_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
        elif state_type == "image":
            if not self.image_config_frame:
                self.create_image_config_ui()
            self.image_config_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
        elif state_type == "complex":
            if not self.complex_config_frame:
                self.create_complex_config_ui()
            self.complex_config_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def browse_template(self):
        """浏览选择模板图像"""
        filepath = filedialog.askopenfilename(
            title="选择模板图像",
            filetypes=[("图像文件", "*.png *.jpg *.jpeg *.bmp")]
        )
        
        if filepath:
            self.template_path_var.set(filepath)
    
    def create_state(self):
        """创建状态"""
        # 获取基本信息
        state_id = self.state_id_var.get().strip()
        app_id = self.app_id_var.get().strip()
        state_name = self.state_name_var.get().strip()
        state_type = self.state_type_var.get()
        
        # 验证基本信息
        if not state_id:
            messagebox.showerror("错误", "状态ID不能为空")
            return
            
        if not app_id:
            messagebox.showerror("错误", "应用ID不能为空")
            return
            
        if not state_name:
            messagebox.showerror("错误", "状态名称不能为空")
            return
        
        # 构建配置
        recognition_config = {
            "name": state_name,
            "type": state_type
        }
        
        try:
            # 根据类型获取特定配置
            if state_type == "text":
                target_text = self.target_text_var.get().strip()
                if not target_text:
                    messagebox.showerror("错误", "目标文本不能为空")
                    return
                    
                recognition_config.update({
                    "target_text": target_text,
                    "lang": self.ocr_lang_var.get(),
                    "threshold": self.text_threshold_var.get()
                })
                
                # 添加ROI
                if self.text_use_roi_var.get():
                    roi_text = self.text_roi_var.get().strip()
                    if roi_text:
                        try:
                            x1, y1, x2, y2 = map(int, roi_text.split(','))
                            recognition_config["roi"] = (x1, y1, x2, y2)
                        except:
                            messagebox.showerror("错误", "ROI格式错误，应为: x1,y1,x2,y2")
                            return
                
            elif state_type == "image":
                template_path = self.template_path_var.get().strip()
                if not template_path:
                    messagebox.showerror("错误", "模板图像路径不能为空")
                    return
                    
                if not os.path.exists(template_path):
                    messagebox.showerror("错误", "模板图像不存在")
                    return
                    
                recognition_config.update({
                    "template_path": template_path,
                    "threshold": self.image_threshold_var.get()
                })
                
                # 添加ROI
                if self.image_use_roi_var.get():
                    roi_text = self.image_roi_var.get().strip()
                    if roi_text:
                        try:
                            x1, y1, x2, y2 = map(int, roi_text.split(','))
                            recognition_config["roi"] = (x1, y1, x2, y2)
                        except:
                            messagebox.showerror("错误", "ROI格式错误，应为: x1,y1,x2,y2")
                            return
                
            elif state_type == "complex":
                # 解析复杂配置JSON
                try:
                    complex_config = json.loads(self.complex_config_text.get(1.0, tk.END))
                    recognition_config.update(complex_config)
                except json.JSONDecodeError:
                    messagebox.showerror("错误", "复杂配置JSON格式错误")
                    return
            
            # 构建结果
            self.result = {
                "state_id": state_id,
                "app_id": app_id,
                "recognition_config": recognition_config
            }
            
            # 关闭对话框
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("错误", f"创建状态失败: {str(e)}")


class StateEditDialog(StateCreateDialog):
    """状态编辑对话框，继承自创建对话框"""
    
    def __init__(self, parent, state):
        """初始化状态编辑对话框
        
        Args:
            parent: 父窗口
            state: 状态数据
        """
        self.parent = parent
        self.state = state
        self.result = None
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑状态")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._setup_ui()
        self._load_state_data()
        
        # 等待对话框关闭
        parent.wait_window(self.dialog)
    
    def _setup_ui(self):
        """设置UI组件"""
        super()._setup_ui()
        
        # 修改按钮文本
        for widget in self.dialog.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Frame) and child.winfo_children():
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, ttk.Button) and grandchild.cget("text") == "创建":
                                grandchild.config(text="保存")
    
    def _load_state_data(self):
        """加载状态数据到UI"""
        # 加载基本信息
        self.state_id_var.set(self.state['state_id'])
        self.app_id_var.set(self.state['app_id'])
        self.state_name_var.set(self.state['name'])
        self.state_type_var.set(self.state['type'])
        
        # 禁用状态ID编辑
        for widget in self.dialog.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.LabelFrame) and child.cget("text") == "基本信息":
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, ttk.Entry) and grandchild.grid_info()['row'] == 0:
                                grandchild.config(state="disabled")
        
        # 解析配置
        try:
            config = json.loads(self.state['config'])
            state_type = self.state['type']
            
            # 确保配置面板已创建
            self.update_config_panel()
            
            # 根据类型加载配置
            if state_type == "text":
                self.target_text_var.set(config.get('target_text', ''))
                self.ocr_lang_var.set(config.get('lang', 'chi_sim+eng'))
                self.text_threshold_var.set(config.get('threshold', 0.6))
                
                # 加载ROI
                if 'roi' in config:
                    self.text_use_roi_var.set(True)
                    roi = config['roi']
                    if isinstance(roi, list) or isinstance(roi, tuple):
                        self.text_roi_var.set(','.join(map(str, roi)))
                
            elif state_type == "image":
                self.template_path_var.set(config.get('template_path', ''))
                self.image_threshold_var.set(config.get('threshold', 0.8))
                
                # 加载ROI
                if 'roi' in config:
                    self.image_use_roi_var.set(True)
                    roi = config['roi']
                    if isinstance(roi, list) or isinstance(roi, tuple):
                        self.image_roi_var.set(','.join(map(str, roi)))
                
            elif state_type == "complex":
                # 删除name和type，这些在基本信息中已有
                if 'name' in config:
                    del config['name']
                if 'type' in config:
                    del config['type']
                    
                # 填充到文本框
                self.complex_config_text.delete(1.0, tk.END)
                self.complex_config_text.insert(tk.END, json.dumps(config, indent=4, ensure_ascii=False))
                
        except Exception as e:
            messagebox.showwarning("警告", f"加载状态配置出错: {str(e)}")
    
    def create_state(self):
        """保存状态（覆盖父类方法）"""
        # 复用父类的创建逻辑，但固定状态ID
        super().create_state()


class StateTransitionDialog:
    """状态转换管理对话框"""
    
    def __init__(self, parent, state_manager, from_state, states):
        """初始化状态转换管理对话框
        
        Args:
            parent: 父窗口
            state_manager: 状态管理器
            from_state: 起始状态ID
            states: 状态字典
        """
        self.parent = parent
        self.state_manager = state_manager
        self.from_state = from_state
        self.states = states
        self.transitions = []
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"管理状态转换 - {from_state}")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._setup_ui()
        self._load_transitions()
        
        # 等待对话框关闭
        parent.wait_window(self.dialog)
    
    def _setup_ui(self):
        """设置UI组件"""
        # 主框架
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建上半部分的转换列表
        list_frame = ttk.LabelFrame(main_frame, text="现有转换")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 转换列表
        columns = ("to_state", "action_name", "function_name")
        self.transition_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.transition_tree.heading("to_state", text="目标状态")
        self.transition_tree.heading("action_name", text="动作名称")
        self.transition_tree.heading("function_name", text="函数名称")
        
        # 设置列宽
        self.transition_tree.column("to_state", width=200)
        self.transition_tree.column("action_name", width=200)
        self.transition_tree.column("function_name", width=200)
        
        # 添加滚动条
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.transition_tree.yview)
        self.transition_tree.configure(yscrollcommand=tree_scroll.set)
        
        # 布局
        self.transition_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定点击事件
        self.transition_tree.bind("<Double-1>", self.on_transition_double_click)
        
        # 按钮区域
        button_frame = ttk.Frame(list_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="添加转换", command=self.add_transition).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑转换", command=self.edit_transition).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除转换", command=self.delete_transition).pack(side=tk.LEFT, padx=5)
        
        # 创建下半部分的编辑区域
        edit_frame = ttk.LabelFrame(main_frame, text="转换编辑")
        edit_frame.pack(fill=tk.X, pady=5)
        
        edit_grid = ttk.Frame(edit_frame)
        edit_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # 目标状态
        ttk.Label(edit_grid, text="目标状态:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # 获取所有状态ID列表（排除当前状态）
        state_ids = [s for s in self.states.keys() if s != self.from_state]
        
        self.to_state_var = tk.StringVar()
        to_state_combo = ttk.Combobox(edit_grid, textvariable=self.to_state_var, values=state_ids, width=30)
        to_state_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 动作名称
        ttk.Label(edit_grid, text="动作名称:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.action_name_var = tk.StringVar()
        ttk.Entry(edit_grid, textvariable=self.action_name_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 函数名称
        ttk.Label(edit_grid, text="函数名称:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.function_name_var = tk.StringVar()
        
        # 常用函数下拉菜单
        common_functions = ["tap", "swipe", "input_text", "press_key", "back", "home"]
        function_combo = ttk.Combobox(edit_grid, textvariable=self.function_name_var, values=common_functions, width=30)
        function_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 参数输入
        ttk.Label(edit_grid, text="参数 (JSON):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        
        # 参数框架
        params_frame = ttk.Frame(edit_grid)
        params_frame.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        params_scroll = ttk.Scrollbar(params_frame)
        params_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.params_text = tk.Text(params_frame, height=5, width=40, yscrollcommand=params_scroll.set)
        self.params_text.pack(side=tk.LEFT, fill=tk.BOTH)
        
        params_scroll.config(command=self.params_text.yview)
        
        # 设置默认参数
        self.params_text.insert(tk.END, '{\n    "x": 100,\n    "y": 100\n}')
        
        # 更新按钮
        ttk.Button(edit_grid, text="保存转换", command=self.save_transition).grid(row=4, column=1, sticky=tk.E, padx=5, pady=10)
        
        # 关闭按钮
        ttk.Button(main_frame, text="关闭", command=self.dialog.destroy).pack(side=tk.RIGHT, pady=10)
    
    def _load_transitions(self):
        """加载状态转换"""
        try:
            # 查询数据库获取转换
            transitions = self.state_manager.db.fetch_all(
                "SELECT * FROM actions WHERE from_state = ?",
                (self.from_state,)
            )
            
            # 清空列表
            self.transition_tree.delete(*self.transition_tree.get_children())
            self.transitions = []
            
            # 填充列表
            for transition in transitions:
                self.transitions.append(transition)
                self.transition_tree.insert("", "end", values=(
                    transition['to_state'],
                    transition['name'],
                    transition['function_name']
                ))
                
        except Exception as e:
            messagebox.showerror("错误", f"加载状态转换失败: {str(e)}")
    
    def on_transition_double_click(self, event):
        """双击转换项事件处理"""
        self.edit_transition()
    
    def add_transition(self):
        """添加新转换"""
        # 清空编辑区域
        self.to_state_var.set("")
        self.action_name_var.set("")
        self.function_name_var.set("tap")
        self.params_text.delete(1.0, tk.END)
        self.params_text.insert(tk.END, '{\n    "x": 100,\n    "y": 100\n}')
    
    def edit_transition(self):
        """编辑选中的转换"""
        # 获取选中项
        selection = self.transition_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个转换")
            return
            
        # 获取项ID
        item_id = selection[0]
        
        # 获取转换数据
        item_values = self.transition_tree.item(item_id, "values")
        to_state, action_name, function_name = item_values
        
        # 在列表中查找完整数据
        transition = None
        for t in self.transitions:
            if (t['to_state'] == to_state and 
                t['name'] == action_name and 
                t['function_name'] == function_name):
                transition = t
                break
                
        if not transition:
            messagebox.showerror("错误", "找不到选中的转换数据")
            return
            
        # 填充编辑区域
        self.to_state_var.set(transition['to_state'])
        self.action_name_var.set(transition['name'])
        self.function_name_var.set(transition['function_name'])
        
        # 解析参数
        try:
            params = json.loads(transition['params'])
            self.params_text.delete(1.0, tk.END)
            self.params_text.insert(tk.END, json.dumps(params, indent=4, ensure_ascii=False))
        except:
            self.params_text.delete(1.0, tk.END)
            self.params_text.insert(tk.END, transition['params'] or "{}")
    
    def delete_transition(self):
        """删除选中的转换"""
        # 获取选中项
        selection = self.transition_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个转换")
            return
            
        # 确认删除
        if not messagebox.askyesno("确认", "确定要删除选中的转换吗？"):
            return
            
        # 获取项ID
        item_id = selection[0]
        
        # 获取转换数据
        item_values = self.transition_tree.item(item_id, "values")
        to_state, action_name, function_name = item_values
        
        try:
            # 删除转换
            self.state_manager.db.execute(
                "DELETE FROM actions WHERE from_state = ? AND to_state = ? AND function_name = ?",
                (self.from_state, to_state, function_name)
            )
            
            # 删除树项
            self.transition_tree.delete(item_id)
            
            # 重新加载转换
            self._load_transitions()
            
            messagebox.showinfo("成功", "已删除状态转换")
            
        except Exception as e:
            messagebox.showerror("错误", f"删除状态转换失败: {str(e)}")
    
    def save_transition(self):
        """保存当前编辑的转换"""
        # 获取数据
        to_state = self.to_state_var.get().strip()
        action_name = self.action_name_var.get().strip()
        function_name = self.function_name_var.get().strip()
        
        # 验证数据
        if not to_state:
            messagebox.showerror("错误", "目标状态不能为空")
            return
            
        if not action_name:
            messagebox.showerror("错误", "动作名称不能为空")
            return
            
        if not function_name:
            messagebox.showerror("错误", "函数名称不能为空")
            return
            
        # 验证参数
        try:
            params_text = self.params_text.get(1.0, tk.END).strip()
            params = json.loads(params_text)
        except json.JSONDecodeError:
            messagebox.showerror("错误", "参数JSON格式错误")
            return
            
        try:
            # 保存转换
            success = self.state_manager.register_state_transition(
                self.from_state,
                to_state,
                action_name,
                function_name,
                params
            )
            
            if success:
                messagebox.showinfo("成功", f"已保存转换: {self.from_state} -> {to_state}")
                
                # 重新加载转换列表
                self._load_transitions()
            else:
                messagebox.showerror("错误", "保存转换失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"保存转换失败: {str(e)}")
